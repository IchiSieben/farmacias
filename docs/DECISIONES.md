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
7. **F4 · Universal en magenta en el gráfico** (#a8327f claro, #f28ac9 oscuro; contraste
   6,1:1 y 7,6:1). Su color de marca es azul como el de Boticas. Revertir: `--cad-universal`
   en `web-v2/src/styles/global.css`.
8. **F4 · marca y laboratorio de InRetail se intercambian al exportar** cuando solo la marca
   parece un laboratorio (94 filas mostraban "Laboratorio: DOLO- QUIMAGESICO"). Solo en
   `export_web`; el matcher no cambia. Revertir: `marca_y_laboratorio`.
9. **F4 · filtro por laboratorio sí; por forma farmacéutica no**: `web/data` no trae la forma.
   Añadirla es cambiar el esquema del exportador (pendiente, no urgente).
10. **Fase C · no se subió la beta.** Sin `PUBLISH_*`, y `publish.py` no sube carpetas.
    Descartado: escribir un subidor FTP/SFTP de carpetas sin poder probarlo, y el conector de
    Hostinger (despliega el sitio entero). Queda un zip listo para subir a mano.
11. **F4 · Lighthouse del inicio 83–88 medido con la CPU al 100 % por procesos ajenos**; no se
    optimizó a ciegas. Remedir con la CPU libre; si sigue < 90, mirar la hidratación de la isla
    (el LCP es el primer nombre de producto, ya viene en el HTML).
12. **F2 · analgésicos en rama propia** (`v2/f2-analgesicos`) con tope de 700 peticiones y detrás
    de un flag: la corrida de las 02:00 no cambia.

## 2026-10-07 · publicar (`../docs/PROMPT-publicar.md`)

13. **`web/data.json` = staging del 2026-10-06.** Es el artefacto que escribe el pipeline (copiado
    de `data/publicar/data.json`, verificado byte a byte con `tests.verificar_desde_cache`), no una
    edición a mano. El de junio mostraba cruces v1 absurdos (+563 %). Revertir:
    `git checkout main -- web/data.json`. El sitio en vivo no cambia hasta que el owner publique.
14. **Se documenta la v1, no la v2.** La v2 (PR #4) espera revisión; no se mergeó a esta rama.
    README y ficha dicen "v2 en revisión" con enlace al PR.
15. **CSP `default-src 'self'` por `<meta>` en la v1**; el script inline del tutorial pasó a
    `web/tutorial-init.js`. Revertir: quitar el `<meta http-equiv>` de `web/index.html`.
16. **README en dos archivos** (`README.md` ES, `README.en.md` EN) en vez de uno con dos
    secciones, como pide la plantilla de publicación.
17. **Sin licencia de datos declarada.** Precios = hechos de las cadenas; código Apache 2.0. Si se
    quiere CC0 para el JSON derivado, lo decide el owner.
18. **Sin push.** El repo ya es público y la plantilla solo permite push a repos privados. La rama
    queda local.
19. **`docs/seed/`, `docs/handoffs/`, `HANDOFF.md` y `docs/PROMPT_AUTONOMO_v2.md` fuera del commit.**
    El seed nombra un repo privado de un ex cliente que este repo no debe mencionar; los otros son
    operativos. Siguen en el disco, sin versionar.
20. **Contraste AA y CLS en la v1.** `--suave` #6b7686 → #5a6474, `--verde` #0a9a52 → #087a41,
    `.ppu` del más barato #2e8b57 → #1f7a4a, sin `opacity` en `.pie .fino`; `main.wrap` con
    `min-height: 100vh` (el pie saltaba al llegar la tabla). Lighthouse a11y 100; CLS móvil
    0,317 → 0,004. Revertir: `git checkout main -- web/styles.css`.
