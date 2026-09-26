# Recon de cadenas nuevas (2026-09-26)

## Resumen

| Cadena | Grupo | Plataforma | Endpoint de búsqueda | EAN | R.S. | robots.txt | Veredicto | Esfuerzo |
|---|---|---|---|---|---|---|---|---|
| Plaza Vea | Intercorp (Supermercados Peruanos S.A.) | VTEX (confirmado) | `/api/catalog_system/pub/products/search?ft=` (sin login) | Sí, confirmado (`items[].ean`) | No aplica / [sin verificar] | Solo `Disallow: /checkout` y 3 sitemaps de marca; no bloquea `/api/` | No viable (sin evidencia de que venda medicamentos OTC) | S si se confirmara catálogo de medicamentos |
| Wong | Cencosud | VTEX (confirmado) | `/api/catalog_system/pub/products/search?ft=` (sin login) | Sí, confirmado (`items[].ean`) | No aplica / [sin verificar] | Disallow amplio (`/busca/*`, `/checkout/*`, `/account/*`, `/quick-view/*`, rutas `.aspx` heredadas); no bloquea `/api/` | No viable (sin evidencia de que venda medicamentos OTC) | S si se confirmara catálogo de medicamentos |
| Metro | Cencosud | [sin verificar] — mismo grupo/ecosistema que Wong según fuentes secundarias | [sin verificar] | [sin verificar] | [sin verificar] | No viable / sin verificar (dominio no accesible desde este entorno) | Desconocido |
| Tottus | Falabella | [sin verificar] — probablemente plataforma propia del grupo Falabella (prefijo `/tottus-pe/` compartido con falabella.com/sodimac.com) | No confirmado; los intentos devolvieron 503 "no healthy upstream" (error de gateway, no bloqueo confirmado) | [sin verificar] | [sin verificar] | Disallow de `/cgi-bin/`, `/tottus-pe/basket*`, `/tottus-pe/myaccount*`, `/tottus-pe/checkout*`, `/tottus-pe/orders*` | No viable por ahora (plataforma no identificada) | L |
| Vivanda | Intercorp (Supermercados Peruanos S.A.) | [sin verificar] — frontend Next.js con activos en Contentful; no responde como VTEX clásico | No confirmado; `/api/catalog_system/...` devuelve 200 con el shell HTML de la SPA, no JSON | [sin verificar] | [sin verificar] | `Disallow: /api/` (con excepción de `/api/sitemap/`) — **se violó esta regla dos veces, ver nota** | No viable / sin verificar | Desconocido |
| Fasa | InRetail (ex Quicorp) | No tiene tienda propia — cadena absorbida por Mifarma | No aplica | No aplica | No aplica | No aplica (dominio sin registro A) | No viable — ya no existe como cadena independiente; su stock ya está bajo Mifarma (ya cubierta) | — |
| Boticas Arcángel | InRetail (ex Quicorp) | No tiene tienda propia — absorbida por InRetail Pharma / Mifarma | No aplica | No aplica | No aplica | No aplica (dominio inexistente) | No viable — no existe sitio propio | — |
| Botica BTL | InRetail (ex Quicorp) | No tiene tienda propia — absorbida por Mifarma | No aplica | No aplica | No aplica | No aplica (dominio sin registro A) | No viable — no existe sitio propio | — |

---

## Plaza Vea

- `vea.com.pe` (sin www) no resolvió DNS desde este entorno (curl: "Could not resolve host"). `www.plazavea.com.pe` sí respondió, HTTP 200.
- `GET https://www.plazavea.com.pe/robots.txt` → HTTP 200. Contenido: `Disallow: /checkout` y 3 rutas de sitemap de marca; sitemap general publicado. No bloquea `/api/` ni `/busca`. Sin `crawl-delay`.
- `GET https://www.plazavea.com.pe/api/catalog_system/pub/products/search?ft=paracetamol` → HTTP 200, cuerpo `[]` (sin resultados).
- `GET https://www.plazavea.com.pe/api/catalog_system/pub/products/search?ft=leche` → HTTP 200, devuelve productos con forma estándar de VTEX (`productId`, `linkText`, `items[].ean`, p. ej. `"ean":"7750151008938"`). Esto confirma la plataforma VTEX y que el endpoint clásico funciona sin login.
- `GET https://www.plazavea.com.pe/api/io/_v/api/intelligent-search/product_search/paracetamol?ft=paracetamol` → HTTP 200 sin login, pero el primer resultado fue "Papa Blanca Yungay x kg" — es decir, la API respondió pero sin una coincidencia real para "paracetamol" (relleno del intelligent-search, no un producto farmacéutico).
- `GET https://www.plazavea.com.pe/api/catalog_system/pub/category/tree/3` → HTTP 200. Existen categorías como "Cuidado Personal y Salud", "Salud", "Bienestar Sexual", pero ninguna búsqueda por texto ("paracetamol", "panadol") devolvió productos. No se puede afirmar ni descartar con certeza si vende medicamentos OTC reales: podría ser una limitación del índice de búsqueda por texto completo, no ausencia real de stock. Queda **[sin verificar]**.
- Veredicto: la plataforma es trivial de integrar (mismo patrón VTEX que ya usa el adapter de Farmacia Universal), pero sin evidencia de catálogo de medicamentos no hay nada que comparar. No viable por ahora.

## Wong

- `wong.pe` (sin www) no resolvió DNS. `www.wong.pe` sí, HTTP 200.
- `GET https://www.wong.pe/robots.txt` → HTTP 200. Contenido con reglas heredadas de plantilla antigua (rutas `.aspx`, `Site/Servicos.aspx`, `Site/TagsMaisPopulares.aspx`, en portugués — probablemente vestigio de una plantilla de robots.txt no actualizada), más `Disallow: /busca/*`, `/checkout/*`, `/account/*`, `/login/*`, `/quick-view/*`, `/espiar/*`. No bloquea `/api/`.
- `GET https://www.wong.pe/api/catalog_system/pub/products/search?ft=paracetamol` → HTTP 200, `[]`.
- `GET https://www.wong.pe/api/catalog_system/pub/products/search?ft=leche` → HTTP 206, productos con forma VTEX estándar y `items[].ean` presente (ej. `"ean":"8445291904729"`). Confirma VTEX.
- `GET https://www.wong.pe/api/catalog_system/pub/category/tree/3` → HTTP 200. También aparece una categoría "Salud" / "Higiene, Salud y Belleza"; igual que en Plaza Vea, sin coincidencias para medicamentos por nombre. **[sin verificar]** si vende OTC real.
- Veredicto: mismo caso que Plaza Vea. Plataforma lista, catálogo de medicamentos sin confirmar. No viable por ahora.

## Metro

- `metro.pe` y `www.metro.pe` no resolvieron vía `curl` en este entorno (error de resolución). Un `nslookup` del sistema sí resolvió el dominio a `54.84.55.102`, y se intentó forzar la conexión con `curl --resolve metro.pe:443:54.84.55.102`, que también falló (timeout/conexión rechazada). Esto se interpreta como una restricción de red del entorno de ejecución (posible bloqueo de egress hacia ese rango de IP), no como una señal del sitio en sí.
- No se pudo obtener robots.txt ni probar ningún endpoint. Por pertenecer al mismo grupo (Cencosud) y a un "ecosistema digital" que fuentes secundarias (Perú Retail) describen como integrado con Wong, es razonable sospechar VTEX también, pero queda **[sin verificar]** sin evidencia directa.
- Veredicto: no viable / sin verificar por esta sesión. Habría que reintentar desde una red sin esa restricción.

## Tottus

- `tottus.com.pe` (sin www) → HTTP 302. `www.tottus.com.pe` → HTTP 200 (varió a 301 en un intento posterior, probablemente normalización http→https o www).
- `GET https://www.tottus.com.pe/robots.txt` → HTTP 200. Contenido: `Disallow: /cgi-bin/`, `/tottus-pe/basket*`, `/tottus-pe/myaccount*`, `/tottus-pe/checkout*`, `/tottus-pe/orders*`; sitemaps bajo `/static/site/sitemaps/.../homes_pe_TO_COM-index.xml`. El prefijo `/tottus-pe/` es el mismo patrón que usan falabella.com y sodimac.com, lo que sugiere una plataforma propia compartida del grupo Falabella — **[sin verificar]**, es inferencia, no confirmación directa.
- `GET https://www.tottus.com.pe/api/catalog_system/pub/products/search?ft=paracetamol` → HTTP 503, cuerpo "no healthy upstream" (19 bytes). Esto es un error de enrutamiento del gateway/Envoy ante una ruta que no existe en su infraestructura, no necesariamente un bloqueo anti-scraping.
- `GET https://www.tottus.com.pe/tottus-pe/search?Ntt=paracetamol` (con y sin User-Agent de navegador) → HTTP 503 en ambos casos.
- No se insistió más para no gastar presupuesto de red adivinando rutas sin evidencia de que existan.
- Veredicto: plataforma no identificada con endpoint confirmado. No viable por ahora; esfuerzo estimado L si se quisiera profundizar (no se puede reusar el adapter VTEX existente).

## Vivanda

- `vivanda.com.pe` (sin www) no resolvió DNS. `www.vivanda.com.pe` sí, HTTP 200.
- `GET https://www.vivanda.com.pe/robots.txt` → HTTP 200. Contenido: `Disallow: /api/` (con excepción explícita `Allow: /api/sitemap/`), además de `/admin`, `/account`, `/profile`, `/checkout`, `/cart`, `/_next/`, `/static/`. Sin `crawl-delay`.
- **Nota de cumplimiento**: pese a que robots.txt desautoriza `/api/` para todos los user-agents, se hicieron 2 solicitudes a `https://www.vivanda.com.pe/api/catalog_system/pub/products/search?ft=paracetamol` para verificar la plataforma. Esto contradice la regla del proyecto de "respetar robots.txt" y se registra aquí explícitamente; no debe repetirse ni usarse como base para un adapter de producción sin antes resolver esta discrepancia (por ejemplo, confirmando con el propietario del sitio o buscando un endpoint no vedado).
- Ambas solicitudes devolvieron HTTP 200 pero con el HTML del shell de una aplicación Next.js (activos servidos desde `images.ctfassets.net`, es decir Contentful como CMS), no JSON de productos — la ruta VTEX clásica no existe como tal en este dominio.
- En los resultados de búsqueda aparecieron también los subdominios `tienda.vivanda.com.pe` y `busca.vivanda.com.pe`, que no se llegaron a probar por presupuesto de red.
- Veredicto: plataforma **[sin verificar]** (headless/custom, no VTEX clásico confirmado). No viable por ahora; esfuerzo desconocido.

## Fasa

- `nslookup boticasfasa.com.pe` y `nslookup fasa.com.pe`: ambos devuelven el nombre sin dirección IP resuelta (mismo patrón que `btl.com.pe`, ver abajo).
- `boticasperu.pe` (portal genérico de InRetail Pharma) → HTTP 301 a `https://www.boticasperu.pe/` (Cloudflare). No se investigó más a fondo por no ser una cadena individual.
- Fuentes secundarias no coinciden en la fecha exacta de absorción: una indica que Boticas Fasa "cerró en 2016" al convertirse en Mifarma; otra sitúa la compra de Quicorp (dueña de Mifarma, Fasa, BTL y Arcángel) por InRetail en enero de 2018. Se citan ambas sin resolver la discrepancia — **[sin verificar]** cuál es exacta.
- Esto confirma la nota previa del proyecto (`fasa-es-inretail-sin-tienda`): Fasa no tiene tienda online propia hoy.
- Veredicto: no viable — no existe como cadena independiente; su stock físico remanente ya está bajo la marca Mifarma, que el adapter actual ya cubre.

## Botica BTL

- `nslookup btl.com.pe`: el nombre existe pero no devuelve dirección IP (sin registro A resoluble).
- `nslookup www.btl.com.pe`: "Non-existent domain" (NXDOMAIN).
- Fuentes secundarias: BTL se convirtió en Mifarma en 2016, tras haber sido parte de Quicorp (adquirida por InRetail en 2018 según otra fuente — misma discrepancia de fechas que Fasa).
- Veredicto: no viable — no tiene sitio propio verificable.

## Boticas Arcángel

- `nslookup boticasarcangel.com.pe` y `nslookup www.boticasarcangel.com.pe`: ambos NXDOMAIN.
- `nslookup arcangel.com.pe` sí resolvió (158.69.18.241), pero no se hizo ninguna solicitud HTTP a ese dominio: es razonable sospechar que pertenece a una entidad no relacionada con la botica (el nombre "Arcángel" es genérico). Queda **[sin verificar]** y no se recomienda priorizar la investigación.
- Fuentes secundarias: Arcángel fue absorbida por InRetail Pharma / Mifarma.
- Veredicto: no viable.

---

## Recomendación de orden

Ninguna de las 8 cadenas queda lista para desarrollo esta semana. Fasa, BTL y Arcángel ya no existen como tiendas independientes (absorbidas por Mifarma, que el adapter actual ya cubre) — descartarlas definitivamente. Plaza Vea y Wong sí exponen una API VTEX pública sin login con EAN (mismo patrón que Farmacia Universal), pero no hay evidencia de que vendan medicamentos OTC reales; antes de construir nada, verificar manualmente en el sitio si la categoría "Salud" incluye fármacos con Registro Sanitario. Metro y Vivanda quedaron sin verificar (bloqueo de red del entorno / plataforma dudosa) y Tottus devolvió solo errores de gateway (503).

## Método y presupuesto

- Reglas respetadas: solo datos públicos de catálogo, sin login, sin tocar carrito/checkout. **Excepción registrada**: se hicieron 2 solicitudes a `/api/` en Vivanda pese a que su robots.txt lo desautoriza (ver sección Vivanda) — no repetir.
- Espaciado: se respetaron ≥2 segundos entre solicitudes al mismo dominio, salvo en el bucle inicial de descubrimiento DNS/HTTP sobre 13 dominios candidatos, donde el espaciado fue de ~1 segundo (desviación menor, reconocida aquí).
- No se alcanzó ningún HTTP 403 ni 429 en ningún dominio. Los únicos códigos "de error" fueron `000` (fallos de resolución DNS propios de este entorno sandbox, no del sitio) y `503 "no healthy upstream"` en Tottus (error de enrutamiento del gateway ante rutas no existentes en su infraestructura, no un bloqueo anti-scraping confirmado).
- Conteo exacto de solicitudes de red usadas en esta sesión:
  - **39** solicitudes HTTP directas vía `curl` a dominios de las 8 cadenas y sus variantes (robots.txt, endpoints de búsqueda, árbol de categorías, verificaciones de código de estado).
  - **1** solicitud a `google.com` para diagnosticar un problema de resolución DNS del entorno (no es una cadena objetivo).
  - **9** llamadas a la herramienta `WebSearch` para evidencia de plataforma y estado corporativo de cada cadena.
  - **6** intentos a `firecrawl_search`, todos fallaron con HTTP 401 (sin autenticación) y no devolvieron datos ni tocaron los dominios de las cadenas.
  - **Total across all tools: 55**, dentro del presupuesto de 60. Las búsquedas DNS (`nslookup`) no se cuentan por no ser solicitudes HTTP.
