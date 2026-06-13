# Radar de Precios — buscador estático

Página estática (HTML + CSS + JavaScript vanilla, **sin backend**) que compara
precios de medicamentos entre **Inkafarma, Mifarma y Boticas Perú**.

## Contenido (subir tal cual al hosting)
```
web/
├── index.html     # estructura + buscador
├── styles.css     # estilos
├── app.js         # carga data.json, filtra en vivo, descarga
└── data.json      # snapshot de precios (datos)
```
Súbela a cualquier hosting estático (tu hosting, Netlify, GitHub Pages, S3…).
No necesita servidor de aplicación ni base de datos.

## Funciones
- Búsqueda en vivo por nombre / marca mientras escribes.
- Filtro por categoría y “solo con las 3 cadenas”.
- Precio de cada cadena, **más barato resaltado** y **brecha %**.
- Botón para **descargar el resultado filtrado** en JSON.

## Vista previa local
`fetch()` no funciona abriendo el archivo con `file://`; sírvelo por HTTP:
```
cd web
py -m http.server 8000
# abrir http://localhost:8000
```

## Regenerar el snapshot (data.json)
Desde la raíz del proyecto:
```
py -m pipeline.build_snapshot --objetivo 150 --salida web/data.json
```
Inkafarma↔Mifarma se emparejan por SKU del grupo InRetail (exacto); Boticas Perú
por nombre + principio activo + presentación (matcher fuzzy con verificación de
tamaño de envase y guard de precio). Donde no hay equivalente comparable, la
cadena queda en “—”.
