"""core/adapters/boticasperu.py — Adaptador Boticas Perú (Salesforce Commerce Cloud).

Boticas Perú corre sobre **Salesforce Commerce Cloud (Demandware / SFRA)**, no
Algolia. Estrategia híbrida descubierta en el recon (Fase 0):

  • LISTADO (Nivel B · HTML)  → Search-UpdateGrid?q=&start=&sz=
        Grilla SSR con tiles de producto. Se parsea con selectolax: pid, nombre,
        precio, url, imagen. Pagina con start/sz.

  • DETALLE (Nivel A · JSON)  → Product-ShowQuickView?pid=
        application/json limpio: precio venta vs lista (descuento real),
        disponibilidad (quiebre de stock), marca, receta, promociones, URL.

A diferencia de Inkafarma/Mifarma, Boticas NO comparte el objectID InRetail ni
expone EAN → el emparejamiento con la canasta es por nombre+specs (core.matcher,
Capa 2, fuzzy). Flujo: search(termino) → candidatos → matcher elige el pid →
get_object(pid) trae el precio/stock limpio.

Python 3.9+. Dependencias: httpx, selectolax, pyyaml.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from selectolax.parser import HTMLParser

from ..adapter_base import AdapterBase
from ..modelo import Producto

ROOT = Path(__file__).resolve().parents[2]
CONFIG_YAML = ROOT / "farmacias.yaml"

DEFAULTS = {
    "dominio": "https://www.boticasperu.pe",
    "controller_base": "https://www.boticasperu.pe/on/demandware.store/Sites-BoticasPeru-Site/es_PE",
}


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s or None


class BoticasPeruAdapter(AdapterBase):
    cadena = "boticasperu"

    def __init__(self, *, config: Optional[Dict[str, Any]] = None, **kw) -> None:
        cfg = dict(DEFAULTS)
        cfg.update(config or {})
        self.dominio = cfg["dominio"].rstrip("/")
        self.ctrl = cfg["controller_base"].rstrip("/")
        kw.setdefault("extra_headers", {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Referer": self.dominio + "/",
        })
        super().__init__(**kw)

    @classmethod
    def from_yaml(cls, path: Path = CONFIG_YAML, **kw) -> "BoticasPeruAdapter":
        config: Dict[str, Any] = {}
        try:
            import yaml
        except ImportError:
            yaml = None
        if yaml is not None and path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for f in data.get("farmacias", []):
                if f.get("id") == "boticasperu":
                    config = dict(f.get("sfra") or {})
                    if f.get("dominio"):
                        config.setdefault("dominio", f["dominio"])
                    break
        return cls(config=config, **kw)

    # --- LISTADO: grilla HTML (Nivel B) ------------------------------------
    def _abs_url(self, href: Optional[str]) -> Optional[str]:
        if not href:
            return None
        return href if href.startswith("http") else self.dominio + href

    def _parse_tile(self, node) -> Optional[Producto]:
        pid = node.attributes.get("data-pid")
        if not pid:
            return None
        # nombre: alt/title de la imagen, o .pdp-link / .product-name
        nombre = None
        img = node.css_first("img.tile-image")
        if img:
            nombre = _clean(img.attributes.get("alt") or img.attributes.get("title"))
        if not nombre:
            link = node.css_first(".pdp-link a, .product-name, a.link")
            if link:
                nombre = _clean(link.text())
        # precio: <span class="value" content="55.40"> o texto "S/ 55.40"
        precio = None
        val = node.css_first(".sales .value")
        if val:
            precio = _num(val.attributes.get("content"))
        if precio is None:
            sales = node.css_first(".sales")
            if sales:
                m = re.search(r"S/\s*([\d.,]+)", sales.text())
                if m:
                    precio = _num(m.group(1).replace(",", ""))
        # url + imagen
        a = node.css_first("a[href]")
        url = self._abs_url(a.attributes.get("href")) if a else None
        imagen = img.attributes.get("src") if img else None

        return Producto(
            cadena=self.cadena, sku=str(pid), nombre_origen=nombre or "",
            precio=precio, precio_regular=precio, url=url, imagen=_clean(imagen),
        )

    def search(self, query: str, *, limit: Optional[int] = None,
               page_size: int = 24) -> List[Producto]:
        """Busca un término en la grilla SSR y devuelve los tiles parseados."""
        productos: List[Producto] = []
        start = 0
        primera = True
        tope = limit or 96
        while len(productos) < tope:
            sz = min(page_size, tope - len(productos))
            url = f"{self.ctrl}/Search-UpdateGrid"
            if not primera:
                self._sleep()
            resp = self._client.get(url, params={"q": query, "start": start, "sz": sz})
            resp.raise_for_status()
            tree = HTMLParser(resp.text)
            tiles = tree.css("div.product[data-pid]")
            if not tiles:
                break
            for t in tiles:
                p = self._parse_tile(t)
                if p:
                    productos.append(p)
            if len(tiles) < sz:
                break  # última página
            start += sz
            primera = False
        return productos[:limit] if limit else productos

    # --- DETALLE: QuickView JSON (Nivel A) ---------------------------------
    def _map_quickview(self, data: Dict[str, Any], *, raw: bool = False) -> Optional[Producto]:
        p = data.get("product")
        if not p:
            return None
        price = p.get("price") or {}
        sales = (price.get("sales") or {}).get("value")
        lista = (price.get("list") or {}).get("value")
        # pricebookPrices como respaldo del precio de lista
        if lista is None:
            pbp = p.get("pricebookPrices") or {}
            lp = pbp.get("listPrice")
            if isinstance(lp, dict):
                lista = lp.get("value")
        sales = _num(sales)
        lista = _num(lista)

        custom = p.get("custom") or {}
        ribbon = _clean(custom.get("ribbon")) or _clean(p.get("ribbon"))
        en_promo = bool(p.get("promotions")) or bool(ribbon) or (
            lista is not None and sales is not None and lista > sales
        )
        receta = custom.get("medicalPrescription")
        prescripcion = ("Venta con receta" if receta else "Venta Libre") if receta is not None else None

        img = None
        images = p.get("images") or {}
        for key in ("large", "small", "medium"):
            arr = images.get(key)
            if isinstance(arr, list) and arr:
                img = arr[0].get("url") if isinstance(arr[0], dict) else arr[0]
                break

        rsanit = _clean(p.get("healthRegistrationNumber") or custom.get("healthRegistrationNumber"))

        return Producto(
            cadena=self.cadena,
            sku=str(p.get("id")),
            nombre_origen=_clean(p.get("productName")) or "",
            precio=sales,
            precio_regular=lista if lista is not None else sales,
            en_promocion=en_promo,
            etiqueta_promo=ribbon,
            marca=_clean(p.get("brand")),
            prescripcion=prescripcion,
            stock=bool(p.get("available")) if p.get("available") is not None else None,
            url=self._abs_url(_clean(p.get("selectedProductUrl"))),
            imagen=_clean(img),
            ean=rsanit,  # no hay EAN; guardamos R.S. (registro sanitario) como id secundario
            raw=p if raw else None,
        )

    def get_object(self, pid: str, *, raw: bool = False) -> Optional[Producto]:
        """Trae el detalle JSON limpio de un producto por su pid (QuickView)."""
        url = f"{self.ctrl}/Product-ShowQuickView"
        resp = self._client.get(url, params={"pid": str(pid)})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._map_quickview(resp.json(), raw=raw)


# ============================ CLI ==========================================
def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Adaptador Boticas Perú (SFCC).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("buscar", help="Buscar en la grilla")
    pb.add_argument("query")
    pb.add_argument("--limit", type=int, default=12)
    pd = sub.add_parser("detalle", help="Detalle JSON por pid")
    pd.add_argument("pid")
    args = parser.parse_args(argv)

    with BoticasPeruAdapter.from_yaml() as a:
        if args.cmd == "buscar":
            for p in a.search(args.query, limit=args.limit):
                print(f"{p.sku:8} S/{(p.precio or 0):7.2f}  {p.nombre_origen[:50]}")
        elif args.cmd == "detalle":
            p = a.get_object(args.pid)
            print(json.dumps(p.to_row(), ensure_ascii=False, indent=1) if p else "no encontrado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
