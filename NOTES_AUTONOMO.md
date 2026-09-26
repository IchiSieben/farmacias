# NOTES_AUTONOMO — corrida autónoma v2 (2026-09-26)

> Bitácora de la corrida sin supervisión (`docs/PROMPT_AUTONOMO_v2.md`). El resumen para
> el celular va arriba al terminar; debajo, el registro en orden.

## Estado real al arrancar (12:47, hora de Lima)

- Worktrees: `farmacias` (main, 1c69537) · `farmacias-f3` (v2/f3-matcher, 7a0d376) ·
  `farmacias-ui` (v2/f4-ui, 490fd13) · `farmacias-fix` (fix/cruce-fuzzy, ya mergeada en #2).
- PRs: #3 F3 (DRAFT). #1 (F1) y #2 (fix matcher) mergeados.
- Última corrida diaria: `2026-09-26T07-00-07Z` (02:00 Lima): 3338 s, 294 filas, 54 con
  las 4 cadenas; Boticas 109, Universal 77; 1 error HTTP de Universal (exit 1).
  Capturada con el código de main: sin QuickView de F3.
- `.env` NO tiene `PUBLISH_*` → la Fase C (subida a beta con `pipeline/publish.py`) está
  bloqueada de antemano. Decisión conservadora: no usar el conector MCP de Hostinger
  en su lugar (`deployStaticWebsite` despliega el sitio entero, no una subcarpeta).
- `../farmacias-f3/scratchpad/REVISION_F3.md` no existe; la revisión está en HANDOFF.md.
- Procesos: ningún `py`/`find` corriendo al arrancar. Solo toco lo que lanzo yo.

## Presupuesto de red (máx. 3 000 requests)

| Paso | Requests |
|---|---|
| `--completar 2026-09-26T07-00-07Z` (QuickView + fotos) | en curso |

## Registro
