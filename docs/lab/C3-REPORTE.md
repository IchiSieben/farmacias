# C3 — Rendimiento e imágenes de la v2, sin cambiar el diseño

Rama `mac/c3-rendimiento`, base `origin/v2/f4-ui`. **Estado: código escrito; nada compilado ni medido.**
Este nodo no tiene `npm`, `node`, `sharp`, Playwright ni Lighthouse, así que todo lo de abajo marcado
**NO VERIFICADO (sin build en el nodo)** debe comprobarse en Windows con los comandos de la última sección.

## Antes / después

"Antes": Lighthouse móvil en Windows sobre `dist/` local servido con gzip (en vivo el CDN devuelve 403 a
Chrome headless). Sin gzip el inicio daba 67–77.

| Página | Métrica | Antes | Después |
|---|---|---|---|
| Inicio `/es/` | Performance | 94–97 | pendiente de medir en Windows |
| Inicio `/es/` | LCP | primera foto de producto (valor no registrado) | pendiente de medir en Windows |
| Inicio `/es/` | CLS · TBT · peso transferido | no registrado | pendiente de medir en Windows |
| Ficha | Performance | 95–97 | pendiente de medir en Windows |
| Ficha | LCP · CLS · TBT · peso transferido | no registrado | pendiente de medir en Windows |
| Panorama `/es/panorama/` | todas | sin medir | pendiente de medir en Windows |

Al medir "después", anotar también los valores de LCP/CLS/TBT/peso del "antes" corriendo el mismo Lighthouse
sobre `main`/`v2/f4-ui` (hoy solo se conserva el puntaje de performance).

## Cambios y motivo

1. **`web-v2/scripts/imagenes_web.mjs` (nuevo).** Lee `imagen` de `web/data/index.json`, descarga cada URL
   única una vez (caché en `$IMAGENES_CACHE` o `~/.cache/radar-precios/imagenes/`, nunca se borra) y genera
   AVIF y WebP a 96/240/480 px sin agrandar (fuente menor → se omiten los anchos mayores; menor que 96 → una
   sola variante a su tamaño). Concurrencia 2 en total; pausa aleatoria 0,5–1 s por host (cola por host,
   `turnoDeHost`); `User-Agent` identificable; un reintento en 429/503 tras 30 s. Idempotente: si el manifiesto
   ya tiene la URL y todos sus archivos existen, no descarga ni recodifica. `sharp` se importa dinámicamente y,
   si falta, imprime `npm i -D sharp` y sale con 1. `--limite=N` sirve para probar con pocas URLs.
2. **`web-v2/src/data/imagenes.manifest.json` (nuevo, `{}`).** Por URL: `hash` (sha1 de la URL, 16 hex), `w`/`h`
   reales (con rotación EXIF), `variantes` {avif, webp} y `placeholder` (color dominante `#rrggbb`).
3. **`src/lib/imagenes.ts` + `src/lib/manifiesto.ts` (nuevos).** El primero es puro (tipos y `atributosImagen`)
   y lo comparten Astro y React; el segundo importa el manifiesto y solo lo usan los `.astro` en el build, para
   que el JSON no entre en el bundle del cliente. `infoImagen` devuelve `null` si la primera variante no existe
   en `public/img/p/`, así un clon sin correr el script no genera `<picture>` rotos.
4. **`src/components/Imagen.astro` (nuevo).** `<picture>` con `<source>` AVIF y WebP, `<img>` con `srcset`,
   `sizes` (prop), `width`/`height` del manifiesto, `loading="lazy"` y `decoding="async"`; con `lcp`:
   `loading="eager"` + `fetchpriority="high"`. Fondo = placeholder hasta el `onload`. Sin entrada en el manifiesto
   → `<img>` original con la misma caja.
5. **Uso.** *Ficha:* `Imagen` con `lcp` en lugar de `Miniatura` (mismas clases y caja 128×128). *Inicio:* las
   fotos viven dentro de la isla React, y un `.astro` no se puede usar ahí; `Miniatura` (`Producto.tsx`) emite el
   mismo `<picture>` con el mismo helper `atributosImagen`. La primera fila lleva `prioritaria` (eager + alta).
   La lista móvil y la de escritorio se renderizan las dos (una oculta por CSS), así que la primera de cada una
   es eager y la oculta descarga una foto de más (≈ unos KB; compensado por el resto en lazy).
   La ficha pierde el respaldo "sin foto" si la imagen remota falla en el navegador (antes lo daba `onError`
   de React); se conserva cuando no hay URL.
6. **`index.json` (310 KB sin comprimir; umbral ~150 KB).** El catálogo completo ya no se pide en idle: se pide
   a la **primera interacción** (toque, tecla, scroll, foco) o enseguida si la URL trae filtros (`?q=`…).
   Se pide junto con el manifiesto de fotos. El inicio sigue mostrando las 30 primeras filas desde el HTML.
   *Por qué no partir por categoría:* buscador, laboratorios, orden por ahorro y CSV cruzan categorías; partir
   obliga a cargar las nueve igualmente, y los `cat_*.json` ya existen pero los genera `pipeline/` (prohibido).
   El contrato público de `web/data/` y `datos.ts` no cambia. Alternativa si 310 KB sigue pesando tras medir:
   cargar solo `cat_<id>.json` al elegir categoría y el índice completo al buscar.
   Efecto colateral a vigilar: el botón "mostrar más" aparece cuando termina la carga (que arranca con el primer
   scroll), y el conteo muestra `total` hasta entonces (ya era así).
7. **Hidratación.** Única isla: `Explorador` con `client:load`, **justificado**: es el buscador del hero y la
   lista de la LCP; con `visible`/`idle` el primer toque en el buscador no respondería. `LogoCadena` y
   `Miniatura` en la ficha se renderizan sin directiva (HTML estático). `grep -rn "client:" web-v2/src` solo
   devuelve esa isla (y el comentario que la justifica).
8. **Fuentes (`global.css`).** Ya se cargaba un solo `woff2` (latin) con `<link rel="preload">` en
   `Base.astro` (sin cambios ahí), no el paquete entero. Ahora: `latin` + `latin-ext` con `unicode-range`,
   `font-display: swap` (antes `optional`), y un respaldo `Inter Fallback` (Arial con `size-adjust` y
   overrides de métricas) para que `swap` no desplace el texto. El navegador sigue pidiendo `latin`
   (preloaded) y **no pide** cirílico, griego ni vietnamita; `latin-ext` solo si la página pinta un carácter de
   su rango. No hay archivo menos que antes: el ahorro de "siete → uno" ya estaba hecho. Revertir a
   `optional` es cambiar una palabra por cara.
9. **`copiar-datos.mjs`.** Copia además el manifiesto a `public/data/` (solo entradas con sus variantes en
   disco) para que la isla lo traiga al cargar el catálogo. Necesario para el punto 5 en el inicio.
10. **`.gitignore` (`web-v2/`).** Se ignora `public/img/p/` (variantes derivadas, reproducibles con el script y
    la caché; ~6 archivos binarios por producto inflarían el repo). Se versiona solo el manifiesto. Consecuencia:
    en un clon limpio el sitio compila y usa las fotos originales hasta correr `imagenes_web.mjs`.
    Si se prefiere versionarlas, borrar esa línea.

## Cómo reproducir en Windows

Desde `web-v2/`:

```
npm i -D sharp                      # cambia package.json/lock: queda a cargo de quien lo ejecute
node scripts/imagenes_web.mjs       # ~300 URLs a 2 concurrentes, ~1 s/petición: varios minutos
node scripts/imagenes_web.mjs       # 2.ª corrida: debe decir "N ya estaban", 0 procesadas
npm run build
npx serve dist                      # con gzip (por defecto)
npx lighthouse http://localhost:3000/es/ --preset=perf --form-factor=mobile --only-categories=performance --view
npx lighthouse http://localhost:3000/es/p/<slug>/ --preset=perf --form-factor=mobile ...   # una ficha con foto
npx lighthouse http://localhost:3000/es/panorama/ --preset=perf --form-factor=mobile ...
```

Ajusta el puerto al que imprima `serve`. Comprobar además: `dist/es/` contiene `<picture>`; en la pestaña Red
del inicio solo se pide `index.json` tras interactuar; `git status` no muestra `public/img/p/`.

## NO VERIFICADO (sin build en el nodo)

- Que todo compile: tipos de `Producto.tsx`/`Explorador.tsx`, import del JSON en `manifiesto.ts`,
  `onload` como atributo-cadena en `Imagen.astro` y el spread `{...comun}` con `fetchpriority`.
- `imagenes_web.mjs` no se ejecutó: ni la descarga, ni `sharp` (AVIF/WebP, color dominante), ni la cola por host.
- Que el sitio se vea igual (cajas, `object-contain`, fondo blanco tras cargar) y que el color de carga
  desaparezca en `Miniatura` incluso con la foto ya en caché (`ref` + `complete`).
- Que el reintento a la primera interacción cargue a tiempo "mostrar más" y no cause parpadeo.
- Todas las cifras "después", incluida la mejora esperada de LCP, y que `swap` + `Inter Fallback` no suba el CLS.
- Los valores de `Inter Fallback` (107,12 % / 90,2 % / 22,48 %) son los habituales de Inter sobre Arial, no medidos aquí.
- Que `@fontsource-variable/inter` trae `files/inter-latin-ext-wght-normal.woff2` (el de `latin` ya lo usaba el repo).
