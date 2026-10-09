# C1 · Identidad visual del Radar de Precios — reporte

Rama base `origin/v2/f4-ui`. Nada se publica: son propuestas en `/{es,en}/lab/portada-{a,b,c}/`.
**Todo lo de este reporte está escrito sin build en el nodo** (ver «NO VERIFICADO»).

## Qué hice

| Archivo | Qué es |
|---|---|
| `web-v2/src/styles/tokens.css` | Tokens: color (tripletas RGB), tipografía, espaciado 4 px, radios, sombras, animación. Oscuro por defecto, claro con `:root.light`. |
| `web-v2/src/layouts/Lab.astro` | Layout del laboratorio: importa `tokens.css`, script inline de tema (antes del primer render), cabecera con wordmark, navegación A/B/C, cambio de idioma y botón de tema. No toca `Base.astro`. |
| `web-v2/src/components/Wordmark.astro`, `web-v2/public/wordmark.svg` | Marca propia: aro de radar + arco + barrido (teal) + punto (acento de ahorro) y el nombre en `<text>` con tipografía de respaldo. Sin emoji. |
| `web-v2/src/pages/[lang]/lab/portada-{a,b,c}.astro` | Las tres portadas, con datos reales (`leerDatos`), máx. 12 / 12 / 24 productos. |
| `web-v2/src/i18n/{es,en}.json` | Solo claves `lab.*` añadidas. |

Tema: `localStorage['theme']` = `light`/`dark` (try/catch); sin valor guardado manda `prefers-color-scheme`, y si no hay preferencia clara, oscuro.

## Tokens

Los de superficie, texto y acento son exactamente los del Landing (tripletas: `rgb(var(--bg) / α)`).

| token | oscuro | claro |
|---|---|---|
| `--bg` | `#0D1117` | `#FFFFFF` |
| `--surface` | `#161B22` | `#F6F8FA` |
| `--border` | `#30363D` | `#D0D7DE` |
| `--fg` | `#E6EDF3` | `#1F2328` |
| `--muted` | `#8B949E` | `#59636E` |
| `--accent` | `#2DD4BF` | `#0D9488` |
| `--accent-strong` | `#2DD4BF` | `#0F766E` |
| **`--saving`** (más barato) | `#E879F9` | `#A21CAF` |
| `--on-saving` (texto sobre relleno) | `#0D1117` | `#FFFFFF` |
| `--cad-inkafarma` | `#4CC27A` | `#1B8F43` |
| `--cad-mifarma` | `#FF9A52` | `#C8561A` |
| `--cad-boticasperu` | `#7B8CE0` | `#334499` |
| `--cad-universal` | `#4DA3FF` | `#004499` |

Los `--cad-*` son hex (se usan directos en barras y trazos). En claro salen de `logos.json`
(Inkafarma, Boticas, Universal tal cual; **Mifarma oscurecido**: su `#FF7929` da 2.62:1 sobre
blanco). En oscuro, Boticas (`#334499` → 2.19:1 sobre `--bg`) y Universal son demasiado oscuros:
van aclarados. Boticas y Universal siguen siendo dos azules cercanos: la barra siempre
lleva su logo al lado y el precio en número, el color nunca es la única señal.

Otros: escala tipográfica modular 1.25 (`--text-xs` 12.8 px … `--text-3xl` 39 px, `--text-4xl`/`--text-5xl`
fluidas con `clamp`), pesos 400–700, interlineados y tracking; espaciado `--sp-1…24` (4 px a 96 px);
radios 4/8/12/16/pill; tres sombras por tema; animación `--dur-fast/base/slow` (120/200/400 ms)
y `--ease-out`, `--ease-in-out`, `--ease-spring`, con reducción a ~0 en `prefers-reduced-motion`.

## Acento de «más barato»: fucsia

Inkafarma es verde y el teal de la marca se le parece, así que el ahorro no puede ser verde ni
teal. Mifarma es naranja, Boticas/Universal azules: el único tono libre y legible en ambos temas es
el fucsia/violeta. (Descartados: ámbar y coral, se confunden con el naranja de Mifarma.)

Ratios calculados a mano con la fórmula WCAG, `(L1+0.05)/(L2+0.05)`, linealizando sRGB
(`c ≤ 0.03928 ? c/12.92 : ((c+0.055)/1.055)^2.4`):

| par | L | ratio | umbral |
|---|---|---|---|
| Oscuro: `#E879F9` (L 0.377) sobre `--bg` (L 0.00548) | | **7.69:1** | texto 4.5 ✔ |
| Oscuro: `#E879F9` sobre `--surface` (L 0.0107) | | **7.03:1** | texto 4.5 ✔ |
| Oscuro: badge — texto `#0D1117` sobre relleno `#E879F9` | | **7.69:1** | texto 4.5 ✔ |
| Oscuro: relleno del badge `#E879F9` frente a `--surface` | | **7.03:1** | componente 3 ✔ |
| Claro: `#A21CAF` (L 0.116) sobre `--bg` (L 1) | | **6.33:1** | texto 4.5 ✔ |
| Claro: `#A21CAF` sobre `--surface` (L 0.936) | | **5.95:1** | texto 4.5 ✔ |
| Claro: badge — texto `#FFFFFF` sobre relleno `#A21CAF` | | **6.33:1** | texto 4.5 ✔ |
| Claro: relleno del badge `#A21CAF` frente a `--bg` / `--surface` | | 6.33 / 5.95 | componente 3 ✔ |

Colores de cadena como componente gráfico (barras ≥ 3:1 contra `--bg`):
claro — Inkafarma 4.15, Mifarma `#C8561A` 4.37, Boticas 8.65, Universal 9.2;
oscuro — Boticas `#7B8CE0` 6.0, Universal `#4DA3FF` 7.2, Inkafarma `#4CC27A` 8.4; Mifarma `#FF9A52` no calculado a mano
(luminancia claramente mayor que el resto de los oscuros, esperable > 8). El texto de precios de cadena
no usa estos colores (usa `--muted` o `--saving`).
Pendiente de medir con herramienta: `--muted` sobre `--surface` en oscuro (`#8B949E` sobre `#161B22`, estimado ≈ 5.7).

## Cómo se ve cada portada (sin capturas)

**A · Editorial.** Columna única de 52 rem, mucho aire (96 px sobre el titular). Titular de 39–61 px
«El mismo medicamento, otro precio.» y una frase. Después 12 entradas separadas por un filete de 1 px, sin tarjetas:
número de orden en mono, nombre en 25 px, presentación en gris, línea «Más barato en [logo] S/ x» y una
fila de precios de las cadenas en mono, con la más barata en fucsia. A la derecha, la cifra del ahorro en mono grande
(39–61 px, fucsia) con «MÁS BARATO · −x %». En móvil la cifra sube arriba de cada entrada.

**B · Tarjetas.** Rejilla `auto-fill` de tarjetas de ≥ 19 rem (12 productos con foto y ≥ 3 cadenas). Foto 4:3 sobre blanco, con el
badge fucsia «Ahorras S/ x» encima. Debajo, nombre y presentación y cuatro filas fijas (mismo orden de cadena siempre): logo · barra
· precio. La barra mide `precio / máximo de la fila` con el color de la cadena; la más barata lleva aro fucsia y precio en negrita fucsia.
Hover: la tarjeta sube 3 px. Nota al pie explicando la escala.

**C · Tablero.** Tabla densa de 24 filas (texto de 14 px, sin foto): producto en una línea con elipsis, una columna por cadena (logo en la cabecera
sticky), precio mínimo con celda teñida de fucsia, badge de ahorro con porcentaje, y sparkline de 120×28 px del precio más bajo del historial (escalón, punto
final fucsia). Sin historial de ≥ 2 puntos: «Sin historial». En móvil, scroll horizontal.

## Recomendación: **C como base, con la cifra de ahorro de A y las barras de B en la ficha**

La propuesta distintiva del radar es *ver cuánto se ahorra y cuándo cambió el precio*, y el tablero C lo da sin un clic, con la
densidad de un comparador útil (24 productos en una pantalla). Es también la que mejor sirve al uso repetido. A es la más
elegante pero enseña 3–4 productos por pantalla; B luce en portafolio, pero la foto ocupa lo que debería ocupar la comparación
y su foto depende de CDN ajenos (hotlink, puede romperse). Concreto: portada = C; ficha de producto = barras a escala de B (comparan mejor que
una tabla de 4 números); titulares y cifra héroe estilo A en la parte alta. El fucsia funciona en las tres.

Decisión tipográfica: **Space Grotesk (display/UI) + JetBrains Mono (cifras)**, como el Landing: da identidad compartida y las cifras en mono
tabular alinean las columnas. Coste: dos fuentes variables más (orden de magnitud 30–50 KB cada una en `woff2` latín, **estimado, sin medir**) frente a
Inter, que ya está. Mitigación: subconjunto latino, `font-display: optional` como en `global.css`, y precarga de la de display. Si
el presupuesto Lighthouse móvil ≥ 90 se resiente, el plan B es Space Grotesk solo en titulares y mono con la pila del sistema (`ui-monospace`), que ya es el respaldo en `tokens.css`.
Mientras no estén instaladas, el laboratorio muestra **Inter** (ya instalada) y la pila del sistema para mono.

## NO VERIFICADO (sin build en el nodo)

- Que `astro build` / `astro dev` compile: ninguna página se ejecutó. Riesgos concretos a mirar primero: `<style is:global>` colocado tras `</html>` en `Lab.astro`;
  `onerror="this.remove()"` como atributo de cadena en `portada-b`; `textLength` en el `<text>` del wordmark (el ancho 154 es una estimación de cómo ocupa «Radar de Precios» a 19 px).
- Que `public/data/` exista: `leerDatos` lee de ahí; hay que correr `npm run datos` (lo hace `npm run dev`).
- Que `hist/<slug>.json` exista para cada producto de la portada C (hay try/catch: si falta, «Sin historial»).
- Aspecto real: alineación de las filas de barras (columna del logo de 6 rem), proporciones del sparkline, acabado en móvil de 390 px, colisión de la cabecera sticky.
- Contrastes: calculados a mano, no medidos; falta `--muted` sobre `--surface` y el Mifarma oscuro.
- Fuentes: `@fontsource-variable/space-grotesk` y `…/jetbrains-mono` **pendientes de instalar**; las dos líneas `import` están comentadas en `Lab.astro` (si no, el build fallaría).
- Tipos: no se corrió `tsc`; las claves `lab.*` están en ambos JSON con las mismas llaves.
- La vista `:root.light` y el guardado en `localStorage` no se probaron en navegador.
- Textos EN: revisados por lectura, no por un hablante nativo.

## Para capturar en Windows

```
cd web-v2
npm install
npm i @fontsource-variable/space-grotesk @fontsource-variable/jetbrains-mono   # luego descomentar los 2 import en src/layouts/Lab.astro
npm run dev -- --port 4321
```

Rutas (1440 y 390 px, claro y oscuro con el botón de tema, ES y EN) → guardar en `docs/img/lab-c1/`:

```
http://localhost:4321/es/lab/portada-a/   http://localhost:4321/en/lab/portada-a/
http://localhost:4321/es/lab/portada-b/   http://localhost:4321/en/lab/portada-b/
http://localhost:4321/es/lab/portada-c/   http://localhost:4321/en/lab/portada-c/
```

(`RADAR_BASE` no definido → base `/`; si se define, antepóngalo a las rutas.)
