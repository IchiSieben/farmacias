"""core/adapters/mifarma.py — Adaptador Mifarma (Nivel A · Algolia).

Wrapper de config sobre `AlgoliaInRetailAdapter`. Mifarma es del mismo grupo que
Inkafarma (InRetail) y usa Algolia con el MISMO esquema de documento; cambia solo
la instancia Algolia (descubierta en el bundle JS del frontend, Fase 0).

Diferencias respecto a Inkafarma:
  • app Algolia propia: `O74E6QKJ1F`, índice `products`, ~12.7k productos WEB.
  • Las keys públicas de Mifarma NO tienen ACL de `browse` ("Method not allowed").
    → el volcado de catálogo va por `sync_facetas()` (partición por subCategory,
      buckets <1000, dedup por objectID). `soporta_browse = False` lo enruta solo.

Validado en Fase 0: para los SKUs comunes con Inkafarma (mismo `objectID`),
Mifarma tiene precios independientes (~69% difieren) → comparación real de precios.
El `objectID` es compartido entre ambas cadenas → matching 1:1 (Capa 1, score 100).

Uso CLI:
    py -m core.adapters.mifarma buscar paracetamol
    py -m core.adapters.mifarma volcar                  # vía facetas, ~12.7k -> JSONL
    py -m core.adapters.mifarma monitorear --terminos "paracetamol,ibuprofeno"
"""

from __future__ import annotations

from .algolia_inretail import AlgoliaInRetailAdapter, run_cli


class MifarmaAdapter(AlgoliaInRetailAdapter):
    cadena = "mifarma"
    YAML_ID = "mifarma"
    soporta_browse = False   # key sin ACL browse -> volcado por facetas
    DEFAULTS = {
        "app_id": "O74E6QKJ1F",
        "api_key": "f14e7e2c350bd2c9bf3b5ff078ccd82f",
        "host": "https://o74e6qkj1f-dsn.algolia.net",
        "index": "products",
        "filtro_canal": "channels:WEB",
        # Mismo patrón que Inkafarma: /producto/{slug}/{objectID} (verificado con
        # navegador headless sobre fichas reales). El slug+id es compartido InRetail.
        "producto_url": "https://www.mifarma.com.pe/producto/{uri}/{sku}",
        "origin": "https://www.mifarma.com.pe",
        # Detalle REST propio de Mifarma (mismo gateway, stage MMMFPRD, companyCode MF):
        # precios independientes de Inkafarma por presentación (pack/fracción).
        "detalle_url": "https://5doa19p9r7.execute-api.us-east-1.amazonaws.com/MMMFPRD/product/{id}",
        "company_code": "MF",
    }


if __name__ == "__main__":
    raise SystemExit(run_cli(MifarmaAdapter))
