---
kind: claude
push: true
---
# TASK-c2-interaccion — `/lab/componentes`: interacción con 12 productos reales

Rama base: `origin/v2/f4-ui` (Astro 7 + islas React 19 + Tailwind 4 en `web-v2/`). Tu worktree ya
está creado por enjambre; no cambies de rama ni toques `main`. Nada se publica: es una página de
laboratorio que el dueño revisa en capturas y video antes de aplicar nada al sitio real.

## Lo que puedes ejecutar (léelo antes de empezar)

Tu allowlist es **Read, Edit, Write, Glob, Grep, `git status`, `git diff`, `ls`**. No hay `npm`,
`node`, Playwright ni grabación de video en este nodo para ti: cualquier otro comando se deniega y
cada denegación acorta el trabajo. No lo intentes. Escribe el código con cuidado imitando los
componentes existentes (`Explorador.tsx`, `Producto.tsx`, `LogoCadena.tsx`, `src/lib/datos.ts`,
`src/lib/contrato.ts`, `src/i18n/`) y en el reporte marca como **NO VERIFICADO (sin build en el
nodo)** todo lo que no pudiste comprobar. El build, las capturas y el video (`recordVideo`) en
`docs/img/lab-c2/` se harán en Windows al recoger tu rama. No tienes reloj: escribe
`docs/lab/C2-REPORTE.md` en versión 1 **pronto** y amplíalo al final. El supervisor hace el commit
(`git add -A`): no necesitas ni puedes hacer `git commit`. **Sin librerías nuevas** (no hay
`npm install`): solo React, Astro, Fuse.js y Tailwind, que ya están.

## Qué construir

Una página bilingüe `web-v2/src/pages/[lang]/lab/componentes.astro` con **12 productos reales** de
`web/data/` elegidos a mano para cubrir las 4 cadenas, al menos 3 con promoción, 3 con historial de
≥ 3 puntos y 2 fracciones (`:fraccion`). Lista los 12 ids en el reporte. Componentes nuevos bajo
`web-v2/src/components/lab/` (islas `client:visible`, nunca `client:load`):

1. **Tarjeta de producto** (`TarjetaLab.tsx`): fotos por cadena que **rotan en hover con crossfade**
   (dos `<img>` superpuestos, transición solo de `opacity`); en móvil (`pointer: coarse` o
   `< 640px`) un **carrusel** con scroll-snap y puntitos. Nombre, presentación, laboratorio, badge de
   promo, "más barato" con el acento (no verde: lo define C1; usa `var(--acento-barato, #F59E0B)` como
   fallback).
2. **Barras de precio a escala** (`BarrasPrecio.tsx`): una barra por cadena, largo proporcional al
   precio máximo de la fila, color y logo de cadena (`LogoCadena.tsx`), precio y **precio por unidad**
   (`precio_unidad` del esquema) en mono.
3. **Filtros** (`FiltrosLab.tsx`): chips de categoría con **contador animado** (el número hace
   tween al cambiar, con `requestAnimationFrame`, sin librerías); **selector de cadenas con logos**
   (multi-select); **slider de brecha %** (rango `brecha_pct`); **orden** (nombre, precio, brecha,
   ahorro); **estado en la URL** (`?cat=&cad=&brecha=&orden=&q=`) con `history.replaceState` y lectura
   al montar, para que un enlace reproduzca el estado.
4. **Buscador instantáneo** (`BuscadorLab.tsx`): Fuse.js sobre los 12 (ya hay un índice en
   `Explorador.tsx`, reutiliza la configuración), **resaltado** de coincidencias (`<mark>`),
   **navegación por teclado** (↑ ↓ Enter Esc, `aria-activedescendant`, roles `listbox`/`option`).
5. **Skeletons** (misma geometría que la tarjeta, shimmer con `transform` sobre un
   pseudo-elemento), **estado vacío** (sin resultados: texto bilingüe + botón "limpiar filtros") y
   **View Transitions** de tarjeta a ficha: `transition:name` por producto en la foto y el nombre,
   compatible con la ficha existente (`[lang]/producto/[id].astro` o la ruta que exista; si la ficha
   no tiene el `transition:name`, añádelo **solo** como atributo, sin cambiar su diseño). Usa
   `<ClientRouter />` de `astro:transitions` únicamente en el layout de laboratorio.
6. **Movimiento**: solo `transform` y `opacity`; todo dentro de `@media (prefers-reduced-motion:
   no-preference)`; con `reduce`, estados finales sin animación. Duraciones ≤ 250 ms salvo el
   crossfade (≤ 400 ms). Nada de `width/height/top/left` animados.
7. **`docs/lab/C2-REPORTE.md`** (en español): los 12 ids y por qué, cada componente con sus props y
   su interacción, cómo se guarda el estado en la URL (ejemplo de enlace), lo NO VERIFICADO, y el
   comando exacto para capturar y grabar en Windows (`npm run dev -- --port 4322`, rutas
   `/es/lab/componentes` y `/en/lab/componentes`, y un guion de 20 s para el video: hover, filtrar,
   buscar con teclado, abrir ficha).

Layout: si existe `web-v2/src/layouts/Lab.astro` (lo crea la tarea C1 en otra rama; aquí **no**
existe), créalo tú mínimo: importa `global.css`, añade `<ClientRouter />` y un `<main>`. No toques
`Base.astro`.

## Files you may touch

- `web-v2/src/pages/[lang]/lab/componentes.astro` (nuevo)
- `web-v2/src/components/lab/*.tsx` y `web-v2/src/components/lab/*.css` (nuevos)
- `web-v2/src/layouts/Lab.astro` (nuevo)
- `web-v2/src/i18n/es.json`, `web-v2/src/i18n/en.json` (solo añadir claves `lab.*`)
- La ficha de producto existente: **solo** añadir atributos `transition:name`, nada más
- `docs/lab/C2-REPORTE.md` (nuevo)
- Prohibido: `Base.astro`, `index.astro`, `Explorador.tsx`, `Producto.tsx`, `web/`, `web/data/`,
  `pipeline/`, `core/`, `tests/`, `package.json`, `main`.

## Done criteria

- Existen la página, los componentes de `components/lab/` y el reporte; ningún archivo prohibido
  cambió (`git status`, `git diff` sobre la ficha muestra solo `transition:name`).
- Los 12 productos son ids reales de `web/data/` y cubren las 4 cadenas.
- `grep -rn "client:load" web-v2/src/components/lab web-v2/src/pages/*/lab` vacío; ninguna
  `transition` anima propiedades distintas de `transform`/`opacity` (grep de `transition:` en los CSS
  nuevos lo muestra).
- Hay un bloque `@media (prefers-reduced-motion: reduce)` que desactiva las animaciones nuevas.
- `docs/lab/C2-REPORTE.md` existe con los 12 ids, el guion del video y la lista de lo NO VERIFICADO.
