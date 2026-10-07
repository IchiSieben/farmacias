# Ficha para el Landing — `radar-precios`

Contenido exacto para `Landing/src/content/projects/es/radar-precios.md` y
`Landing/src/content/projects/en/radar-precios.md`. Lo importa la sesión del Landing; esta
sesión no editó el Landing. Escrito el 2026-10-07 contra el esquema de
`Landing/src/content/config.ts` (todas las `skills` existen en `src/content/skills/`).

**Condición:** las cifras de `results` son del snapshot del 2026-10-06 que ya está en
`web/data.json` de la rama `publicar/2026-10-07`. El sitio en vivo sigue mostrando el de junio
hasta que el owner suba ese `data.json` (ver `docs/PUBLICAR.md`). Si la ficha se importa antes,
usar las cifras de junio: 296 / 100 / 42 (las 4 cadenas; la ficha actual dice 64 "en las tres",
que en realidad es el número con precio de Universal).

Qué cambia frente a la ficha actual: "tres cadenas" → cuatro; cifras con fecha; `next` sin lo
que ya está hecho (historial, corrida automática, cuarta cadena); `techLine` y `applied` al
matcher v2; `skills` + `parquet`; `date` y `standards` al día. `media` se mantiene (renovar los
archivos: `docs/CAPTURAS.md`).

## `es/radar-precios.md`

```markdown
---
title: "Radar de Precios"
segment: "mercado-comparadores"
tech: ["scraping", "data-viz", "etl-bases-de-datos"]
sector: ["salud", "retail-negocio"]
order: 4
featured: true
status: "live"
geo:
  place: "Perú"
  at: [[-9.19, -75.02]]
summary: "Compara el precio del mismo medicamento en cuatro cadenas de farmacias peruanas. Resuelve el problema difícil: decidir sin catálogo compartido que dos listados distintos son el mismo producto, y preferir un hueco antes que un cruce falso."
repoUrl: "https://github.com/IchiSieben/farmacias"
demoUrl: "https://ichisieben.dev/radar-precios/"
localPath: "/radar-precios/"
tier: "B"
maturity: "usable"
oneLine: "Emparejo 296 medicamentos entre cuatro cadenas de farmacias peruanas leyendo sus propias APIs de catálogo, cada noche."
techLine: "Adaptadores en Python · Algolia, Salesforce CC y VTEX · matcher por capas con registro sanitario · Parquet · web estática"
media:
  kind: video
  poster: /media/radar-precios/poster.webp
  posterMobile: /media/radar-precios/poster-mobile.webp
  video:
    mp4: /media/radar-precios/preview.mp4
skills:
  - "python"
  - "scraping"
  - "matching"
  - "beautifulsoup"
  - "parquet"
  - "javascript"
applied:
  python: "Un adaptador por cadena sobre una base común con caché del crudo, delays y back-off; la corrida nocturna es un comando."
  scraping: "Endpoints públicos de catálogo de tres plataformas (Algolia, Salesforce Commerce Cloud, VTEX), leídos como los llama la propia tienda."
  matching: "Capas de costo creciente: curados, ID compartido o EAN, registro sanitario DIGEMID, texto con reglas duras y foto; asignación uno a uno con evidencia por par."
  beautifulsoup: "selectolax para la grilla HTML de la cadena que no expone una API de búsqueda."
  parquet: "Cada corrida deja ofertas, eventos de precio y cruces en Parquet, archivados en Drive con rclone."
  javascript: "La comparativa es HTML plano: carga el JSON y arma la tabla en el cliente, sin build y con CSP estricta."
date: "2026-10-07"
since: 2026
problem: "El mismo medicamento puede costar bastante más en una cadena de farmacias peruana que en otra, y dos de las cuatro cadenas comparadas son del mismo grupo. Las tiendas no comparten códigos de producto, así que comparar exige decidir primero qué listados son el mismo producto."
results:
  - { label: "productos con precio en 2 o más cadenas (snapshot 2026-10-06)", value: 296, source: "web/data.json" }
  - { label: "con precio en las cuatro cadenas", value: 37, source: "web/data.json" }
  - { label: "pares de regresión del matcher en verde", value: 85, source: "tests/test_matcher_regresion.py" }
  - { label: "errores de red en la corrida nocturna (1 354 peticiones)", value: 0, source: "docs/PUBLICAR.md" }
next:
  - "Publicar la interfaz v2 (Astro, bilingüe, historial por producto, panorama y metodología), hoy en revisión en el PR #4."
  - "Cobertura por categoría completa en vez de canasta (F2), empezando por analgésicos."
  - "\"Arma tu botiquín\": total por cadena y la combinación más barata, en el cliente."
standards:
  quality: "No se corrió un checklist formal de ISO/IEC 25010. El riesgo más duro, los cruces falsos, se ataca con un matcher por capas, vetos duros, guarda de precio > 3× y una regresión de 85 pares curados que se corre en cada cambio."
  webVitals: "CLS 0,004 en móvil (Playwright, 2026-10-07). Performance de Lighthouse sin medir con validez: la CPU de la máquina estaba al 100 % por procesos ajenos."
  a11y: "Lighthouse móvil 100 en accesibilidad, 100 en buenas prácticas y 100 en SEO (v1, 2026-10-07)."
  fair4rs: "n/a — no es software de investigación"
  security: "Solo llaves públicas de solo búsqueda de las propias cadenas, leídas de .env (no están en el árbol; commits de junio de 2026 sí las tuvieron). Demo estático con CSP default-src 'self'; gitleaks sin hallazgos en el árbol versionado."
  reproducibility: "requirements.txt; .env.example completo; el crudo se cachea y el reproceso sin red da el mismo data.json byte a byte (verificado el 2026-10-07). Smoke de Playwright del demo en subcarpeta."
  benchmark: "sin benchmark externo; la regresión curada es la referencia interna"
  dataMl: "n/a"
  versioning: "Sin SemVer; ramas por frente (F1–F4) con PR; CITATION.cff 1.0.0."
---

Adaptadores por cadena sobre los endpoints públicos de catálogo de tres plataformas (Algolia,
Salesforce Commerce Cloud y VTEX) y un matcher por capas que decide, sin catálogo compartido,
cuándo dos listados son el mismo medicamento.

Inkafarma y Mifarma son del mismo grupo y comparten un ID interno de producto, así que cruzan
gratis. Farmacia Universal expone el EAN. Boticas Perú no expone ninguno de los dos: su adaptador
combina la grilla HTML con el JSON de vista rápida de la propia tienda, de donde sale el registro
sanitario DIGEMID. Ninguna es una API oficial; cada corrida pide lo mismo que pide la tienda desde
el navegador, una petición a la vez, con 2 a 6 segundos entre peticiones.

El matcher prefiere un "—" antes que un cruce falso. Primero los pares curados a mano, luego el ID
o el EAN, luego el registro sanitario, luego texto con reglas duras (principio activo,
concentración, cantidad, etapa, laboratorio) y, en la zona gris, la foto. Cada cruce guarda su
evidencia y la asignación es uno a uno. Cuando el matcher se endureció, las filas con las cuatro
cadenas bajaron de 54 a 42 sobre la misma corrida: menos cobertura, a cambio de no mostrar
ahorros que no existen.

Cada noche la corrida guarda el crudo, lo procesa a JSON y Parquet y lo archiva en Drive. Como el
crudo queda cacheado, cualquier corrida se puede reprocesar sin red y da el mismo resultado byte a
byte. El sitio publicado es HTML/CSS/JS estático sin build, que lee un JSON y arma la tabla en el
cliente: no cuesta nada de hosting y funciona en cualquier subcarpeta.
```

## `en/radar-precios.md`

```markdown
---
title: "Radar de Precios"
segment: "mercado-comparadores"
tech: ["scraping", "data-viz", "etl-bases-de-datos"]
sector: ["salud", "retail-negocio"]
order: 4
featured: true
status: "live"
geo:
  place: "Peru"
  at: [[-9.19, -75.02]]
summary: "Compares the price of the same medicine across four Peruvian pharmacy chains. It solves the hard part: deciding, with no shared catalog, that two different listings are the same product, and leaving a gap rather than showing a false match."
repoUrl: "https://github.com/IchiSieben/farmacias"
demoUrl: "https://ichisieben.dev/radar-precios/"
localPath: "/radar-precios/"
tier: "B"
maturity: "usable"
oneLine: "Every night I match 296 medicines across four Peruvian pharmacy chains by reading their own catalog APIs."
techLine: "Python adapters · Algolia, Salesforce CC and VTEX · layered matcher with sanitary registry · Parquet · static web"
media:
  kind: video
  poster: /media/radar-precios/poster.webp
  posterMobile: /media/radar-precios/poster-mobile.webp
  video:
    mp4: /media/radar-precios/preview.mp4
skills:
  - "python"
  - "scraping"
  - "matching"
  - "beautifulsoup"
  - "parquet"
  - "javascript"
applied:
  python: "One adapter per chain on a shared base with a raw cache, delays and back-off; the nightly run is a single command."
  scraping: "Public catalog endpoints on three platforms (Algolia, Salesforce Commerce Cloud, VTEX), called the same way each store calls them."
  matching: "Layers of rising cost: curated pairs, shared ID or EAN, Peru's sanitary registry number, text under hard rules, then photos; one-to-one assignment with evidence per pair."
  beautifulsoup: "selectolax for the HTML grid of the one chain that exposes no search API."
  parquet: "Every run leaves offers, price events and matches in Parquet, archived to Drive with rclone."
  javascript: "The comparison view is plain HTML: it loads the JSON and builds the table client-side, with no build step and a strict CSP."
date: "2026-10-07"
since: 2026
problem: "The same medicine can cost noticeably more at one Peruvian pharmacy chain than at another, and two of the four chains compared belong to the same group. The stores share no product codes, so comparing them first means deciding which listings are the same product."
results:
  - { label: "products priced in 2 or more chains (snapshot 2026-10-06)", value: 296, source: "web/data.json" }
  - { label: "priced in all four chains", value: 37, source: "web/data.json" }
  - { label: "matcher regression pairs passing", value: 85, source: "tests/test_matcher_regresion.py" }
  - { label: "network errors in the nightly run (1,354 requests)", value: 0, source: "docs/PUBLICAR.md" }
next:
  - "Ship the v2 interface (Astro, bilingual, per-product history, market overview and methodology), now in review in PR #4."
  - "Full-category coverage instead of a basket (F2), starting with painkillers."
  - "\"Build your medicine cabinet\": per-chain totals and the cheapest split, computed in the browser."
standards:
  quality: "No formal ISO/IEC 25010 checklist was run. The hardest quality risk, false matches, is handled by a layered matcher, hard vetoes, a > 3× price guard and an 85-pair curated regression run on every change."
  webVitals: "Mobile CLS 0.004 (Playwright, 2026-10-07). Lighthouse performance not validly measured: the machine's CPU was pinned at 100 % by unrelated processes."
  a11y: "Mobile Lighthouse: 100 accessibility, 100 best practices, 100 SEO (v1, 2026-10-07)."
  fair4rs: "n/a — not research software"
  security: "Only the chains' own public search-only keys, read from .env (not in the tree; June 2026 commits did contain them). Static demo under a default-src 'self' CSP; gitleaks finds nothing in the tracked tree."
  reproducibility: "requirements.txt; complete .env.example; raw responses are cached and an offline replay yields a byte-identical data.json (verified 2026-10-07). Playwright smoke test of the demo under a subfolder."
  benchmark: "no external benchmark; the curated regression is the internal reference"
  dataMl: "n/a"
  versioning: "No SemVer; one branch and PR per workstream (F1–F4); CITATION.cff 1.0.0."
---

Per-chain adapters over the public catalog endpoints of three platforms (Algolia, Salesforce
Commerce Cloud and VTEX), and a layered matcher that decides, with no shared catalog, when two
listings are the same medicine.

Inkafarma and Mifarma belong to the same group and share an internal product ID, so they match
for free. Farmacia Universal exposes the EAN barcode. Boticas Perú exposes neither: its adapter
combines the HTML grid with the store's own quick-view JSON, which carries the DIGEMID sanitary
registry number. None of these is an official API; each run asks for what the store itself asks
for from the browser, one request at a time, two to six seconds apart.

The matcher would rather show "—" than a false match. Curated pairs come first, then the ID or
EAN, then the registry number, then text under hard rules (active ingredient, strength, pack
size, stage, manufacturer) and, in the grey zone, the photo. Every match keeps its evidence and
the assignment is one-to-one. When the matcher was tightened, rows priced in all four chains fell
from 54 to 42 on the same recorded run: less coverage, in exchange for not showing savings that
don't exist.

Each night the run stores the raw responses, turns them into JSON and Parquet and archives them
to Drive. Because the raw data is cached, any run can be replayed offline with a byte-identical
result. The published site is static HTML/CSS/JS with no build step: it reads one JSON file and
builds the table in the browser, costs nothing to host and works in any subfolder.
```
