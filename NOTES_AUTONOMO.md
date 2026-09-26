# NOTES_AUTONOMO — corrida autónoma v2 (2026-09-26)

> Bitácora de la corrida sin supervisión (`docs/PROMPT_AUTONOMO_v2.md`). El resumen para
> el celular va arriba al terminar; debajo, el registro en orden.

## Estado real al arrancar (12:47, hora de Lima)

- Worktrees: `farmacias` (main, 1c69537) · `farmacias-f3` (v2/f3-matcher, 7a0d376) ·
  `farmacias-ui` (v2/f4-ui, 490fd13) · `farmacias-fix` (fix/cruce-fuzzy, ya mergeada en #2).
- PRs: #3 F3 (DRAFT). #1 (F1) y #2 (fix matcher) mergeados.
- Última corrida diaria: `2026-09-26T07-00-07Z` (02:00 Lima): 3338 s, 294 filas, 54 con
  las 4 cadenas; Boticas 109, Universal 77; 1 error HTTP de Universal (exit 1).
  Capturada con el código de main: sin QuickView de F3.
- `.env` NO tiene `PUBLISH_*` → la Fase C (subida a beta con `pipeline/publish.py`) está
  bloqueada de antemano. Decisión conservadora: no usar el conector MCP de Hostinger
  en su lugar (`deployStaticWebsite` despliega el sitio entero, no una subcarpeta).
- `../farmacias-f3/scratchpad/REVISION_F3.md` no existe; la revisión está en HANDOFF.md.
- Procesos: ningún `py`/`find` corriendo al arrancar. Solo toco lo que lanzo yo.

## Presupuesto de red (máx. 3 000 requests)

| Paso | Requests |
|---|---|
| `--completar 2026-09-26T07-00-07Z` (QuickView + fotos) | 164 (138 QuickView + 26 fotos), 0 errores |
| D.2 recon de cadenas (agente) | 55 (39 a cadenas, 1 google, 9 WebSearch, 6 firecrawl fallidos), 0 403/429 |

## Registro

### Fase A — F3 cerrada y mergeada (PR #3 → 83e4ca5)

- Reglas de §1 aplicadas; regresión 85/85 (3.12 y 3.9); 4 suites OK; reproceso
  `--desde-cache 2026-09-26T07-00-07Z` byte a byte determinista; 0 SKUs en dos filas.
- Cifras (misma corrida): main 109 Boticas / 77 Universal / 54 con 4 cadenas / 17 SKUs
  dobles → F3 87 / 71 / 42 / 0. Equivalentes 19. Zona gris 10.
- Añadido por criterio propio (mismo principio "falso positivo peor que —"): zona gris exige
  la marca; `flex`/`triplesure` modificadores; vetos curados Huggies (3) y Pediasure 10+.
- Dudosos listados en `docs/revision/F3_final.md` §5 (7 casos).
- Desvío: el prompt pedía `REVISION_F3.md` de `../farmacias-f3/scratchpad/`; no existía,
  se usó la lista de HANDOFF.md.

### Fase B — F4 terminada en rama (`v2/f4-ui`, pusheada, sin mergear)

- Merge de main (no rebase: la rama ya estaba en el remoto) → 0a47699. Datos regenerados
  desde la corrida `2026-09-26T07-00-07Z` reprocesada con F3 (295 filas, 87 Boticas,
  71 Universal, 42 con las 4).
- Arreglos visibles: los 4 logos en la misma píldora (Boticas sobre su azul, PNG de 76 KB a
  4,8 KB), ancho tope 5× el alto; "Nuevo" = no estaba en la captura anterior (tooltip con
  la fecha); historial de cada cadena solo con puntos del SKU actual; Universal en magenta
  (Boticas y Universal eran dos azules). "A revisar" ya iba al final y con aviso (hoy 0 filas).
- Panorama (`/es/panorama/`, `/en/panorama/`) y Metodología (grupos, capturas, capas del
  emparejado, "mejor — que falso", alcance y por qué no cosmética, no afiliación, licencia).
  Navegación en la cabecera y pie compartido.
- Filtro por laboratorio en "Más filtros" (con `?lab=`). Forma farmacéutica: el dato no
  existe en `web/data`, no se hizo.
- Corrección de datos: en 94 filas InRetail trae marca y laboratorio cruzados ("Laboratorio:
  DOLO- QUIMAGESICO"); `export_web.marca_y_laboratorio` los intercambia. Quedan casos con
  laboratorios fuera de la lista (Cifarma, Farmaindustria sin "LABORATORIO").
- `base` configurable: `RADAR_BASE=/radar-precios-beta/` (en Git Bash, con `MSYS_NO_PATHCONV=1`).
- Verificación del build beta: 597 páginas; 0 enlaces/assets internos rotos, 0 rutas fuera
  de la base, 0 claves i18n sin traducir. Playwright: 11 páginas × móvil/escritorio ×
  claro/oscuro, 0 errores de consola, 0 peticiones fallidas, 0 imágenes rotas.
- Lighthouse móvil (build local, **CPU al 100 % por VS Code y Brave, ajenos**):
  inicio 83/88 (es) y 83 (en) · ficha 99 · panorama 96 · metodología 95. Accesibilidad 100
  en todas. El inicio no llega a 90: LCP 3,0–3,3 s con TTFB local de 470 ms (la carga).
  Remedir con la CPU libre antes de promover.
- Capturas: `docs/revision/beta_local_*.png` en la rama F4.

### Fase C — beta NO subida (bloqueada)

- `.env` sin `PUBLISH_*` y `pipeline/publish.py` solo sube `data.json`, no un `dist/`.
  No escribí un subidor de carpetas porque no se puede probar contra el servidor, ni usé el
  conector de Hostinger (despliega el sitio entero, no una subcarpeta).
- Dejé listo `../farmacias-ui/data/beta/radar-precios-beta.zip` (7,7 MB, build con base
  `/radar-precios-beta/`). Subida manual: hPanel → Administrador de archivos →
  `public_html/` → crear `radar-precios-beta/` → subir el zip dentro → Extraer → borrar el zip.

### Fase D

- D.2 recon de cadenas: rama `v2/d2-recon-cadenas` (d1f0f15), `docs/RECON_CADENAS.md`.
  Ninguna lista: Fasa, BTL y Arcángel ya son Mifarma; Plaza Vea y Wong exponen VTEX con EAN
  pero no se vio OTC; Metro sin resolver; Tottus 503. **Incidente:** el agente hizo 2
  peticiones a `vivanda.com.pe/api/` que su robots.txt prohíbe. Está registrado en el
  documento; no se repite. 55 peticiones.
- D.3 idea retail: rama `v2/d3-idea-retail` (252d4a7), subsección en V2_PLAN §3.

## Promoción a `/radar-precios/` — NO ejecutada (solo cuando iC7 escriba "publicar")

```
# 0. Antes: remedir Lighthouse del inicio con la CPU libre; revisar la beta.
# 1. Build con la base definitiva (worktree F4)
cd ../farmacias-ui/web-v2
npx tsc --noEmit -p . && npm run build          # base por defecto: /radar-precios/
py -c "import shutil; shutil.make_archive('../data/beta/radar-precios-v2','zip','dist')"
# 2. Respaldo de v1 (hPanel → Administrador de archivos, en public_html/):
#    renombrar radar-precios/ → radar-precios-v1/   (reversible: renombrar de vuelta)
# 3. Crear public_html/radar-precios/, subir radar-precios-v2.zip, Extraer, borrar el zip.
# 4. Verificar: /radar-precios/ redirige a /es/; /es/, /en/, panorama, metodología y 5 fichas
#    dan 200; logos e imágenes cargan (scratchpad verificar_web.py contra la URL pública).
# Vuelta atrás: borrar radar-precios/ y renombrar radar-precios-v1/ → radar-precios/.
```

Ojo: la v2 hornea los datos en el build. `pipeline/publish.py` sigue subiendo solo el
`data.json` de la v1: tras la promoción, actualizar precios = regenerar `web/data` +
build + subir. Automatizarlo es trabajo pendiente (no hecho).
