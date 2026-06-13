"""core/adapters/algolia_inretail.py — Base común para cadenas InRetail (Algolia).

Inkafarma y Mifarma son del mismo holding (InRetail) y exponen su catálogo sobre
**Algolia** con el MISMO esquema de documento (`priceList`, `pricePromo`,
`skuMifarma`, etc.). Cambia solo la instancia: `app_id`, `api_key`, `host`,
`origin`. Por eso toda la lógica vive aquí y cada cadena es un wrapper de config
(ver `inkafarma.py`, `mifarma.py`).

Dos vías de ingesta (estrategia híbrida):

  • search()        → POST /1/indexes/*/queries
        Búsqueda dirigida de un término. Tope Algolia: 1000 hits por query.
        Es la mitad de "monitoreo frecuente" del híbrido (canasta ancla).

  • iter_catalogo() → volcado del catálogo COMPLETO. Elige automáticamente:
        - browse()        si la key lo permite (Inkafarma): cursor, sin tope.
        - sync_facetas()  si browse está bloqueado (Mifarma): particiona por
          una faceta (subCategory) en buckets <1000 y deduplica por objectID.

Las credenciales y el mapeo se cargan de `farmacias.yaml` (bloque <id> →
`algolia:`), para que rotar una API key sea editar config, no código.

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
from ..modelo import Producto

ROOT = Path(__file__).resolve().parents[2]
CONFIG_YAML = ROOT / "farmacias.yaml"
RAW_DIR = ROOT / "data" / "raw"


# --- helpers de normalización -----------------------------------------------
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


def _first(v: Any) -> Optional[str]:
    """Primer elemento no vacío si es lista; el valor limpio si es escalar."""
    if isinstance(v, (list, tuple)):
        for x in v:
            c = _clean(x)
            if c:
                return c
        return None
    return _clean(v)


class AlgoliaInRetailAdapter(AdapterBase):
    """Base para adaptadores de cadenas InRetail sobre Algolia."""

    cadena: str = "?"
    YAML_ID: Optional[str] = None          # id del bloque en farmacias.yaml
    DEFAULTS: Dict[str, Any] = {}          # cada cadena pone sus credenciales
    soporta_browse: bool = True            # Mifarma lo pone en False (key sin ACL browse)

    def __init__(self, *, config: Optional[Dict[str, Any]] = None, **kw) -> None:
        cfg = dict(self.DEFAULTS)
        cfg.update(config or {})
        self.app_id = cfg["app_id"]
        self.api_key = cfg["api_key"]
        self.host = cfg["host"].rstrip("/")
        self.index = cfg["index"]
        self.filtro_canal = cfg.get("filtro_canal") or None
        self.producto_url = cfg.get("producto_url")
        self.origin = cfg.get("origin")

        extra = {
            "X-Algolia-Application-Id": self.app_id,
            "X-Algolia-API-Key": self.api_key,
            "content-type": "application/json",
        }
        if self.origin:
            extra["Origin"] = self.origin
            extra["Referer"] = self.origin.rstrip("/") + "/"
        kw.setdefault("extra_headers", extra)
        super().__init__(**kw)

    # --- carga de config ----------------------------------------------------
    @classmethod
    def from_yaml(cls, path: Path = CONFIG_YAML, **kw) -> "AlgoliaInRetailAdapter":
        config: Dict[str, Any] = {}
        try:
            import yaml
        except ImportError:
            yaml = None
        if yaml is not None and cls.YAML_ID and path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for f in data.get("farmacias", []):
                if f.get("id") == cls.YAML_ID:
                    config = f.get("algolia") or {}
                    break
        return cls(config=config, **kw)

    # --- construcción de params Algolia ------------------------------------
    def _params(
        self,
        query: str,
        length: int,
        offset: int,
        filtros: Optional[List[str]] = None,
        extra: str = "",
    ) -> str:
        qs = urllib.parse.urlencode(
            {"query": query or "", "length": str(length), "offset": str(offset)}
        )
        if filtros:
            groups = [[f] for f in filtros]   # cada grupo ANDed entre sí
            qs += "&facetFilters=" + urllib.parse.quote(json.dumps(groups))
        if extra:
            qs += extra
        return qs

    def _filtros(self, solo_web: bool, extra: Optional[List[str]] = None) -> List[str]:
        out: List[str] = []
        if solo_web and self.filtro_canal:
            out.append(self.filtro_canal)
        if extra:
            out.extend(extra)
        return out

    # --- mapeo hit Algolia -> Producto (esquema InRetail) ------------------
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
            # El índice de búsqueda no trae stock en vivo (vive en el detalle).
            stock=None,
            url=url,
            imagen=_clean(hit.get("image")),
            ean=_clean(hit.get("gtin")),
            sku_mifarma=_clean(hit.get("skuMifarma")),
            sku_sap=_clean(hit.get("skuSap")),
            raw=hit if raw else None,
        )

    # --- motor de paginación de /queries -----------------------------------
    def _query_paged(
        self,
        query: str,
        filtros: List[str],
        *,
        raw: bool = False,
        limit: Optional[int] = None,
        extra: str = "",
    ) -> Iterator[Producto]:
        """Pagina una query hasta nbHits (o `limit`), respetando el tope 1000."""
        url = f"{self.host}/1/indexes/*/queries"
        page_len = 250
        tope = min(limit, 1000) if limit else 1000
        offset = 0
        primera = True
        while offset < tope:
            length = min(page_len, tope - offset)
            body = {
                "requests": [
                    {"indexName": self.index,
                     "params": self._params(query, length, offset, filtros, extra)}
                ]
            }
            res = self._post_json(url, body)["results"][0]
            hits = res.get("hits", [])
            for h in hits:
                yield self._map_hit(h, raw=raw)
            nb = res.get("nbHits", 0)
            offset += len(hits)
            if not hits or offset >= min(nb, tope):
                break
            if not primera:
                self._sleep()
            primera = False

    # --- traer un producto puntual por objectID (match 1:1) ----------------
    def get_object(self, object_id: str, *, raw: bool = False) -> Optional[Producto]:
        """Trae un producto por su objectID (getObject). None si no existe.

        El objectID es la llave InRetail compartida entre Inkafarma y Mifarma,
        así que el mismo id resuelve el mismo producto en ambas cadenas.
        """
        import httpx
        url = f"{self.host}/1/indexes/{self.index}/{urllib.parse.quote(str(object_id))}"
        resp = self._client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._map_hit(resp.json(), raw=raw)

    # --- VÍA 1: búsqueda dirigida ------------------------------------------
    def search(
        self,
        query: str,
        *,
        limit: Optional[int] = None,
        solo_web: bool = True,
        raw: bool = False,
    ) -> List[Producto]:
        """Busca un término y devuelve las ofertas (paginadas, tope 1000)."""
        return list(
            self._query_paged(query, self._filtros(solo_web), raw=raw, limit=limit)
        )

    def search_canasta(
        self, terminos: List[str], *, raw: bool = False
    ) -> Dict[str, List[Producto]]:
        """Refresca cada término de la canasta ancla (delay entre términos)."""
        out: Dict[str, List[Producto]] = {}
        for i, t in enumerate(terminos):
            if i:
                self._sleep()
            out[t] = self.search(t, raw=raw)
        return out

    # --- VÍA 2a: volcado por cursor (browse) -------------------------------
    def browse(
        self,
        *,
        solo_web: bool = True,
        max_paginas: Optional[int] = None,
        raw: bool = False,
    ) -> Iterator[Producto]:
        """Catálogo completo vía cursor (1000/página). Requiere ACL browse."""
        url = f"{self.host}/1/indexes/{self.index}/browse"
        cursor: Optional[str] = None
        pagina = 0
        while True:
            if cursor is None:
                body: Dict[str, Any] = {
                    "params": self._params("", 1000, 0, self._filtros(solo_web))
                }
            else:
                body = {"cursor": cursor}
            data = self._post_json(url, body)
            if data.get("message") and not data.get("hits"):
                raise RuntimeError(
                    f"[{self.cadena}] browse no disponible: {data['message']}. "
                    f"Usa sync_facetas() (vía facetas)."
                )
            for h in data.get("hits", []):
                yield self._map_hit(h, raw=raw)
            pagina += 1
            cursor = data.get("cursor")
            if not cursor or (max_paginas and pagina >= max_paginas):
                break
            self._sleep((0.3, 0.9))  # browse pega al CDN de Algolia: delay liviano

    # --- VÍA 2b: volcado por facetas (cuando browse está bloqueado) --------
    def sync_facetas(
        self,
        *,
        dimension: str = "subCategory",
        solo_web: bool = True,
        raw: bool = False,
        max_buckets: Optional[int] = None,
    ) -> Iterator[Producto]:
        """Catálogo completo particionando por `dimension` (buckets <1000) y
        deduplicando por objectID. Alternativa a browse para keys sin ACL.
        """
        url = f"{self.host}/1/indexes/*/queries"
        body = {
            "requests": [{
                "indexName": self.index,
                "params": self._params(
                    "", 0, 0, self._filtros(solo_web),
                    extra=f'&facets=["{dimension}"]&maxValuesPerFacet=1000',
                ),
            }]
        }
        facets = self._post_json(url, body)["results"][0].get("facets", {})
        valores = list(facets.get(dimension, {}).keys())
        vistos = set()
        for i, val in enumerate(valores):
            if max_buckets and i >= max_buckets:
                break
            if i:
                self._sleep((0.3, 0.9))
            filtros = self._filtros(solo_web, extra=[f"{dimension}:{val}"])
            for p in self._query_paged("", filtros, raw=raw):
                if p.sku in vistos:
                    continue
                vistos.add(p.sku)
                yield p

    # --- selector automático de volcado ------------------------------------
    def iter_catalogo(self, *, raw: bool = False, **kw) -> Iterator[Producto]:
        """Vuelca el catálogo completo eligiendo la mejor vía disponible."""
        if self.soporta_browse:
            yield from self.browse(raw=raw, **kw)
        else:
            yield from self.sync_facetas(raw=raw, **kw)


# ============================ CLI compartida ================================
def _print_tabla(productos: List[Producto], limite: int = 25) -> None:
    print(f"\n{len(productos)} productos\n")
    print("%-9s %-8s %-8s %-6s %-11s %s" %
          ("SKU", "precio", "regular", "promo", "skuMifarma", "nombre"))
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


def run_cli(adapter_cls, argv: Optional[List[str]] = None) -> int:
    """CLI común a todas las cadenas InRetail."""
    cadena = adapter_cls.cadena
    parser = argparse.ArgumentParser(
        description=f"Adaptador {cadena} (Algolia). Vías: search y volcado.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("buscar", help="Búsqueda dirigida de un término")
    p_b.add_argument("query")
    p_b.add_argument("--limit", type=int, default=None)
    p_b.add_argument("--json", action="store_true")

    p_v = sub.add_parser("volcar", help="Volcado del catálogo completo a JSONL")
    p_v.add_argument("--max-buckets", type=int, default=None,
                     help="(modo facetas) límite de buckets")
    p_v.add_argument("--max-paginas", type=int, default=None,
                     help="(modo browse) límite de páginas")
    p_v.add_argument("--salida", default=None)

    p_m = sub.add_parser("monitorear", help="Refresca precios de una canasta de términos")
    p_m.add_argument("--terminos", required=True, help="Lista separada por comas")
    p_m.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    adapter = adapter_cls.from_yaml()

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
            destino = (Path(args.salida) if args.salida
                       else RAW_DIR / cadena / date.today().isoformat() / "catalogo.jsonl")
            via = "browse" if adapter.soporta_browse else "facetas"
            print(f"Volcando catálogo {cadena} (vía {via}) -> {destino}", file=sys.stderr)
            kw = ({"max_paginas": args.max_paginas} if adapter.soporta_browse
                  else {"max_buckets": args.max_buckets})
            n = _dump_jsonl(adapter.iter_catalogo(**kw), destino)
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
