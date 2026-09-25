"""tests/verificar_desde_cache.py — Aceptación F1: `--desde-cache` sin red, byte a byte.

Bloquea los sockets del proceso (cualquier intento de red revienta), reprocesa una
corrida grabada a un archivo temporal y lo compara byte a byte con un data.json
de referencia (por defecto, web/data.json).

    PYTHONIOENCODING=utf-8 py -m tests.verificar_desde_cache 2026-09-24
    PYTHONIOENCODING=utf-8 py -m tests.verificar_desde_cache 2026-09-24 --contra otra/data.json

Usa el RAW_DIR del entorno / .env, igual que pipeline.run.
"""

from __future__ import annotations

import argparse
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class RedBloqueada(RuntimeError):
    pass


def _sin_red(*a, **k):
    raise RedBloqueada("intento de red durante --desde-cache")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corrida", help="fecha (YYYY-MM-DD) o id de corrida")
    ap.add_argument("--contra", default=str(ROOT / "web" / "data.json"))
    args = ap.parse_args(argv)

    from pipeline import run  # importar antes de bloquear (ssl hereda de socket)

    socket.socket.connect = _sin_red      # type: ignore[method-assign]
    socket.socket.connect_ex = _sin_red   # type: ignore[method-assign]
    socket.create_connection = _sin_red   # type: ignore[assignment]
    socket.getaddrinfo = _sin_red         # type: ignore[assignment]

    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp) / "data.json"
        rc = run.main(["--desde-cache", args.corrida, "--salida", str(salida), "--sin-historial"])
        if rc != 0:
            print(f"FALLA: pipeline.run devolvió {rc}")
            return 1
        a, b = salida.read_bytes(), Path(args.contra).read_bytes()
        if a == b:
            print(f"OK: sin red y byte a byte igual a {args.contra} ({len(a)} bytes)")
            return 0
        print(f"FALLA: difiere de {args.contra} ({len(a)} vs {len(b)} bytes)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
