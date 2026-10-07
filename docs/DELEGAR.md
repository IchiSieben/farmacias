# Delegar a la Mac — farmacias (Radar de Precios)

Router: `../enjambre/routing.toml` (tutorial 22 de enjambre). Sin pantalla → Mac. `ssh mac` a pelo está bloqueado por un hook: todo pasa por enjambre.

| Conviene en la Mac | Comando (desde esta carpeta) |
|---|---|
| Ver la ruta sin gastar nada | `python ../enjambre/enjambre.py run --repo farmacias --task docs/tasks/TASK-<id>.md --kind tests --dry-run` |
| Ejecutarlo (agente `claude -p`, gasta cuota) | el mismo, sin `--dry-run` |
| Verificar (la suite de este repo) | un TASK con `kind: tests` cuyo criterio sea `PYTHONIOENCODING=utf-8 python3 -m tests.test_matcher_regresion` (en la Mac no hay `py`) |
| Corrida completa / reconstruir snapshot (script largo) | un TASK con `kind: scrape` que nombre `pipeline/run.py --todo` y su criterio de hecho |
| ¿Está libre la Mac? ¿Terminó? | `python ../enjambre/enjambre.py status` (nodos, cola, últimos trabajos) |
| Cuánto tarda cada tipo | `python ../enjambre/enjambre.py history` |

Estado del nodo:
- Repo **clonado en la Mac** el 2026-10-07 en `~/Documents/Portfolio/farmacias` (HTTPS público, `main` = `1a721ff`). Sin `.env`: las claves (Algolia, rclone) las copia el dueño, nunca un agente.
- `AGENTS.md` está en la rama `publicar/2026-10-07`; `run` lo busca en el checkout de `main` de Windows, así que hasta el merge no se puede delegar sin copiarlo allí.
- La Mac tiene `python3` 3.9 del sistema y además `/opt/homebrew/bin/python3.12` y `uv`, pero **no** un entorno con `requirements.txt` (NEEDS-OWNER de enjambre).
- El worker `claude` no puede ejecutar python (allowlist: Read/Edit/Write/Glob/Grep, `git status|diff`, `ls`): un `kind: tests` hoy sale `incomplete`. Hueco de enjambre, anotado en su NEEDS-OWNER.

Se queda en Windows: `scripts/instalar_tarea_windows.ps1` (Programador de tareas), `recon/*` (herramientas de desarrollo del navegador), `pipeline/publish.py` (rclone + credenciales).
Escribe `kind: tests` (o `scrape`) al principio del TASK y no hace falta `--kind`.

**Probado (2026-10-07): dry-run, sin corrida real** (`docs/tasks/TASK-farmacias-tests-mac.md`). El dry-run no escribe en el ledger; su salida:
`{"action": "run", "node": "mac", "routed_by": "rule", "reason": "tests -> mac: first free node of prefer ['mac', 'win']", "diverted_from": null, "trace": ["win: fits, but has no executor yet (runnable = false)"], "id": "farmacias-tests-mac", "kind": "tests", "kind_source": "flag", "route_reason": "tests -> mac: first free node of prefer ['mac', 'win']"}`
