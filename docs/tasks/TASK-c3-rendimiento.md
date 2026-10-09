---
kind: claude
push: true
---
# TASK-c3-rendimiento — rendimiento e imágenes de la v2, sin cambiar el diseño

Rama base: `origin/v2/f4-ui` (Astro 7 + islas React 19 + Tailwind 4 en `web-v2/`). Tu worktree ya
está creado por enjambre; no cambies de rama ni toques `main`. Nada se publica desde aquí.

## Lo que puedes ejecutar (léelo antes de empezar)

Tu allowlist es **Read, Edit, Write, Glob, Grep, `git status`, `git diff`, `ls`** (`ls -l` sí sirve
para pesar archivos). No hay `npm`, `node`, `sharp`, Playwright ni Lighthouse en este nodo para ti:
cualquier otro comando se deniega y cada denegación acorta el trabajo. No lo intentes. Esta tarea
es, por tanto, **código + medición en diferido**: escribes el script y el componente, dejas la tabla
"antes" con los datos que te doy y la columna "después" como pendiente de medir en Windows. Marca
todo lo no comprobado como **NO VERIFICADO (sin build en el nodo)**. No tienes reloj: escribe
`docs/lab/C3-REPORTE.md` en versión 1 **pronto** y amplíalo. El supervisor hace el commit
(`git add -A`). **No añadas dependencias a `package.json`** (no hay `npm install`): `sharp` se
declara en el reporte como `npm i -D sharp` pendiente y el script falla con un mensaje claro si falta.

Medición de base ya hecha en Windows (Lighthouse móvil sobre `dist/` local servido con gzip; en
vivo el CDN devuelve 403 a Chrome headless): **inicio 94–97, ficha 95–97**; sin gzip el inicio daba
67–77. Panorama: sin medir. LCP del inicio: la primera foto de producto. Úsalos como columna "antes".

## Qué construir

1. **`web-v2/scripts/imagenes_web.mjs`** (ESM, Node 22+, `sharp` importado dinámicamente con
   mensaje si falta):
   - lee las URLs de foto que aparecen en `web/data/` (mira `src/lib/datos.ts`/`contrato.ts` para
     el campo exacto) y **descarga cada URL una sola vez** (dedupe por URL, caché en disco fuera del
     repo: `IMAGENES_CACHE` o `~/.cache/radar-precios/imagenes/`), **concurrencia 2 en total** y
     **pausa aleatoria de 0,5–1 s por dominio** entre peticiones al mismo host; `User-Agent`
     identificable; reintento único en 429/503 tras 30 s; nunca borra la caché;
   - genera **AVIF y WebP en 96, 240 y 480 px** de ancho (sin agrandar: si la fuente es menor,
     el tamaño mayor se omite) en `web-v2/public/img/p/<hash>-<ancho>.<ext>`;
   - escribe **`web-v2/src/data/imagenes.manifest.json`**: por URL original → hash, ancho/alto
     reales, variantes disponibles y un **placeholder** (color dominante o LQIP de ≤ 200 bytes);
   - idempotente: una segunda corrida no descarga ni recodifica lo que ya está.
2. **Componente `web-v2/src/components/Imagen.astro`**: recibe la URL original y el manifest; emite
   `<picture>` con `<source type="image/avif">`, `<source type="image/webp">` y `<img>` con `srcset`,
   `sizes` (prop), `width` y `height` **fijos** (del manifest, para evitar CLS), `loading="lazy"` y
   `decoding="async"` por defecto, y con la prop `lcp` cambia a `loading="eager"` +
   `fetchpriority="high"`; fondo con el placeholder; si la URL no está en el manifest, cae a la
   `<img>` original sin romper. Úsalo en el inicio y en la ficha **sin cambiar el diseño** (mismas
   clases, mismo tamaño visual); la primera foto del inicio lleva `lcp`.
3. **Ajustes generales**, cada uno en su propio cambio pequeño y explicado en el reporte:
   - **`index.json`**: pésalo con `ls -l web/data/`; si pasa de ~150 KB, propón e implementa en
     `scripts/copiar-datos.mjs` (o donde se genere) la partición por categoría o por página, y
     adapta la carga (`src/lib/datos.ts`) sin cambiar el contrato público; si no pesa, documenta el
     peso y no partas nada;
   - **hidratación**: revisa cada isla (`grep -rn "client:" web-v2/src`) y deja solo
     `client:visible` o `client:idle`, salvo que el componente sea la LCP o el buscador del hero
     (justifica cada excepción);
   - **fuentes self-hosted con subset**: hoy `@fontsource-variable/inter` carga el paquete entero;
     deja solo los subsets `latin` y `latin-ext` (imports concretos del paquete) con
     `font-display: swap` y un `<link rel="preload">` del único archivo de la fuente de texto;
     documenta qué archivos deja de pedir el navegador.
4. **`docs/lab/C3-REPORTE.md`** (en español): tabla **antes / después** (inicio, ficha, panorama;
   performance, LCP, CLS, TBT, peso transferido) con "antes" relleno con los datos de arriba y
   "después" marcado "pendiente de medir en Windows"; lista de cambios con el motivo de cada uno;
   los comandos exactos para reproducir en Windows: `npm i -D sharp`, `node scripts/imagenes_web.mjs`,
   `npm run build`, `npx serve dist` (con gzip) y Lighthouse móvil (`--preset=perf
   --form-factor=mobile`) sobre `/es/`, una ficha y `/es/panorama/`; y lo NO VERIFICADO.

## Files you may touch

- `web-v2/scripts/imagenes_web.mjs` (nuevo), `web-v2/src/components/Imagen.astro` (nuevo)
- `web-v2/src/data/imagenes.manifest.json` (nuevo, puede quedar vacío `{}` porque no hay `sharp` aquí)
- `web-v2/scripts/copiar-datos.mjs`, `web-v2/src/lib/datos.ts` (solo si partes `index.json`)
- Páginas y componentes existentes **solo** para sustituir `<img>` por `<Imagen>`, cambiar
  directivas `client:*` y los imports de fuente: nada de clases, layout ni textos
- `web-v2/src/layouts/Base.astro` (solo el `<link rel="preload">` de la fuente)
- `web-v2/.gitignore` (añadir `public/img/p/` si decides no versionar las variantes; justifícalo)
- `docs/lab/C3-REPORTE.md` (nuevo)
- Prohibido: `package.json`, `package-lock.json`, `web/`, `web/data/`, `pipeline/`, `core/`,
  `tests/`, `main`.

## Done criteria

- `imagenes_web.mjs` existe, importa `sharp` dinámicamente con mensaje de error claro, respeta
  concurrencia 2 y pausa 0,5–1 s por dominio (visible en el código), cachea fuera del repo y es
  idempotente.
- `Imagen.astro` emite `width`/`height` fijos, `srcset`+`sizes`, lazy por defecto y
  `fetchpriority="high"` solo con `lcp`; el inicio y la ficha lo usan sin cambios visuales de diseño
  (`git diff` muestra solo sustituciones de `<img>`, directivas `client:*` e imports de fuente).
- `grep -rn "client:load" web-v2/src` vacío o cada caso justificado en el reporte.
- `package.json` sin cambios.
- `docs/lab/C3-REPORTE.md` existe con la tabla antes/después y los comandos de reproducción.
