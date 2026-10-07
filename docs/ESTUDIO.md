# Estudio — lo que enseña Radar de Precios

Cuatro conceptos, cada uno con el formato de ficha de la sección de estudio del portafolio:
qué es, por qué importa aquí, ejemplo real de este repo, error típico, para saber más.

---

# Resolución de entidades (*entity resolution*)

## Qué es

Decidir cuándo dos registros de fuentes distintas describen la misma cosa del mundo real, sin
una llave común. Se resuelve por capas: primero lo barato y seguro (identificadores), después lo
caro y dudoso (texto, imagen), y en cada capa reglas que **vetan** aunque el resto se parezca.

## Por qué importa aquí

Las cuatro cadenas no comparten catálogo. Inkafarma y Mifarma son del mismo grupo y comparten un
ID interno; Universal expone el EAN; Boticas Perú no expone ninguno de los dos. El producto
entero depende de cruzarlas bien: la tabla sin el matcher son cuatro listas sueltas.

## Ejemplo real

Corrida del 2026-10-06, cruces de Boticas Perú y Universal contra la fila de referencia, por
capa que decidió (`data/logs/run_2026-10-06T07-00-03Z.log`):

```
curado 6 · ean 47 · registro_sanitario 19 · fuzzy 69 · imagen 2 · (equivalente 20 = no es match)
```

El orden importa: un registro sanitario igual gana a un texto 100 % parecido
(`docs/DECISIONES.md`, punto 4). Detalle de cada capa en `docs/MATCHING.md`.

## Error típico

Confiar en el parecido del nombre. "Suprahyal" y "Mensille" (un ácido hialurónico y un
anticonceptivo) casaron en septiembre solo porque ambos nombres decían "inyectable" y "jeringa":
S/ 257,80 contra S/ 19,20, una brecha de 13×. Desde el commit `feef11d` esas palabras cuentan como
vía o dispositivo, no como principio activo, y hay una guarda de precio [1/3, 3] sobre todo cruce
difuso; el caso quedó en la regresión.

## Para saber más

- Christen, P. (2012). *Data Matching*. Springer. Capítulos 1 y 6.
- WDC Products, banco de pruebas de *product matching*: https://webdatacommons.org/largescaleproductcorpus/wdc-products/

---

# Precisión antes que exhaustividad (*precision over recall*)

## Qué es

En una clasificación con dos errores posibles, elegir explícitamente cuál es más caro. **Precisión**:
de los cruces que doy, cuántos son correctos. **Exhaustividad** (*recall*): de los cruces que
existen, cuántos encuentro. Subir una suele bajar la otra.

## Por qué importa aquí

Un cruce falso pone dos productos distintos en la misma fila y muestra un "ahorro" que no existe:
alguien podría comprar otra cosa por error. Un hueco ("—") solo pierde una comparación. Por eso
la regla del proyecto es "un falso positivo es peor que un —" (`CLAUDE.md`).

## Ejemplo real

Con el matcher v2 (F3) sobre la misma corrida grabada del 2026-09-26: Boticas pasó de 109 a 87
cruces y las filas con las cuatro cadenas de 54 a 42 (`NOTES_AUTONOMO.md`). Menos cobertura, a
propósito: se fueron cruces de otra marca, de otra etapa (Huggies Puro y Natural vs Recién Nacido) o de
otro laboratorio. El snapshot publicado antes del cambio mostraba una Desloratadina con +563 %
de brecha; el del 2026-10-06, ninguna por encima de +60 %.

## Error típico

Medir solo cobertura ("¿cuántos productos tienen las cuatro cadenas?") y optimizar ese número.
Sube fácil aflojando el umbral del texto, y cada punto que sube trae falsos positivos que nadie ve
hasta que un usuario los encuentra.

## Para saber más

- Precisión y exhaustividad: https://developers.google.com/machine-learning/crash-course/classification/accuracy-precision-recall

---

# Hash perceptual de imagen (pHash)

## Qué es

Una huella corta (64 bits) de una imagen que cambia poco si la imagen cambia poco: se reduce,
se pasa a grises, se aplica una transformada del coseno y se guarda qué coeficientes quedan sobre
la mediana. Dos fotos "iguales a la vista" quedan a pocos bits de distancia (Hamming), aunque
tengan otro tamaño o compresión.

## Por qué importa aquí

Las cadenas suelen usar la foto del fabricante. Si el texto deja un par en la zona gris, una foto
casi idéntica es evidencia extra barata: no hace falta red neuronal ni GPU.

## Ejemplo real

En la corrida del 2026-10-06 la imagen decidió 2 cruces de 143. Y en F3 se **apagó como veto**
(`docs/MATCHING.md` §4, commit `20be319`). La calibración del 2026-09-25 lo explica: entre
productos distintos al azar, el percentil 1 de distancia pHash fue 18; entre el **mismo** producto
(mismo registro sanitario) en dos cadenas, la distancia iba de 2 a 34, porque cada cadena
fotografía distinto (frasco o caja, fondo, ángulo). Una foto casi igual (≤ 6) sí prueba
identidad; una "claramente distinta" no prueba nada. Con el veto encendido, Boticas caía de 109
a 74 cruces, casi todos buenos.

## Error típico

Usar la distancia de imagen en los dos sentidos. Que dos fotos se parezcan mucho es evidencia;
que se parezcan poco no lo es. Además, Inkafarma y Mifarma reusan la misma foto para varias
presentaciones (caja y blíster), así que tampoco basta una foto igual sin las reglas de cantidad.

## Para saber más

- Zauner, C. (2010). *Implementation and Benchmarking of Perceptual Image Hash Functions*.
- Biblioteca usada: ImageHash, https://github.com/JohannesBuchner/imagehash

---

# Grabar y reproducir (*record/replay*) para pipelines deterministas

## Qué es

Guardar cada respuesta de red tal cual llega, con una llave estable por petición, y poder volver
a ejecutar todo el procesamiento leyendo solo de ese archivo. Si el proceso es determinista, la
salida es idéntica byte a byte.

## Por qué importa aquí

Las tiendas cambian a diario, así que un bug del parser no se puede reproducir "volviendo a
scrapear". Con el crudo grabado, se depura contra el caché y se prueba un matcher nuevo sobre la
misma corrida, sin una sola petición extra a las cadenas.

## Ejemplo real

```
$ PYTHONIOENCODING=utf-8 py -m tests.verificar_desde_cache 2026-10-06T07-00-03Z
  procesado desde el crudo: 1354 respuestas del caché · 0 por red
OK: sin red y byte a byte igual a data/publicar/data.json (440659 bytes)
real 0m12.451s
```

La prueba bloquea los sockets del proceso: cualquier intento de red revienta. La corrida en vivo
tardó 58 min; el reproceso, 12 s.

## Error típico

Incluir en la llave de caché algo que cambia entre ejecuciones (un *timestamp*, el orden de los
parámetros, una cabecera aleatoria): el replay no encuentra nada y sale a la red sin avisar.
`tests/test_http_cache.py` comprueba que la llave es estable ante orden, host y cabeceras.

## Para saber más

- VCR.py, la misma idea para pruebas en Python: https://vcrpy.readthedocs.io/
