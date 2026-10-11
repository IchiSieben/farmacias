# Notas de arquitectura: Radar de Precios

Respuestas a las 9 preguntas del manual, con evidencia en el código. Fecha: 2026-10-10. Lo que no está en el código está marcado "por confirmar" y no se dibuja.

## 1. Actores

- Visitante: abre la página estática en su navegador (`web/index.html`, `web/app.js`).
- Responsable del proyecto: programa la tarea diaria y publica a mano (`pipeline/publish.py`, confirmación escrita).
- Sistemas externos: cuatro catálogos públicos de cadenas de farmacias, nombrados aquí por plataforma (ver §2) y un almacén en la nube que recibe copias (rclone).

## 2. Contenedores

| Id | Qué es | Stack | Dónde corre |
|---|---|---|---|
| sched | Tarea programada diaria | `scripts/instalar_tarea_windows.ps1` registra con `schtasks` (`/SC DAILY /ST 02:00 /IT`); ejecuta `scripts/corrida_diaria.cmd` | PC Windows (solo con sesión iniciada) |
| run | Orquestador de la corrida | `pipeline/run.py` (`main`: capturar, procesar, validar, exportar, sincronizar, resumen) | PC Windows |
| eng | Adaptadores y motor HTTP | `core/adapters/*`, `core/adapter_base.py` (httpx, delays, backoff), `core/http_cache.py` (`SesionHttp`) | PC Windows |
| ca | Cadena A (Algolia) | `core/adapters/inkafarma.py` sobre `algolia_inretail.py`; llaves públicas de solo búsqueda por entorno | Externo |
| cb | Cadena B (Algolia) | `core/adapters/mifarma.py` sobre `algolia_inretail.py`; mismo esquema de documento que A | Externo |
| cc | Cadena C (SFCC) | `core/adapters/boticasperu.py`: grilla HTML (selectolax) + QuickView JSON | Externo |
| cd | Cadena D (VTEX) | `core/adapters/universal.py`: catalog search legacy, trae EAN | Externo |
| raw | Crudo comprimido | `core/storage.py` `RawStore`: `respuestas_<corrida>.jsonl.gz` por cadena + manifiesto + `previo.json.gz` | Disco del PC (`RAW_DIR`) |
| mat | Normalizador y matcher | `core/normalizer.py`, `core/matcher.py`, `core/imagen.py`, `pipeline/build_snapshot.py` (`construir`, `_candidatos`, `_asignar`), `pipeline/cambios.py` | PC Windows |
| out | Salidas de la corrida | `data/publicar/data.json` (staging), `data/snapshots/`, eventos CSV, Parquet (`pipeline/parquet.py`) | Disco del PC |
| cloud | Almacén en la nube | destino de `rclone copy` (`RCLONE_REMOTE`, `RCLONE_REMOTE_PROCESSED` en `.env.example`) | Externo |
| pub | Publicador | `pipeline/publish.py` (`comparar`, `verificar_umbral`, `cargar_publicado`, `DestinoFTP`/`DestinoSFTP`, `subir`) | PC Windows, a mano |
| host | Hosting estático | `web/` tal cual: HTML, CSS, JS, `data.json`, `data.demo.json` | Hostinger (ver §7) |
| vis | Navegador del visitante | `web/app.js` hace `fetch(DATA_FILE)`; CSP `default-src 'self'` por `<meta>` en `web/index.html` | Navegador del usuario |

Nota sobre cadenas: el repo tiene cuatro adaptadores en `main` y `pipeline/run.py` define `CADENAS` con las cuatro. La ficha de la Landing habla de tres. Por confirmar cuál es la cifra vigente para el público; el diagrama dibuja los cuatro adaptadores que existen.

## 3. Llamadas reales

| Id | De a | Protocolo y carga | Evidencia (archivo:función) |
|---|---|---|---|
| e1 | sched a run | proceso local: `py -m pipeline.run --todo` | `scripts/corrida_diaria.cmd` |
| e2 | run a eng | llamada de función: `construir(...)` con transporte que graba | `pipeline/run.py:capturar`, `pipeline/build_snapshot.py:construir` |
| e3 | eng a ca | HTTPS, búsqueda Algolia y REST de detalle por presentación | `core/adapters/algolia_inretail.py`, `inkafarma.py` (`get_presentaciones`) |
| e4 | eng a cb | HTTPS, búsqueda Algolia y detalle | `core/adapters/mifarma.py`, `algolia_inretail.py` |
| e5 | eng a cc | HTTPS, HTML de listado y QuickView JSON | `core/adapters/boticasperu.py` |
| e6 | eng a cd | HTTPS, JSON del catalog search | `core/adapters/universal.py` |
| e7 | eng a raw | archivo: cada respuesta se graba y se publica comprimida | `core/http_cache.py:TransporteCache.handle_request`, `core/storage.py:RawStore.publicar_archivo`, `pipeline/run.py:capturar` |
| e8 | raw a mat | archivo: reproduce el crudo sin red (modo REPRODUCIR) | `pipeline/run.py:procesar`, `core/http_cache.py:SesionHttp` |
| e9 | mat a out | archivo: `data.json` de staging, histórico, eventos, Parquet | `pipeline/run.py:exportar`, `pipeline/cambios.py:persistir_snapshot`, `pipeline/parquet.py:exportar_parquet` |
| e10 | out a cloud | `rclone copy` del Parquet | `pipeline/run.py:sincronizar` |
| e11 | raw a cloud | `rclone copy` del crudo | `pipeline/run.py:sincronizar` |
| e12 | out a pub | archivo: `data/publicar/data.json` | `pipeline/publish.py:main`, `STAGING_DEFAULT` |
| e13 | pub a host | FTPS (o SFTP): sube a un temporal y renombra | `pipeline/publish.py:DestinoFTP.reemplazar`, `subir` |
| e14 | vis a host | HTTPS GET de `data.json` | `web/app.js` (`fetch(DATA_FILE)`) |

La corrida vuelve a leer lo grabado: la salida oficial sale siempre del crudo, también en `--todo` (docstring de `pipeline/run.py`).

## 4. Flujos

1. Corrida diaria: e1, e2, e3 a e6, e7, e8, e9, e11, e10.
2. Reproceso sin red: e8, e9 (`--desde-cache`; `tests/verificar_desde_cache.py` lo prueba byte a byte).
3. Publicar a mano: e12, e13 (comparación contra lo publicado, tope de 20 % de desaparecidos, confirmación escrita, respaldo, verificación posterior).
4. Una visita: e14.

## 5. Componentes internos del núcleo

No aplica como hexágono: no hay API ni capa de casos de uso. El núcleo es un motor de scripts (`core/` + `pipeline/`); la vista hex se omite. El matcher tiene tres capas (id/EAN, texto difuso con reglas duras, imagen por pHash desde texto 60) con umbrales 85 de coincidencia y 70 de revisión (`core/matcher.py`: `UMBRAL_MATCH`, `UMBRAL_REVISION`, `UMBRAL_IMAGEN`).

## 6. Datos

No hay base de datos; el almacenamiento son archivos. Vista "data" omitida en esta primera versión. Estructura:

- `RAW_DIR/<cadena>/<fecha>/respuestas_<corrida>.jsonl.gz` y manifiesto por corrida (`core/storage.py`).
- `RAW_DIR/imagenes/` para fotos (`core/imagen.py:AlmacenImagenes`).
- `data/publicar/data.json` (staging), `data/snapshots/` (histórico), eventos CSV, Parquet (esquema en `docs/ESQUEMA_DATOS.md`).
- `web/data.json`: espejo de lo último publicado; artefacto generado, no se edita a mano (`CLAUDE.md` del repo).

## 7. Despliegue

- Hoy: tarea diaria 02:00 en un PC Windows con la sesión iniciada; sin sesión o con el PC apagado esa corrida no se hace (`scripts/instalar_tarea_windows.ps1`). Sin CI en el repo.
- Publicación: manual, `publicar` escrito a mano; credenciales `PUBLISH_*` solo por entorno (`pipeline/publish.py:destino_desde_entorno`). Los comentarios de `publish.py` y `docs/PUBLICAR.md` nombran Hostinger como destino, por eso se dibuja "Hosting estático (Hostinger)".
- Por confirmar: ruta final en el hosting (la ficha de la Landing habla de subdominio propio; el `CLAUDE.md` del repo y `URL_PUBLICA_DEFAULT` apuntan a una subcarpeta). No se dibuja una ruta concreta.
- Por confirmar: destino exacto de rclone (se lee del entorno; el ejemplo de `.env.example` apunta a un Drive, se dibuja como "almacén en la nube").
- Al escalar (propuesta, no es código): mover la corrida a una máquina siempre encendida y añadir CI. Marcado como propuesta en la página.
- `web-v2` no está en `main`: no se dibuja. `docs/DECISIONES.md` menciona una UI v2 en otra rama.

## 8. Historias de usuario

No aplica: herramienta de portafolio sin requisitos de terceros.

## 9. Decisiones (de `docs/DECISIONES.md` y del código; parafraseadas)

1. Grabar el crudo antes de parsear y producir la salida siempre desde el crudo (`pipeline/run.py`, docstring).
2. Staging separado de lo servido: la corrida nunca escribe `web/data.json`; publicar es manual (`pipeline/publish.py`).
3. Negarse a publicar si desaparece más del 20 % (`verificar_umbral`).
4. Validar antes de exportar: respuestas 401/403 o un snapshot sin filas de la cadena base abortan sin pisar el histórico (`pipeline/run.py:validar`).
5. `rclone copy`, nunca sync: no borra en destino (`sincronizar`).
6. Un falso positivo es peor que un guion: reglas duras, marca exigida en la zona gris, reparto uno a uno por fuerza de evidencia (DECISIONES 1 a 5).
7. Web estática sin build y cálculo en el cliente: cero costo variable (`PUBLICAR.md`).
8. CSP `default-src 'self'` y script del tutorial en archivo aparte (DECISIONES 15).
9. Datos públicos de catálogo, delays por dominio y backoff ante 429/503 (`core/adapter_base.py`).

## Privacidad

- `docs/seed/` y `docs/handoffs/` no se leyeron ni se citan.
- No se imprime ningún valor de llave; solo los nombres de variables de entorno aparecen como concepto, no en la página.
- El historial público del repo contiene hallazgos ya anotados en `docs/PUBLICAR.md` (no se repiten aquí).
