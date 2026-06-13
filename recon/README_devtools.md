# Fase 0 — Guía de Reconocimiento con DevTools

Objetivo: encontrar los **endpoints JSON reales** que consume el frontend de cada
cadena y volcarlos a `farmacias.yaml`. **No avanzamos a la Fase 1 hasta tener los
endpoints confirmados.**

El script `recon/inspect_site.py` tantea la página de resultados y guarda la
respuesta cruda en `data/raw/recon/<fecha>/`, pero los SPA (Inkafarma, Mifarma)
cargan los datos por XHR/fetch: ahí entra DevTools.

---

## 0. Setup

```bash
py -m pip install httpx pyyaml
```

Probar el script (guarda crudo + detecta WAF, sin parsear nada):

```bash
py recon/inspect_site.py --from-yaml boticasperu --query paracetamol
py recon/inspect_site.py --dominio https://inkafarma.pe --query paracetamol
# inspeccionar un endpoint exacto que ya capturaste:
py recon/inspect_site.py --url "https://www.boticasperu.pe/.../Search-ShowAjax?q=paracetamol" -q paracetamol
```

Cada corrida deja un `.<ext>` (crudo) y un `.meta.json` (status, content-type,
tamaño, headers, robots, señales de WAF) en `data/raw/recon/<fecha>/`.

---

## 1. Cómo capturar un endpoint (procedimiento general)

1. Abre el sitio en Chrome/Edge. Pulsa **F12** → pestaña **Network**.
2. Marca **Preserve log** y filtra por **Fetch/XHR** (botón en la barra de Network).
3. Borra la lista (🚫) y **realiza la acción**: escribe el término en el buscador,
   abre un producto, navega una categoría.
4. Observa las peticiones que aparecen. Busca las que devuelven **JSON** con
   nombres/precios (en *Preview* o *Response* se ve la estructura).
5. Sobre la petición correcta → clic derecho:
   - **Copy → Copy as cURL** (trae URL + método + headers + cookies completos), y/o
   - **Copy → Copy link address** (solo la URL).
6. Anota: **URL exacta**, **método** (GET/POST), **query params**, **headers
   necesarios** (cookie de sesión, `csrf-token`/`x-*`, `authorization`, `apikey`),
   y la **forma del JSON** (qué campo es nombre, precio, stock, ean, imagen).
7. Pega lo capturado en `farmacias.yaml` (ver sección 5).

> Pista para distinguir el endpoint bueno: en el filtro de Network escribe parte
> del término buscado (p. ej. `paracetamol`) o una palabra como `search`,
> `product`, `catalog`, `query`. La petición útil suele responder `application/json`
> y pesar bastante.

---

## 2. Boticas Perú — `boticasperu.pe` (Salesforce Commerce Cloud / SFRA)

Plataforma estándar y documentada. Los pipelines tienen nombres predecibles.

**Qué disparar y qué buscar en Network (Fetch/XHR):**

| Acción en la web | Endpoint esperado (SFRA) | Para qué |
|---|---|---|
| Buscar "paracetamol" | `Search-Show` / `Search-ShowAjax?q=...` | grilla: nombre, precio, listPrice, badges, imagen, id, url |
| Abrir un producto | `Product-Show` / `Product-ShowQuickView?pid=...` | precio regular vs venta, disponibilidad/stock, variantes, EAN/UPC, marca |
| Navegar una categoría | `Search-Show?cgid=<categoria>` | recorrer TODO el catálogo por categoría |
| Aplicar filtro (marca, etc.) | params `prefn1`/`prefv1` | facetas/refinamientos |

**Campos a mapear del JSON/HTML** → `price`, `listPrice` (descuento real),
`badges`/`promotions`, `availability`/`inStock`/`ats` (quiebre de stock),
`productId`/`ean` (llave de matching), `brand`/`manufacturerName`.

> SFRA a veces devuelve **HTML** (no JSON) en `Search-Show`. Si es así, sube el
> `nivel` del YAML a `B` y captura el HTML; el `Product-ShowQuickView` suele dar
> fragmentos más limpios. Si encuentras un endpoint `*-ShowAjax` que responde
> JSON, déjalo como `nivel: A`.

---

## 3. Inkafarma — `inkafarma.pe` (SPA + Contentful)

SPA: el HTML inicial casi no trae datos; todo llega por XHR/fetch a una API interna.

**Qué disparar:** buscar "paracetamol" y abrir un producto, observando Fetch/XHR.

**Qué buscar:**
- Peticiones a un host de API (puede ser un subdominio tipo `api.*`,
  `*.inretail.pe`, o un gateway) que respondan `application/json`.
- Endpoints con palabras como `search`, `products`, `catalog`, `pricing`.
- Revisa si la petición lleva **headers de API**: `apikey`, `authorization: Bearer ...`,
  `x-api-key`, `ocp-apim-subscription-key` (típico de Azure API Management).
- Contentful suele verse como peticiones a `cdn.contentful.com` (contenido
  editorial/imágenes); el **precio y stock** probablemente vengan de OTRO endpoint
  (el de comercio), no de Contentful. Captura ambos si aplica.

**Anota especialmente** los headers de auth: sin ellos el request directo dará 401/403.

---

## 4. Mifarma — `mifarma.com.pe` (SPA, grupo InRetail)

Mifarma e Inkafarma son del **mismo holding (InRetail)** → muy probablemente
comparten backend/API.

**Primero verifica reutilización:** repite la captura del paso 1 buscando un
producto. Compara el host y la forma del JSON con lo capturado en Inkafarma:
- Si el **host de API y los campos coinciden** → reutiliza el adaptador de Inkafarma
  (anótalo en `api_busqueda` y deja una nota `reutiliza: inkafarma`).
- Si difieren → captúralo como endpoint propio.

---

## 5. Dónde pegar lo capturado en `farmacias.yaml`

Para cada farmacia, reemplaza los `TODO`:

```yaml
  - id: boticasperu
    busqueda_url: "https://www.boticasperu.pe/.../Search-ShowAjax?q={query}"   # <- URL real
    producto_url: "https://www.boticasperu.pe/.../Product-ShowQuickView?pid={pid}"
    categoria_url: "https://www.boticasperu.pe/.../Search-Show?cgid={categoria}"
    metodo: "GET"
    headers_extra:            # solo los que el endpoint EXIGE (cookie, csrf, apikey...)
      x-ejemplo: "valor"
    campos_json:              # ruta/clave del campo dentro del JSON de respuesta
      id: "productId"
      nombre: "productName"
      precio: "price.sales.value"
      precio_regular: "price.list.value"
      promo_badge: "promotions[0].calloutMsg"
      stock: "availability.inStock"
      ean: "ean"
      imagen: "images.large[0].url"
```

Convención: usa `{query}`, `{pid}`, `{categoria}` como placeholders en las URLs;
el motor de la Fase 1 los sustituirá. En `campos_json` usa notación con puntos
para campos anidados y `[i]` para índices de lista.

---

## 6. Fallback Playwright (Nivel C) — cuándo y cómo

Si un request directo con `httpx` da **403 / 429 / challenge** (el script lo marca
como `WAF/Cloudflare: SÍ` y `probable challenge`), el adaptador caerá a Playwright,
que pasa por un navegador real y obtiene cookies/headers válidos.

Preparar el entorno (se usará en la Fase 1, no ahora):

```bash
py -m pip install playwright
py -m playwright install chromium
```

Idea del fallback (a implementar en Fase 1): abrir la página con Chromium headless,
dejar que resuelva el challenge y cargue los XHR, e **interceptar la respuesta JSON**
(`page.on("response", ...)`) en vez de re-parsear el DOM. Así reaprovechamos el mismo
endpoint capturado aquí, pero con sesión válida.

**Siempre:** respetar `robots.txt`, delays aleatorios 2–6s y cachear el crudo. Esto
es monitoreo de precios públicos, no intrusión.

---

## 7. Checklist de salida de la Fase 0

- [ ] `boticasperu`: `busqueda_url`, `producto_url`, `categoria_url` + `campos_json` reales.
- [ ] `inkafarma`: `api_busqueda` (con headers de auth) + `campos_json`.
- [ ] `mifarma`: confirmado si reutiliza Inkafarma o endpoint propio.
- [ ] Sin `TODO` en las 3 cadenas principales del `farmacias.yaml`.
- [ ] Crudos guardados en `data/raw/recon/<fecha>/` como evidencia.

Cuando esto esté ✅, recién pasamos a la **Fase 1** (adaptadores + motor genérico).
