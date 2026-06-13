"""core/adapters/inkafarma.py — Adaptador Inkafarma (Nivel A · API Algolia).

Inkafarma corre su búsqueda sobre **Algolia** (search hospedado). No hay que
parsear HTML: el catálogo es JSON limpio. El frontend usa una *clave pública de
solo-búsqueda* embebida en el navegador; la replicamos directamente.

Dos vías (estrategia híbrida confirmada con el usuario):

  • search()  → endpoint /1/indexes/*/queries
       Búsqueda dirigida de un término. Algolia limita a 1000 hits por query.
       Ideal para refrescar precios de la **canasta de productos ancla** seguido.

  • browse()  → endpoint /1/indexes/{index}/browse
       Recorre el catálogo COMPLETO vía `cursor` (1000 hits/página, sin tope).
       ~46k productos WEB en ~47 páginas. Ideal para el **volcado periódico**
       que arma la base de productos.

Credenciales y mapeo de campos se cargan de `farmacias.yaml` (bloque inkafarma →
`algolia:`), para que rotar la API key sea editar config, no código.

Nota de grupo: Inkafarma y Mifarma son del mismo holding (InRetail). El hit trae
`skuMifarma` → lo guardamos como llave de cruce directo con Mifarma.

Uso CLI:
    py -m core.adapters.inkafarma buscar paracetamol
    py -m core.adapters.inkafarma buscar paracetamol --json
    py -m core.adapters.inkafarma volcar                 # catálogo completo -> JSONL
    py -m core.adapters.inkafarma volcar --max-paginas 3
    py -m core.adapters.inkafarma monitorear --terminos "paracetamol,ibuprofeno"

Python 3.9+. Dependencias: httpx, pyyaml.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from ..adapter_base import AdapterBase
from ..modelo import COLUMNAS_SNAPSHOT, Producto

ROOT = Path(__file__).resolve().parents[2]
CONFIG_YAML = ROOT / "farmacias.yaml"
RAW_DIR = ROOT / "data" / "raw" / "inkafarma"

# Defaults (se pueden sobreescribir desde farmacias.yaml → inkafarma.algolia).
DEFAULTS = {
    "app_id": "15W622LAQ4",
    "api_key": "ccd8cbda203928003f7fe6f44ddbfc3a",
    "host": "https://15w622laq4-dsn.algolia.net",
    "index": "products",
    "filtro_canal": "channels:WEB",
    "producto_url": "https://inkafarma.pe/producto/{uri}",
}


# --- helpers de normalización -----------------------------------------------
def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _first(v: Any) -> Optional[str]:
    """Primer elemento si es lista; el valor limpio si es escalar."""
    if isinstance(v, (list, tuple)):
        for x in v:
            c = _clean(x)
            if c:
                return c
        return None
    return _clean(v)


class InkafarmaAdapter(AdapterBase):
    cadena = "inkafarma"

    def __init__(self, *, config: Optional[Dict[str, Any]] = None, **kw) -> None:
        cfg = dict(DEFAULTS)
        cfg.update(config or {})
        self.app_id = cfg["app_id"]
        self.api_key = cfg["api_key"]
        self.host = cfg["host"].rstrip("/")
        self.index = cfg["index"]
        self.filtro_canal = cfg.get("filtro_canal") or None
        self.producto_url = cfg.get("producto_url")

        # Headers Algolia + Origin/Referer para mimetizar al navegador real.
        extra = {
            "X-Algolia-Application-Id": self.app_id,
            "X-Algolia-API-Key": self.api_key,
            "Origin": "https://inkafarma.pe",
            "Referer": "https://inkafarma.pe/",
            "content-type": "application/json",
        }
        kw.setdefault("extra_headers", extra)
        super().__init__(**kw)

    # --- carga de config ----------------------------------------------------
    @classmethod
    def from_yaml(cls, path: Path = CONFIG_YAML, **kw) -> "InkafarmaAdapter":
        config: Dict[str, Any] = {}
        try:
            import yaml
        except ImportError:
            yaml = None
        if yaml is not None and path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for f in data.get("farmacias", []):
                if f.get("id") == "inkafarma":
                    config = f.get("algolia") or {}
                    break
        return cls(config=config, **kw)

    # --- construcción de params Algolia ------------------------------------
    def _params(self, query: str, length: int, offset: int, solo_web: bool) -> str:
        qs = urllib.parse.urlencode(
            {"query": query or "", "length": str(length), "offset": str(offset)}
        )
        if solo_web and self.filtro_canal:
            ff = json.dumps([[self.filtro_canal]])
            qs += "&facetFilters=" + urllib.parse.quote(ff)
        return qs

    # --- mapeo hit Algolia -> Producto -------------------------------------
    def _map_hit(self, hit: Dict[str, Any], *, raw: bool = False) -> Producto:
        price_list = _num(hit.get("priceList"))
        price_promo = _num(hit.get("pricePromo"))
        price_card = _num(hit.get("priceWithCard"))

        tiene_promo = price_promo is not None and price_promo > 0
        en_promo = bool(hit.get("withPromotion")) or tiene_promo
        precio = price_promo if tiene_promo else price_list

        uri = _clean(hit.get("uri"))
        url = (
            self.producto_url.format(uri=uri)
            if uri and self.producto_url
            else None
        )

        return Producto(
            cadena=self.cadena,
            sku=str(hit.get("objectID")),
            nombre_origen=_clean(hit.get("name")) or "",
            precio=precio,
            precio_regular=price_list,
            precio_tarjeta=price_card if (price_card and price_card > 0) else None,
            en_promocion=en_promo,
            etiqueta_promo=None,  # Algolia no expone el label de campaña; se deriva por diff de snapshots
            marca=_clean(hit.get("brand")),
            laboratorio=_clean(hit.get("laboratory")) or _clean(hit.get("lab")),
            principio_activo=_clean(hit.get("activePrinciples")),
            presentacion=_clean(hit.get("presentation")),
            categoria=_first(hit.get("category")),
            subcategoria=_first(hit.get("subCategory")),
            prescripcion=_clean(hit.get("prescription")),
            # El índice de búsqueda no trae stock en vivo (eso vive en el detalle
            # de producto). Lo dejamos desconocido en vez de inventarlo.
            stock=None,
            url=url,
            imagen=_clean(hit.get("image")),
            ean=_clean(hit.get("gtin")),
            sku_mifarma=_clean(hit.get("skuMifarma")),
            sku_sap=_clean(hit.get("skuSap")),
            raw=hit if raw else None,
        )

    # --- VÍA 1: búsqueda dirigida ------------------------------------------
    def search(
        self,
        query: str,
        *,
        limit: Optional[int] = None,
        solo_web: bool = True,
        raw: bool = False,
    ) -> List[Producto]:
        """Busca un término. Pagina hasta `limit` (o hasta nbHits, tope 1000)."""
        url = f"{self.host}/1/indexes/*/queries"
        page_len = 250
        tope = min(limit, 1000) if limit else 1000
        productos: List[Producto] = []
        offset = 0
        primera = True
        while offset < tope:
            length = min(page_len, tope - offset)
            body = {
                "requests": [
                    {"indexName": self.index,
                     "params": self._params(query, length, offset, solo_web)}
                ]
            }
            data = self._post_json(url, body)
            res = data["results"][0]
            hits = res.get("hits", [])
            for h in hits:
                productos.append(self._map_hit(h, raw=raw))
            nb = res.get("nbHits", len(productos))
            tope = min(tope, nb)
            offset += len(hits)
            if not hits or offset >= nb:
                break
            if not primera:
                self._sleep()
            primera = False
        return productos[:limit] if limit else productos

    def search_canasta(
        self, terminos: List[str], *, raw: bool = False
    ) -> Dict[str, List[Producto]]:
        """Busca cada término de la canasta ancla. delay entre términos."""
        out: Dict[str, List[Producto]] = {}
        for i, t in enumerate(terminos):
            if i:
                self._sleep()
            out[t] = self.search(t, raw=raw)
        return out

    # --- VÍA 2: volcado completo del catálogo ------------------------------
    def browse(
        self,
        *,
        solo_web: bool = True,
        max_paginas: Optional[int] = None,
        raw: bool = False,
    ) -> Iterator[Producto]:
        """Recorre el catálogo completo vía cursor. Yields Producto uno a uno."""
        url = f"{self.host}/1/indexes/{self.index}/browse"
        cursor: Optional[str] = None
        pagina = 0
        while True:
            if cursor is None:
                body: Dict[str, Any] = {"params": self._params("", 1000, 0, solo_web)}
            else:
                body = {"cursor": cursor}
            data = self._post_json(url, body)
            for h in data.get("hits", []):
                yield self._map_hit(h, raw=raw)
            pagina += 1
            cursor = data.get("cursor")
            if not cursor:
                break
            if max_paginas and pagina >= max_paginas:
                break
            # browse pega al CDN de Algolia (pensado para esto): delay liviano.
            self._sleep((0.3, 0.9))


# ============================ CLI ==========================================
def _print_tabla(productos: List[Producto], limite: int = 25) -> None:
    print(f"\n{len(productos)} productos\n")
    hdr = ("SKU", "precio", "regular", "promo", "skuMifarma", "nombre")
    print("%-9s %-8s %-8s %-6s %-11s %s" % hdr)
    print("-" * 78)
    for p in productos[:limite]:
        print("%-9s %-8s %-8s %-6s %-11s %s" % (
            p.sku,
            "" if p.precio is None else f"{p.precio:.2f}",
            "" if p.precio_regular is None else f"{p.precio_regular:.2f}",
            "sí" if p.en_promocion else "",
            p.sku_mifarma or "",
            (p.nombre_origen or "")[:38],
        ))
    if len(productos) > limite:
        print(f"... (+{len(productos) - limite} más)")


def _dump_jsonl(productos: Iterator[Producto], destino: Path) -> int:
    destino.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with destino.open("w", encoding="utf-8") as fh:
        for p in productos:
            fh.write(json.dumps(p.to_row(), ensure_ascii=False) + "\n")
            n += 1
            if n % 2000 == 0:
                print(f"  ... {n} productos volcados", file=sys.stderr)
    return n


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Adaptador Inkafarma (Algolia). Dos vías: search y browse.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("buscar", help="Búsqueda dirigida de un término")
    p_b.add_argument("query")
    p_b.add_argument("--limit", type=int, default=None)
    p_b.add_argument("--json", action="store_true", help="Salida JSONL en vez de tabla")

    p_v = sub.add_parser("volcar", help="Volcado del catálogo completo (browse) a JSONL")
    p_v.add_argument("--max-paginas", type=int, default=None, help="Límite de páginas (1000 hits c/u)")
    p_v.add_argument("--salida", default=None, help="Ruta del JSONL (por defecto data/raw/inkafarma/<fecha>/)")

    p_m = sub.add_parser("monitorear", help="Refresca precios de una canasta de términos")
    p_m.add_argument("--terminos", required=True, help="Lista separada por comas")
    p_m.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    adapter = InkafarmaAdapter.from_yaml()

    with adapter:
        if args.cmd == "buscar":
            prods = adapter.search(args.query, limit=args.limit)
            if args.json:
                for p in prods:
                    print(json.dumps(p.to_row(), ensure_ascii=False))
            else:
                _print_tabla(prods)
            return 0

        if args.cmd == "volcar":
            if args.salida:
                destino = Path(args.salida)
            else:
                destino = RAW_DIR / date.today().isoformat() / "catalogo.jsonl"
            print(f"Volcando catálogo Inkafarma -> {destino}", file=sys.stderr)
            n = _dump_jsonl(adapter.browse(max_paginas=args.max_paginas), destino)
            print(f"\nListo: {n} productos en {destino}")
            return 0

        if args.cmd == "monitorear":
            terminos = [t.strip() for t in args.terminos.split(",") if t.strip()]
            res = adapter.search_canasta(terminos)
            total = sum(len(v) for v in res.values())
            print(f"Canasta: {len(terminos)} términos, {total} ofertas\n", file=sys.stderr)
            for t, prods in res.items():
                if args.json:
                    for p in prods:
                        print(json.dumps(p.to_row(), ensure_ascii=False))
                else:
                    print(f"### {t} ({len(prods)})")
                    _print_tabla(prods, limite=10)
                    print()
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
