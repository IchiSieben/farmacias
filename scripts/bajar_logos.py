"""scripts/bajar_logos.py — Descarga el logo OFICIAL de cada cadena desde su propio sitio.

Regla dura (F4_UI_BRIEF §3): nunca se dibuja ni se reconstruye un logo. Solo se
guardan, tal cual, activos que la cadena sirve en su sitio. Si no se consigue uno
limpio, la UI usa un monograma sobre el color de la cadena, y punto.

Prioridad de candidatos (primero que pase el control de calidad):
  1. <img> del header cuyo class/alt/src diga "logo" (sin logos de medios de pago
     ni de marcas de terceros), en orden de aparición
  2. og:image SOLO si el archivo se llama logo/imagotipo/isotipo (si no, suele ser
     un banner)
  3. <img> de logo en el header YA RENDERIZADO (Playwright, una carga de la home):
     SPAs que pintan el header desde su CMS (Inkafarma)
  4. el ícono más grande declarado (<link rel=icon|apple-touch-icon sizes>)
Control de calidad: SVG válido, o raster decodificable con lado menor >= 64 px.

Salida en web-v2/public/logos/: <cadena>.<ext> y logos.json con
{cadena: {archivo, color, fuente, origen}}. `color` = color dominante del propio
logo (no inventado); `archivo` = null -> la UI muestra el monograma.

Uso:  py scripts/bajar_logos.py            (4 cadenas, ~10 requests, 2–6 s entre ellas)
      py scripts/bajar_logos.py inkafarma  (solo esas cadenas; conserva el resto de logos.json)
"""

from __future__ import annotations

import io
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.adapter_base import USER_AGENTS  # noqa: E402

SALIDA = ROOT / "web-v2" / "public" / "logos"
SITIOS = {
    "inkafarma": "https://inkafarma.pe",
    "mifarma": "https://www.mifarma.com.pe",
    "boticasperu": "https://www.boticasperu.pe",
    "universal": "https://www.farmaciauniversal.com",
}
# logos de terceros que aparecen en headers/footers y no son la cadena
_AJENOS = re.compile(r"visa|master|amex|american|diners|yape|plin|isdin|propiel|brands|sip|epago|"
                     r"libro|reclamac|google|apple|facebook|instagram|tiktok|whatsapp", re.I)
_MIN_LADO = 64


def _dormir() -> None:
    time.sleep(random.uniform(2, 6))


def candidatos(html: str, base: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for tag in re.findall(r"<img\b[^>]*>", html, re.I):
        src = re.search(r'\b(?:data-src|src)="([^"]+)"', tag)
        if not src or not re.search(r"logo", tag, re.I):
            continue
        if _AJENOS.search(tag):
            continue
        out.append(("header-img", urljoin(base, src.group(1))))
    for m in re.findall(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html, re.I):
        if re.search(r"logo|imagotipo|isotipo", m.rsplit("/", 1)[-1], re.I):
            out.append(("og:image", urljoin(base, m)))
    iconos = []
    for tag in re.findall(r"<link\b[^>]*rel=\"[^\"]*icon[^\"]*\"[^>]*>", html, re.I):
        href = re.search(r'href="([^"]+)"', tag)
        if not href:
            continue
        tam = re.search(r'sizes="(\d+)x\d+"', tag)
        lado = int(tam.group(1)) if tam else (512 if href.group(1).endswith(".svg") else 0)
        iconos.append((lado, urljoin(base, href.group(1))))
    out += [("icono", u) for _, u in sorted(iconos, reverse=True)]
    vistos, unicos = set(), []
    for fuente, u in out:
        if u not in vistos:
            vistos.add(u)
            unicos.append((fuente, u))
    return unicos


def candidatos_renderizados(sitio: str) -> List[Tuple[str, str]]:
    """Logo del header tras ejecutar el JS (SPAs como Inkafarma: el HTML estático no
    trae <img> de logo, ni manifest, ni apple-touch-icon; el header lo pinta desde el
    CMS de la propia cadena). Una sola carga de la home. Sin Playwright -> []."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(viewport={"width": 1366, "height": 900}, user_agent=USER_AGENTS[0])
        pg.goto(sitio, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(8000)
        imgs = pg.evaluate("""() => [...document.querySelectorAll('header img, [class*=header] img')]
            .map(i => [i.currentSrc || i.src, i.alt || '', i.getBoundingClientRect().width])""")
        nav.close()
    out: List[Tuple[str, str]] = []
    for src, alt, ancho in imgs:
        texto = f"{alt} {src.rsplit('/', 1)[-1]}"
        if ancho >= 40 and re.search(r"logo|imagotipo|isotipo", texto, re.I) and not _AJENOS.search(texto):
            if ("header-render", src) not in out:
                out.append(("header-render", src))
    return out


def _es_svg(datos: bytes) -> bool:
    cabeza = datos[:512].lstrip().lower()
    return cabeza.startswith(b"<svg") or (cabeza.startswith(b"<?xml") and b"<svg" in datos[:4096].lower())


def _color_svg(datos: bytes) -> Optional[str]:
    colores = re.findall(rb"(?:fill|stop-color|stroke)[:=]\s*\"?#([0-9a-fA-F]{6})", datos)
    utiles = [c.decode().lower() for c in colores if not _neutro(c.decode())]
    return f"#{Counter(utiles).most_common(1)[0][0]}" if utiles else None


def _neutro(hexa: str) -> bool:
    r, g, b = (int(hexa[i:i + 2], 16) for i in (0, 2, 4))
    return max(r, g, b) - min(r, g, b) < 30  # blanco, negro y grises


def _color_raster(img) -> Optional[str]:
    px = img.convert("RGBA").resize((64, 64)).tobytes()
    cuenta: Counter = Counter()
    for i in range(0, len(px), 4):
        r, g, b, a = px[i:i + 4]
        if a < 128:
            continue
        hexa = f"{r // 16 * 17:02x}{g // 16 * 17:02x}{b // 16 * 17:02x}"
        if not _neutro(hexa):
            cuenta[hexa] += 1
    return f"#{cuenta.most_common(1)[0][0]}" if cuenta else None


def evaluar(datos: bytes) -> Tuple[Optional[str], Optional[str], str]:
    """(extension, color, motivo). extension None = no pasa el control (el color
    se devuelve igual: sirve para el monograma, sigue viniendo de un activo oficial)."""
    if _es_svg(datos):
        return "svg", _color_svg(datos), "svg"
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(datos))
        img.load()  # ICO: Pillow abre el tamaño más grande que trae
    except Exception as exc:
        return None, None, f"no decodifica ({type(exc).__name__})"
    if min(img.size) < _MIN_LADO:
        return None, _color_raster(img), f"muy chico ({img.size[0]}x{img.size[1]})"
    ext = {"JPEG": "jpg", "ICO": "png"}.get(img.format or "", (img.format or "png").lower())
    return ext, _color_raster(img), f"{img.format} {img.size[0]}x{img.size[1]}"


def _candidatos_en_orden(html: str, sitio: str):
    """Estáticos primero; el header renderizado solo si ningún estático es un logo
    (los íconos van al final: si solo hay íconos, antes se prueba el render)."""
    estaticos = candidatos(html, sitio)
    yield from [c for c in estaticos if c[0] != "icono"]
    yield from candidatos_renderizados(sitio)
    yield from [c for c in estaticos if c[0] == "icono"]


def bajar(cliente: httpx.Client, cadena: str, sitio: str) -> dict:
    html = cliente.get(sitio).text
    _dormir()
    color_respaldo: Tuple[Optional[str], Optional[str]] = (None, None)
    for fuente, url in _candidatos_en_orden(html, sitio):
        try:
            resp = cliente.get(url)
            _dormir()
        except httpx.HTTPError as exc:
            print(f"  {cadena}: {fuente} {url} -> error {exc}")
            continue
        if resp.status_code != 200:
            print(f"  {cadena}: {fuente} {url} -> HTTP {resp.status_code}")
            continue
        ext, color, motivo = evaluar(resp.content)
        print(f"  {cadena}: {fuente} {url} -> {motivo}")
        if ext is None:
            if color and not color_respaldo[0]:
                color_respaldo = (color, url)
            continue
        datos = resp.content
        if ext == "png" and not datos.startswith(b"\x89PNG"):  # .ico: se guarda su PNG mayor, sin retocar
            from PIL import Image
            buf = io.BytesIO()
            Image.open(io.BytesIO(datos)).save(buf, format="PNG")
            datos = buf.getvalue()
        archivo = f"{cadena}.{ext}"
        (SALIDA / archivo).write_bytes(datos)
        return {"archivo": archivo, "color": color, "fuente": fuente, "origen": url}
    # Sin logo limpio: monograma. Su color, del activo oficial rechazado (p.ej. favicon).
    return {"archivo": None, "color": color_respaldo[0], "fuente": "monograma",
            "origen": color_respaldo[1]}


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    cliente = httpx.Client(headers={"User-Agent": USER_AGENTS[0],
                                    "Accept-Language": "es-PE,es;q=0.9"},
                           follow_redirects=True, timeout=30)
    solo = set(sys.argv[1:])  # p.ej. `py -m scripts.bajar_logos inkafarma`
    previo = SALIDA / "logos.json"
    resultado = json.loads(previo.read_text(encoding="utf-8")) if solo and previo.exists() else {}
    for cadena, sitio in SITIOS.items():
        if solo and cadena not in solo:
            continue
        try:
            resultado[cadena] = bajar(cliente, cadena, sitio)
        except httpx.HTTPError as exc:
            print(f"  {cadena}: sitio no disponible ({exc}) -> monograma")
            resultado[cadena] = {"archivo": None, "color": None, "fuente": "monograma", "origen": None}
    cliente.close()
    (SALIDA / "logos.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    for c, r in resultado.items():
        print(f"{c:12} {r['fuente']:10} {r['archivo'] or '—':18} color {r['color'] or '—'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
