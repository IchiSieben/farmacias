"""core/adapters/inkafarma.py — Adaptador Inkafarma (Nivel A · Algolia).

Wrapper de config sobre `AlgoliaInRetailAdapter` (toda la lógica vive ahí, porque
Inkafarma y Mifarma comparten el backend Algolia de InRetail).

Inkafarma: índice `products`, ~46k productos WEB. Su key pública (la del propio
frontend de la cadena) SÍ permite `browse` → volcado de catálogo por cursor.
Credenciales por entorno: INKAFARMA_ALGOLIA_APP_ID / _API_KEY (ver .env.example).

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
        # app_id / api_key / host: por variables de entorno (ver .env.example);
        # el host se deriva del app_id si no se define.
        "index": "products",
        "filtro_canal": "channels:WEB",
        "producto_url": "https://inkafarma.pe/producto/{uri}/{sku}",  # slug + objectID (verificado)
        "origin": "https://inkafarma.pe",
        # API REST de detalle: precio por presentación (pack/fracción) + precio/unidad.
        # El search Algolia solo trae el precio de la presentación por defecto.
        "detalle_url": "https://5doa19p9r7.execute-api.us-east-1.amazonaws.com/MMPROD/product/{id}",
        "company_code": "IKF",
    }


if __name__ == "__main__":
    raise SystemExit(run_cli(InkafarmaAdapter))
