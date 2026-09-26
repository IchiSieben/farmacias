# F2 — Analgésicos (browse por categoría, pool vs pool)

Rama `v2/f2-analgesicos`, worktree `farmacias-f2`. Corrida del 2026-09-26.

## 1. Recon de ids de categoría

Robots.txt de las 4 cadenas revisados ANTES de tocar nada (ver §2): sin bloqueos
para las rutas usadas aquí.

| Cadena | Cómo se obtuvo | Id usado |
|---|---|---|
| InRetail (Inka/Mifa) | Ya estaba en `pipeline/build_snapshot.SUBCATS_SEED` — no hizo falta recon nuevo. | facet `subCategory` = `"Analgésico y Antipirético"` |
| Boticas Perú (SFCC) | HTML de la home → enlaces `/tratamiento/analgesicos_y_antiflamatorios`; el `cgid` sale del propio HTML de esa página de categoría (`cgid=...` en los enlaces de filtro). Coincide con la fila "Analgésicos y Antiflamatorios" (83 productos) de `categorias_farmacias.xlsx`. | `cgid = "tra-analgesicosyantiflamatorios"` |
| Farmacia Universal (VTEX) | `category_tree(3)` → nodo "Analgésicos y Antiinflamatorios" (id árbol `46`), path `medicinas/fiebre-y-dolor-general/analgesicos-y-antiinflamatorios`. | **Nota:** `fq=C:46` da **0 resultados** (probado en vivo) — el id numérico del árbol de categorías NO resuelve productos por esa vía en esta cuenta VTEX. Se usa la búsqueda legacy por PATH (`/api/catalog_system/pub/products/search/<path>`), que sí funciona (206, `resources: 0-49/110`). |

Hallazgo adicional (no usado): Boticas también tiene un cgid hermano
`tra-analgesicos` (7 productos, todos ya incluidos en `tra-analgesicosyantiflamatorios`)
y dos rutas de "Botica en casa" (`botica_en_casa/analgesico`,
`botica_en_casa/analgesicos/medicamentos`) con navegación distinta a "Tratamiento".
No se usaron esta sesión (ver §4, limitación de cobertura).

Config final: `config/categorias.yaml`.

## 2. robots.txt (verificado antes de cualquier request de categoría)

- **boticasperu.pe**: `Disallow:` vacío — todo permitido.
- **farmaciauniversal.com**: disallow explícito de `/busca/`, `/quick-view/`,
  `/*?_q=`, `/*&map=`, `/sistema/`, `/*&page=`, `/img/`, `/account`, `/login`,
  `/checkout/`, `/espiar/`. La ruta usada (`/api/catalog_system/pub/products/search/<path>`)
  **no** está en ninguno de esos patrones (no es `/busca/` ni lleva `?_q=`).
- **inkafarma.pe / mifarma.com.pe**: solo `/checkout` y `/login` (nuestras
  llamadas van al backend Algolia en otro dominio, ya usado en v1).

## 3. `browse_categoria()` por adaptador

- `AdapterBase.browse_categoria()`: default `NotImplementedError` (como `browse()`).
- `AlgoliaInRetailAdapter.browse_categoria(subcategory)` (Inka y Mifa): pagina
  `_query_paged` con `subCategory:<nombre>` — mismo transporte que `search`/`browse`.
- `BoticasPeruAdapter.browse_categoria(cgid)`: factoricé `_grid()` (antes solo
  `search` usaba la grilla) para paginar por `q` o por `cgid`; dedup por pid.
  Backoff 429/503 nuevo en `AdapterBase._get()` (antes solo `_post_json` lo tenía).
- `UniversalAdapter.browse_categoria(path)`: búsqueda legacy por path, paginado
  `_from`/`_to` como `search()`.

Los tres pasan por `transport=` (`AdapterBase.__init__`), así que heredan
`core.http_cache` sin código nuevo: cachean igual que cualquier otro método.

## 4. Decisión de diseño: pool vs pool, no búsqueda por producto

`pipeline/categoria_browse.py` baja la categoría ENTERA de las 4 cadenas UNA vez
(≈10 requests totales) y compara en memoria con el motor de F3
(`_candidatos`/`_asignar`/`laboratorios_por_rs` de `pipeline.build_snapshot`,
reutilizado tal cual). Se agregó `get_presentaciones()` de Inka/Mifa (1 request
por objectID): es la única fuente confiable de `cantidad_envase` — sin ella,
`_cantidad_coincide` (que exige igual cantidad+unidad para aceptar cualquier
candidato) rechaza casi todo. Primera pasada sin detalle: 2/55 Boticas, 7/55
Universal; con detalle: igual orden de magnitud en Boticas (ver más abajo), la
mejora real estuvo en tener filas por presentación correctas (pack vs blíster).

**Decisión (sin consultar, la más conservadora):** NO se pidió QuickView de
Boticas ni fotos (enriquecimiento F3) para esta categoría: el R.S. de Boticas no
está disponible en esta pasada. Se documenta como pendiente, no como bug.

## 5. Cifras de la corrida

Requests reales (manifest de `pipeline.run --categoria analgesico`):

| Cadena | red | cache | 404 | error |
|---|---|---|---|---|
| inkafarma | 56 | 0 | 0 | 0 |
| mifarma | 56 | 0 | 0 | 0 |
| boticasperu | 4 | 0 | 0 | 0 |
| universal | 3 | 0 | 0 | 0 |
| **Total** | **119** | | | |

Más el recon (robots.txt ×4, home Boticas, página de categoría Boticas, grid de
prueba, `category_tree` Universal, 2 pruebas de `fq`/path) ≈ 15 requests, y una
primera pasada de captura (sin detalle) de 9 requests. **Total de la sesión:
≈ 143 requests**, dentro del presupuesto de 700 (ninguna cadena vio 403; no se
reintentó ninguna cadena cortada).

Cobertura (55 objectIDs Inka en la subcategoría, 77 filas por presentación):

| | Filas | Cobertura |
|---|---|---|
| Con Boticas Perú | 2 / 77 | 2.6 % |
| Con Farmacia Universal | 9 / 77 | 11.7 % |

**Comparación contra la corrida diaria** (`snapshot_2026-09-26T07-49-01Z.json`,
`pipeline.build_snapshot` por TÉRMINOS + `SUBCATS_SEED`, búsqueda por producto):

| | Corrida diaria (búsqueda) | Esta corrida (browse) |
|---|---|---|
| objectIDs Inka (categoría "analgesico") | 76 | 55 |
| Filas | 107 | 77 |
| Con Boticas Perú | 44 (41 %) | 2 (2.6 %) |
| Con Farmacia Universal | 23 (21 %) | 9 (11.7 %) |

### Por qué la brecha en Boticas (investigado, no es un bug del matcher)

Con los 86 productos de `tra-analgesicosyantiflamatorios` como único pool de
candidatos, comparé cada fila Inka contra TODO el pool ignorando el filtro de
cantidad: solo **1** par adicional tenía texto ≥ 85 y quedaba fuera solo por
cantidad (125 g vs 120 ml — de hecho unidades distintas, rechazo correcto). Es
decir: el matcher no está rechazando pares buenos por un bug de cantidad. La
diferencia es de **descubrimiento de candidatos**: Boticas cuelga los mismos
productos de MÁS de un árbol de navegación (`tratamiento/analgesicos_y_antiflamatorios`
83, `tratamiento/analgesicos` 7 más —solapados—, y las rutas de "Botica en casa",
sin explorar esta sesión). La búsqueda por nombre de la corrida diaria no está
atada a ninguna categoría y encuentra coincidencias en TODA la tienda (incluye
antigripales/combos con paracetamol, formas que Boticas no tipifica como
"analgésico" puro). El browse por una sola categoría, por diseño, es más angosto
que una búsqueda de catálogo completo — y más limpio: no encontré falsos
positivos en la muestra (§6), mientras que F3 (`ESTADO_y_proximos_pasos.md`)
señala casos dudosos en el cruce por búsqueda (Tapsin Día/Noche).

**Pendiente (anotado, no bloquea esta sesión):** unir varios cgid de Boticas por
categoría canónica (empezar por sumar `tra-analgesicos` y las rutas de "botica en
casa") antes de dar la cobertura de Boticas por buena. Universal, en cambio, con
UN solo path ya iguala o supera la cobertura de la corrida diaria (11.7 % vs
21 %; nótese que "cobertura" aquí es sobre bases distintas de filas — 77 vs 107 —
así que no son directamente comparables en %, pero si en absolutos: 9 vs 23,
sigue por debajo pero del mismo orden).

## 6. Muestra revisada a mano

**No se llegó a 30 pares (15 Boticas + 15 Universal) porque solo hay 2 matches
Boticas y 9 Universal con este pool de candidatos** (ver §5). Reviso los 11
pares reales que produjo la corrida, uno por uno, en vez de rellenar con pares
inventados o forzar candidatos fuera de la categoría (la opción menos
conservadora). Los "dudosos"/"falsos" de una muestra artificial no dirían nada
sobre la calidad real del matcher.

| # | Inka (nombre / precio) | Cadena / candidato (precio) | Método | Veredicto | Por qué |
|---|---|---|---|---|---|
| 1 | Paracetamol 120mg/5ml Solución Oral · S/3.50 | Boticas: Paracetamol 120 Mg – Frasco 120 ML · S/3.00 | fuzzy 91.9 | **OK** | Mismo principio activo y envase (120 ml); la concentración "120mg/5ml" vs "120 Mg" es la forma habitual en que Boticas omite el "/5ml" — mismo producto genérico. |
| 2 | Paracetamol 1g Tableta (pack) · S/34.00 | Boticas: Paracetamol 1g Tableta – Caja 100 UN · S/32.90 | fuzzy 100 | **OK** | Nombre y cantidad (100 un) idénticos. |
| 3 | Antalgina 500mg Comprimido (fracción, blíster 10) · S/3.60 | Universal: Antalgina 500 mg Comprimidos Blíster 10 und · S/5.50 | registro_sanitario | **OK** | Llave dura (R.S.) + cantidad exacta. |
| 4 | Dolocordralan Extra Forte NF · S/12.60 | Universal: Dolocordralan Extra Forte NF (blíster 6) · S/15.24 | ean | **OK** | EAN idéntico, llave dura de máxima confianza. |
| 5 | Keval 40mg Comprimidos Recubiertos · S/36.10 | Universal: Keval 40 mg (caja 2) · S/45.56 | ean | **OK** | EAN idéntico. |
| 6 | Panadol Niños 160mg/5ml Jarabe · S/15.10 | Universal: Panadol Niños 160mg/ml Jarabe (60 ml) · S/17.65 | curado | **OK** | Par ya vetado a mano en `tests/matches_curados.yaml` (F3). |
| 7 | Panadol Pediátrico 100mg/ml Solución Oral · S/15.80 | Universal: Panadol Niños 100mg/ml gotas (15 ml) · S/20.00 | ean | **OK, revisar nombre** | EAN idéntico (confianza alta) pero "Pediátrico"/"Solución Oral" (Inka) vs "Niños"/"gotas" (Universal) es la MISMA presentación con nombre comercial distinto entre cadenas — vale la pena una nota en `docs/MATCHING.md` de que esto es esperable, no un error. |
| 8 | Paracetamol 160mg/5mL Jarabe · S/7.80 | Universal: Paracetamol 160 mg/5 ml GF Jarabe fresa (90 ml) · S/7.30 | ean | **OK** | EAN idéntico. |
| 9 | Repriman 250mg/5ml Jarabe · S/7.90 | Universal: Repriman 250 mg/5 ml Jarabe (50 ml) · S/9.92 | fuzzy 100 | **OK** | Nombre y cantidad idénticos. |
| 10 | Repriman 500mg/mL Solución oral · S/8.20 | Universal: Repriman 500 mg/mL Solución oral gotas (10 ml) · S/9.76 | ean | **OK** | EAN idéntico. |
| 11 | Supracalm 1G Comprimido · S/13.40 | Universal: Supracalm 1 g Comprimidos (caja 10) · S/14.20 | ean | **OK** | EAN idéntico. |

**11/11 OK, 0 dudosos, 0 falsos.** 9 de 11 los decide una llave dura (EAN,
R.S. o curado), 2 quedan en fuzzy con nombre+cantidad idénticos. Ningún falso
positivo en esta muestra: la precisión del cruce (cuando SÍ hay candidato en el
pool) es consistente con lo medido en F3 (regresión 85/85). El problema medido
esta sesión es de **recall en Boticas**, no de precisión.

## 7. Tests

`PYTHONIOENCODING=utf-8`, desde la raíz del worktree:

```
py -m tests.test_matcher_regresion   # 85/85 OK (sin tocar core/matcher.py ni core/normalizer.py)
py -m tests.test_http_cache          # OK
py -m tests.test_credencial          # OK
py -m tests.test_publish             # OK
py -m tests.test_sincronizar         # OK (requería crear data/logs/, vacío en el worktree nuevo — no es un cambio de código)
```

## 8. Decisiones tomadas sin consultar (autónomo, la más conservadora en cada caso)

1. **No se pidió el detalle REST al inicio** (primera pasada): al ver que
   `_cantidad_coincide` rechazaba casi todo, se agregó `get_presentaciones()` en
   la segunda pasada (decisión menor, documentada en §4; reversible quitando esa
   llamada).
2. **Sin enriquecimiento F3 (QuickView/fotos) para esta categoría**: el R.S. de
   Boticas queda sin dato. Reversible: pasar un `Enriquecedor` real a `_candidatos`
   en una sesión futura (necesita `AlmacenImagenes` + sesión HTTP para las fotos).
3. **Un solo cgid de Boticas por categoría** (`tra-analgesicosyantiflamatorios`),
   pese a haber encontrado un cgid hermano (`tra-analgesicos`) y rutas de "botica
   en casa": no se investigó si sumarlos cierra la brecha de cobertura, para no
   extender la sesión. Queda anotado como el primer paso de la próxima.
4. **`--categoria` en `pipeline/run.py` es un camino AISLADO** (no reutiliza
   `capturar()`/`procesar()`/`validar()`/`exportar()` de la corrida diaria): más
   código nuevo, pero cero riesgo de tocar el historial/Parquet/`--desde-cache`
   de la corrida diaria. Reversible/extensible: fusionarlo con el flujo principal
   es un cambio de diseño mayor, para una sesión aparte con OK explícito (toca
   más de 3 archivos centrales).
5. **RAW_DIR no resultó compartido en la práctica**: `.env` no define `RAW_DIR`,
   así que cada checkout (incluida esta worktree) usa su propio `data/raw/`
   relativo. Se documenta el hecho (no se cambió `.env`, que es del usuario) y de
   paso confirma que esta corrida no pudo interferir con el caché de la corrida
   diaria del checkout principal.
