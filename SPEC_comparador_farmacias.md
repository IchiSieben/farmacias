# FarmaComparador Perú — Documento de Arquitectura (SPEC v1)

> Esqueleto técnico para implementación en Claude Code. NO es código productivo;
> es el diseño: estructura, enrutamiento, estrategia de scraping y modelo de datos.
> Pensado para ser **replicable** a otros rubros (veterinarias, retail, etc.).

---

## 0. Objetivo y pitch

Comparador de precios entre cadenas de farmacias peruanas — "un Trivago de farmacias".
Permite a una cadena (caso piloto: **Boticas Perú**) ver en un dashboard cómo están
sus precios vs. la competencia, qué promociones/campañas corren, y dónde está
parada o cara respecto al mercado.

**Demo objetivo:** dashboard visual con comparación de precios por producto,
detección de promociones, y KPIs de posicionamiento competitivo.

---

## 1. Universo de fuentes (farmacias objetivo)

Priorizadas por tamaño de mercado y facilidad técnica. El diseño NO codifica cada
sitio a mano: usa un sistema de **adaptadores** (ver §4) configurables por YAML.

| # | Cadena            | Dominio                  | Plataforma e-commerce (detectada)        | Estrategia primaria       | Dificultad |
|---|-------------------|--------------------------|------------------------------------------|---------------------------|------------|
| 1 | Inkafarma         | inkafarma.pe             | SPA + Contentful, APIs JSON internas     | API JSON                  | Media      |
| 2 | Mifarma           | mifarma.com.pe           | Mismo grupo que Inkafarma (Inretail)     | API JSON (probable mismo) | Media      |
| 3 | Boticas Perú      | boticasperu.pe           | Salesforce Commerce Cloud (Demandware)   | URL de búsqueda + HTML    | Baja       |
| 4 | Farmacia Universal| farmaciauniversal.com    | Por confirmar (probable VTEX)            | API JSON o HTML           | Media      |
| 5 | Boticas y Salud   | hogarysalud.com.pe       | Por confirmar                            | HTML genérico             | Media      |
| 6 | Boticas Arcángel  | boticasarcangel.com      | Por confirmar                            | HTML genérico             | Media      |
| 7 | Fasa              | fasa.com.pe              | Por confirmar                            | HTML genérico             | Media-Alta |

> **Nota Inkafarma/Mifarma:** pertenecen al mismo holding (Inretail). Muy probable que
> compartan backend de catálogo → un solo adaptador podría servir para ambas.

**Validación pendiente en implementación (primer paso de Claude Code):** para cada
dominio, abrir DevTools → Network → filtrar XHR/Fetch mientras se busca un producto,
y capturar el endpoint JSON real. Si existe API limpia, se usa esa. Si no, fallback a HTML.

---

## 2. Estrategia de scraping (el corazón)

Tres niveles, de menor a mayor costo/fragilidad. El adaptador elige automáticamente.

### Nivel A — API JSON interna (preferido)
Muchas SPA modernas (Contentful, VTEX, SFCC) exponen endpoints JSON que el propio
frontend consume. Se replican esas llamadas directamente con `httpx`/`requests`.
- **Ventaja:** rápido, estructurado, barato, robusto.
- **Cómo se descubre:** inspección de Network en DevTools (manual, una sola vez por sitio).
- Se documenta el endpoint + parámetros en el YAML del adaptador.

### Nivel B — HTML estático con detección inteligente (tu método Chasqui)
Si no hay API: se descarga el HTML completo de la página de resultados y se deja que
el extractor **detecte la estructura** (cards de producto) en vez de hardcodear selectores.
- Reutiliza tu enfoque previo: capturar HTML crudo → analizar patrones de producto.
- Detección por heurística: bloques que contienen {nombre + precio (S/) + imagen}.
- Selectores se infieren y se guardan; si el sitio cambia, se re-infieren.

### Nivel C — Navegador headless (último recurso)
Para sitios con render 100% JS o defensas anti-bot (ver §3). Usa **Playwright**
simulando comportamiento humano (delays, user-agent real, viewport, scroll).
- Solo cuando A y B fallan, porque es el más lento y caro.

```
decisión por adaptador:
  ¿hay endpoint JSON conocido?  -> Nivel A
  ¿HTML llega completo sin JS?  -> Nivel B
  si no                          -> Nivel C (Playwright)
```

---

## 3. Anti-bot — qué esperar y cómo manejarlo

Ninguna de estas farmacias necesita login para ver precios (catálogo público), lo cual
ayuda. Pero hay que respetar y mimetizar:

- **Cloudflare / rate limiting:** posible en las grandes. Mitigación: pool de user-agents
  realistas, delays aleatorios (2–6 s entre requests), respeto de `robots.txt`,
  no más de N requests concurrentes por dominio.
- **Headers realistas:** `User-Agent`, `Accept-Language: es-PE`, `Referer` correcto.
- **Sesiones con cookies:** mantener cookie jar por dominio (algunas APIs piden cookie de sesión).
- **Geolocalización:** algunos precios/stock dependen de tienda/distrito seleccionado.
  El adaptador debe poder fijar una tienda/ubicación por defecto (ej: Lima centro).
- **Backoff exponencial** ante 429/503.
- **Caché local** del HTML/JSON crudo por corrida (carpeta `data/raw/<fecha>/`) para
  no re-pegarle al sitio al depurar — esto ahorra muchísimo y es buena práctica ética.

> Regla ética/legal: solo datos públicos de catálogo, sin saturar servidores,
> identificándose con UA honesto si se desea. Esto es monitoreo de precios públicos,
> práctica estándar en retail intelligence.

---

## 4. Arquitectura de software (modular y replicable)

Patrón **adaptador + motor genérico**, para que clonar a "veterinarias" sea cambiar config, no código.

```
farmacomparador/
├── config/
│   ├── farmacias.yaml          # 1 bloque por cadena: dominio, nivel, endpoints, selectores
│   └── productos_objetivo.yaml # SKUs/keywords a monitorear (la "canasta")
├── core/
│   ├── adapter_base.py         # interfaz común: search(query) -> List[Producto]
│   ├── adapter_api.py          # Nivel A
│   ├── adapter_html.py         # Nivel B (detección inteligente)
│   ├── adapter_browser.py      # Nivel C (Playwright)
│   ├── normalizer.py           # limpia y unifica: nombre, precio, presentación, marca
│   ├── matcher.py              # empareja "el mismo producto" entre cadenas (fuzzy match)
│   └── storage.py              # guarda crudo + tabla normalizada (SQLite/Parquet)
├── pipeline/
│   ├── run_scrape.py           # orquesta: por cada farmacia, por cada producto
│   └── build_dataset.py        # consolida en tabla comparativa
├── dashboard/
│   └── app.py                  # visualización (Streamlit) o export a HTML estático
├── data/
│   ├── raw/<fecha>/            # HTML/JSON crudo cacheado
│   └── processed/comparativa.parquet
└── README.md
```

### Pieza crítica: `matcher.py` (el reto real del proyecto)
El problema difícil no es scrapear, es saber que "Paracetamol 500mg x 100 tab"
en una cadena es el MISMO producto que "Paracetamol 500 mg caja 100" en otra.
- Estrategia: normalizar (principio activo + concentración + presentación + cantidad)
  y hacer fuzzy matching (rapidfuzz) + reglas. Empezar con una canasta pequeña de
  productos de alta rotación bien identificados (código de barras / EAN si está disponible).
- Para la demo: arrancar con ~20–50 productos "ancla" comparables a mano, e ir creciendo.

---

## 5. Modelo de datos (tabla normalizada)

```
producto_comparado
├── match_id            # id del producto canónico (agrupa equivalentes)
├── nombre_canonico     # "Paracetamol 500mg x100"
├── principio_activo
├── concentracion
├── presentacion        # tableta / jarabe / cápsula
├── cantidad
├── ean                 # si existe
└── ofertas[]
     ├── cadena         # inkafarma / boticasperu / ...
     ├── nombre_origen  # como aparece en esa web
     ├── precio
     ├── precio_regular # para detectar descuento
     ├── en_promocion   # bool
     ├── etiqueta_promo # "2x1", "-30%", "Día del Padre"
     ├── url
     ├── stock          # si está disponible
     ├── tienda/region  # si aplica
     └── capturado_en   # timestamp
```

Guardar en SQLite (consultas fáciles) o Parquet (analítica). Cada corrida = snapshot,
para poder graficar **evolución de precios en el tiempo** (KPI valioso).

---

## 6. Dashboard / KPIs (la cara visible, lo que vende)

Salida en **Streamlit** (demo interactiva) o export a **HTML estático** para colgar en tu hosting.

**Vistas:**
1. **Tabla comparativa** — producto × cadena, precio más bajo resaltado.
2. **Posicionamiento de [cadena cliente]** — ¿en cuántos productos es la más barata?
   ¿la más cara? ranking vs. competencia.
3. **Radar de promociones** — qué campañas corre cada cadena ahora (Día del Padre, etc.).
4. **Evolución temporal** — línea de precio por producto a lo largo de las corridas.
5. **Alertas** — productos donde el cliente está >X% sobre el mercado.

**KPIs sugeridos:**
- % de productos donde la cadena cliente tiene el mejor precio.
- Brecha promedio de precio vs. el líder más barato.
- N° de promociones activas por competidor.
- Índice de competitividad por categoría (medicamentos, dermo, cuidado personal).

> Para el pitch a Boticas Perú: la vista #2 y #5 son las que le hacen decir "lo quiero".
> Muestran al dueño, en 5 segundos, dónde está perdiendo frente a Inkafarma/Mifarma.

---

## 7. Roadmap de implementación (para Claude Code)

**Fase 0 — Reconocimiento (1 sesión corta):**
Para los 7 dominios, capturar en DevTools si hay API JSON. Llenar `farmacias.yaml`.
Decidir nivel A/B/C por cada uno.

**Fase 1 — MVP demo (núcleo):**
- Adaptadores para las 3 más fáciles: Boticas Perú (SFCC), Inkafarma, Mifarma.
- Canasta de ~30 productos ancla.
- `matcher.py` básico (fuzzy).
- Tabla comparativa + dashboard Streamlit con vistas #1 y #2.

**Fase 2 — Robustez:**
- Sumar Farmacia Universal, Boticas y Salud, Arcángel, Fasa.
- Caché crudo, backoff, geolocalización.
- Vistas #3, #4, #5. Snapshots temporales.

**Fase 3 — Producto vendible / export:**
- Export a HTML estático para hosting (portafolio).
- Botón "ver futuras integraciones" (caja de roadmap: veterinarias, importación, etc.).
- Programar corrida diaria (GitHub Actions, como Chasqui).

---

## 8. Caja de futuro (mostrar en demo, no construir aún)

Bloque visual "Próximamente" en el dashboard, para que el cliente vea el potencial:
- 🐾 Comparador de **veterinarias** (mismo motor, otra config).
- 🌎 Comparación con **precio de importación** / referencia internacional.
- 📦 Monitoreo de **stock por tienda/distrito**.
- 🔔 Alertas automáticas por correo/WhatsApp cuando un competidor baja un precio.
- 📈 Predicción de cuándo conviene lanzar promoción.

---

## 9. Stack técnico

- **Lenguaje:** Python 3.11+
- **HTTP:** httpx (async) / requests
- **HTML parsing:** selectolax (rápido) o BeautifulSoup
- **Headless:** Playwright (solo Nivel C)
- **Fuzzy match:** rapidfuzz
- **Datos:** pandas + SQLite/Parquet
- **Dashboard:** Streamlit (demo) → export HTML estático (portafolio)
- **Scheduling:** GitHub Actions (reutiliza patrón Chasqui)
- **Config:** YAML (pyyaml)

---

## 10. Notas de reutilización (por qué esto es un activo, no un proyecto)

El motor (`core/`) es agnóstico al rubro. Para clonar a otro negocio:
1. Nuevo `config/<rubro>.yaml` con los dominios.
2. Nueva canasta de productos objetivo.
3. (Opcional) ajustar heurísticas de `matcher` al vocabulario del rubro.

Esto convierte un proyecto en una **plantilla vendible** a múltiples clientes:
farmacias, veterinarias, ferreterías, retail de electrónica (¡tu comparador de
Digital City encaja aquí!), etc. Un solo codebase, N negocios.
