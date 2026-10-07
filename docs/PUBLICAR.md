# PUBLICAR — Radar de Precios (2026-10-07)

Sesión de `../docs/PROMPT-publicar.md`, desatendida. Rama `publicar/2026-10-07` (worktree
`../farmacias-publicar`; el checkout `farmacias/` se quedó en `main` porque la tarea de las 02:00
corre desde ahí). **No se publicó nada**: ni push, ni Hostinger, ni cambio de visibilidad.

El repo no tiene `NOTES.md`: este archivo hace de notas de la sesión (la bitácora anterior es
`NOTES_AUTONOMO.md`, 2026-09-26). La línea del portafolio está en `Portfolio/NOTES.md`.

## Estado

### Verificado corriendo (2026-10-07)

| Qué | Evidencia |
|---|---|
| Regresión del matcher | `py -m tests.test_matcher_regresion` → `REGRESIÓN LIMPIA: 85/85 casos OK` |
| 4 suites de F1 | `test_http_cache`, `test_credencial`, `test_publish`, `test_sincronizar` → `todo OK` cada una. `test_sincronizar` fallaba en un clon limpio (`data/logs/` no existe, rclone no abre su log): arreglado en `pipeline/run.py` |
| Demo v1 en subcarpeta `/radar-precios/` | `py -m tests.test_web_smoke` (nuevo) → escritorio y móvil: 296 filas, búsqueda filtra, 0 errores de consola, 0 recursos propios 4xx/5xx, 0 violaciones de CSP → `WEB SMOKE: todo OK` |
| El smoke detecta lo que dice detectar | Prueba negativa: con un `<script>` inline inyectado da `WEB SMOKE: 4 FALLAS` (`script-src-elem inline`) |
| Reproceso sin red | `py -m tests.verificar_desde_cache 2026-10-06T07-00-03Z` → `1354 respuestas del caché · 0 por red` · `OK: sin red y byte a byte igual a data/publicar/data.json (440659 bytes)` · 12 s |
| Corrida nocturna en vivo | `data/logs/run_2026-10-06T07-00-03Z.log`: 3 464 s, 296 filas, 37 con las 4 cadenas, 1 354 peticiones, `errores: 0` (no se relanzó: es la tarea de las 02:00) |
| Lighthouse móvil de la v1 | Accesibilidad 100 · Buenas prácticas 100 · SEO 100 (`--only-categories`, tras arreglar contraste) |
| CLS | Playwright con `PerformanceObserver`: móvil 0,317 → **0,004**, escritorio 0,168 → **0,005** |
| Sitio en vivo | `https://ichisieben.dev/radar-precios/data.json` → `generado 2026-06-14`, 296 productos (snapshot viejo) |

### Dice el doc (no re-verificado hoy)

- UI v2 (PR #4, rama `v2/f4-ui`): 597 páginas, 0 enlaces rotos, Lighthouse ficha 99 / inicio 83–88
  con CPU saturada (`NOTES_AUTONOMO.md`). Beta en zip, no subida.
- F2 analgésicos (rama sin PR): 11 cruces, 11 OK, Boticas 2/77.
- Recon de cadenas (rama `v2/d2-recon-cadenas`): ninguna cadena nueva lista.

### Qué se decidió y por qué

`docs/DECISIONES.md` §2026-10-07 (puntos 13–20). Lo central: documentar la **v1** (lo que sirve la
URL) y no mergear la v2; actualizar `web/data.json` al snapshot del 2026-10-06, que es el que
produce el pipeline actual.

## Pendientes reales (diff seed/roadmap ↔ disco)

Ordenados por valor para quien mira el portafolio dos minutos. Lo que no cupo está en
[`ROADMAP.md`](../ROADMAP.md).

| # | Pendiente | Estado tras esta sesión |
|---|---|---|
| 1 | El sitio en vivo muestra cruces v1 absurdos (Desloratadina +563 %) | **Resuelto en la rama**: `web/data.json` del 2026-10-06 (máx. +59 %). Falta subirlo (owner) |
| 2 | README sin cifras con fecha, con un dato mal ("64 en las cuatro": eran 42; 64 = con Universal) | **Hecho**: `README.md` + `README.en.md` con cifras del 2026-10-06 |
| 3 | Ficha del hub vieja ("tres cadenas", `next` ya hecho) | **Hecho**: `docs/FICHA-LANDING.md` |
| 4 | Contraste AA y CLS de la v1 | **Hecho** (a11y 100, CLS 0,004) |
| 5 | CSP del demo | **Hecho** (`<meta>` en `web/index.html`) |
| 6 | Tutorial con texto falso ("te lo baja en CSV": baja JSON) y sin tildes | **Hecho** (`web/tutorial-init.js`) |
| 7 | UI v2 bilingüe | En revisión (PR #4) — ROADMAP #2 |
| 8 | "Arma tu botiquín" (seed) | ROADMAP #6. Tiene sentido, pero sobre la v2, no sobre la v1 |
| 9 | Alinear fuentes de la v2 con el hub (seed) | Lo decide el owner al revisar el PR #4; no aplica a la v1 |
| 10 | CI en GitHub Actions (seed) | ROADMAP #8 |

El seed proponía cosas que ya no aplican: "mergear `fix/cruce-fuzzy` antes de publicar" (ya
mergeado, PR #2) y "tarjeta dice tres cadenas" (resuelto en la ficha).

## Auditoría

| Revisión | Comando | Resultado |
|---|---|---|
| Autores | `git log --all --format='%an <%ae>' \| sort \| uniq -c` | `IchiSieben <correo personal>` en 106 commits (79 en `main`), `noreply` en 3 |
| Terceros en el árbol | `git grep` de los nombres prohibidos por la regla 2.1 del brief del portafolio, `@gmail`, IPs privadas, rutas `C:\Users`, nombre del repo del ex cliente | 0 hallazgos (solo el nombre del autor en LICENSE/CITATION) |
| Terceros en el historial | `git log --all -S"<palabra>"` / `-G` con la misma lista | **un** nombre prohibido en `c54fb92` (2026-06-13), retirado en `aed7361` (2026-09-18); `C:\Users\Usuario\Mi unidad` en `b9d5284` y `92f3eba` (nombre de usuario genérico de Windows); el resto de la lista, `@gmail` e IPs: 0 |
| gitleaks árbol | `../orquestador/.tools/gitleaks.exe dir . --no-banner` | 10 hallazgos, **todos en rutas ignoradas** (`.env`, `data/raw/recon/*.html`); `git ls-files data/` vacío y ningún commit tocó `data/raw` |
| gitleaks historial | `gitleaks.exe git . --no-banner` | 5 hallazgos en `23b3cc9` y `8a6b9aa` (2026-06-13): las llaves Algolia públicas de solo búsqueda de Inkafarma y Mifarma. Identificadas en `docs/PUBLISH-AUDIT-2026-09-22.md` del portafolio (search-only, ya fuera de HEAD); el historial no se purgó por decisión del owner |
| Licencias de terceros | `requirements.txt` | httpx BSD-3, PyYAML MIT, rapidfuzz MIT, selectolax MIT, ImageHash BSD-2, Pillow MIT-CMU, pyarrow Apache 2.0: compatibles con Apache 2.0. Logos de cadenas: solo en la v2 (rama), no en esta |

**Decisión.** El repo **ya es público** (`gh repo view` → `PUBLIC`), así que la rama
"historial sucio → repo nuevo de un solo commit" no aplica tal cual: un repo nuevo no retira un
historial que ya se puede clonar. Lo expuesto (correo personal, un nombre de tercero ya retirado,
llaves públicas de las cadenas) es de bajo riesgo y ya estaba identificado. **Se queda público aquí.**
Reescribir el historial necesitaría push forzado: decisión del owner, no de esta sesión.

## Checklist final

Adaptado de `enjambre/docs/PUBLISH-CHECKLIST.md` y del criterio por demo del brief §7.

- [x] Demo carga en `/radar-precios/` con rutas relativas, 0 recursos propios con 404 —
      `test_web_smoke` → `0 recursos propios con 4xx/5xx []`
- [x] 0 errores de consola — `test_web_smoke` → `0 errores de consola []`
- [x] CSP compatible con el Landing (`connect-src 'self'`, sin CDN) — `0 violaciones de CSP []`
- [x] Cero costo variable de API — web estática, cálculo en el cliente
- [x] Tutorial de apertura funcional y descartable — el smoke lo abre y lo cierra con "Saltar"
- [x] Tests en verde — 85/85 + 4 suites + smoke (salidas arriba)
- [x] README en español y en inglés, escritos por separado — `README.md`, `README.en.md`
- [x] Captura de portada y gráfica con datos reales, revisadas a tamaño real — `docs/CAPTURAS.md`
- [x] Diagrama mermaid, comandos probados, cifras con fecha, límites, licencias, cómo citar
- [x] `docs/ESTUDIO.md` (4 conceptos) · `docs/FICHA-LANDING.md` · `ROADMAP.md`
- [x] Easter egg elegido y documentado solo en `docs/private/EASTER-EGG.md` —
      `git check-ignore -v` → `.gitignore:28:docs/private/`
- [x] `.gitignore` (datos, `.env`, privados), `.env.example` completo (comparado contra el código),
      `SECURITY.md`, `LICENSE` Apache 2.0, `CITATION.cff` válido (se quitó `orcid: ""`)
- [x] Sin nombres de terceros prohibidos en el árbol — grep arriba
- [x] gitleaks sin hallazgos en archivos versionados — los 10 están en rutas ignoradas
- [x] Contrato de enjambre: `AGENTS.md` en la raíz y `docs/DELEGAR.md` desde las plantillas, sin
      `ssh mac` a pelo — Grep `ssh mac|<[a-z-]+>` → solo la nota del hook y `TASK-<id>`
- [x] Repo clonado en la Mac (2026-10-07, una vez, `ENJAMBRE_RAW_SSH=1` + `tmux-run.sh`) —
      `git log --oneline -1` en la Mac → `1a721ff`, `## main...origin/main`
- [x] Suite por enjambre: **dry-run, sin corrida real** (decisión del owner: el worker no puede
      correr python y la Mac no tiene el entorno; la corrida daría `failed` y empujaría `mac/<id>`
      al repo público). Salida: `{"action": "run", "node": "mac", "routed_by": "rule", "reason":
      "tests -> mac: first free node of prefer ['mac', 'win']", ..., "id": "farmacias-tests-mac",
      "kind": "tests"}` (completa en `docs/DELEGAR.md`). El dry-run no escribe en `jobs.jsonl`.
- [ ] **Owner:** entorno en la Mac (`uv`, ver NEEDS-OWNER de enjambre) y allowlist del worker para
      el tests-cmd; luego la primera corrida real con `docs/tasks/TASK-farmacias-tests-mac.md`
- [ ] **Owner:** copiar `.env` a `~/Documents/Portfolio/farmacias` en la Mac
- [ ] **Owner:** subir `web/data.json` (2026-10-06) y `web/` al sitio (ver abajo)
- [ ] **Owner:** revisar y mergear esta rama (y decidir el push: el repo es público)
- [ ] **Owner:** activar *Private vulnerability reporting* (Settings → Security). Hoy
      `gh api repos/IchiSieben/farmacias/private-vulnerability-reporting` → `{"enabled":false}`;
      `SECURITY.md` remite a esa vía
- [ ] **Owner:** decidir licencia para el JSON derivado (¿CC0?) o dejar "precios de las cadenas"
- [ ] **Owner:** renovar poster y video del Landing (`docs/CAPTURAS.md`)
- [ ] **Owner:** remedir Lighthouse *performance* con la CPU libre (hoy al 100 % por procesos
      ajenos: la corrida dio `PROTOCOL_TIMEOUT` y no es válida)

## Qué falta de tu parte, en orden

1. **Revisar la rama** `publicar/2026-10-07` (`git log main..publicar/2026-10-07`). Si te sirve:
   `git checkout main && git merge --ff-only publicar/2026-10-07 && git push` (es un repo público:
   el push publica).
2. **Subir el demo actualizado.** Cambiaron `web/index.html`, `web/app.js`, `web/styles.css`,
   `web/data.json` y hay un archivo nuevo, `web/tutorial-init.js`. `pipeline/publish.py` solo
   sube `data.json`, así que los otros cuatro van por hPanel → Administrador de archivos →
   `public_html/radar-precios/` (respaldar antes la carpeta como `radar-precios-v1-junio/`).
   Verificar después: `py -m tests.test_web_smoke` no prueba la URL pública; abrir
   https://ichisieben.dev/radar-precios/ y ver "snapshot 2026-10-06" en la cabecera.
3. Lo demás del checklist de arriba.
