"""tests/test_http_cache.py — Graba/reproduce del crudo HTTP (V2_PLAN F1), sin red.

Se corre como script (como la regresión del matcher):
    PYTHONIOENCODING=utf-8 py -m tests.test_http_cache

Un "sitio" falso (httpx.MockTransport) hace de red; el test verifica que lo
grabado se reproduce idéntico, que un faltante en modo reproducir falla sin tocar
la red, que reanudar solo pide lo que falta y que la key Algolia no llega al crudo.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import httpx

from core import http_cache as hc
from core.storage import RawStore

LLAMADAS = []


def _sitio(request: httpx.Request) -> httpx.Response:
    LLAMADAS.append(request.url.path)
    if request.url.path == "/caido":
        raise httpx.ConnectError("sitio caído", request=request)
    if request.url.path == "/html":
        return httpx.Response(200, headers={"content-type": "text/html; charset=ISO-8859-1"},
                              content="<p>Ibuprofeno 400 mg · Caja</p>".encode("latin-1"))
    body = json.loads(request.content or b"{}")
    return httpx.Response(200, json={"eco": body, "q": dict(request.url.params), "ñ": "sí"})


def _cliente(sesion: hc.SesionHttp, cadena: str, key: str = "SECRETA") -> httpx.Client:
    return httpx.Client(transport=sesion.transporte(cadena),
                        headers={"X-Algolia-API-Key": key}, base_url="https://sitio.test")


def _pedir(cli: httpx.Client):
    out = [cli.post("/1/indexes/*/queries", json={"b": 2, "a": 1}).json(),
           cli.get("/p", params={"z": "1", "a": "2"}).json(),
           cli.get("/html").text]
    try:
        cli.get("/caido")
        out.append("sin error")
    except httpx.TransportError as exc:
        out.append(type(exc).__name__)
    return out


def main() -> int:
    fallas = []

    def check(cond: bool, msg: str) -> None:
        print(f"  [{'OK  ' if cond else 'FAIL'}] {msg}")
        if not cond:
            fallas.append(msg)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        red = httpx.MockTransport(_sitio)

        # 1) grabar
        s1 = hc.SesionHttp(hc.GRABAR, tmp / "staging", delay=(0, 0), red=red)
        vivo = _pedir(_cliente(s1, "inkafarma"))
        s1.cerrar()
        check(len(LLAMADAS) == 4, "grabar: 4 requests salen a la red")
        crudo = (tmp / "staging" / "inkafarma.jsonl").read_text(encoding="utf-8")
        check("SECRETA" not in crudo, "la API key no llega al crudo")

        # 2) publicar al RAW (gzip) y reproducir sin red
        store = RawStore(tmp / "raw")
        dest = store.publicar_archivo(tmp / "staging" / "inkafarma.jsonl",
                                      "inkafarma", "2026-09-24", "respuestas_X.jsonl.gz")
        LLAMADAS.clear()
        s2 = hc.SesionHttp(hc.REPRODUCIR, tmp / "no_usar", fuentes={"inkafarma": dest}, red=red)
        cli2 = _cliente(s2, "inkafarma", key="OTRA-KEY-ROTADA")
        cli2.base_url = "https://otro-host.test"  # host distinto: la llave no depende del host
        repro = _pedir(cli2)
        check(repro == vivo, "reproducir devuelve exactamente lo grabado (json, html latin-1, error)")
        check(not LLAMADAS, "reproducir no toca la red")

        # 3) faltante en reproducir: falla y se cuenta, sin red
        try:
            cli2.get("/nunca-grabado")
            check(False, "faltante lanza FaltaEnCache")
        except hc.FaltaEnCache:
            check(True, "faltante lanza FaltaEnCache")
        check(len(s2.fallos()) == 1 and not LLAMADAS, "faltante se cuenta y no sale a la red")
        s2.cerrar()

        # 4) reanudar: lo grabado sale de caché, solo lo nuevo va a la red
        s3 = hc.SesionHttp(hc.REANUDAR, tmp / "staging", delay=(0, 0), red=red)
        cli3 = _cliente(s3, "inkafarma")
        _pedir(cli3)
        cli3.get("/nuevo")
        s3.cerrar()
        check(LLAMADAS == ["/nuevo"], "reanudar solo pide lo que faltaba")
        n_lineas = len((tmp / "staging" / "inkafarma.jsonl").read_text(encoding="utf-8").splitlines())
        check(n_lineas == 5, "reanudar anota lo nuevo en el mismo staging")

        # 4b) corte a mitad de un write: la última línea del staging queda a medias
        staging = tmp / "staging" / "inkafarma.jsonl"
        with open(staging, "a", encoding="utf-8") as fh:
            fh.write('{"k": "cortada", "cuerpo": "<html>mitad de la respu')
        LLAMADAS.clear()
        s4 = hc.SesionHttp(hc.REANUDAR, tmp / "staging", delay=(0, 0), red=red)
        _cliente(s4, "inkafarma").get("/tras-el-corte")
        s4.cerrar()
        colas = hc.cargar_registros(staging)
        nueva = hc.llave(httpx.Request("GET", "https://x.test/tras-el-corte"))
        check(LLAMADAS == ["/tras-el-corte"] and nueva in colas,
              "reanudar tras línea cortada: lo nuevo se conserva")
        check("cortada" not in colas, "el fragmento cortado se descarta")

        # 4c) 404 es informativo; 403 cuenta como error de auth
        s5 = hc.SesionHttp(hc.GRABAR, tmp / "staging5", delay=(0, 0), red=httpx.MockTransport(
            lambda r: httpx.Response(404 if r.url.path == "/no" else 403)))
        c5 = _cliente(s5, "mifarma")
        c5.get("/no"); c5.get("/auth")
        s5.cerrar()
        st = s5.estadisticas()["mifarma"]
        check(st["http_404"] == 1 and st["http_error"] == 1 and st["http_auth"] == 1,
              "404 informativo, 403 = error de auth")

        # 5) llave: orden de query y de claves JSON no importa
        r1 = httpx.Request("POST", "https://a.test/x?b=1&a=2", json={"x": 1, "y": 2})
        r2 = httpx.Request("POST", "https://b.test/x?a=2&b=1", json={"y": 2, "x": 1},
                           headers={"X-Algolia-API-Key": "k"})
        check(hc.llave(r1) == hc.llave(r2), "llave estable ante orden, host y headers")

    print("-" * 60)
    if fallas:
        print(f"HTTP CACHE: {len(fallas)} FALLAS")
        return 1
    print("HTTP CACHE: todo OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
