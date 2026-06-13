# Radar de Precios — Farmacias Perú (demo)

Comparador de precios entre cadenas de farmacias peruanas — *"un Trivago de farmacias"*.

**[`comparativa-demo.html`](comparativa-demo.html)** — muestra estática de la tabla
comparativa: una canasta de 34 productos de alta rotación, con el precio de cada
cadena, el más barato resaltado y la brecha porcentual. Generada automáticamente
por `pipeline/build_comparativa.py` (snapshot de captura, sin datos sensibles).

Fuentes en la demo: **Inkafarma** y **Mifarma** (API JSON sobre Algolia). El motor
es modular (un adaptador por cadena) y replicable a otros rubros.

> Para regenerar: `py -m pipeline.build_comparativa`
