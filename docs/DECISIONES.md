# DECISIONES tomadas sin iC7 (modo autónomo)

Formato: fecha · tarea · qué se eligió · por qué · qué se descartó · cómo revertirlo.

## 2026-09-26 · corrida autónoma v2 (`docs/PROMPT_AUTONOMO_v2.md`)

1. **F3 · zona gris exige la marca de la referencia.** Con la asignación uno a uno, una fila
   que pierde su mejor SKU cae al siguiente candidato y ahí aparecían otras marcas
   (Huggies → Agugu, Eucerin → Anthelios). Descartado: exigir la marca siempre (se perdían
   dos La Roche-Posay legítimos con texto ≥ 85). Revertir: quitar el bloque
   `_marca_ausente` en `core/matcher.comparar`.
2. **F3 · `flex` y `triplesure` como modificadores de fórmula.** Supracalm Flex tiene otro
   activo; Triplesure es otra línea como Peptigro. Revertir: sacarlos de
   `_MODIFICADOR_NUCLEO`.
3. **F3 · vetos curados** para toallitas Huggies (4 en 1, Cuidados 4 en 1, Triple Acción) y
   Pediasure 10+. No hay regla razonable para la "línea" de una toallita. Revertir: borrar
   las entradas en `tests/matches_curados.yaml`.
4. **F3 · orden del reparto uno a uno:** fuerza de evidencia antes que score (curado >
   id/EAN > R.S. > texto/foto > zona gris). Así un R.S. gana a un texto 100 empatado.
   Revertir: `_FUERZA`/`_fuerza` en `pipeline/build_snapshot.py`.
5. **F3 · laboratorios conocidos:** lista cerrada con alias; Boehringer (línea de consumo)
   y Genfar agrupados con Sanofi para no perder Mucosolvan/Bisolvon. Laboratorios dudosos
   (Ansolat, Cifarma, Biopharm) fuera de la lista: no se comparan. Revertir: editar
   `_LABORATORIOS`.
6. **Git · F4 se actualiza con merge de main, no con rebase.** La rama `v2/f4-ui` ya está en
   el remoto; un rebase obliga a `push --force`, que la corrida prohíbe.

## 2026-09-26 · F2 analgésicos (`v2/f2-analgesicos`, worktree `farmacias-f2`)

Detalle completo en `docs/revision/F2_analgesicos.md`. Resumen:

1. **Universal por PATH, no `fq=C:<id>`.** El id numérico del árbol de categorías VTEX
   (`46`) da 0 resultados por `fq`; la búsqueda legacy por path sí funciona. Descartado:
   `fq=C:46` (probado en vivo, sin resultados). Revertir: no aplica, es lo único que
   funcionó.
2. **`get_presentaciones()` de Inka/Mifa sí se pide** (1 request/objectID): sin cantidad
   real, `_cantidad_coincide` rechaza casi todo. Costo asumido (~110 requests para 55
   productos), dentro del presupuesto de 700. Revertir: quitar la llamada en
   `pipeline/categoria_browse.construir` y volver a parsear cantidad solo del nombre.
3. **Sin enriquecimiento F3 (QuickView Boticas/fotos) para esta categoría.** El R.S. de
   Boticas queda sin dato en esta pasada; el veto por R.S. no actúa de ese lado. Revertir/
   extender: pasar un `Enriquecedor` real a `_candidatos` en `pipeline/categoria_browse.py`.
4. **Un solo cgid de Boticas por categoría** (`tra-analgesicosyantiflamatorios`), aunque
   existe un cgid hermano (`tra-analgesicos`, 7 productos solapados) y rutas de "botica en
   casa" sin explorar. Causa medida de la brecha de cobertura Boticas (2/77 vs 44/107 de la
   corrida diaria por búsqueda) — NO es un bug del matcher (ver investigación en el archivo
   de revisión: solo 1 par adicional quedaba bloqueado por cantidad, y era un rechazo
   correcto). Revertir/extender: sumar cgids al `config/categorias.yaml` (lista en vez de un
   solo id) y unir sus candidatos.
5. **`pipeline/run.py --categoria` es un camino aislado**, no reutiliza
   `capturar()`/`procesar()`/`validar()`/`exportar()` de la corrida diaria: cero riesgo de
   tocar el historial/Parquet/`--desde-cache` de la corrida diaria a cambio de más código
   nuevo (`pipeline/categoria_browse.py`). Revertir/fusionar: cambio de diseño mayor, para
   sesión aparte con OK explícito.
6. **Muestra de revisión: 11 pares reales (2 Boticas + 9 Universal), no 30.** No se
   completaron 15+15 porque el pool de candidatos de esta corrida solo produjo 11 cruces
   totales. Descartado: rellenar con pares forzados fuera de la categoría o candidatos de
   baja confianza para llegar a 30 — no diría nada real sobre la calidad del matcher.
   Resultado de los 11: 11 OK, 0 dudosos, 0 falsos.
