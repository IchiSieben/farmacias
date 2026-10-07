# Capturas e imágenes

Todas en `docs/img/`. Revisadas a tamaño real el 2026-10-07. Ninguna muestra datos personales:
solo la UI con precios públicos.

## Generadas por script (hechas)

| Archivo | Qué muestra | Cómo se regenera |
|---|---|---|
| `v1_escritorio_busqueda.png` | **Portada del README.** Búsqueda "paracetamol", 1366×860, 4 cadenas, más barato en verde, brecha a la derecha | `CAPTURAS=docs/img PYTHONIOENCODING=utf-8 py -m tests.test_web_smoke` |
| `v1_escritorio_tutorial.png` | Primer paso del tutorial de apertura, escritorio | idem |
| `v1_movil_busqueda.png` | Búsqueda en 390×844 | idem |
| `v1_movil_tutorial.png` | Tutorial en móvil | idem |
| `mas_barato_es.png` / `mas_barato_en.png` | % de sus productos en que cada cadena es la más barata, snapshot 2026-10-06 | `py scripts/grafica_readme.py` |

Las capturas salen con las fotos de producto bloqueadas (el smoke no depende de servidores
ajenos); la tabla v1 no muestra fotos, así que no cambia nada visible.

## Pendientes (owner o sesión del Landing)

El Landing ya tiene `poster.webp`, `poster-mobile.webp`, `poster-640/960.webp`, `og.jpg` y
`preview.mp4` de septiembre (snapshot de junio). No faltan: conviene **renovarlos**.

| Archivo | Qué debe mostrar | Por qué no se hizo aquí |
|---|---|---|
| `Landing/public/media/radar-precios/poster*.webp`, `og.jpg` | Renovar con la misma escena que `v1_escritorio_busqueda.png`, recortada al formato de tarjeta del hub | Esta sesión no toca el Landing; la sesión del Landing convierte la PNG |
| `Landing/public/media/radar-precios/preview.mp4` | Renovar: recorrido de 15–30 s: buscar "paracetamol", subir la brecha mínima, abrir una ficha | Video con HyperFrames; fuera del alcance de esta sesión |
| `v2_*.png` (escritorio y móvil, inicio, ficha con historial, panorama) | La UI v2 | Existen en la rama `v2/f4-ui` (`docs/revision/beta_local_*.png`); entran al README cuando se mergee el PR #4 |

`docs/poster.webp` (portada anterior, junio) queda en el repo por si alguna página externa la
enlaza; el README ya no la usa.
