"""core/adapters/inkafarma.py — Adaptador Inkafarma (Nivel A · Algolia).

Wrapper de config sobre `AlgoliaInRetailAdapter` (toda la lógica vive ahí, porque
Inkafarma y Mifarma comparten el backend Algolia de InRetail).

Inkafarma: app Algolia `15W622LAQ4`, índice `products`, ~46k productos WEB.
Su key pública SÍ permite `browse` → volcado de catálogo por cursor.

Uso CLI:
    py -m core.adapters.inkafarma buscar paracetamol
    py -m core.adapters.inkafarma volcar                       # browse, ~46k -> JSONL
    py -m core.adapters.inkafarma monitorear --terminos "paracetamol,ibuprofeno"
"""

from __future__ import annotations

from .algolia_inretail import AlgoliaInRetailAdapter, run_cli


class InkafarmaAdapter(AlgoliaInRetailAdapter):
    cadena = "inkafarma"
    YAML_ID = "inkafarma"
    soporta_browse = True
    DEFAULTS = {
        "app_id": "15W622LAQ4",
        "api_key": "ccd8cbda203928003f7fe6f44ddbfc3a",
        "host": "https://15w622laq4-dsn.algolia.net",
        "index": "products",
        "filtro_canal": "channels:WEB",
        "producto_url": "https://inkafarma.pe/producto/{uri}",
        "origin": "https://inkafarma.pe",
    }


if __name__ == "__main__":
    raise SystemExit(run_cli(InkafarmaAdapter))
