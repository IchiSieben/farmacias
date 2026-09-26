# Esquema de datos — Radar de Precios v2 (F1 + F3)

Tres capas: **RAW** (lo que respondieron los sitios, tal cual), **PROCESSED** (Parquet
tipado) y **WEB** (JSON para la página). Todo instante va en **UTC**.

## 1. RAW — `RAW_DIR` (local, default `data/raw/`; archivado en Drive con `rclone copy` a `RCLONE_REMOTE`)

```
RAW_DIR/
  <cadena>/<YYYY-MM-DD>/respuestas_<corrida>.jsonl.gz
  boticasperu/<YYYY-MM-DD>/quickview_<corrida>.jsonl.gz   # F3, complemento opcional
  _corridas/<corrida>/manifest.json
  _corridas/<corrida>/previo.json.gz
  imagenes/indice.jsonl                                   # F3, una línea por URL de foto
  imagenes/<aa>/<sha1(url)>                               # la foto tal cual se bajó
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

F3 suma al manifiesto: `complementos` (`boticasperu_quickview` → nombre del
`quickview_<corrida>.jsonl.gz`), `enriquecimiento` (QuickView pedidos/con R.S./sin dato,
fotos de caché/red/error) y, si se corrió `--completar`, la lista `completado` con
lo que se bajó después y cuándo.

### `quickview_<corrida>.jsonl.gz` (F3) — mismo formato que `respuestas_*`

El registro sanitario de Boticas solo está en el QuickView (uno por pid), no en el
grid de búsqueda. Se pide para los candidatos que pasan cantidad y precio con texto
≥ 60. Es **opcional**: al reprocesar, un pid que no está es "sin R.S.", no un error.

### `imagenes/indice.jsonl` (F3)

| Campo | Tipo | Nota |
|---|---|---|
| `url` | str | URL de la foto (llave) |
| `t` | str ISO-8601 UTC | cuándo se bajó |
| `phash`, `dhash` | str hex (64 bits) | ausentes si hubo `error` |
| `tam` | `[ancho, alto]` | |
| `archivo` | str | `<aa>/<sha1(url)>` dentro de `imagenes/` |
| `error` | str | red, HTTP o imagen ilegible; no se reintenta en cada corrida |

Sin red (`--desde-cache`), una URL fuera del índice es "sin dato": el matcher no
decide por imagen.

## 2. PROCESSED — `PROCESSED_DIR` (default `data/processed/`)

```
history/<YYYY-MM-DD>/ofertas.parquet   eventos.parquet   matches.parquet
latest/ofertas.parquet                 eventos.parquet   matches.parquet
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

### `matches` (F3) — una fila por cruce (producto_id, cadena, tipo)

La referencia es la presentación de Inkafarma. Mifarma entra como `id` (mismo objectID
InRetail); Boticas y Universal con la evidencia del matcher. Qué cuenta como "el mismo
producto": `docs/MATCHING.md`.

| Columna | Tipo Arrow | Nota |
|---|---|---|
| `corrida`, `capturado_en` | string, timestamp[ms, UTC] | |
| `producto_id`, `cadena` | string | |
| `tipo` | string | `match` (precio de la fila) · `equivalente` (mismo activo, concentración, forma y cantidad con otro R.S.; NO se muestra como match) |
| `sku_cadena` | string | id del producto en esa cadena |
| `metodo` | string | `id`, `ean`, `registro_sanitario`, `fuzzy`, `imagen`, `curado` (`tests/matches_curados.yaml`), `equivalente` |
| `score` | double | 0–100 |
| `revisar` | bool | zona gris 70–85 sin confirmación por imagen |
| `motivo` | string | frase legible de la decisión |
| `rs_ref`, `rs_cadena` | string \| null | R.S. normalizado `LETRAS-DIGITOS` |
| `cantidad_ref`, `cantidad_cadena`, `unidad` | double, double, string | |
| `cantidad_fuente_ref`, `cantidad_fuente_cadena` | string | `atributo` (campo de la API) · `descripcion` · `nombre` |
| `texto_score` | double \| null | score por texto (núcleo + nombre) |
| `imagen_veredicto` | string \| null | `identica`, `intermedia`, `distinta`; null = sin foto |
| `imagen_dist_phash`, `imagen_dist_dhash` | int16 \| null | Hamming sobre 64 bits |
| `ratio_precio` | double \| null | precio de la cadena / precio de Inkafarma |
| `precio`, `url` | double, string \| null | solo en `equivalente`: el match ya los tiene en `ofertas` |
| `evidencia` | string (JSON) | el mismo objeto que `data.json` |

`fichas` no se persiste todavía: la ficha se arma en memoria en cada corrida
(`core/ficha.py`) y lo que decide queda en `evidencia`.

## 3. WEB — `data.json` (contrato v1 + `evidencia` desde F3)

Cada producto suma `evidencia`: cadena (`boticasperu`, `universal`) → `{sku, metodo,
score, revisar, motivo, ratio_precio, rs, rs_fuente, cantidad, unidad,
cantidad_fuente, texto?, imagen?}`. Los pares `[a, b]` son `[Inkafarma, cadena]`.
Es la fuente del panel "¿Por qué se emparejó?" (F4). Clave nueva: `web/app.js` la ignora.

Y `equivalentes`: cadena → el mismo objeto más `nombre`, `precio`, `url`, con
`metodo: "equivalente"`. No entra en `precios` ni en el ahorro: es la semilla de
"alternativas con el mismo principio activo" (docs/MATCHING.md §5).

La corrida lo escribe en staging (`data/publicar/data.json`); `pipeline.publish` lo sube
al hosting con confirmación y deja `web/data.json` como espejo de lo publicado. Lo
consume `web/app.js` hasta que F4 lo reemplace por `web/data/`
particionado. Además se guarda una copia por corrida en
`data/snapshots/snapshot_<generado>.json` y los eventos en
`data/processed/eventos_<fecha>.csv` (formato ANEXO §C).
