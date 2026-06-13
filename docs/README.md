# Radar de Precios — Farmacias Perú (demo)

Comparador de precios entre cadenas de farmacias peruanas — *"un Trivago de farmacias"*.

**[`comparativa-demo.html`](comparativa-demo.html)** — muestra estática de la tabla
comparativa: una canasta de 34 productos de alta rotación, con el precio de cada
cadena, el más barato resaltado y la brecha porcentual. Generada automáticamente
por `pipeline/build_comparativa.py` (snapshot de captura, sin datos sensibles).

Fuentes en la demo: **Inkafarma**, **Mifarma** (API JSON sobre Algolia) y
**Boticas Perú** (Salesforce Commerce Cloud — listado HTML + detalle JSON). El
motor es modular (un adaptador por cadena) y replicable a otros rubros.

Las cadenas se emparejan así: Inkafarma↔Mifarma por SKU compartido (grupo
InRetail); Boticas Perú por nombre + principio activo + concentración, con un
matcher fuzzy y **verificación de presentación** (no se compara 220 ml contra
850 g). Donde no hay equivalente comparable, la celda queda en "—".

> Para regenerar: `py -m pipeline.build_comparativa`
