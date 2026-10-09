---
kind: claude
push: true
---
# TASK-c1-identidad — identidad visual del Radar de Precios y tres portadas de laboratorio

Rama base: `origin/v2/f4-ui` (app Astro 7 + islas React + Tailwind 4 en `web-v2/`). Tu worktree
ya está creado por enjambre; no cambies de rama ni toques `main`. Nada de esto se publica: son
propuestas en `/lab/` que el dueño compara en capturas antes de aplicar nada al sitio real.

## Lo que puedes ejecutar (léelo antes de empezar)

Tu allowlist es **Read, Edit, Write, Glob, Grep, `git status`, `git diff`, `ls`**. No hay
`npm`, `node`, Playwright ni Lighthouse en este nodo para ti: cualquier otro comando se deniega y
cada denegación acorta el trabajo. No lo intentes. Escribe el código con cuidado (Astro 7, React 19,
Tailwind 4 vía `@tailwindcss/vite`; mira `web-v2/package.json`, `astro.config.mjs` y los componentes
existentes para imitar el estilo) y en el reporte marca como **NO VERIFICADO (sin build en el nodo)**
todo lo que no pudiste comprobar. El build, las capturas Playwright (1440 y 390 px, claro y oscuro,
ES y EN, en `docs/img/lab-c1/`) y el contraste medido se harán en Windows al recoger tu rama.
No tienes reloj: escribe `docs/lab/C1-REPORTE.md` en versión 1 **pronto** y amplíalo al final;
el trabajo termina cuando se agote el presupuesto, con lo que haya en disco. El supervisor hace el
commit por ti (`git add -A`): no necesitas ni puedes hacer `git commit`.

## Qué construir

1. **`web-v2/src/styles/tokens.css`** — tokens como custom properties: color, tipografía (escala
   modular, pesos, line-height), espaciado (escala de 4 px), radios, sombras y animación (duraciones
   y easings). Dos temas **reales**: oscuro por defecto y claro con `:root.light` (misma convención
   que el Landing). Hereda los tokens del Landing de ichisieben.dev, que son estos:

   | token | oscuro (por defecto) | claro (`:root.light`) |
   |---|---|---|
   | `--bg` | `#0D1117` | `#FFFFFF` |
   | `--surface` | `#161B22` | `#F6F8FA` |
   | `--border` | `#30363D` | `#D0D7DE` |
   | `--fg` | `#E6EDF3` | `#1F2328` |
   | `--muted` | `#8B949E` | `#59636E` |
   | `--accent` (teal) | `#2DD4BF` | `#0D9488` |
   | `--accent-strong` | `#2DD4BF` | `#0F766E` |

   El Landing los guarda como tripletas RGB (`--bg: 13 17 23;`) para usar `rgb(var(--bg) / α)`;
   usa la misma técnica. Tipografías del Landing: **Space Grotesk** (display/UI) y **JetBrains Mono**
   (cifras y código). El `web-v2` ya trae `@fontsource-variable/inter`: decide si el radar usa
   Space Grotesk como el Landing (recomendado, es la identidad) y deja la decisión y su coste en
   el reporte; no añadas paquetes (no hay `npm install`): si hace falta `@fontsource-variable/space-grotesk`,
   escribe el `import` y anótalo como pendiente de instalar.
2. **Toggle de tema persistente**: script inline mínimo (sin framework) que lee `localStorage`
   (guardado con try/catch), aplica `:root.light` antes del primer render y escucha el botón.
   Ponlo en un layout nuevo **`web-v2/src/layouts/Lab.astro`** que importe `tokens.css`; **no
   toques `Base.astro`** ni las páginas existentes.
3. **Wordmark SVG propio** (`web-v2/src/components/Wordmark.astro` + `web-v2/public/wordmark.svg`):
   el nombre "Radar de Precios" dibujado como texto en paths o con tipografía del sistema con
   fallback, más una marca geométrica pequeña (arcos de radar, aro, barra… tu propuesta). **Fuera el
   emoji 📡**: en las páginas de `/lab/` no aparece.
4. **Color y logo fijos por cadena**: define en `tokens.css` `--cad-inkafarma`, `--cad-mifarma`,
   `--cad-boticasperu`, `--cad-universal` tomando los colores de los logos que ya existen en
   `web-v2/public/logos/` y `web-v2/src/components/LogoCadena.tsx`. Inkafarma es verde: por eso
   **el acento de "más barato" NO puede ser verde** (ni teal que se confunda). Propón un acento propio
   (ámbar, coral, magenta…) con contraste **AA** sobre `--bg` y `--surface` en ambos temas; pon en el
   reporte los ratios calculados a mano (fórmula WCAG) para texto normal y para el badge.
5. **Tres portadas**, rutas bilingües bajo `web-v2/src/pages/[lang]/lab/` (usa `src/i18n/` para los
   textos; cada una con `Lab.astro`, datos reales de `web-v2/src/lib/datos.ts`, máximo ~24 productos):
   - `portada-a.astro` — **editorial y sobria**: tipografía grande, mucho aire, una columna, cifras
     en mono, sin tarjetas.
   - `portada-b.astro` — **tarjetas con foto grande** y **barras de precio a escala** (la barra de
     cada cadena proporcional al precio máximo de la fila, con color de cadena y logo).
   - `portada-c.astro` — **tablero denso** con filas compactas y **sparkline** del historial por
     producto (SVG inline; mira `SvgHistorial.astro` y `src/lib/historial.ts`).
   Tienen que ser distintas de verdad (estructura, densidad, jerarquía), no tres tonos del mismo azul.
6. **`docs/lab/C1-REPORTE.md`** (en español): qué hiciste, tabla de tokens, acento elegido con sus
   ratios, cómo se ve cada portada (descripción, porque no hay captura), **tu recomendación** y por
   qué, lo que queda NO VERIFICADO y el comando exacto para capturar en Windows
   (`npm run dev -- --port 4321` y las rutas `/es/lab/portada-a` …).

## Files you may touch

- `web-v2/src/styles/tokens.css` (nuevo), `web-v2/src/layouts/Lab.astro` (nuevo)
- `web-v2/src/components/Wordmark.astro` (nuevo), `web-v2/public/wordmark.svg` (nuevo)
- `web-v2/src/pages/[lang]/lab/portada-{a,b,c}.astro` (nuevos)
- `web-v2/src/i18n/es.json`, `web-v2/src/i18n/en.json` (solo añadir claves `lab.*`)
- `docs/lab/C1-REPORTE.md` (nuevo)
- Prohibido: `web-v2/src/layouts/Base.astro`, `web-v2/src/pages/index.astro`, las páginas existentes
  de `[lang]/`, `web/`, `web/data/`, `pipeline/`, `core/`, `tests/`, `package.json`, `main`.

## Done criteria

- Existen los archivos nuevos listados y ningún archivo prohibido cambió (`git status`).
- `tokens.css` define los dos temas con los valores del Landing y los cuatro colores de cadena.
- El acento de "más barato" no es verde y el reporte trae sus ratios de contraste (≥ 4.5:1 texto,
  ≥ 3:1 componentes) en ambos temas.
- Ninguna página de `/lab/` contiene el emoji 📡 (`grep -rn "📡" web-v2/src/pages/*/lab` vacío).
- `docs/lab/C1-REPORTE.md` existe, con recomendación y la lista de lo NO VERIFICADO.
