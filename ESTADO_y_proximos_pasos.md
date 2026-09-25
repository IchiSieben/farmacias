# ESTADO DEL PROYECTO — Radar de Precios (para retomar)

> Abre esto al empezar la sesión. Claude Code lo actualiza al cerrar cada fase.
> Última actualización: 2026-09-24 (F1 implementada en rama `v2/f1-data-lake`, PR pendiente).

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
| F1 | Data lake: crudo a Google Drive (`RAW_DIR`), Parquet, `pipeline/run.py`, tarea diaria Windows, `--desde-cache` | 🟨 hecha en rama; falta 1ª corrida completa + merge |
| F2 | Cobertura por categoría (browse/facetas/cgid/fq), `config/categorias.yaml`, una categoría por sesión con muestra revisada | ⬜ siguiente |
| F3 | Matcher v2: `core/ficha.py` (atributos > nombre), registro sanitario como llave, imagen en todo candidato, evidencia por match, set curado | ⬜ |
| F4 | UI v2 bilingüe (Astro): buscador, ficha con historial, panorama por cadena, metodología | ⬜ |
| F5 | README final con capturas nuevas, `docs/` (esquema, matching, operación), CITATION 2.0.0 | ⬜ |

**Arranque:** pegar `PROMPT_claude_code.md` en Claude Code desde la raíz del repo.

### F1 — qué quedó (rama `v2/f1-data-lake`)

| Pieza | Archivo | Nota |
|---|---|---|
| Crudo particionado | `core/storage.py` | `RAW_DIR/<cadena>/<fecha>/`, gzip, escritura atómica, manifiesto por corrida. Solo stdlib. |
| Graba/reproduce HTTP | `core/http_cache.py` + `core/adapter_base.py` | Transporte httpx: graba cada respuesta **antes** del parseo; reproduce sin red (un faltante falla, no sale a la red); reanuda corridas cortadas. Delay por dominio solo en requests reales. Las keys Algolia nunca llegan al crudo. |
| Orquestador | `pipeline/run.py` | `--todo`, `--solo-captura`, `--desde-cache`, `--reanudar`, `--delay` (default 2–6 s), `--sin-semillas`. La salida oficial **siempre** se reprocesa desde el crudo. Log en `data/logs/`. |
| Parquet | `pipeline/parquet.py` + `docs/ESQUEMA_DATOS.md` | `ofertas` y `eventos`, esquema Arrow explícito, `history/<fecha>/` + `latest/`. |
| Tarea diaria | `scripts/instalar_tarea_windows.ps1` + `corrida_diaria.cmd` | `schtasks /IT` (solo con sesión iniciada: Drive se monta por sesión). **Aún no registrada.** |
| Config | `.env.example`, `.gitignore` | `RAW_DIR`, `PROCESSED_DIR`, `PUBLISH_*` (reservado). `data/` anclado a `/data/` (antes también ignoraba `web/data/`). |

Verificado: regresión 32/32; `tests/test_http_cache.py` OK en Python 3.12 y 3.9
(incluye reanudar tras una línea cortada); captura real de 3 productos (15 requests,
0 errores) → `--desde-cache` con **sockets bloqueados** da un `data.json` **byte a
byte igual**; `--reanudar` termina con 0 requests de red; una captura simulada con
key Algolia rotada (403) sale con código 2 **sin** escribir `data.json` ni snapshot.
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
.\scripts\instalar_tarea_windows.ps1 -Hora 04:30 -Simular                      # muestra el schtasks, no registra
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
  la regla del portafolio exige confirmación explícita. Falta acordar el mecanismo
  (p.ej. subir a una carpeta staging y confirmar a mano el cambio).

Pendiente para cerrar F1:
1. `RAW_DIR`: en esta sesión Google Drive para escritorio **no estaba montado** (no
   existían `G:\Mi unidad` ni `C:\Users\Usuario\Mi unidad`). Abrirlo, ver la ruta en
   el Explorador y ponerla en `.env`.
2. Primera corrida completa real: `py -m pipeline.run --todo`. Duración **sin
   medir**: la mini captura dio ~11 s por producto con 2–6 s por dominio; con 150
   productos más las semillas de 2 subcategorías, **estimo** 1 h o más. Medirla en esta
   primera corrida (sale en el resumen) antes de elegir la hora de la tarea.
   Después, `py -m tests.verificar_desde_cache <id-corrida>`.
3. Registrar la tarea: `.\scripts\instalar_tarea_windows.ps1 -Hora 04:30`. Con `/IT`,
   cerrar sesión a mitad de la corrida la mata: se retoma con `--reanudar <id>`.
4. PR `v2/f1-data-lake` → `main`.

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
  la corrida v2 **no exporta** si ve 401/403 (código 2, `data.json` intacto). Falta
  cortar en el primer 403: hoy prueba todos los términos (~75 requests) antes de
  rendirse → tarea chica para F2.
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
PYTHONIOENCODING=utf-8 py -m tests.verificar_desde_cache <fecha|id> [--contra web/data.json]
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
