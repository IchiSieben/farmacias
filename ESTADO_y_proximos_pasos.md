# ESTADO DEL PROYECTO — Radar de Precios (para retomar)

> Abre esto al empezar la sesión. Claude Code lo actualiza al cerrar cada fase.
> Última actualización: 2026-09-25 (F1 cerrada: corrida completa medida, byte a byte a escala,
> tarea diaria registrada; PR `v2/f1-data-lake` → `main` abierto).

---

## ✅ v1 — HECHO y en producción

- **4 cadenas:** Inkafarma + Mifarma (Algolia InRetail), Boticas Perú (SFCC),
  Farmacia Universal (VTEX, con EAN).
- **Matcher de 3 capas** con reglas duras (concentración, cantidad, forma, pediátrico,
  vitamina, gomita, efervescente, activo compartido) + pHash en zona gris.
  Regresión: 32/32 OK.
- **Snapshots por corrida** + `pipeline/cambios.py` (▲▼, promos, nuevos).
- **Web estática** (`web/`) desplegada en https://ichisieben.dev/radar-precios/ —
  296 productos, 64 con las 4 cadenas. Tutorial de apertura. Vista `?demo`.
- README bilingüe, CITATION.cff, Apache 2.0. Repo público
  `github.com/IchiSieben/farmacias`.

## 🚧 v2 — EN CURSO (plan completo en `V2_PLAN.md`)

| Fase | Qué | Estado |
|---|---|---|
| F1 | Data lake: caché local + archivo en Drive (rclone), Parquet, `pipeline/run.py`, tarea diaria, `--desde-cache`, publicación manual | ✅ cerrada; PR abierto |
| F2 | Cobertura por categoría (browse/facetas/cgid/fq), `config/categorias.yaml`, una categoría por sesión con muestra revisada | ⬜ siguiente |
| F3 | Matcher v2: `core/ficha.py` (atributos > nombre), registro sanitario como llave, imagen en todo candidato, evidencia por match, set curado | ⬜ (adelanto: rama `fix/cruce-fuzzy`, ver Deuda) |
| F4 | UI v2 bilingüe (Astro): buscador, ficha con historial, panorama por cadena, metodología | 🟨 rama `v2/f4-ui` (worktree `../farmacias-ui`): inicio hecha, ficha en curso |
| F5 | README final con capturas nuevas, `docs/` (esquema, matching, operación), CITATION 2.0.0 | ⬜ |

**Arranque:** pegar `PROMPT_claude_code.md` en Claude Code desde la raíz del repo.

### F1 — qué quedó (rama `v2/f1-data-lake`)

| Pieza | Archivo | Nota |
|---|---|---|
| Crudo particionado | `core/storage.py` | `RAW_DIR/<cadena>/<fecha>/`, gzip, escritura atómica, manifiesto por corrida. Solo stdlib. |
| Graba/reproduce HTTP | `core/http_cache.py` + `core/adapter_base.py` | Transporte httpx: graba cada respuesta **antes** del parseo; reproduce sin red (un faltante falla, no sale a la red); reanuda corridas cortadas. Delay por dominio solo en requests reales. Las keys Algolia nunca llegan al crudo. |
| Orquestador | `pipeline/run.py` | `--todo`, `--solo-captura`, `--desde-cache`, `--reanudar`, `--delay` (default 2–6 s), `--sin-semillas`. La salida oficial **siempre** se reprocesa desde el crudo. Log en `data/logs/`. |
| Parquet | `pipeline/parquet.py` + `docs/ESQUEMA_DATOS.md` | `ofertas` y `eventos`, esquema Arrow explícito, `history/<fecha>/` + `latest/`. |
| Archivo en Drive | `pipeline/run.py --sincronizar` | `rclone copy` (nunca `sync`) del crudo y el Parquet a `RCLONE_REMOTE*`, **después** de snapshot y Parquet: si Drive falla, la corrida ya está completa y el copy se reintenta mañana. Incluido al final de `--todo`/`--reanudar`. |
| Publicación | `pipeline/publish.py` | La corrida exporta a staging (`data/publicar/data.json`), nunca a lo servido. `publish` muestra resumen (productos, cambios de precio, desaparecidos, tamaño), pide escribir `publicar`, rechaza si desaparece >20 % salvo `--forzar`, sube por FTP/SFTP (`PUBLISH_*` en `.env`) con respaldo local del remoto. `--simular` prueba la conexión en solo lectura. **No** lo llama la tarea diaria. |
| Tarea diaria | `scripts/instalar_tarea_windows.ps1` + `corrida_diaria.cmd` | **Registrada: diaria a las 02:00** (`RadarPrecios-CorridaDiaria`), `schtasks /IT`: corre con la sesión iniciada (bloqueada vale) sin guardar contraseña. |
| Config | `.env.example`, `.gitignore`, `.gitattributes` | `RAW_DIR`, `PROCESSED_DIR`, `RCLONE_REMOTE*`, `PUBLISH_*`. `data/` anclado a `/data/` (antes también ignoraba `web/data/`). `*.json`/`*.py` en LF. |

Verificado: regresión 32/32; `tests/test_http_cache.py` OK en Python 3.12 y 3.9
(incluye reanudar tras una línea cortada); captura real de 3 productos (15 requests,
0 errores) → `--desde-cache` con **sockets bloqueados** da un `data.json` **byte a
byte igual**; `--reanudar` termina con 0 requests de red; una captura simulada con
key Algolia rotada (403) sale con código 2 **sin** escribir `data.json` ni snapshot, y la
captura se corta en el **primer** 403 con un mensaje que dice qué key rotó y cómo recapturarla.

**A escala (corrida `2026-09-25T03-33-29Z`, `--objetivo 150`, con historial):** 3131 s
(**52 min**) + ~1,5 min de rclone; 1232 requests, 0 errores; 296 filas, 55 con las 4
cadenas. `--desde-cache` de esa corrida con sockets bloqueados: **byte a byte igual**
(334 188 bytes) en 5 s. Tests `http_cache`, `credencial`, `publish`, `sincronizar`: OK.
`web/` sin cambios respecto de `main`.

**Verificarlo tú en 5 minutos (PowerShell, desde la raíz del repo):**

```powershell
git checkout v2/f1-data-lake
py -m pip install -r requirements.txt            # suma pyarrow
$env:PYTHONIOENCODING = "utf-8"
py -m tests.test_matcher_regresion               # 32/32 OK
py -m tests.test_http_cache                      # todo OK
# Mini captura real (~40 s). --salida y --sin-historial son OBLIGATORIOS aquí:
# sin ellos pisa web/data.json con 3 productos y deja un snapshot de 3 filas que
# sería el "previo" de la primera corrida real.
$env:RAW_DIR = "$env:TEMP\raw_prueba"; New-Item -ItemType Directory -Force $env:RAW_DIR | Out-Null
py -m pipeline.run --todo --objetivo 3 --sin-semillas --salida "$env:TEMP\vivo.json" --sin-historial
# Copia el id que imprime la primera línea ("Corrida 2026-...Z") y:
py -m tests.verificar_desde_cache <id-corrida> --contra "$env:TEMP\vivo.json"   # OK: sin red y byte a byte igual
Get-ChildItem -Recurse $env:RAW_DIR | Select-Object FullName, Length          # crudo por cadena + _corridas
.\scripts\instalar_tarea_windows.ps1 -Simular                                 # muestra el schtasks, no registra
Remove-Item Env:RAW_DIR
```

Decisiones (y por qué):
- **Caché a nivel HTTP (record/replay), no volcado de catálogo:** la v1 descubre
  productos por consultas, y los candidatos de cada búsqueda deciden el match. Solo
  reproduciendo las mismas respuestas se obtiene la misma salida. El volcado por
  catálogo queda para F2.
- **Byte a byte = `web/data.json`, no `web/data/`:** el export particionado es de F4.
  `generado` y el snapshot previo viajan con la corrida, así que el reproceso es
  idéntico en cualquier máquina.
- **`fichas`/`matches` no entran todavía al Parquet:** son de F3.
- **pandas fuera de `core/`** (regla 3.9): el Parquet vive en `pipeline/`, con pyarrow.
- **`publicar` NO se automatizó:** subir a Hostinger sobrescribe el sitio público, y
  la regla del portafolio exige confirmación explícita. Contrato: la tarea exporta a
  staging; `pipeline.publish` compara con lo publicado y pide confirmación.
- **Caché local + archivo en Drive vía rclone** (no Drive para escritorio montado):
  la corrida no depende de una unidad de red; ver `V2_PLAN.md` §1 (enmendado).
- **02:00:** 52 min medidos + rclone terminan hacia las 03:00.

Después de F1 (fuera del PR):
1. `PUBLISH_*` en `.env` (credenciales FTP/SFTP, las pone el usuario) y probar
   `py -m pipeline.publish --simular`. La primera publicación real, a mano.
2. Mergear `fix/cruce-fuzzy` **antes** de la primera publicación: sin él, el staging
   trae Suprahyal↔Mensille (13×) y dos Desloratadina a 6–9× (ver Deuda).
3. Con `/IT`, cerrar sesión a mitad de la corrida la mata: se retoma con
   `--reanudar <id>`.

### F2 — por dónde empezar

1. Recon de ids de categoría: `cgid` de Boticas y `fq=C:<id>` de Universal
   (**[verificar]** en V2_PLAN), usando `recon/mapa_categorias.py`.
2. `config/categorias.yaml` con una sola categoría canónica (propuesta: analgésicos,
   que ya tiene semilla y regresión).
3. `browse_categoria()` en los 4 adaptadores. Pasa por el mismo `TransporteCache`,
   así que hereda el crudo y `--desde-cache` sin trabajo extra.
4. Muestra de 30 matches revisada a mano → nuevos casos de regresión → siguiente
   categoría. Presupuesto de requests por cadena: ya sale en el resumen de `run.py`.

## 🔧 Deuda conocida (sigue vigente)

- Llaves Algolia rotan → 403; recapturar desde DevTools y actualizar `.env`. Desde F1
  la corrida v2 **no exporta** si ve 401/403 (código 2, staging intacto) y corta en el
  primer 403 diciendo qué key rotó.
- **Cruce fuzzy absurdo (rama `fix/cruce-fuzzy`, PR aparte):** Suprahyal (ác.
  hialurónico) casó con Mensille (anticonceptivo) porque "inyectable"/"jeringa"
  contaban como principio activo, y `_precio_plausible` estaba muerto desde 219e668.
  El arreglo los vuelve genéricos y reactiva la guarda en todo cruce fuzzy con
  [1/3, 3]. Reproducida la corrida del 25-09 con el arreglo: cambian exactamente esas
  3 filas. Regresión 36/36.
- Corridas pesadas contra Boticas se han cortado alguna vez. Desde F1,
  `py -m pipeline.run --reanudar <corrida>` sigue desde el staging sin repetir
  requests. No reintentar en bucle.
- `pipeline.build_snapshot` (entrada v1) sigue con delay 0 y pausa de 0,15 s entre
  productos. La corrida v2 (`pipeline.run`) usa 2–6 s por dominio: no usar la v1
  para corridas automáticas.
- El histórico se resetea si cambian los ids de match (pasó al separar
  presentaciones). En F3 el `match_id` pasa a ser estable (derivado de llaves duras
  cuando existan).
- Stock no se captura en InRetail (vive en el detalle) — entra en F2 con el detalle
  REST por producto, solo para lo que ya está emparejado.

## 🚀 Cómo correr (v2, F1)

```
PYTHONIOENCODING=utf-8 py -m pipeline.run --todo                      # corrida diaria
PYTHONIOENCODING=utf-8 py -m pipeline.run --desde-cache 2026-09-25    # reproceso sin red
PYTHONIOENCODING=utf-8 py -m pipeline.run --reanudar <id-corrida>     # captura cortada
PYTHONIOENCODING=utf-8 py -m tests.test_http_cache
PYTHONIOENCODING=utf-8 py -m tests.verificar_desde_cache <fecha|id>   # contra data/publicar/data.json
PYTHONIOENCODING=utf-8 py -m pipeline.run --sincronizar               # reintenta el copy a Drive
PYTHONIOENCODING=utf-8 py -m pipeline.publish --simular               # resumen + prueba de conexión
PYTHONIOENCODING=utf-8 py -m pipeline.publish                         # pide escribir "publicar"
```

Ojo: la fecha de corrida está en **UTC** (de noche en Lima ya es el día siguiente).
Ante la duda, usar el id que imprime el log (`Corrida 2026-09-25T02-09-04Z`).

## 🚀 Cómo correr / verificar (v1, sigue igual hasta F4)

```
PYTHONIOENCODING=utf-8 py -m tests.test_matcher_regresion
py -m pipeline.build_snapshot --objetivo 150 --salida web/data.json
py -m http.server -d web 8000     # http://localhost:8000  ·  ?demo=1 para la demo
py -m pipeline.make_demo          # regenerar data.demo.json tras cambiar data.json
```

## Cómo retomar la próxima sesión

1. Leer esta tabla y `V2_PLAN.md` de la fase que toca.
2. Pedir a Claude Code diagnóstico → plan corto → implementar → controles → commit.
3. Una fase (o una categoría, en F2) por sesión. Actualizar esta tabla al cerrar.
