# Matching — cómo se decide que dos ofertas son el mismo producto (F3)

## 1. Definición

**Una fila del radar es el mismo producto registrado: misma marca, mismo laboratorio,
mismo registro sanitario (R.S.) DIGEMID, misma presentación.** No es un equivalente
terapéutico. Un paracetamol 500 mg genérico de otro laboratorio no va en la fila del
paracetamol de marca, aunque cure lo mismo.

Consecuencias:

- Un falso positivo (dos productos distintos en la misma fila) es peor que un "—".
- Los productos con el mismo activo, concentración, forma y cantidad pero otro R.S. se
  guardan aparte como `equivalente` (§5). No son precio de la fila.

## 2. Ficha canónica (`core/ficha.py`)

Cada oferta se lleva a una ficha: activos, concentración, forma, cantidad + unidad,
laboratorio, marca, R.S., EAN, foto (pHash + dHash). Cada campo guarda su fuente:
`atributo` (campo estructurado de la API) > `descripcion` (texto de la ficha) >
`nombre` (se deduce del nombre). Un atributo manda sobre el nombre.

El R.S. se normaliza a `LETRAS-DIGITOS` (`DE-0340`). Para comparar se quitan los ceros a
la izquierda (`DE-340`). Fuentes por cadena:

| Cadena | De dónde sale el R.S. | Cobertura (corrida 2026-09-25) |
|---|---|---|
| Inkafarma / Mifarma | texto del detalle ("Registro Sanitario …") | 104/224 detalles (los de receta no lo traen) |
| Universal (VTEX) | especificación "Registro Sanitario" | 729/730 |
| Boticas Perú | QuickView, pedido solo para candidatos (§4) | 109/139 |

Si un texto trae dos R.S. distintos (packs), no se toma ninguno.

## 3. Capas (`core/matcher.py` + `pipeline/build_snapshot._candidatos`)

Antes del matcher, dos compuertas: cantidad exacta del envase (10 % de tolerancia,
misma unidad) y precio plausible (entre 1/3 y 3 veces el de Inkafarma).

| Capa | Regla | Resultado |
|---|---|---|
| 1 | mismo `objectID` InRetail · mismo EAN | 100, `id` / `ean` |
| 1b | antes del R.S.: etapa/talla ("recién nacido" en un solo lado; tallas si ambos declaran), variante de fórmula (`dia`/`noche`, `forte`, `advance`, `flex`, `triplesure`…), envase sobre ≠ blíster (sufijo del SKU de Boticas) | 0, `regla_dura` |
| 1 | mismo R.S. **y** misma cantidad | 100, `registro_sanitario` |
| 1 | R.S. distinto en ambos lados | 0, veto (`VETO_RS = "estricto"`) |
| 2 | reglas duras: concentración, forma (`aceite` ≠ `gel`), pediátrico, variante, marca distinta con núcleo genérico ("aspirador nasal", "termómetro digital"…) | 0, `regla_dura` |
| 2 | laboratorio distinto, si ambos lados resuelven a un laboratorio conocido (marca/`brand`, nombre, siglas de Universal, o su R.S. en el mapa R.S.→laboratorio de la corrida) | 0, `laboratorio` |
| 3 | score por texto (núcleo pesa más que el nombre): ≥ 85 casa; 70–85 casa con `revisar` **si el candidato nombra la marca de la referencia**; foto idéntica (≤ 6 bits) sube a match | `fuzzy` / `imagen` |
| 4 | `tests/matches_curados.yaml`: pares decididos a mano | manda sobre todo, `curado` |

**Uno a uno (`_asignar`).** Cada fila junta sus candidatos aceptables; luego, por
cadena, todos los pares (fila, SKU) se ordenan por fuerza de evidencia (curado > id/EAN >
R.S. > texto ≥ 85 o foto > zona gris) y score, y se aceptan en ese orden saltando filas y
SKUs ya tomados (greedy; no húngaro). Las filas InRetail del mismo producto (mismo R.S. o
EAN, misma presentación y cantidad) forman un grupo y comparten el cruce. Resultado: un
SKU nunca queda en dos filas distintas.

Cada cruce guarda su evidencia (R.S. de ambos lados, cantidades y su fuente, score de
texto, veredicto de imagen, ratio de precio, motivo en una frase) en `matches.parquet`
y en `data.json` (`docs/ESQUEMA_DATOS.md`).

## 4. Imagen: confirma, no veta

pHash y dHash se calculan una vez por URL y se cachean en `RAW_DIR/imagenes/`. Se
piden solo para candidatos que pasan cantidad y precio con texto ≥ 60.

Calibración sobre la corrida 2026-09-25:

- Pares al azar (productos distintos): percentil 1 de pHash = 18, de dHash = 11.
- Pares con el mismo R.S. entre cadenas (el mismo producto): pHash de 2 a 34. Cada
  cadena fotografía distinto (frasco vs caja, fondo, ángulo).

Por eso una foto muy parecida (≤ 6) sí prueba identidad, pero una foto "claramente
distinta" no prueba nada. `VETO_IMAGEN = False`: la imagen solo confirma. Con el veto
encendido Boticas caía de 109 a 74 cruces, casi todos buenos.

## 5. Equivalentes

Si un candidato cae **solo** por R.S. o laboratorio distinto, se vuelve a comparar sin el R.S. Si así
casaría con fuerza (≥ 85 o foto idéntica), se guarda como `tipo = "equivalente"` en
`matches.parquet` y en `data.json → equivalentes`, con su nombre, precio y enlace.

No entra en `precios` ni en el ahorro. Es la semilla de una vista futura
"alternativas con el mismo principio activo". El umbral es alto a propósito: con 70,
Supradyn Energy (otra fórmula, texto 72) salía como equivalente de Supradyn.

## 6. Curados (`tests/matches_curados.yaml`)

Para pares de la misma marca y laboratorio cuyo R.S. aparece renumerado en una cadena
(Panadol Niños tiene tres R.S. vigentes en distintas cadenas). Criterio para curar un
`match`: misma marca, laboratorio, concentración, forma y cantidad, precio alineado.
Nunca se curan genéricos de otro laboratorio: esos son equivalentes. `decision: veto`
bloquea un par que el matcher aceptaría.

Cada entrada lleva motivo y fecha de revisión. La regresión cubre la ruta real
(`CURADO_Y_EQUIVALENTE` en `tests/test_matcher_regresion.py`).

## 7. Riesgos conocidos

- **R.S. cruzado en Boticas.** Tapsin Plus Día y Noche muestran el R.S. de la otra en su
  QuickView. Desde el 2026-09-26 la variante (día/noche) se compara antes del R.S., así
  que la Noche ya no casa con la Día; la Día correcta de Boticas queda como equivalente
  (`docs/revision/F3_final.md` §5).
- **El laboratorio se deduce, no se lee.** InRetail no trae laboratorio (a veces la
  `marca` lo es), Boticas tampoco. Si la marca de InRetail está mal (Diclofenaco 268175:
  marca PORTUGAL, EAN de Farmindustria) el veto deja un "—". El mapa R.S.→laboratorio es
  por corrida: si la fila que lo aporta no sale ese día, no se conoce.
- **El uno a uno reparte, no adivina.** Dos filas InRetail del mismo producto sin R.S. ni
  EAN no se agrupan: compiten y una se queda en "—" o con el SKU de otro envase.
- **Cambio de SKU cruzado = evento falso.** Si un cruce cambia de SKU entre dos
  corridas, `pipeline/cambios.py` ve una subida o bajada que no pasó. Pasará en la
  primera corrida tras el merge de F3.
- **Sin `match_id` estable** todavía: el cruce se identifica por
  (producto_id, cadena, sku_cadena).
- El QuickView de Boticas agrega requests a la corrida diaria (uno por candidato con
  texto ≥ 60, ~140) y las fotos nuevas se bajan una vez.

## 8. Cómo cambiar el matcher

Todo cambio en `core/matcher.py`, `core/normalizer.py` o `core/ficha.py` agrega casos a
`tests/test_matcher_regresion.py` y la deja en verde:

```
PYTHONIOENCODING=utf-8 py -m tests.test_matcher_regresion
```

Luego se reprocesa la última corrida desde caché y se revisan a mano los cruces que
cambian.
