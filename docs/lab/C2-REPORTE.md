# C2 — `/lab/componentes`: interacción con 12 productos reales

Rama `mac/c2-interaccion` (base `origin/v2/f4-ui`). Página de laboratorio, sin publicar.
**Estado: escrito sin build.** En este nodo no hay `npm`, `node` ni navegador: nada de lo de abajo
se ha compilado, tipado ni visto en pantalla. Ver [NO VERIFICADO](#no-verificado-sin-build-en-el-nodo).

## Archivos

| Archivo | Qué es |
|---|---|
| `web-v2/src/pages/[lang]/lab/componentes.astro` | Página `/es/lab/componentes/` y `/en/lab/componentes/`; elige los 12 por id |
| `web-v2/src/layouts/Lab.astro` | Layout mínimo: `global.css`, tema, `<ClientRouter />`, `<main>` (`noindex`) |
| `web-v2/src/components/lab/GaleriaLab.tsx` | Única isla (`client:visible`): estado, URL, filtrado, orden, rejilla |
| `.../TarjetaLab.tsx` | Tarjeta + `TarjetaSkeleton` |
| `.../BarrasPrecio.tsx` | Barras a escala |
| `.../FiltrosLab.tsx` | Chips, cadenas, brecha, orden |
| `.../BuscadorLab.tsx` | Buscador Fuse con listbox |
| `.../Movimiento.tsx` | `useReducida`, `useMovil`, `Contador` (tween con rAF) |
| `.../lab.css` | Todo el CSS de movimiento |
| `web-v2/src/i18n/{es,en}.json` | Solo claves nuevas `lab.*` |
| `web-v2/src/pages/[lang]/p/[slug].astro` | Solo `transition:name` (ver abajo) |

## Los 12 productos

Todos con las 4 cadenas (Inkafarma, Mifarma, Boticas Perú, Universal), ids reales de `web/data/`
(snapshot 2026-10-06). Elegidos para cubrir las 7 categorías con 4 cadenas y casos distintos de
brecha/promo/foto.

| id | Producto | Cat. | Por qué |
|---|---|---|---|
| `011251:pack` | Calcibone Natal Forte | vitaminas | promo (Inka+Mifarma); más barato Universal; historial 3 puntos |
| `072373:pack` | Centrum Silver | vitaminas | brecha 19,3 %, más barato Boticas |
| `025104:pack` | Ensure Advance Chocolate | nutrición | promo (Inka+Mifarma+Universal); brecha baja (2,9 %), 3 empatadas |
| `072767:pack` | Magnesol Kids | nutrición | promo; más barato Boticas (brecha 20,5 %) |
| `230451:fraccion` | Apronax 550 mg, blíster 4 | analgésico | **fracción**; historial 13 puntos; precio/unidad en S/ 1,8–1,9 |
| `203068:fraccion` | Naproxeno sódico 550 mg, blíster 10 | analgésico | **fracción**; promo; empate Inka/Boticas |
| `420207:pack` | Bisolvon jarabe adultos | antigripal | única de la categoría con 4 cadenas |
| `428332:pack` | Desloratadina jarabe Genfar | alergia | fotos distintas en 3 cadenas (rotación) |
| `420618:pack` | Loratadina jarabe | alergia | brecha 47,4 % (la mayor), ppu < S/ 1 (3 decimales), fotos en 3 cadenas |
| `421011:pack` | Enterogermina | gastro | promo; historial 13 puntos |
| `425311:pack` | Loción Cetaphil piel sensible | dermo | más barato Boticas, precios altos (escala de barras) |
| `085338:pack` | Sérum La Roche-Posay Hyalu B5 | dermo | promo; historial 7 puntos; brecha 25 % |

Cobertura pedida: 4 cadenas ✓ · promociones: 6 (011251, 025104, 072767, 203068, 421011, 085338) ✓ ·
historial ≥ 3 puntos verificado en 011251 (3), 230451 (13), 421011 (13), 085338 (7) ✓ ·
fracciones: 2 ✓. El propio `componentes.astro` lanza un error de build si un id desaparece de
`index.json`.

## Componentes

**`GaleriaLab`** `{ idioma, dic, cadenas, productos, base }` — junta todo. Es una sola isla porque
buscador, filtros y rejilla comparten estado; varias islas `client:visible` no se pueden hablar sin un
store. SSR pinta los 12 skeletons; al montar lee la URL y, a los 600 ms, muestra las tarjetas. Botón
«Simular carga» para volver a ver los skeletons en el video.

**`TarjetaLab`** `{ p, cadenas, activas, idioma, dic, base, movil, retraso? }`
- Escritorio: `FotoRotativa`, dos `<img>` superpuestos; en hover/foco avanza cada 1,1 s por las
  fotos distintas (una por URL: Mifarma comparte la de Inkafarma) y al salir vuelve a la primera. La
  capa de atrás precarga y recién entonces pasa al frente; solo cambia `opacity` (350 ms).
- Móvil (`pointer: coarse` o `< 640px`): `Carrusel` con `scroll-snap` y puntitos (botones de 24 px,
  `aria-current`).
- Insignias: «Promo» (si alguna cadena activa la tiene) y «Más barato» con
  `var(--acento-barato, #F59E0B)`. Texto «Ahorras S/ X en <cadena>» abajo.
- `viewTransitionName`: `foto-<slug>` en el contenedor de la foto y `nombre-<slug>` en el `<h3>`.

**`BarrasPrecio`** `{ p, activas, idioma, dic, base }` — una fila por cadena activa con precio:
`LogoCadena`, barra, precio y `ppu` (`precio_unidad` del texto; el campo del esquema es `ppu`) en
mono. Largo = `transform: scaleX(precio / máximo de la fila)` (variable CSS `--r`); la barra de la
cadena más barata usa el acento. Color de cadena: `--cad-<id>` de `global.css`.

**`FiltrosLab`** `{ dic, base, cadenas, categorias, cat, onCat, activas, onCadena, brecha,
brechaMax, onBrecha, orden, onOrden }` — controlado.
- Chips de categoría con `Contador` (tween 240 ms con rAF, escribe en el DOM sin re-render). Los
  conteos respetan los demás filtros (cadenas, brecha, búsqueda), no la propia categoría.
- Cadenas: multi-select con logos; siempre queda al menos una. Recalcula barras y «más barato» sobre
  las activas.
- Brecha: `<input type=range>` 0…48; filtra `ahorroActivo(p).pct ≥ valor`.
- Orden: `ahorro` (por defecto), `nombre`, `precio` (más bajo), `brecha`.

**`BuscadorLab`** `{ productos, q, onQ, dic }` — Fuse con `FUSE_OPCIONES` (mismas claves, pesos y
umbral que `Explorador.tsx`) + `includeMatches`; `<mark>` sobre `nombre`. Teclado: ↑ ↓ mueven
(circular), Enter elige (pone el nombre en `q`), Esc cierra y un segundo Esc limpia.
`role=combobox` + `aria-controls` + `aria-activedescendant`; `listbox`/`option`; región `aria-live`.
Escribir filtra también la rejilla.

**Estado vacío**: título, texto y botón «Limpiar filtros» bilingües. **Skeleton**: mismas clases de
bloque que la tarjeta (`lab-card__foto/body/nombre/meta/barras/pie`, alturas mínimas fijas), shimmer
con `transform: translateX` sobre `::after`.

## Estado en la URL

`?cat=&cad=&brecha=&orden=&q=`; solo se escribe lo que difiere del valor inicial; se lee al montar y se
escribe con `history.replaceState(history.state, …)` (se conserva `history.state` porque
`ClientRouter` guarda ahí el índice y el scroll).

Ejemplo: `/es/lab/componentes/?cat=vitaminas&cad=inkafarma,universal&brecha=3&orden=brecha&q=cal`
(vitaminas, solo Inkafarma y Universal, brecha ≥ 3 %, orden por brecha, búsqueda «cal»).

## View Transitions

`<ClientRouter />` solo en `layouts/Lab.astro`. La ficha (`[lang]/p/[slug].astro`) recibe
`transition:name={`foto-${p.slug}`}` y `nombre-${p.slug}` (mismos nombres que la tarjeta). Desviación
mínima: `Miniatura` es un componente React y no admite la directiva, así que la foto va envuelta en
`<div class="shrink-0" transition:name=…>`; es neutro en layout (hijo flex que no se encoge). El `h1`
lleva el atributo directo. `git diff` de la ficha: 2 líneas.

## Movimiento

Solo `transform` y `opacity`; todo dentro de `@media (prefers-reduced-motion: no-preference)`; con
`reduce` hay un bloque que pone `animation: none; transition: none`, quita el shimmer, desactiva la
rotación de fotos (JS: `useReducida`), el scroll suave del carrusel y el tween del contador.
Duraciones: crossfade 350 ms (≤ 400), resto 150–250 ms.
**Excepción a revisar:** el shimmer del skeleton es un bucle de 1200 ms (a 250 ms parpadearía); no es
una transición de estado.

## NO VERIFICADO (sin build en el nodo)

- Que `npm run build` compile y que `tsc`/`astro check` pase (tipos de `viewTransitionName` en
  `CSSProperties`, custom properties con `as CSSProperties`, `IFuseOptions`).
- Que `astro:transitions` / `<ClientRouter />` y `transition:name` se comporten igual en Astro 7.3.
- La transición real tarjeta → ficha (y la vuelta: la ficha usa `Base.astro`, sin router) y que los
  nombres coincidan en el vuelo; el efecto de `transform` en `:hover` sobre `view-transition-name`.
- Que Tailwind 4 recoja las clases de `components/lab/` (detección automática; no hay `@source`).
- Hidratación: `useReducida` arranca en `true` en SSR; `useMovil` en `false`.
- El crossfade con fotos remotas (CloudFront, Boticas, VTEX) y que no falle por hotlinking; el
  carrusel con scroll-snap en un móvil táctil real.
- Contraste del acento `#F59E0B` (texto oscuro sobre él) en claro y oscuro; `--acento-barato` lo
  define C1, aquí es solo fallback.
- Que el valor `brechaMax` (48) y los conteos de chips coincidan con lo esperado.
- El historial «≥ 3 puntos» de 072373, 072767, 203068, 420207, 428332, 420618, 425311 no se comprobó
  (no se usa en la página; solo se verificaron los cuatro de arriba).
- Que `grep -rn "client:load" web-v2/src/components/lab web-v2/src/pages/*/lab` esté vacío: lo
  comprobé con Grep sobre `web-v2/src/**/lab/**` (sin coincidencias).

## Capturar y grabar en Windows

```
cd web-v2
npm install            # si no está
npm run dev -- --port 4322
```
Rutas: `http://localhost:4322/es/lab/componentes/` y `http://localhost:4322/en/lab/componentes/`.
Capturas y video a `docs/img/lab-c2/` (Playwright con `recordVideo: { dir: 'docs/img/lab-c2/' }`,
viewport 1280×800 y otro 390×844 con `hasTouch: true` para el carrusel; repetir con
`reducedMotion: 'reduce'` para comprobar estados finales).

### Guion del video (20 s, escritorio)

| s | Acción |
|---|---|
| 0–3 | Carga: se ven los skeletons y luego las tarjetas (entrada escalonada) |
| 3–7 | Hover sobre «Desloratadina» y «Loratadina»: crossfade entre fotos; barras a escala |
| 7–11 | Chip «Vitaminas» (el contador cambia con tween), quitar Mifarma, mover la brecha a ~10 %, orden por brecha; mostrar la URL con el estado |
| 11–16 | Foco en el buscador: escribir «lora», ↓ ↓ Enter; «xyz» para ver el estado vacío y «Limpiar filtros» |
| 16–20 | Click en el nombre de una tarjeta: View Transition a la ficha (foto y nombre se desplazan) |

## Decisiones tomadas sin el dueño

- Una sola isla (`GaleriaLab`) en vez de una por componente: comparten estado.
- Semántica de cadenas: un producto se muestra si tiene precio en alguna cadena activa; con los 12
  elegidos (todos con 4) no cambia nada, pero queda igual que en `Explorador`.
- No se tocó `docs/DECISIONES.md` (fuera de los archivos permitidos): las decisiones están aquí.
