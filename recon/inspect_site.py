#!/usr/bin/env python3
"""
recon/inspect_site.py — Fase 0 (Reconocimiento) de FarmaComparador Perú.

Dado un dominio y un término de búsqueda, hace la petición con headers/UA
realistas, guarda la respuesta CRUDA en data/raw/recon/<fecha>/ y reporta:
  - status code, content-type, tamaño, tiempo de respuesta
  - detección de Cloudflare / WAF (headers cf-*, server, challenge en el body)
  - estado de robots.txt para la ruta consultada

NO scrapea ni parsea catálogo: solo inspecciona. El objetivo es mapear los
endpoints reales para volcarlos a config/farmacias.yaml antes de la Fase 1.

Uso:
    py recon/inspect_site.py --dominio https://www.boticasperu.pe --query paracetamol
    py recon/inspect_site.py --from-yaml boticasperu --query paracetamol
    py recon/inspect_site.py --url "https://.../Search-Show?q=paracetamol"   # endpoint exacto

Dependencias: httpx, pyyaml  ->  py -m pip install httpx pyyaml
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.robotparser
from datetime import date
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    sys.exit(
        "Falta httpx. Instala las dependencias de la Fase 0:\n"
        "    py -m pip install httpx pyyaml"
    )

try:
    import yaml
except ImportError:
    yaml = None  # solo se necesita para --from-yaml; se avisa al usarlo


# --- Rutas del proyecto (este archivo vive en recon/) -----------------------
ROOT = Path(__file__).resolve().parent.parent
CONFIG_YAML = ROOT / "farmacias.yaml"
RAW_DIR = ROOT / "data" / "raw" / "recon"

# UA realistas (espejo de los de farmacias.yaml; rotamos uno por corrida).
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "application/json;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

DELAY_RANGE = (2.0, 6.0)  # respetar al sitio: delay aleatorio entre requests


def ext_for_content_type(content_type: str) -> str:
    ct = (content_type or "").lower()
    if "json" in ct:
        return "json"
    if "html" in ct:
        return "html"
    if "xml" in ct:
        return "xml"
    if "javascript" in ct or "ecmascript" in ct:
        return "js"
    if "text/plain" in ct:
        return "txt"
    return "bin"


def safe_slug(text: str, maxlen: int = 60) -> str:
    """Convierte un texto en un fragmento de nombre de archivo seguro."""
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", text.strip().lower())
    slug = slug.strip("_") or "x"
    return slug[:maxlen]


# --- Detección de WAF / Cloudflare ------------------------------------------
WAF_BODY_SIGNATURES = [
    "__cf_chl",          # Cloudflare challenge
    "cf-challenge",
    "cf_chl_opt",
    "/cdn-cgi/challenge-platform",
    "attention required",
    "checking your browser",
    "just a moment",
    "ddos protection by",
    "access denied",
    "request blocked",
    "incapsula",
    "akamai",
]


def detect_waf(headers: "httpx.Headers", status_code: int, body_sample: str) -> dict:
    """Heurística de detección de Cloudflare/WAF/anti-bot."""
    h = {k.lower(): v for k, v in headers.items()}
    signals = []

    server = h.get("server", "")
    if "cloudflare" in server.lower():
        signals.append(f"server={server}")

    for key in ("cf-ray", "cf-cache-status", "cf-mitigated", "cf-chl-bypass"):
        if key in h:
            signals.append(f"{key}={h[key]}")

    if any(k.startswith("x-akamai") or k.startswith("akamai") for k in h):
        signals.append("headers akamai-*")
    if "x-iinfo" in h or "incap_ses" in str(h.get("set-cookie", "")).lower():
        signals.append("incapsula/imperva")
    if "x-sucuri-id" in h:
        signals.append("sucuri")

    body_low = (body_sample or "").lower()
    matched_sigs = [s for s in WAF_BODY_SIGNATURES if s in body_low]
    if matched_sigs:
        signals.append("body:" + ",".join(matched_sigs))

    challenge_status = status_code in (403, 429, 503)
    if challenge_status and signals:
        signals.append(f"status={status_code} (probable challenge)")

    return {
        "waf_detectado": bool(signals),
        "server_header": server,
        "senales": signals,
        "probable_challenge": challenge_status and bool(signals),
    }


# --- robots.txt -------------------------------------------------------------
def check_robots(url: str, user_agent: str) -> dict:
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        allowed = rp.can_fetch(user_agent, url)
        crawl_delay = rp.crawl_delay(user_agent)
        return {
            "robots_url": robots_url,
            "leido": True,
            "permitido": bool(allowed),
            "crawl_delay": crawl_delay,
        }
    except Exception as exc:  # robots inaccesible: avisar, no bloquear
        return {
            "robots_url": robots_url,
            "leido": False,
            "permitido": None,
            "error": str(exc),
        }


# --- Construcción de URL -----------------------------------------------------
def build_search_url(dominio: str, query: str) -> str:
    """
    URL de búsqueda genérica. Para la Fase 0 sirve para tantear la página de
    resultados HTML. El endpoint JSON exacto se captura con DevTools (ver
    recon/README_devtools.md) y se pega en farmacias.yaml.
    """
    dominio = dominio.rstrip("/")
    q = urllib.parse.quote(query)
    # Patrón de búsqueda más común (Salesforce SFRA, VTEX y muchos SPA lo aceptan).
    return f"{dominio}/search?q={q}"


def load_yaml_domain(farmacia_id: str) -> str:
    if yaml is None:
        sys.exit("Falta pyyaml para --from-yaml. Instala: py -m pip install pyyaml")
    if not CONFIG_YAML.exists():
        sys.exit(f"No se encontró {CONFIG_YAML}")
    data = yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8"))
    for f in data.get("farmacias", []):
        if f.get("id") == farmacia_id:
            dominio = f.get("dominio")
            if not dominio:
                sys.exit(f"La farmacia '{farmacia_id}' no tiene 'dominio' en el YAML.")
            return dominio
    ids = ", ".join(f.get("id", "?") for f in data.get("farmacias", []))
    sys.exit(f"No existe la farmacia '{farmacia_id}'. Disponibles: {ids}")


# --- Inspección --------------------------------------------------------------
def inspect(url: str, site_label: str, query: Optional[str], no_delay: bool) -> int:
    user_agent = random.choice(USER_AGENTS)
    headers = dict(BASE_HEADERS)
    headers["User-Agent"] = user_agent

    print(f"\n=== Reconocimiento: {site_label} ===")
    print(f"URL    : {url}")
    print(f"UA     : {user_agent}")

    robots = check_robots(url, user_agent)
    if robots["leido"]:
        estado = "PERMITIDO" if robots["permitido"] else "BLOQUEADO por robots.txt"
        print(f"robots : {estado} ({robots['robots_url']})", end="")
        if robots.get("crawl_delay"):
            print(f" | crawl-delay={robots['crawl_delay']}s", end="")
        print()
        if robots["permitido"] is False:
            print("  ⚠  robots.txt desaconseja esta ruta. Revisa antes de continuar.")
    else:
        print(f"robots : no se pudo leer ({robots.get('error', 'desconocido')})")

    if not no_delay:
        delay = random.uniform(*DELAY_RANGE)
        print(f"delay  : esperando {delay:.1f}s antes de la petición...")
        time.sleep(delay)

    t0 = time.perf_counter()
    try:
        with httpx.Client(
            headers=headers,
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            resp = client.get(url)
    except httpx.HTTPError as exc:
        print(f"\n✗ Error de red: {type(exc).__name__}: {exc}")
        return 2
    elapsed = time.perf_counter() - t0

    content_type = resp.headers.get("content-type", "")
    body_bytes = resp.content
    body_sample = body_bytes[:8192].decode("utf-8", errors="replace")
    waf = detect_waf(resp.headers, resp.status_code, body_sample)

    print(f"\n--- Resultado ---")
    print(f"status        : {resp.status_code} {resp.reason_phrase}")
    print(f"content-type  : {content_type or '(sin header)'}")
    print(f"tamaño        : {len(body_bytes):,} bytes")
    print(f"tiempo        : {elapsed:.2f}s")
    if str(resp.url) != url:
        print(f"redirigido a  : {resp.url}")

    if waf["waf_detectado"]:
        print(f"WAF/Cloudflare: SÍ -> {', '.join(waf['senales'])}")
        if waf["probable_challenge"]:
            print("  ⚠  Probable challenge anti-bot. Considera el fallback Playwright")
            print("     (Nivel C): ver recon/README_devtools.md, sección Fallback.")
    else:
        print("WAF/Cloudflare: no detectado en esta respuesta")

    # --- Guardar crudo + metadatos ---
    fecha = date.today().isoformat()
    out_dir = RAW_DIR / fecha
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = ext_for_content_type(content_type)
    q_part = f"_{safe_slug(query)}" if query else ""
    base_name = f"{safe_slug(site_label)}{q_part}_{int(t0)}"
    raw_path = out_dir / f"{base_name}.{ext}"
    meta_path = out_dir / f"{base_name}.meta.json"

    raw_path.write_bytes(body_bytes)

    meta = {
        "fecha": fecha,
        "site_label": site_label,
        "query": query,
        "url_solicitada": url,
        "url_final": str(resp.url),
        "status_code": resp.status_code,
        "reason": resp.reason_phrase,
        "content_type": content_type,
        "tamano_bytes": len(body_bytes),
        "tiempo_seg": round(elapsed, 3),
        "user_agent": user_agent,
        "request_headers": headers,
        "response_headers": dict(resp.headers),
        "robots": robots,
        "waf": waf,
        "raw_file": raw_path.name,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nguardado crudo: {raw_path.relative_to(ROOT)}")
    print(f"guardado meta : {meta_path.relative_to(ROOT)}")
    print(
        "\nSiguiente paso: abre DevTools -> Network (Fetch/XHR) en el navegador para\n"
        "capturar el endpoint JSON real y pégalo en farmacias.yaml.\n"
        "Guía paso a paso: recon/README_devtools.md\n"
    )
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspecciona un sitio de farmacia y guarda la respuesta cruda (Fase 0).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--dominio", help="Dominio base, ej: https://www.boticasperu.pe")
    src.add_argument("--from-yaml", dest="from_yaml", help="ID de farmacia en farmacias.yaml")
    src.add_argument("--url", help="URL/endpoint exacto a inspeccionar (ignora --query para construir URL)")

    parser.add_argument("--query", "-q", help="Término de búsqueda, ej: paracetamol")
    parser.add_argument("--label", help="Etiqueta para los archivos de salida (por defecto se infiere)")
    parser.add_argument("--no-delay", action="store_true", help="Omitir el delay aleatorio (solo para pruebas)")

    args = parser.parse_args(argv)

    if args.url:
        url = args.url
        netloc = urllib.parse.urlparse(url).netloc
        label = args.label or safe_slug(netloc)
        return inspect(url, label, args.query, args.no_delay)

    if not args.query:
        parser.error("--query es obligatorio cuando usas --dominio o --from-yaml")

    if args.from_yaml:
        dominio = load_yaml_domain(args.from_yaml)
        label = args.label or args.from_yaml
    else:
        dominio = args.dominio
        label = args.label or safe_slug(urllib.parse.urlparse(dominio).netloc)

    url = build_search_url(dominio, args.query)
    return inspect(url, label, args.query, args.no_delay)


if __name__ == "__main__":
    raise SystemExit(main())
