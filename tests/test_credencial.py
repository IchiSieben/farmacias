"""tests/test_credencial.py — La corrida se corta en el PRIMER 403 de Algolia (sin red).

    PYTHONIOENCODING=utf-8 py -m tests.test_credencial

Un "sitio" falso responde 403 a todo lo que va a Algolia. Se verifica que
`construir()` no se traga el rechazo (sale tras UNA request, no ~75), que el
mensaje nombra la variable de la key y cómo recapturarla, y que `pipeline.run`
deja la corrida como `abortada`, sin exportar nada y con el staging listo para
`--reanudar`.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import httpx

from core import http_cache as hc
from core.adapter_base import CredencialRechazada
from core.storage import RawStore
from pipeline import build_snapshot, run

PEDIDAS = []


def _sitio(request: httpx.Request) -> httpx.Response:
    PEDIDAS.append(request.url.host)
    if "algolia" in request.url.host:
        return httpx.Response(403, json={"message": "Invalid Application-ID or API key"})
    return httpx.Response(404)


class _SesionFalsa(hc.SesionHttp):
    def __init__(self, *a, **k):
        k["red"] = httpx.MockTransport(_sitio)
        k["delay"] = (0, 0)
        super().__init__(*a, **k)


def main() -> int:
    fallas = []

    def check(cond: bool, msg: str) -> None:
        print(f"  [{'OK  ' if cond else 'FAIL'}] {msg}")
        if not cond:
            fallas.append(msg)

    for var in ("INKAFARMA_ALGOLIA_APP_ID", "INKAFARMA_ALGOLIA_API_KEY",
                "MIFARMA_ALGOLIA_APP_ID", "MIFARMA_ALGOLIA_API_KEY"):
        os.environ[var] = "test"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 1) construir() propaga el rechazo en la primera request
        sesion = _SesionFalsa(hc.GRABAR, tmp / "staging_1")
        try:
            build_snapshot.construir(
                150, pausa=0, adapter_kw=lambda c: {"transport": sesion.transporte(c)})
            check(False, "construir() lanza CredencialRechazada")
            msg = ""
        except CredencialRechazada as exc:
            check(True, "construir() lanza CredencialRechazada")
            msg = str(exc)
        finally:
            sesion.cerrar()
        algolia = [h for h in PEDIDAS if "algolia" in h]
        check(len(algolia) == 1, f"corta en el primer 403 (requests a Algolia: {len(algolia)})")
        check("INKAFARMA_ALGOLIA_API_KEY" in msg and "DevTools" in msg and "--reanudar" in msg,
              "el mensaje nombra la key, cómo recapturarla y cómo reanudar")

        # 2) pipeline.run: corrida abortada, nada exportado, staging conservado
        PEDIDAS.clear()
        original = hc.SesionHttp  # run.hc es el mismo módulo: se parchea y se restaura
        hc.SesionHttp = _SesionFalsa
        run.STAGING_DIR = tmp / "staging"
        raw = RawStore(tmp / "raw")
        corrida = "2026-09-25T00-00-00Z"
        try:
            run.capturar(raw, corrida, objetivo=150, semillas=True, delay=(0, 0))
            check(False, "capturar() falla con ErrorCorrida")
        except run.ErrorCorrida as exc:
            check("INKAFARMA_ALGOLIA_API_KEY" in str(exc), "capturar() falla con ErrorCorrida")
        finally:
            hc.SesionHttp = original
        man = raw.leer_manifest(corrida)
        check(man["estado"] == "abortada" and "motivo" in man, "manifiesto queda 'abortada' con motivo")
        check((tmp / "staging" / corrida / "inkafarma.jsonl").exists(),
              "staging conservado para --reanudar")
        check(not (tmp / "raw" / "inkafarma").exists(), "no se publica crudo de una corrida abortada")

    print("-" * 60)
    if fallas:
        print(f"CREDENCIAL: {len(fallas)} FALLAS")
        return 1
    print("CREDENCIAL: todo OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
