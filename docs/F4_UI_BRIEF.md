# F4 — Brief de la interfaz v2

> Complementa `V2_PLAN.md` §F4. Esto es lo que "profesional" significa en concreto.
> Se trabaja en la rama `v2/f4-ui`, en un worktree aparte, en paralelo a F1.
> Solo depende del contrato de datos (§4), no del data lake.

## 1. Qué está mal en la v1 (y qué no)

La v1 es una tabla correcta y legible. Lo que le falta no es corrección, es producto:
no muestra el producto (sin foto), no muestra a quién compara (sin logos), no le dice
al usuario qué hacer (brecha en % en vez de ahorro en soles), mezcla filtros de
analista con filtros de persona, y no tiene una ficha por producto ni historial.
El rediseño conserva todo lo que la v1 calcula bien y cambia cómo se presenta.

## 2. Stack y despliegue

- **Astro** (salida estática) + **islas React** para lo interactivo (buscador, tabla,
  gráfico, selector de idioma). Tailwind. Sin servidor: el `dist/` se sube tal cual a
  Hostinger en `/radar-precios/` con `pipeline/publish.py` (misma URL, no se rompe).
- i18n nativo de Astro: `/radar-precios/es/…` y `/radar-precios/en/…`; la raíz
  redirige según `navigator.language` con toggle persistente (localStorage).
- Fuentes: una sola familia variable (Inter o similar) self-hosted. Nada de CDN de
  terceros salvo las imágenes de producto.
- Tema claro/oscuro por `prefers-color-scheme` con toggle.
- Presupuesto: Lighthouse móvil ≥ 90 en rendimiento y accesibilidad; JS inicial
  < 150 KB gz; `index.json` < 300 KB gz.

## 3. Identidad visual

### Logos de cadenas — regla dura
**No se dibujan ni se reconstruyen.** Se descargan los activos oficiales que cada
cadena sirve en su propio sitio (favicon de alta resolución, `og:image`, o el logo del
header) con `scripts/bajar_logos.py`, se guardan en `web/public/logos/<cadena>.{svg,png}`
y se usan tal cual, con el aviso de no afiliación que ya existe. Si un archivo falta o
falla, fallback a un monograma (letra inicial) sobre el color de la cadena. Si un logo
oficial no se puede obtener limpiamente, se usa el monograma y punto — nunca una
imitación.

Colores de cadena (para bordes, monogramas, series del gráfico): tomar el color
dominante del logo oficial descargado; no inventarlos. Grupo InRetail comparte matiz
(Inkafarma/Mifarma se distinguen por tono), Boticas y Universal tienen el suyo.

### Fotos de producto
- Fuente: campo `imagen` de cada oferta en los snapshots (CDN de la cadena). Se
  enlazan, no se descargan. `loading="lazy"`, `referrerpolicy="no-referrer"`,
  tamaño fijo para evitar saltos de layout, placeholder neutro si falla.
- Se muestra una miniatura por producto (la de la cadena más barata) en la lista, y
  todas las fotos por cadena en la ficha (útil para ver que el matcher acertó).

## 4. Contrato de datos (`web/data/`, generado por `pipeline/export_web.py`)

Definirlo primero; F1 y F4 lo comparten. Versión de esquema en cada archivo.

```
web/data/
├── meta.json         # generado, snapshot, cadenas[{id,nombre,grupo,color,logo}], categorias[], kpis
├── index.json        # lista liviana para buscar: [{id, nombre, activo, marca, cat, pres,
│                     #   precios{cad:num}, ppu{cad:num}, ahorro{soles, pct, en}, imagen, promos[]}]
├── cat_<cat>.json    # mismo esquema que index, completo por categoría (para paginar)
├── hist_<id>.json    # [{fecha, precios{cad:num}, promos{cad:bool}}] por producto
└── kpis.json         # por cadena y categoría: % más barata, brecha media vs líder, promos activas
```

`ahorro` = precio_máx − precio_mín en soles, `en` = cadena más barata. Es la métrica
principal en la lista. `brecha_pct` sigue existiendo para Panorama y para "más filtros".

Mientras F1 no exporte esto, `export_web.py` lo genera desde `web/data.json` +
`data/snapshots/*.json` actuales (las imágenes están en los snapshots).

## 5. Pantallas

### 5.1 Inicio / buscador (`/`)
- Cabecera compacta: nombre, subtítulo, fecha del snapshot, toggle ES/EN y tema.
- Buscador prominente con búsqueda instantánea (Fuse.js sobre `index.json`) por
  nombre, principio activo, marca y laboratorio. Sugerencias al escribir.
- Chips de categoría con conteo. Chips de cadena con logo (activar/desactivar).
- Un solo toggle visible: "Solo productos en todas las cadenas activas".
  "Más filtros" plegado: ahorro mínimo, posición de una cadena (más cara / más barata).
- Resultado en **tarjetas en móvil** y **tabla en escritorio**, con el mismo componente:
  miniatura · nombre · presentación · [logo] precio por cadena (mejor resaltado) ·
  precio por unidad debajo · **"Ahorras S/ X en <cadena>"** · ▲▼ vs. captura anterior.
  Clic en el precio abre la ficha de la cadena; clic en el nombre abre la ficha interna.
- Orden por columna, URL con estado (`?q=&cat=&cad=`), estado vacío con sugerencias,
  esqueletos de carga. Descargar CSV/JSON del filtro actual.

### 5.2 Ficha de producto (`/p/<id>`)
- Foto(s), nombre canónico, activo, concentración, laboratorio, presentaciones
  agrupadas (blíster / caja / frasco como filas del mismo producto).
- Precio por cadena con logo y link, precio por unidad, ahorro en soles.
- **Gráfico de historial**: una línea por cadena, últimos 30/90 días, marcas de promo
  y de quiebre de stock. Recharts o similar; leyenda con logos.
- Eventos recientes: "Mifarma bajó 12 % el 3 de sept.", "Boticas inició promo…".
- Panel "¿Por qué se emparejó?": método (id, EAN, R.S., fuzzy + imagen) y evidencia.
  En v1 solo hay método; se muestra lo que haya.
- Botón compartir (copia URL). Meta tags OG con foto y precio mínimo.

### 5.3 Panorama (`/panorama`)
- Por cadena: % de productos donde es la más barata, brecha media vs. el líder,
  promos activas. Por categoría. Gráficos simples (barras), sin dashboards
  sobrecargados. Aquí vive la "brecha" con su explicación en una línea.

### 5.4 Metodología (`/metodologia`)
- Cómo se capturan los datos, cómo se emparejan (las capas), alcance y límites
  (sin cosmética, por qué), frecuencia, aviso de no afiliación, licencia. Bilingüe.

## 6. i18n
- Todo texto visible en `src/i18n/{es,en}.json`. Nada hardcodeado en componentes.
- Números y moneda con `Intl.NumberFormat('es-PE')` / `('en-US')` pero siempre en S/.
- Fechas relativas localizadas ("hace 2 días" / "2 days ago").
- El tutorial de apertura se mantiene, con los pasos en ambos idiomas.

## 7. Accesibilidad y detalle
- Contraste AA en ambos temas; foco visible; navegación por teclado en tabla y chips.
- La tabla usa `<th scope>` y `aria-sort`; las tarjetas son `<article>`.
- Colores de "más barato / más caro" acompañados de icono o texto, no solo color.
- Sin saltos de layout al cargar imágenes ni datos.

## 8. Orden de trabajo sugerido
1. `git worktree add ../farmacias-ui -b v2/f4-ui` y scaffold Astro en `web-v2/`
   (la `web/` v1 no se toca hasta el cambio final).
2. `pipeline/export_web.py` + `scripts/bajar_logos.py` (contrato §4, logos §3).
3. Inicio (5.1) con datos reales. Revisión visual contigo antes de seguir.
4. Ficha (5.2) con historial desde los snapshots existentes.
5. Panorama y Metodología. i18n completa. Lighthouse.
6. `publish.py` aprende a subir `web-v2/dist/` a `/radar-precios/`; se publica con
   confirmación explícita; `web/` v1 se archiva en una rama.
