# ROADMAP — Radar de Precios

Lo que falta, ordenado por valor para quien mira el portafolio dos minutos. Cada línea con la
fecha en que se anotó. El plan de fondo sigue siendo [`V2_PLAN.md`](V2_PLAN.md); este archivo
solo dice qué viene primero.

| # | Qué | Por qué primero | Dónde está | Anotado |
|---|---|---|---|---|
| 1 | **Subir `web/data.json` del 2026-10-06 al sitio** | El sitio en vivo muestra el snapshot de junio, con cruces v1 como una Desloratadina a +563 %. El nuevo no tiene ninguno sobre +60 % | Este repo, rama `publicar/2026-10-07`; owner (`pipeline.publish` o hPanel) | 2026-10-07 |
| 2 | **Revisar y mergear la UI v2** (PR #4): Astro, ES/EN, historial por producto, panorama, metodología | Es la vitrina: bilingüe (regla del portafolio), con ficha por producto. La v1 solo está en español | Rama `v2/f4-ui`; beta en `../farmacias-ui/data/beta/radar-precios-beta.zip` | 2026-09-26 |
| 3 | Remedir Lighthouse del inicio v2 con la CPU libre (≥ 90 móvil) antes de promoverla | La última medida (83–88) se hizo con la CPU al 100 % por procesos ajenos | `NOTES_AUTONOMO.md` §Fase B | 2026-09-26 |
| 4 | Automatizar la publicación de la v2 (build + subida de la carpeta) | La v2 hornea los datos en el build: `pipeline/publish.py` solo sube un `data.json` | `NOTES_AUTONOMO.md` §Promoción | 2026-09-26 |
| 5 | F2 analgésicos: unir los árboles de categoría de Boticas (hoy 2 de 77) y mergear | Cobertura real por categoría en vez de canasta | Rama `v2/f2-analgesicos` | 2026-09-26 |
| 6 | "Arma tu botiquín": total por cadena y combinación más barata, en el cliente, con `?b=` compartible | La interacción que convierte la tabla en producto | idea del backlog del portafolio (no versionado) | 2026-09-25 |
| 7 | Mapa persistente registro sanitario → laboratorio | Barato; cierra huecos del veto por laboratorio | `docs/revision/F3_final.md` §5.1 | 2026-09-26 |
| 8 | CI en GitHub Actions: regresión + 4 suites (3.9 y 3.12) + smoke web, sin red | Badge verde y exit code por PR | — | 2026-10-07 |
| 9 | Mensajes de la v1 en inglés | La regla "todo visible en ES y EN" no se cumple en la v1; la v2 la resuelve, así que solo vale si la v2 se demora | `web/` | 2026-10-07 |

Descartado por ahora: más cadenas. Fasa, BTL y Arcángel ya son del grupo de Mifarma; Plaza Vea y
Wong exponen VTEX pero no se vio venta de medicamentos; Tottus respondió 503
(`docs/RECON_CADENAS.md` en la rama `v2/d2-recon-cadenas`, 2026-09-26).
