# Radar de Precios — buscador estático

Página estática (HTML + CSS + JavaScript vanilla, **sin backend**) que compara
precios de medicamentos entre **Inkafarma, Mifarma, Boticas Perú y Farmacia
Universal**.

## Alcance (decisión de diseño)

El comparador cubre **medicamentos, suplementos y dermo** — categorías donde el
emparejamiento entre cadenas se hace por **principio activo + concentración +
presentación**, que es confiable.

**No cubre cosmética / cuidado personal** (afeitado, desodorantes, shampoo,
maquillaje…). Ahí no hay principio activo: la marca se comparte entre muchos
modelos distintos (Gillette Sensor3 vs Mach3, Rexona Clinical vs Men V8) y, sin
una concentración que discrimine, el matcher produciría falsos. Por eso en esas
categorías solo se comparan las cadenas del grupo InRetail (Inkafarma/Mifarma) y
las independientes (Boticas/Universal) quedan en “—”. Es un límite deliberado del
método, no un dato faltante.

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
- Filtro por categoría y “solo con todas las cadenas”.
- Precio de cada cadena, **más barato resaltado** y **brecha %**.
- Agrupación por conglomerado (InRetail vs independientes).
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
(SFCC) y Farmacia Universal (VTEX) por nombre + principio activo + concentración +
presentación (matcher endurecido: cantidad exacta + reglas duras). Donde no hay
equivalente comparable —o en categorías fuera de alcance (cosmética)— la cadena
queda en “—”.
