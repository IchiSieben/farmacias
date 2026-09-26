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
