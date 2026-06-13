# PROMPT DE ARRANQUE PARA CLAUDE CODE
# Pégale esto a Claude Code junto con SPEC_comparador_farmacias.md,
# ANEXO_matching_api_historico.md y farmacias.yaml.

---

Estoy construyendo "FarmaComparador Perú", un comparador de precios entre cadenas de
farmacias peruanas (estilo Trivago de farmacias). Te adjunto el SPEC de arquitectura,
un anexo técnico (matching, explotación de API, histórico) y un farmacias.yaml inicial.

Lee los tres documentos primero. Quiero que trabajemos por fases. NO escribas todo el
proyecto de golpe.

## FASE 0 — Reconocimiento (empezamos AQUÍ)
Antes de codear el scraper, necesito mapear los endpoints reales. Para boticasperu.pe
(Salesforce Commerce Cloud), inkafarma.pe (SPA Contentful) y mifarma.com.pe:

1. Crea un script `recon/inspect_site.py` que, dado un dominio y un término de búsqueda,
   haga la petición con headers/UA realistas y guarde la respuesta cruda en
   `data/raw/recon/`. Que reporte: status code, content-type, tamaño, y si detecta
   Cloudflare/WAF (headers cf-*, server, challenge).
2. Para los sitios SPA, dame instrucciones claras de qué filtrar en DevTools → Network
   (Fetch/XHR) para encontrar el endpoint JSON, qué copiar (URL, método, params, headers),
   y dónde pegarlo en farmacias.yaml.
3. Si un request directo da 403/anti-bot, prepara el fallback con Playwright.

NO avances a Fase 1 hasta que tengamos los endpoints confirmados en farmacias.yaml.

## Estructura del proyecto
Sigue la del SPEC (config/, core/, pipeline/, dashboard/, data/). Patrón adaptador +
motor genérico, para que sea replicable a otros rubros cambiando solo la config.

## Stack
Python 3.11, httpx, selectolax, rapidfuzz, imagehash, pandas, pyyaml, playwright (fallback),
gspread (para el histórico en Sheets). Streamlit para el dashboard.

## Reglas
- Datos públicos de catálogo solamente. Delays aleatorios 2–6s, respeto de robots.txt.
- Cachea siempre el crudo en data/raw/<fecha>/ para no re-pegarle al sitio mientras depuramos.
- Empezamos con una canasta de ~30 productos ancla (la defino yo / la generamos juntos).

Arranca con la Fase 0: crea recon/inspect_site.py y dame las instrucciones de DevTools.
```
