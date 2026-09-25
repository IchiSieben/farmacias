# Radar de Precios · Pharmacy Price Radar (Peru)

[Español](#español) · [English](#english)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Static site](https://img.shields.io/badge/frontend-static%2C%20no%20server-informational)
![Status](https://img.shields.io/badge/status-live%20·%20v2%20in%20progress-brightgreen)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

**Live:** [ichisieben.dev/radar-precios](https://ichisieben.dev/radar-precios/)

![Comparison table preview](docs/poster.webp)

---

## English

### The one-line pitch

The same box of paracetamol, from the same lab, costs 20–70 % more in one Peruvian
pharmacy chain than in the one across the street — and two of the four chains belong
to the same holding. Radar de Precios collects public catalog prices every run,
decides when two listings are the *same* product, and publishes a comparison anyone
can search.

### Why it is not a trivial scraper

Pulling prices is the easy part. The hard part is **matching**: chains name the same
product differently ("Paracetamol 500mg Tableta x 100" vs "Paracetamol 500 mg caja
100"), hide the pack size in a separate attribute, and reuse the same photo for the
box of 100 and the blister of 10. A wrong match is worse than a missing one, so the
matcher is built as layers of increasing cost with hard guards at each step:

1. **Hard identifiers** — a shared internal ID (Inkafarma ↔ Mifarma), EAN/GTIN where
   a storefront exposes it, and (v2) the Peruvian sanitary-registry code.
2. **Structured rules** — active ingredient, concentration, dosage form, pack size,
   pediatric vs adult, vitamin letter, gummy vs tablet… any mismatch is a veto,
   however similar the names look.
3. **Fuzzy text** on the normalized core (ingredient + brand), weighted above the
   full name.
4. **Perceptual image hashing** to confirm doubtful pairs (v2: for every candidate,
   also as a veto).
5. **A curated golden set** of confirmed and rejected pairs that overrides everything
   and grows with every review session (`tests/`).

### What it covers today (v1)

| Chain | Platform | How we read it | Cross-chain key |
|---|---|---|---|
| Inkafarma | Algolia (InRetail) | public search-only client key | shared `objectID` with Mifarma |
| Mifarma | Algolia (InRetail) | public search-only client key | shared `objectID` with Inkafarma |
| Boticas Perú | Salesforce Commerce Cloud | HTML grid + QuickView JSON | name + specs (+ sanitary registry in v2) |
| Farmacia Universal | VTEX | public catalog API | EAN-13 when real, else name + specs |

Scope: medicines, supplements and dermocosmetics — categories where active ingredient
+ concentration + presentation identify a product. Cosmetics and personal care are
deliberately out (no active ingredient to disambiguate near-identical SKUs).

Current snapshot: 296 products priced in ≥ 2 chains, 64 in all four; one snapshot per
run so price moves (▲▼) and promotions are detected by diffing runs, not by trusting
promo labels.

### What v2 is doing (see `V2_PLAN.md`)

Full category coverage instead of a hand-picked basket; raw dumps archived to Google
Drive and processed to Parquet; a multi-signal matcher that reads structured
attributes and sanitary-registry codes and hashes every product image; and a redesigned
bilingual UI with per-product price history and a chain-positioning dashboard.

### Run it

Verified on Windows, Python 3.12.

```bash
py -m pip install -r requirements.txt
cp .env.example .env            # fill in the Algolia search keys (see below)
PYTHONIOENCODING=utf-8 py -m tests.test_matcher_regresion    # matcher regression, must be all OK
py -m pipeline.build_snapshot --objetivo 150 --salida web/data.json
py -m http.server -d web 8000   # http://localhost:8000
```

The `.env` keys are the public, search-only Algolia keys each chain ships in its own
storefront JavaScript. They are not secrets, but they rotate; when search returns 403,
re-capture them from DevTools → Network → `*.algolia.net`.

`web/` is plain HTML/CSS/JS with no build step: every path is relative, so the folder
drops into any static host unchanged.

### Data, ethics and affiliation

Prices are read from each chain's own public storefront endpoints, at low frequency
(once per run) with randomized delays and back-off, never behind a login. Prices belong
to their chains; this is an independent comparison exercise, not affiliated with
Inkafarma, Mifarma, Boticas Perú or Farmacia Universal. The engine is domain-agnostic:
a new vertical (veterinary, hardware, groceries) is a new adapter config, not new code.

### Author

Yoichi Palacios Tanaka (IchiSieben) · [ichisieben.dev](https://ichisieben.dev) ·
Apache 2.0 · Cite with `CITATION.cff`.

---

## Español

### El pitch en una línea

La misma caja de paracetamol, del mismo laboratorio, cuesta 20–70 % más en una cadena
de farmacias peruana que en la de enfrente — y dos de las cuatro cadenas son del mismo
holding. Radar de Precios captura precios públicos de catálogo en cada corrida, decide
cuándo dos listados son *el mismo* producto y publica una comparación que cualquiera
puede buscar.

### Por qué no es un scraper más

Sacar precios es la parte fácil. Lo difícil es el **emparejamiento**: las cadenas
nombran distinto al mismo producto ("Paracetamol 500mg Tableta x 100" vs "Paracetamol
500 mg caja 100"), esconden la cantidad en otro atributo y reusan la misma foto para
la caja de 100 y el blíster de 10. Un cruce equivocado es peor que un "—", así que el
matcher está armado por capas de costo creciente, con vetos duros en cada paso:

1. **Identificadores duros** — ID interno compartido (Inkafarma ↔ Mifarma), EAN/GTIN
   donde la tienda lo expone y (v2) el registro sanitario DIGEMID.
2. **Reglas estructuradas** — principio activo, concentración, forma farmacéutica,
   cantidad, pediátrico vs adulto, letra de vitamina, gomita vs tableta… cualquier
   desacuerdo veta el cruce por más que los nombres se parezcan.
3. **Fuzzy de texto** sobre el núcleo normalizado (activo + marca), con más peso que
   el nombre completo.
4. **Hash perceptual de imagen** para confirmar pares dudosos (v2: en todo candidato,
   también como veto).
5. **Set curado** de pares confirmados y rechazados que manda sobre todo lo demás y
   crece con cada sesión de revisión (`tests/`).

### Qué cubre hoy (v1)

| Cadena | Plataforma | Cómo se lee | Llave entre cadenas |
|---|---|---|---|
| Inkafarma | Algolia (InRetail) | llave pública de solo búsqueda | `objectID` compartido con Mifarma |
| Mifarma | Algolia (InRetail) | llave pública de solo búsqueda | `objectID` compartido con Inkafarma |
| Boticas Perú | Salesforce Commerce Cloud | grilla HTML + QuickView JSON | nombre + specs (+ registro sanitario en v2) |
| Farmacia Universal | VTEX | API pública de catálogo | EAN-13 cuando es real; si no, nombre + specs |

Alcance: medicamentos, suplementos y dermocosmética — categorías donde principio
activo + concentración + presentación identifican un producto. Cosmética y cuidado
personal quedan fuera a propósito (sin principio activo no hay cómo distinguir SKUs
casi idénticos).

Snapshot actual: 296 productos con precio en ≥ 2 cadenas, 64 en las cuatro; un
snapshot por corrida, así que subidas/bajadas (▲▼) y promociones se detectan
comparando corridas, no confiando en la etiqueta de promo.

### Qué está haciendo la v2 (ver `V2_PLAN.md`)

Cobertura por categoría completa en vez de canasta elegida a mano; crudo archivado en
Google Drive y procesado a Parquet; matcher multi-señal que lee atributos
estructurados y registro sanitario y hashea todas las imágenes; y una interfaz
rediseñada, bilingüe, con historial de precio por producto y panorama de
posicionamiento por cadena.

### Cómo correrlo

Verificado en Windows, Python 3.12.

```bash
py -m pip install -r requirements.txt
cp .env.example .env            # completar las llaves Algolia (ver abajo)
PYTHONIOENCODING=utf-8 py -m tests.test_matcher_regresion    # regresión del matcher, todo OK
py -m pipeline.build_snapshot --objetivo 150 --salida web/data.json
py -m http.server -d web 8000   # http://localhost:8000
```

Las llaves del `.env` son las públicas de solo búsqueda que cada cadena embebe en su
propio JavaScript. No son secretas, pero rotan; cuando la búsqueda devuelva 403, hay
que recapturarlas desde DevTools → Network → `*.algolia.net`.

`web/` es HTML/CSS/JS plano sin build: todas las rutas son relativas, así que la
carpeta funciona en cualquier hosting estático sin cambios.

### Datos, ética y afiliación

Los precios se leen de los endpoints públicos de cada cadena, a baja frecuencia (una
vez por corrida), con delays aleatorios y back-off, nunca detrás de un login. Los
precios pertenecen a sus cadenas; este es un ejercicio de comparación independiente,
sin afiliación con Inkafarma, Mifarma, Boticas Perú ni Farmacia Universal. El motor es
agnóstico al rubro: un vertical nuevo (veterinarias, ferreterías, abarrotes) es una
configuración de adaptador nueva, no código nuevo.

### Autor

Yoichi Palacios Tanaka (IchiSieben) · [ichisieben.dev](https://ichisieben.dev) ·
Apache 2.0 · Citar con `CITATION.cff`.

---

*Documentos de trabajo: `V2_PLAN.md` (plan vigente), `CLAUDE.md` (contexto para
Claude Code), `SPEC_comparador_farmacias.md` y `ANEXO_matching_api_historico.md`
(diseño original v1), `ROADMAP_expansion_farmacias.md` (expansión a más cadenas).*
