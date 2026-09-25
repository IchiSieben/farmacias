# Prompt de arranque v2 para Claude Code

> Pegar en Claude Code desde la raíz del repo (`farmacias/`). El prompt de la v1
> (Fase 0, reconocimiento) quedó en el historial de git; ya no aplica.
> Modelo sugerido: Opus, effort alto. Una fase por sesión.

---

Lee primero, en este orden: `CLAUDE.md`, `V2_PLAN.md`, `ESTADO_y_proximos_pasos.md`,
`farmacias.yaml`. Luego recorre `core/`, `pipeline/build_snapshot.py`, `web/app.js` y
`tests/test_matcher_regresion.py` para ver cómo está construida la v1. No propongas
reescribir desde cero: la v1 está viva en producción y funciona; v2 la extiende.

Vamos a ejecutar `V2_PLAN.md` fase por fase. Empezamos por **F1 (data lake y corrida
automática)**. Antes de escribir código:

1. Corre la regresión (`PYTHONIOENCODING=utf-8 py -m tests.test_matcher_regresion`) y
   confirma que está en verde. Ese es el piso.
2. Dame un diagnóstico corto (≤ 20 líneas) de qué tocarías en F1 y en qué orden, con
   los archivos exactos. Señala cualquier punto del plan que te parezca mal o
   arriesgado — quiero que discutas, no que obedezcas.
3. Recién después, crea la rama `v2/f1-data-lake` e implementa. Un commit por pieza
   (`core/storage.py`, adaptadores → `RawStore`, `pipeline/run.py`, esquema Parquet,
   tarea de Windows, `.env.example`). Mensajes en español, imperativo.

Restricciones que no se negocian: solo datos públicos con los delays actuales; el
crudo se cachea antes de parsear; nada de credenciales en el repo; `web/data.json` y
`web/` actuales siguen funcionando hasta que F4 los reemplace; toda pieza nueva se
prueba con `--desde-cache` sin tocar la red.

Mi `RAW_DIR` va a ser una carpeta de Google Drive montada en Windows (te paso la ruta
cuando la pidas). Termina la sesión con: qué quedó hecho, cómo lo verifico yo en 5
minutos, y qué sigue en F2. Actualiza `ESTADO_y_proximos_pasos.md` con eso antes del
último commit.
