"""core/adapters/universal.py — Adaptador Farmacia Universal (VTEX).

Farmacia Universal (cadena INDEPENDIENTE, familiar) corre sobre **VTEX**, con las
APIs de catálogo públicas (no requieren auth ni pasan por el reCAPTCHA, que solo
gatea formularios). Cuenta VTEX: `farmaciauniversalpe`.

Vía de ingesta: la **legacy catalog_system search**
    /api/catalog_system/pub/products/search/<query>?_from=&_to=
que en UNA llamada devuelve productos con items (SKU), precio/lista, stock en vivo
(`AvailableQuantity`), laboratorio y —clave para el matcher— **EAN/GTIN**.

A diferencia de Boticas (sin EAN → solo fuzzy), aquí muchos productos traen EAN-13
real, lo que habilita el match de Capa 1 por EAN (id duro) contra el `gtin` de
Inka/Mifarma. Los que traen código interno de laboratorio (p.ej. "EG010300000")
caen a fuzzy. El emparejamiento lo decide `core.matcher` (Capa 1 EAN → Capa 2 fuzzy).

Python 3.9+. Dependencias: httpx, pyyaml.
"""

from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..adapter_base import AdapterBase
from ..modelo import Producto

ROOT = Path(__file__).resolve().parents[2]
CONFIG_YAML = ROOT / "farmacias.yaml"

DEFAULTS = {
    "dominio": "https://www.farmaciauniversal.com",
}


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _ean_valido(v: Any) -> Optional[str]:
    """EAN solo si parece un código de barras real (dígitos, 8–14). Los códigos
    internos de laboratorio ("EG010300000") se descartan para no ensuciar la
    llave de cruce (no colisionan con el gtin de Inka/Mifa, pero mejor explícito)."""
    s = _clean(v)
    if s and s.isdigit() and 8 <= len(s) <= 14:
        return s
    return None


class UniversalAdapter(AdapterBase):
    cadena = "universal"

    def __init__(self, *, config: Optional[Dict[str, Any]] = None, **kw) -> None:
        cfg = dict(DEFAULTS)
        cfg.update(config or {})
        self.dominio = cfg["dominio"].rstrip("/")
        kw.setdefault("extra_headers", {
            "Accept": "application/json",
            "Referer": self.dominio + "/",
        })
        super().__init__(**kw)

    @classmethod
    def from_yaml(cls, path: Path = CONFIG_YAML, **kw) -> "UniversalAdapter":
        config: Dict[str, Any] = {}
        try:
            import yaml
        except ImportError:
            yaml = None
        if yaml is not None and path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for f in data.get("farmacias", []):
                if f.get("id") == "universal":
                    config = dict(f.get("vtex") or {})
                    if f.get("dominio"):
                        config.setdefault("dominio", f["dominio"])
                    break
        return cls(config=config, **kw)

    # --- mapeo producto VTEX -> Producto (uno por SKU/item) ----------------
    def _spec(self, prod: Dict[str, Any], nombre: str) -> Any:
        """Lee una especificación VTEX (vienen como claves sueltas con lista de valores)."""
        v = prod.get(nombre)
        if isinstance(v, list):
            return _clean(v[0]) if v else None
        return _clean(v)

    def _map_item(self, prod: Dict[str, Any], item: Dict[str, Any], *,
                  raw: bool = False) -> Optional[Producto]:
        sellers = item.get("sellers") or []
        offer = (sellers[0].get("commertialOffer") if sellers else None) or {}
        precio = _num(offer.get("Price"))
        lista = _num(offer.get("ListPrice"))
        sin_desc = _num(offer.get("PriceWithoutDiscount"))
        if lista is None:
            lista = sin_desc
        en_promo = bool(offer.get("Teasers") or offer.get("PromotionTeasers")
                        or offer.get("DiscountHighLight")) or (
            lista is not None and precio is not None and lista > precio)

        disp = offer.get("AvailableQuantity")
        is_avail = offer.get("IsAvailable")
        stock = bool(is_avail) if is_avail is not None else (
            (disp is not None and disp > 0) if disp is not None else None)

        imgs = item.get("images") or []
        imagen = _clean(imgs[0].get("imageUrl")) if imgs else None

        receta = self._spec(prod, "Requiere receta médica")
        prescripcion = None
        if receta is not None:
            prescripcion = "Venta con receta" if receta.lower() in ("sí", "si", "true", "1") else "Venta Libre"

        return Producto(
            cadena=self.cadena,
            sku=str(item.get("itemId") or prod.get("productId")),
            nombre_origen=_clean(item.get("nameComplete") or item.get("name")
                                 or prod.get("productName")) or "",
            precio=precio,
            precio_regular=lista if lista is not None else precio,
            en_promocion=en_promo,
            marca=_clean(prod.get("brand")),
            laboratorio=_clean(prod.get("brand")),
            presentacion=self._spec(prod, "Presentación"),
            prescripcion=prescripcion,
            stock=stock,
            url=_clean(prod.get("link")),
            imagen=imagen,
            ean=_ean_valido(item.get("ean")),
            raw=prod if raw else None,
        )

    def _map_producto(self, prod: Dict[str, Any], *, raw: bool = False) -> List[Producto]:
        out: List[Producto] = []
        for item in prod.get("items") or []:
            p = self._map_item(prod, item, raw=raw)
            if p:
                out.append(p)
        return out

    # --- búsqueda (legacy catalog_system search) ---------------------------
    def search(self, query: str, *, limit: Optional[int] = None,
               page_size: int = 50) -> List[Producto]:
        """Busca un término (fulltext VTEX) y devuelve un Producto por SKU.

        Pagina con _from/_to (VTEX limita el rango a 50). `limit` cuenta SKUs.
        """
        productos: List[Producto] = []
        tope = limit or 50
        frm = 0
        primera = True
        q = urllib.parse.quote(query)
        while len(productos) < tope:
            to = frm + min(page_size, tope - len(productos)) - 1
            url = f"{self.dominio}/api/catalog_system/pub/products/search/{q}"
            if not primera:
                self._sleep()
            resp = self._client.get(url, params={"_from": frm, "_to": to})
            if resp.status_code not in (200, 206):
                break
            data = resp.json()
            if not data:
                break
            for prod in data:
                productos.extend(self._map_producto(prod))
            if len(data) < (to - frm + 1):
                break  # última página
            frm = to + 1
            primera = False
        return productos[:limit] if limit else productos

    # --- árbol de categorías (para mapa de organización) -------------------
    def category_tree(self, niveles: int = 3) -> List[Dict[str, Any]]:
        url = f"{self.dominio}/api/catalog_system/pub/category/tree/{niveles}"
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json()


# ============================ CLI ==========================================
def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Adaptador Farmacia Universal (VTEX).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("buscar", help="Buscar un término")
    pb.add_argument("query")
    pb.add_argument("--limit", type=int, default=12)
    pb.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    with UniversalAdapter.from_yaml() as a:
        prods = a.search(args.query, limit=args.limit)
        if args.json:
            for p in prods:
                print(json.dumps(p.to_row(), ensure_ascii=False))
        else:
            print(f"{len(prods)} SKUs\n")
            for p in prods:
                ean = p.ean or "—"
                print(f"  {p.sku:8} S/{(p.precio or 0):7.2f}  EAN:{ean:14} {p.nombre_origen[:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
