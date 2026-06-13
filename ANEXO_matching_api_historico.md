# ANEXO TÉCNICO — Matching, Explotación de API y Tracking Histórico

> Complemento del SPEC principal. Responde 3 decisiones de diseño clave:
> (1) cómo saber que dos productos son el mismo, (2) qué datos "ocultos" sacar
> de los APIs, (3) cómo guardar histórico gratis en Google Sheets.

---

## A. MATCHING DE PRODUCTOS — "¿es el mismo producto?"

Estrategia en **3 capas combinadas**, de la más barata/confiable a la más cara.
Cada par de candidatos recibe un **score 0–100**; arriba de un umbral = match.

### Capa 1 — Identificador duro (la mejor, si existe)
- **EAN / código de barras / SKU del fabricante.** Si el API lo expone (muchos SFCC/VTEX
  lo traen como `ean`, `gtin`, `upc` o `manufacturerSKU`), el match es 1:1 garantizado.
- **Primer paso del scraper: buscar siempre estos campos.** Si están, el problema se acabó
  para esos productos. Score = 100, sin ambigüedad.

### Capa 2 — Nombre + specs normalizados (tu idea de distancia)
Correcta. Se normaliza y se compara con distancia de strings.
- Extraer estructuradamente: `principio_activo` + `concentración` (500mg) +
  `forma` (tableta/jarabe/cápsula) + `cantidad` (x100) + `marca/laboratorio`.
- Normalizar: minúsculas, sin tildes, unidades unificadas (mg, ml), sinónimos
  (tab=tableta=comprimido; cap=cápsula).
- Comparar con **rapidfuzz** (token_sort_ratio) sobre la cadena normalizada.
- Reglas duras además del fuzzy: si concentración o cantidad NO coinciden → NO es match,
  aunque el nombre se parezca (250mg ≠ 500mg es un producto distinto). Esto evita
  falsos positivos peligrosos.

### Capa 3 — Imagen (tu otra idea — sí es posible y barata)
Muchas cadenas usan **la misma foto del proveedor**. Dos vías:
- **Rápida y gratis (hash perceptual):** `imagehash` (pHash/dHash). Se calcula un hash
  de cada imagen; imágenes iguales o casi iguales dan hashes con distancia de Hamming ~0.
  Detecta fotos idénticas o reescaladas. Cuesta milisegundos, no usa IA.
- **Robusta (embeddings):** si las fotos difieren (ángulos, watermark), usar embeddings
  de visión (CLIP local) y comparar por similitud coseno. Más caro; solo para los
  casos que la Capa 2 deja dudosos.

### Score final (ponderado)
```
si hay EAN coincidente              -> match (100), fin.
si no:
   score = 0.55 * sim_nombre_specs
         + 0.30 * sim_imagen
         + 0.15 * sim_marca
   con reglas duras: concentracion y cantidad DEBEN coincidir.
match si score >= 85 ; "revisar a mano" si 70–85 ; descartar < 70.
```

> **Para la demo:** arrancar con una canasta de ~30–50 productos ancla de alta rotación,
> emparejados/validados a mano UNA vez. Eso da una demo impecable sin pelear con los
> 10,000 SKUs del catálogo el primer día. El matcher automático crece esa base después.

---

## B. EXPLOTACIÓN DEL API — "¿qué datos ocultos podemos sacar?"

Boticas Perú corre sobre **Salesforce Commerce Cloud (Demandware/SFRA)**. Esto es muy
bueno: la estructura de URLs y respuestas es ESTÁNDAR y documentada. Lo que el frontend
consume, nosotros lo replicamos.

### Endpoints típicos de SFRA a probar (en DevTools → Network, filtrar Fetch/XHR):
- **Búsqueda (grid de productos):** pipeline `Search-Show` / `Search-ShowAjax`.
  Devuelve la grilla con nombre, precio, precio de lista, badges de promo, imagen, URL, id.
- **Detalle de producto:** `Product-Show` / `Product-ShowQuickView` con `pid`.
  Suele traer MÁS de lo visible: precio regular vs. precio de venta, disponibilidad/stock,
  variantes, EAN/UPC, marca, categoría completa, a veces inventario por tienda.
- **Categoría:** `Search-Show?cgid=<categoria>` → recorrer TODO el catálogo por categoría,
  no solo lo que buscas. Así se construye el universo completo de SKUs.
- **Refinamientos/facetas:** los parámetros `prefn1/prefv1` exponen filtros (marca, etc.).

### Datos valiosos que el SFCC suele exponer y la gente no mira:
- **`price` vs `listPrice`** → permite detectar **descuento real** (no solo el que anuncian).
- **`badges` / `promotions`** → campañas activas (2x1, Día del Padre, %).
- **`availability` / `inStock` / `ats`** → señal de **quiebre de stock** del competidor
  (¡oportunidad comercial enorme: si Inkafarma quebró stock de un producto, Boticas Perú
  sube precio o promociona ese SKU!).
- **`productId` / `ean`** → llave de matching (Capa 1).
- **`brand`, `manufacturerName`** → segmentación.
- **Fecha de alta / orden de catálogo** → a veces permite inferir **productos nuevos**.

### Detección de eventos (lo que vende el dashboard) — se deriva COMPARANDO snapshots:
No vienen "listos" en el API; se calculan entre corrida de hoy vs. ayer:
- **Producto nuevo:** SKU presente hoy, ausente en snapshots previos.
- **Cambio de precio:** mismo SKU, `price` distinto → ↑ o ↓ y cuánto (%).
- **Inicio/fin de promoción:** aparición/desaparición de badge o `listPrice != price`.
- **Quiebre/retorno de stock:** `inStock` cambia de true↔false.
- **Campaña detectada:** varios SKUs de una categoría bajan a la vez en la misma fecha.

> Por eso el **histórico es obligatorio**: sin snapshots no hay detección de cambios.
> Ver sección C.

### Reconocimiento (primer trabajo de Claude Code, en tu máquina, no en sandbox):
1. Abrir boticasperu.pe, DevTools → Network → Fetch/XHR.
2. Buscar "paracetamol", abrir un producto, navegar una categoría.
3. Anotar: URL exacta de cada request, método, parámetros, headers necesarios
   (cookie de sesión, csrf token si hay), y la forma del JSON/HTML de respuesta.
4. Volcar esos endpoints al `config/farmacias.yaml`.
5. Repetir para Inkafarma (Contentful + su API) y Mifarma.

> NOTA sobre defensas: es posible que haya Cloudflare/WAF (el catálogo es público, así que
> es accesible, pero puede pedir headers/cookies realistas). Si un request directo da 403,
> el adaptador cae a Playwright (Nivel C) que pasa por el navegador real. Respetar siempre
> delays y robots.txt; esto es monitoreo de precios públicos, no intrusión.

---

## C. TRACKING HISTÓRICO GRATIS — Google Sheets como base de datos

Idea correcta y muy vendible (estilo "CamelCamelCamel de farmacias"). Diseño gratis:

### Flujo
```
GitHub Actions (cron diario)
   -> corre el scraper
   -> normaliza + detecta cambios vs. último snapshot
   -> escribe filas nuevas en Google Sheets (append, nunca sobrescribe)
   -> Sheets queda como base histórica viva y compartible
```

### Cómo escribir a Sheets gratis
- **Google Sheets API** con una **Service Account** (gratis): se crea en Google Cloud,
  se comparte la hoja con el email de la service account, y se escribe con `gspread`.
- Las credenciales (JSON) van como **secret** en GitHub Actions (no en el repo).
- `gspread` permite `append_row` / `append_rows` → ideal para snapshots incrementales.

### Estructura de la hoja (2 pestañas)
**Pestaña `snapshots` (histórico crudo, append-only):**
```
fecha | cadena | match_id | nombre_origen | precio | precio_regular |
en_promo | etiqueta_promo | stock | url | ean
```
**Pestaña `eventos` (cambios detectados, lo interesante):**
```
fecha | tipo_evento | cadena | producto | valor_anterior | valor_nuevo | delta_%
```
(tipo_evento ∈ {nuevo, baja_precio, sube_precio, inicia_promo, fin_promo, quiebre_stock})

### Por qué Sheets y no SQL (por ahora)
- Gratis, cero infraestructura, compartible por link, el cliente lo VE en vivo.
- Se conecta directo a **Looker Studio** (gratis) para dashboards bonitos sin código.
- Migrable a SQLite/BigQuery cuando el volumen crezca. Empezar simple.

> Límite a vigilar: Sheets aguanta ~10M celdas / 5M filas por libro. Para una canasta
> de cientos de productos × corrida diaria, da para años. Cuando apriete, rotar a Parquet/BigQuery.

### Visualización histórica (el gráfico tipo Amazon/Camel)
- Por cada `match_id`: línea de `precio` en el tiempo, una serie por cadena.
- Permite ver: "Inkafarma bajó este SKU 15% el martes" → gatillo para contraofertar.
- En el dashboard: selector de producto → gráfico multi-cadena + tabla de eventos recientes.

---

## D. Resumen de lo que esto le dice al cliente (Boticas Perú)

Con A+B+C, el dashboard puede afirmar cosas como:
- "Hoy estás más caro que Inkafarma en 23 de 50 productos clave (brecha promedio 8%)."
- "Mifarma lanzó promo Día del Padre en 12 SKUs ayer; tú no tienes respuesta en 9 de ellos."
- "Inkafarma quebró stock de [producto X]: oportunidad para captar demanda."
- "El precio de [producto Y] en la competencia subió 10% esta semana; puedes seguirlo."

Eso es exactamente lo que justifica contratar a alguien que "sabe hacer estas cosas".
