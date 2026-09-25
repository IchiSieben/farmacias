"""tests/test_sincronizar.py — Paso --sincronizar (rclone copy), sin tocar Drive.

    PYTHONIOENCODING=utf-8 py -m tests.test_sincronizar

Usa una carpeta local como "remoto" (rclone copy acepta rutas locales). Requiere
rclone instalado (RCLONE_EXE, PATH o WinGet).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from pipeline import run


def main() -> int:
    fallas = []

    def check(cond: bool, msg: str) -> None:
        print(f"  [{'OK  ' if cond else 'FAIL'}] {msg}")
        if not cond:
            fallas.append(msg)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        raw, proc = tmp / "raw", tmp / "processed"
        (raw / "inkafarma" / "2026-09-25").mkdir(parents=True)
        (raw / "inkafarma" / "2026-09-25" / "respuestas_X.jsonl.gz").write_bytes(b"x")
        (raw / "inkafarma" / "2026-09-25" / "a_medias.jsonl.gz.tmp").write_bytes(b"x")
        (proc / "latest").mkdir(parents=True)
        (proc / "latest" / "ofertas.parquet").write_bytes(b"p")
        os.environ["RCLONE_REMOTE"] = str(tmp / "drive" / "raw")
        os.environ["RCLONE_REMOTE_PROCESSED"] = str(tmp / "drive" / "derivados")

        check(run.sincronizar(raw, proc, "test") == [], "copia sin errores")
        check((tmp / "drive/raw/inkafarma/2026-09-25/respuestas_X.jsonl.gz").exists()
              and (tmp / "drive/derivados/latest/ofertas.parquet").exists(),
              "crudo y Parquet quedan en el remoto")
        check(not (tmp / "drive/raw/inkafarma/2026-09-25/a_medias.jsonl.gz.tmp").exists(),
              "los .tmp (escrituras a medias) no se suben")

        (raw / "inkafarma" / "2026-09-25" / "respuestas_X.jsonl.gz").unlink()
        run.sincronizar(raw, proc, "test")
        check((tmp / "drive/raw/inkafarma/2026-09-25/respuestas_X.jsonl.gz").exists(),
              "copy nunca borra en el remoto lo que ya no está en local")

        os.environ["RCLONE_REMOTE"] = "RemotoQueNoExiste:x"
        errs = run.sincronizar(raw, proc, "test")
        check(len(errs) == 1 and "reintenta" in errs[0], "remoto roto -> error informado, no excepción")
        os.environ["RCLONE_REMOTE"] = ""
        check(run.sincronizar(raw, proc, "test") != [], "sin RCLONE_REMOTE -> error informado")

    print("-" * 60)
    if fallas:
        print(f"SINCRONIZAR: {len(fallas)} FALLAS")
        return 1
    print("SINCRONIZAR: todo OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
