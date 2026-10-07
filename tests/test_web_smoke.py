"""tests/test_web_smoke.py — Smoke del demo estático (web/) servido en subcarpeta.

Copia web/ a <tmp>/radar-precios/, lo sirve en 127.0.0.1 y lo abre con Playwright
(Chromium) en escritorio y móvil. Sin red a las cadenas: las fotos de producto se
bloquean (son de terceros) para que el resultado no dependa de sus servidores.

    PYTHONIOENCODING=utf-8 py -m tests.test_web_smoke
    CAPTURAS=docs/img PYTHONIOENCODING=utf-8 py -m tests.test_web_smoke   # además guarda PNG

Requiere `py -m pip install playwright` y `py -m playwright install chromium`.
"""

from __future__ import annotations

import functools
import http.server
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"
BASE = "/radar-precios/"

VISTAS = [
    ("escritorio", {"width": 1366, "height": 860}, False),
    ("movil", {"width": 390, "height": 844}, True),
]


def _servidor(directorio: Path):
    class _Silencioso(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):  # noqa: D401 - sin ruido en la salida
            pass

    handler = functools.partial(_Silencioso, directory=str(directorio))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright no está instalado: py -m pip install playwright")
        return 2

    capturas = os.environ.get("CAPTURAS")
    fallas = []

    def check(ok: bool, msg: str) -> None:
        print(f"  [{'OK  ' if ok else 'FALLA'}] {msg}")
        if not ok:
            fallas.append(msg)

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(WEB, Path(tmp) / BASE.strip("/"))
        srv = _servidor(Path(tmp))
        origen = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            with sync_playwright() as p:
                nav = p.chromium.launch()
                for nombre, viewport, movil in VISTAS:
                    print(f"== {nombre} {viewport['width']}x{viewport['height']}")
                    ctx = nav.new_context(viewport=viewport, is_mobile=movil,
                                          has_touch=movil, locale="es-PE")
                    page = ctx.new_page()
                    errores, propios_fallidos, consola_info = [], [], []

                    # Fotos de producto: de terceros, fuera del alcance del smoke.
                    page.route(lambda u: not u.startswith(origen),
                               lambda route: route.abort())
                    page.on("console", lambda m: (errores if m.type == "error"
                                                  else consola_info).append(m.text))
                    page.on("pageerror", lambda e: errores.append(str(e)))
                    page.on("response", lambda r: r.url.startswith(origen)
                            and r.status >= 400 and propios_fallidos.append(r.url))
                    page.add_init_script(
                        "window.__csp=[];document.addEventListener("
                        "'securitypolicyviolation',e=>window.__csp.push("
                        "e.violatedDirective+' '+e.blockedURI))")

                    page.goto(origen + BASE, wait_until="networkidle")
                    page.wait_for_selector("#filas tr", timeout=10_000)
                    filas = page.locator("#filas tr").count()
                    tutorial = page.locator(".ic7-tutorial-root.ic7-tutorial-on")
                    tutorial.wait_for(timeout=5_000)
                    if capturas:
                        Path(capturas).mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(Path(capturas) / f"v1_{nombre}_tutorial.png"))
                    page.locator(".ic7-tutorial-skip").click()
                    tutorial.wait_for(state="hidden", timeout=5_000)

                    page.fill("#q", "paracetamol")
                    page.wait_for_timeout(400)
                    filtradas = page.locator("#filas tr").count()
                    if capturas:
                        page.screenshot(path=str(Path(capturas) / f"v1_{nombre}_busqueda.png"))

                    csp = page.evaluate("window.__csp")
                    check(filas > 0, f"la tabla carga ({filas} filas)")
                    check(0 < filtradas <= filas, f"la búsqueda filtra ({filtradas} con 'paracetamol')")
                    check(not errores, f"0 errores de consola {errores[:3]}")
                    check(not propios_fallidos, f"0 recursos propios con 4xx/5xx {propios_fallidos[:3]}")
                    check(not csp, f"0 violaciones de CSP {csp[:3]}")
                    check(any("Un cruce equivocado no" in t for t in consola_info),
                          "mensaje de consola presente")
                    ctx.close()
                nav.close()
        finally:
            srv.shutdown()

    print("-" * 60)
    if fallas:
        print(f"WEB SMOKE: {len(fallas)} FALLAS")
        return 1
    print("WEB SMOKE: todo OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
