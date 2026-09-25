# Radar de Precios v2 — Plan de trabajo

> Documento de diseño para la segunda versión. Lo ejecuta Claude Code por fases;
> cada fase termina en un PR mergeable con sus controles en verde.
> Lo que está marcado **[verificar]** es una hipótesis razonable, no un hecho
> comprobado en el sitio: se confirma con recon antes de construir encima.

**English TL;DR.** v1 is live (4 chains, 296 matched products, static page). v2 has
four workstreams, in order: (1) a proper data lake — local raw cache archived to Google Drive via rclone,
processed Parquet, small JSON for the web; (2) real coverage by category instead of
hand-picked search terms; (3) a multi-signal matcher (structured attributes, Peruvian
sanitary-registry codes, image hashing for every candidate pair, a curated golden set);
(4) a redesigned bilingual ES/EN UI with per-product price history. Each workstream is
one branch/PR with acceptance criteria listed below.

---

## 0. Diagnóstico honesto de la v1

Lo que está bien y se conserva:

- El patrón adaptador + motor genérico funciona. Cuatro plataformas distintas (Algolia,
  SFCC, VTEX) entran por la misma interfaz `search() -> List[Producto]`.
- Las reglas duras del matcher (concentración, cantidad, forma, pediátrico, vitamina,
  gomita) son la razón de que no haya falsos positivos visibles. Eso no se afloja.
- Snapshots por corrida + `cambios.py` ya dan historial; solo falta mostrarlo.

Lo que limita:

| Problema | Consecuencia | Frente v2 |
|---|---|---|
| La canasta sale de `TERMINOS` (términos escritos a mano) | 296 productos es una muestra, no cobertura. Un cliente pregunta "¿y omeprazol 40?" y no está | F2 |
| El crudo va a `data/raw/<fecha>/` en disco local y `.gitignore` | No hay histórico reproducible; una corrida cortada pierde todo | F1 |
| El matcher lee casi todo del **nombre** (`extrae_specs(nombre_origen)`) | Cuando la cantidad/concentración vive en `presentation`, en un atributo o en la ficha, el nombre no la trae y el match falla o cae a zona gris | F3 |
| pHash solo en zona gris 70–85 | La imagen podría **subir** matches de 60–70 y **vetar** falsos de 85+ con foto claramente distinta; hoy no se usa para eso | F3 |
| Sin llave dura fuera de InRetail salvo EAN de Universal | Boticas expone **registro sanitario** (`healthRegistrationNumber`) y no lo usamos como llave | F3 |
| `web/` vanilla sin build, una sola tabla, solo español | Se ve "de prototipo"; sin ficha por producto, sin historial, sin URL compartible, sin EN | F4 |
| Corrida manual | Los ▲▼ dependen de que alguien corra el script | F1 |

---

## 1. Arquitectura v2

```
                 ┌──────────────── corrida (local, Task Scheduler) ────────────────┐
                 │                                                                 │
 adapters ──► http_cache ──► RAW local (RAW_DIR, default data/raw/)                 │
 (consultas;    graba antes   <cadena>/<fecha>/respuestas_<corrida>.jsonl.gz        │
  F2: browse)   de parsear    _corridas/<corrida>/manifest.json                     │
                                     │                                             │
                                     ▼  (reproducido SIN red)                       │
                              parse/normalize + matcher ──► PROCESSED (Parquet)     │
                                     │                      data/processed/         │
                                     ▼                      ofertas · eventos       │
                              export: data/publicar/data.json (staging)             │
                                     │                                             │
                                     ▼                                             │
                              sincronizar: rclone copy ──► Gdrive: (archivo) ───────┘
                                     ·
                                     · (manual, con resumen y confirmación)
                                     ▼
                              publish (FTPS/SFTP Hostinger)
```

Decisiones:

- **RAW: caché local + archivo en Google Drive vía rclone** *(enmendado 2026-09-24;
  antes: Drive para escritorio montado como carpeta — no se instala)*. El pipeline
  escribe el crudo en `RAW_DIR`, una carpeta local (default `data/raw/`); de ahí se
  reprocesa con `--desde-cache`. Al final de `--todo`, el paso `--sincronizar` hace
  `rclone copy` (nunca `sync`: no borra en Drive) a `RCLONE_REMOTE`
  (`Gdrive:03-Datasets/raw/radar-precios`) y el Parquet a `RCLONE_REMOTE_PROCESSED`.
  Corre después de escribir snapshot y Parquet: si Drive falla, la corrida ya está
  completa y el copy del día siguiente sube lo pendiente (es incremental). Realismo:
  un volcado completo de Inkafarma (~46k hits Algolia) pesa decenas de MB en JSONL,
  ~5–10 MB gzip; cuatro cadenas diarias son unos cientos de MB/mes y 5 TB dan para
  décadas. Se comprime (`.jsonl.gz`, pocos archivos por corrida) porque rclone sube
  mejor pocos archivos grandes que miles de chicos.
- **PROCESSED en Parquet, local y versionable por fecha**, con `pandas` + `pyarrow`.
  Es lo que consume el matcher y la analítica. Se mantiene un `latest/` y un
  `history/<fecha>/`. Parquet también se copia a Drive (chico), con el mismo rclone.
- **Web recibe JSON pequeño y particionado.** No un `data.json` de 300 KB que crecerá
  a 5 MB: un `index.json` (lista liviana para el buscador) + `cat_<categoria>.json`
  + `hist_<match_id>.json` bajo demanda. Hostinger compartido sirve estático sin
  problema; es el mismo modelo que hoy.
- **La corrida vive en tu PC, no en GitHub Actions.** Razones: Boticas está detrás
  de Cloudflare y responde mejor desde IP residencial; rclone ya está configurado ahí; las
  llaves Algolia rotan y es más simple en un `.env` local. Windows Task Scheduler
  lanza `py -m pipeline.run --todo` a diario. GitHub Actions queda como opción para
  InRetail-only si algún día se quiere.
- **Publicar es manual y va aparte de la corrida** *(enmendado 2026-09-24)*. La
  corrida diaria exporta a staging (`data/publicar/`), nunca a lo servido.
  `pipeline/publish.py` compara contra lo publicado (productos, cambios de precio,
  desaparecidos, tamaño), se niega si desaparece > 20 % salvo `--forzar`, pide
  confirmación escrita y sube por FTPS/SFTP con credenciales en `.env`. Alternativa
  futura: git auto-deploy de Hostinger apuntando a una rama `deploy`.

---

## 2. Fases

### F1 — Data lake y corrida automática

Objetivo: cualquier corrida deja crudo reproducible (local + archivo en Drive), procesado en Parquet, y
se puede relanzar desde el caché sin volver a pegarle al sitio.

Tareas:

1. `core/storage.py`: `RawStore(RAW_DIR)` con `write(cadena, nombre, bytes)` y
   `read_latest(cadena, patron)`; particiona por `<cadena>/<YYYY-MM-DD>/`; gzip
   transparente. `ProcessedStore` para Parquet (`latest/`, `history/<fecha>/`).
2. Los adaptadores dejan de escribir en `data/raw/` directo y pasan por `RawStore`.
   Modo `--desde-cache <fecha>` en el pipeline: reprocesa sin red.
3. `pipeline/run.py` (nuevo orquestador): `capturar` → `normalizar` → `matchear` →
   `exportar` → `publicar`, cada paso invocable solo, con log a archivo y resumen
   final (productos por cadena, matches, eventos, duración, errores).
4. Esquema Parquet documentado en `docs/ESQUEMA_DATOS.md` (ofertas, fichas, matches,
   eventos). Tipos explícitos, `capturado_en` en UTC.
5. `scripts/instalar_tarea_windows.ps1`: registra la tarea diaria (hora configurable)
   con `schtasks`. Documentar cómo verla y cómo leer el log.
6. `.env.example` gana `RAW_DIR`, `PROCESSED_DIR`, `PUBLISH_*`.

Aceptación: una corrida completa deja `RAW_DIR/<cadena>/<fecha>/` con los cuatro
crudos, `data/processed/latest/*.parquet`, y `--desde-cache` regenera `web/data/`
byte-a-byte igual sin tocar la red. `.gitignore` cubre `data/` y `.env`.

### F2 — Cobertura por categoría (datos "de verdad", no muestra)

Objetivo: pasar de 296 productos elegidos a mano a categorías completas de
medicamentos, suplementos y dermo, validadas una por una.

Lo que ya sabemos de las fuentes (de `farmacias.yaml` y `recon/`):

- **Inkafarma**: Algolia con `browse` habilitado → catálogo completo por cursor
  (~46k con `channels:WEB`). Filtrar por `category`/`subCategory` para bajar solo lo
  que entra en alcance.
- **Mifarma**: browse **bloqueado** por la key pública → volcado particionado por
  faceta `subCategory` con `/queries` (ya existe `sync_facetas`). Tope 1000 hits por
  query: si una subcategoría pasa de 1000, sub-particionar por `brand` o `laboratory`.
- **Boticas Perú**: `Search-UpdateGrid?cgid=<categoria>&start&sz` recorre una
  categoría entera **[verificar cgid reales]**; `Product-ShowQuickView?pid` da la
  ficha limpia (precio lista/venta, stock, marca, registro sanitario, imagen).
- **Farmacia Universal**: VTEX `catalog_system/pub/products/search?fq=C:<id>`
  pagina por categoría **[verificar ids de categoría]**; trae EAN y stock.

Tareas:

1. `AdapterBase.browse_categoria(cat_id)` como método opcional; implementarlo en los
   cuatro adaptadores (Inka por browse, Mifa por facetas, Boticas por cgid, Universal
   por fq).
2. Mapa de categorías cross-cadena en `config/categorias.yaml` (hay una base en
   `categorias_farmacias.xlsx` y `recon/mapa_categorias.py`): categoría canónica →
   ids en cada cadena. Alcance v2: analgésicos, antigripales, alergia, gastro,
   antibióticos/crónicos, vitaminas y suplementos, dermo. Cosmética/cuidado personal
   sigue fuera (decisión de v1, se mantiene).
3. Escalar **una categoría por sesión**: capturar → matchear → revisar muestra de 30
   matches a mano → ampliar la regresión con lo aprendido → siguiente categoría.
   `pipeline/escala_categoria.py` ya tiene la idea; adaptarlo al nuevo storage.
4. Presupuesto de red por corrida (requests por cadena) impreso al final; si una
   categoría dispara el costo, se paginan menos resultados o se baja la frecuencia.

Aceptación: ≥ 2 000 productos con precio en al menos dos cadenas, con tasa de falsos
positivos < 2 % sobre una muestra aleatoria de 100 matches revisada a mano (se guarda
la muestra revisada en `tests/muestras/<fecha>.csv`).

### F3 — Matcher v2 multi-señal

Objetivo: decidir "mismo producto" con **todas** las señales que las fuentes dan, no
solo el nombre, y que cada decisión quede explicada.

#### 3.1 `Ficha` canónica por oferta (`core/ficha.py`)

Antes de comparar, cada `Producto` se convierte en una ficha estructurada que combina
**nombre + atributos + detalle**:

```
Ficha
├── activos: [str]          # normalizados; de `activePrinciples` (InRetail), nombre, ficha
├── concentracion: str      # parseada de nombre O de atributo O de ficha (la primera que exista)
├── forma: str              # tableta/jarabe/... de nombre O de `presentation`
├── cantidad, unidad        # de `presentation` ("CAJA 100 UN"), de nombre, de atributos VTEX/SFCC
├── laboratorio, marca
├── registro_sanitario: str # DIGEMID, normalizado (ver 3.2)
├── ean: str
├── imagen_url, imagen_phash, imagen_dhash
├── fuentes: {campo: "nombre"|"atributo"|"ficha"}   # de dónde salió cada dato (trazabilidad)
└── texto_norm, nucleo      # como hoy
```

Regla: si un dato existe en un atributo estructurado, gana sobre lo que se parsea del
nombre. Esto ataca directamente el caso "la cantidad está escondida en otro lado".

Qué expone cada fuente (confirmado en `farmacias.yaml` salvo marca **[verificar]**):

| Dato | Inka/Mifa (Algolia hit + detalle REST) | Boticas (QuickView JSON) | Universal (VTEX) |
|---|---|---|---|
| Activo | `activePrinciples` | en nombre / `custom.*` **[verificar]** | `specifications` **[verificar]** |
| Presentación/cantidad | `presentation`, detalle por pack/fracción | nombre ("Caja 30") | `items[].unitMultiplier`, nombre |
| Registro sanitario | detalle REST **[verificar]** | `healthRegistrationNumber` ✔ | `specifications` **[verificar]** |
| EAN | `gtin` | — | `items[].ean` ✔ (cuando es EAN-13 real) |
| Imagen | `image` | `images.large[0]` | `items[].images` |
| Stock | detalle | `available` | `AvailableQuantity` |

#### 3.2 Llaves duras nuevas

- **Registro sanitario (R.S. DIGEMID)**: identifica producto + laboratorio + forma +
  concentración en Perú. Formato tipo `EE-01234`, `N-12345`, `EN-...`, con variantes de
  escritura (guiones, espacios, sufijos). Normalizar a `LETRAS-DIGITOS`. Si dos ofertas
  comparten R.S. y la **cantidad** coincide → match 100 (Capa 1). Si comparten R.S. pero
  la cantidad difiere → misma familia, distinta presentación (se agrupan bajo el mismo
  producto canónico, filas distintas — como hoy blíster vs caja).
- **Catálogo maestro DIGEMID** (opcional, alto valor): el Observatorio de Productos
  Farmacéuticos de DIGEMID publica el registro nacional (nombre, forma, concentración,
  laboratorio, R.S.). Si es descargable **[verificar acceso y formato]**, se usa como
  tabla canónica: cada oferta se resuelve contra el maestro y el match entre cadenas es
  transitivo (A ↔ maestro ↔ B). Esto convierte el problema de "fuzzy entre cadenas" en
  "resolver contra un catálogo oficial", que es mucho más estable. Solo si el acceso es
  público y razonable; no scrapear un portal del Estado a lo bruto.

#### 3.3 Imagen para todos, no solo zona gris

- Calcular pHash **y** dHash de la imagen de cada oferta **una vez** (en F1, al
  normalizar) y guardarlos en la ficha/Parquet. Descarga con caché en `RAW_DIR/imagenes/`
  por hash de URL. Ya no se descarga durante el match.
- En el score: `sim_imagen ∈ {1.0 idéntica (Hamming ≤ 6), 0.5 parecida (≤ 12),
  0.0 distinta, None sin dato}`.
- Uso: (a) **confirmar** candidatos 60–85 cuando la foto es idéntica; (b) **vetar**
  candidatos ≥ 85 cuando la foto es claramente distinta *y* las cantidades vienen de
  atributo (no de nombre) — porque un 85 por texto con foto distinta suele ser
  variante/envase; (c) nunca decidir solo por imagen: las cadenas reusan la foto de la
  caja de 100 para el blíster de 10.
- Metadatos de imagen: los CDN (Algolia/SFCC/VTEX) suelen despojar EXIF; no contar con
  ellos. Lo que sí sirve a veces: el **nombre de archivo** de la imagen trae el código
  del laboratorio o el SKU (`/12345-paracetamol-500.jpg`) — extraerlo como señal débil.
- Embeddings (CLIP local vía `open_clip`) **solo** como experimento en una rama aparte
  para pares que quedan en revisión manual tras todo lo anterior. No entra al pipeline
  principal hasta demostrar que reduce la cola de revisión sin sumar falsos.

#### 3.4 Score y decisión

```
Capa 1 (llave dura): mismo objectID InRetail | mismo EAN | mismo R.S. + misma cantidad  → 100
Capa 2 (reglas duras): concentración, cantidad, forma, pediátrico, vitamina, gomita,
        efervescente, activo compartido → si falla, 0 con motivo (como hoy)
Capa 3 (score):
  score = 0.45 * sim_nucleo + 0.20 * sim_nombre + 0.20 * sim_imagen* + 0.15 * sim_lab
  (* si sim_imagen es None se reparte su peso entre núcleo y nombre)
  ≥ 85 match · 70–85 revisar (con imagen idéntica: match) · < 70 no
Capa 4 (curado): tests/matches_curados.yaml manda sobre todo lo anterior
        (pares confirmados y pares vetados a mano; se acumulan sesión a sesión)
```

Cada decisión guarda `evidencia` (qué señales, valores, fuentes) en `matches.parquet`
y se muestra en la UI como "¿por qué se emparejó?".

#### 3.5 Generación de candidatos offline

Con catálogos completos en Parquet ya no se buscan candidatos con queries al sitio: se
indexa por `(activo_principal, concentracion)` y por `nucleo` (n-gramas) y se comparan
solo los bloques. `rapidfuzz.process.cdist` sobre bloques de cientos, no de miles.

Aceptación: regresión ampliada a ≥ 150 pares (los 32 actuales + los nuevos por
categoría), 100 % en verde; cola de "revisar a mano" < 5 % de los candidatos; toda
fila de `matches.parquet` tiene `evidencia` legible.

### F4 — UI v2 bilingüe

Objetivo: que se vea y se sienta como producto, no como prototipo, en móvil y
escritorio, en español e inglés.

Stack propuesto: **Astro** (salida estática, cero servidor, encaja con Hostinger
compartido y con tu stack de portafolio) + islas de Preact/React solo donde hay
interacción (buscador, tabla, gráfico) + Tailwind. i18n con rutas `/es/` y `/en/`
(Astro lo trae nativo) y detección del idioma del navegador con toggle persistente.
Si prefieres seguir sin build, la alternativa es mantener vanilla pero con un
rediseño completo; el costo es hacer i18n y rutas por producto a mano. Recomendación:
Astro.

Pantallas:

1. **Inicio / buscador**: búsqueda instantánea por nombre, activo, marca y laboratorio
   (índice liviano `index.json` en memoria; Fuse.js o similar); chips de categoría;
   filtros actuales (brecha, cadenas, posición de precio); tabla con precio, precio por
   unidad, más barato resaltado, brecha, ▲▼, promo; miniatura de producto al pasar el
   mouse; orden por columna; URL con estado (`?q=paracetamol&cat=analgesico`).
2. **Ficha de producto** (`/es/p/<match_id>`): las presentaciones agrupadas, precio por
   cadena con link a la tienda, **gráfico de historial de precios** por cadena (desde
   `hist_<match_id>.json`), eventos (subidas, bajadas, promos, quiebres de stock),
   panel "¿por qué se emparejó?" con la evidencia del matcher. Compartible.
3. **Panorama** (`/es/panorama`): KPIs por cadena — % de productos donde es la más
   barata, brecha promedio vs. el líder, promos activas, por categoría. Es la vista
   que "vende" a un cliente de retail.
4. **Metodología** (`/es/metodologia`): cómo se capturan y emparejan los datos, alcance
   y límites, fuentes, aviso de no afiliación. Texto bilingüe.

Diseño: mobile-first, tema claro/oscuro, tipografía y espaciado consistentes, tabla
que en móvil se convierte en tarjetas, estados vacíos y de carga cuidados, accesible
(foco visible, contraste, `aria`). Mantener el tutorial de apertura pero en ambos
idiomas.

Datos: `pipeline/export_web.py` genera `web/data/` particionado (índice, categorías,
historial por producto, KPIs) con `generado` y versión de esquema. El build de Astro
copia `web/data/` tal cual.

Aceptación: Lighthouse ≥ 90 en rendimiento/accesibilidad en móvil; toda cadena de
texto visible tiene ES y EN; `/en/` y `/es/` sirven el mismo dato; ficha de producto
con gráfico funcionando con ≥ 7 días de historial; despliegue en
`ichisieben.dev/radar-precios/` sin romper la URL actual.

### F5 — README y presentación (al cerrar F4)

- README bilingüe con capturas nuevas (inicio, ficha con gráfico, panorama), cifras
  reales del último snapshot, y un párrafo claro de "cómo se usaría en Perú" +
  "cómo se replica a otro rubro/país" (el motor es agnóstico).
- `docs/` con `ESQUEMA_DATOS.md`, `MATCHING.md` (reemplaza al ANEXO), `OPERACION.md`
  (correr, programar, publicar, qué hacer cuando rota una key).
- `CITATION.cff` a versión 2.0.0.

---

## 3. Orden y ritmo

F1 → F2 (una categoría) → F3 → F2 (resto de categorías, ya con matcher v2) → F4 → F5.
F1 y F4 pueden avanzar en paralelo si se trabaja en ramas separadas, porque F4 solo
depende del contrato de `web/data/` (definirlo primero en F1).

Cada fase: rama `v2/f<N>-<nombre>`, PR con checklist de aceptación, merge a `main`.
Nada se despliega a la URL pública hasta que F4 esté completa; mientras tanto la v1
sigue viva.

---

## 4. Riesgos conocidos

- **Rotación de llaves Algolia**: detectar 403 y abortar con mensaje claro; documentar
  la recaptura en `OPERACION.md`.
- **Cloudflare en Boticas**: si empieza a desafiar, bajar concurrencia a 1 y subir
  delays antes de pensar en Playwright.
- **Deriva de esquema** en cualquier cadena: validar los campos clave al inicio de
  cada corrida (smoke test de 3 productos conocidos) y fallar rápido.
- **Falsos positivos al escalar**: por eso el orden es matcher v2 antes de volcar
  todas las categorías, y por eso existe la muestra revisada a mano por categoría.
- **Términos de uso**: seguimos en monitoreo de precios públicos con carga mínima.
  Nada de esto cambia en v2; el volumen sube pero la frecuencia (1×/día) y los delays
  se mantienen.
