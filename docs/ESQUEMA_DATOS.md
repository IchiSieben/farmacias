# Esquema de datos — Radar de Precios v2 (F1)

Tres capas: **RAW** (lo que respondieron los sitios, tal cual), **PROCESSED** (Parquet
tipado) y **WEB** (JSON para la página). Todo instante va en **UTC**.

## 1. RAW — `RAW_DIR` (local, default `data/raw/`; archivado en Drive con `rclone copy` a `RCLONE_REMOTE`)

```
RAW_DIR/
  <cadena>/<YYYY-MM-DD>/respuestas_<corrida>.jsonl.gz
  _corridas/<corrida>/manifest.json
  _corridas/<corrida>/previo.json.gz
```

- `<corrida>` = instante UTC de arranque, `2026-09-24T08-30-00Z`. La fecha de la
  partición es la de la corrida (UTC).
- `<cadena>` ∈ `inkafarma`, `mifarma`, `boticasperu`, `universal`.

### `respuestas_<corrida>.jsonl.gz` — una línea por request HTTP, en orden

| Campo | Tipo | Nota |
|---|---|---|
| `k` | str | sha1 de método + ruta + query ordenada + cuerpo JSON canónico. **Sin host ni headers.** |
| `t` | str ISO-8601 UTC | momento de la respuesta |
| `metodo`, `url` | str | `url` sin query |
| `query` | `[[k, v], ...]` | ordenada; nunca incluye parámetros de API key |
| `body` | str \| null | cuerpo de la request, JSON canónico |
| `status` | int | HTTP status (ausente si hubo `error`) |
| `headers` | obj | solo `content-type` y `location` |
| `cuerpo` | str | cuerpo de la respuesta, ya decodificado (gzip/br) a texto |
| `error` | `{tipo, mensaje}` | error de red (timeout, conexión); se reproduce igual |

Las llaves Algolia viajan en headers y **nunca** se escriben. Una misma `k` puede
aparecer varias veces (reintentos 429→200): se reproduce en el mismo orden.

### `manifest.json`

| Campo | Contenido |
|---|---|
| `corrida`, `inicio`, `fin` | id y marcas UTC |
| `estado` | `en_curso` (captura cortada → `--reanudar`) · `completa` |
| `args` | `objetivo`, `semillas`, `delay` con que se capturó (el reproceso usa los mismos) |
| `generado` | sello del snapshot; el reproceso lo reutiliza (salida byte a byte igual) |
| `previo` | `generado` del snapshot contra el que se calculan ▲▼ |
| `archivos` | cadena → nombre del `.jsonl.gz` |
| `requests` | por cadena: `red`, `cache`, `http_error`, `red_error`, `faltantes` |

`previo.json.gz` es la copia del snapshot anterior, congelada al empezar la captura:
el reproceso da las mismas flechas en cualquier máquina.

## 2. PROCESSED — `PROCESSED_DIR` (default `data/processed/`)

```
history/<YYYY-MM-DD>/ofertas.parquet   eventos.parquet
latest/ofertas.parquet                 eventos.parquet
```

Compresión zstd. Metadatos del esquema: `esquema`, `version` (hoy `1`). Una corrida
por día: si hay dos, la última gana. Reprocesar una fecha vieja no pisa `latest/`.

### `ofertas` — una fila por (producto_id, cadena) con precio

| Columna | Tipo Arrow | Nota |
|---|---|---|
| `corrida` | string | id de corrida |
| `capturado_en` | timestamp[ms, UTC] | = `generado` del snapshot |
| `producto_id` | string | `<objectID InRetail>:<pack\|fraccion>` (id de fila v1) |
| `nombre`, `categoria`, `marca`, `presentacion` | string | del producto ancla (Inkafarma) |
| `cantidad` | double | unidades del envase |
| `unidad` | string | `un`, `ml`, `g`… |
| `cadena`, `grupo` | string | `grupo`: `inretail`, `boticasperu`, `universal` |
| `precio` | double | S/ en esa cadena |
| `precio_unidad` | double \| null | S/ por unidad |
| `en_promocion` | bool | |
| `url` | string \| null | ficha en la tienda |
| `es_mas_barato` | bool | false también en empate |
| `brecha_pct` | double \| null | brecha max/min del producto (≥ 2 cadenas) |
| `n_cadenas` | int8 | cadenas con precio para ese producto |
| `tendencia` | string \| null | `sube`, `baja`, `igual`, `nuevo` vs. la corrida previa |
| `precio_anterior` | double \| null | |

### `eventos` — cambios contra la corrida previa

| Columna | Tipo Arrow | Nota |
|---|---|---|
| `corrida`, `capturado_en` | string, timestamp[ms, UTC] | |
| `tipo_evento` | string | `nuevo`, `sube_precio`, `baja_precio`, `inicia_promo`, `fin_promo` |
| `producto_id`, `producto` | string | |
| `cadena` | string \| null | null en `nuevo` (evento a nivel producto) |
| `valor_anterior`, `valor_nuevo` | string \| null | precio como texto, o `sí`/`no` en promos |
| `delta_pct` | double \| null | solo en cambios de precio |

**Fuera de F1:** `fichas` y `matches` (con `evidencia`) se definen en F3, cuando exista
el matcher multi-señal.

## 3. WEB — `data.json` (contrato v1, sin cambios de formato)

La corrida lo escribe en staging (`data/publicar/data.json`); `pipeline.publish` lo sube
al hosting con confirmación y deja `web/data.json` como espejo de lo publicado. Lo
consume `web/app.js` hasta que F4 lo reemplace por `web/data/`
particionado. Además se guarda una copia por corrida en
`data/snapshots/snapshot_<generado>.json` y los eventos en
`data/processed/eventos_<fecha>.csv` (formato ANEXO §C).
