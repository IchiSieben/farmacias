"""pipeline/export_web.py — Genera web/data/ para la UI v2 (contrato F4_UI_BRIEF §4).

    web/data/
      meta.json         generado, snapshot, cadenas[{id,nombre,grupo,color,logo}], categorias, kpis
      index.json        lista liviana para buscar (una fila por producto × presentación)
      cat_<cat>.json    mismo esquema que index, por categoría
      hist/<slug>.json  serie por producto: [{fecha, precios{cad}, promos{cad}}]
      kpis.json         por cadena, global y por categoría

Cada archivo lleva `version` (VERSION_ESQUEMA) y `generado`.

Fuentes (todas de solo lectura):
  - `web/data.json` (snapshot v1) — precios, presentaciones, urls, tendencia.
  - `data/snapshots/*.json` — historial.
  - crudo (`RAW_DIR`): fotos, principio activo y laboratorio. El snapshot v1 NO trae
    imagen (build_snapshot la descarta), así que se reconstruye desde lo que las
    cadenas respondieron: volcados `catalogo.jsonl` y respuestas grabadas por
    core.http_cache (`respuestas_*.jsonl.gz`), parseadas con los mismos adaptadores
    que las produjeron. Nunca se deriva una URL de imagen por patrón.
    Si el snapshot trae `imagenes{cad:url}` (contrato futuro de F1), eso manda.
  - `web-v2/public/logos/logos.json` (scripts/bajar_logos.py) — logo y color de cadena.

Uso:
    py -m pipeline.export_web
    py -m pipeline.export_web --snapshots ../farmacias/data/snapshots --raw ../farmacias/data/raw
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

ROOT = Path(__file__).resolve().parent.parent
VERSION_ESQUEMA = 1
CADENAS_ORDEN = ["inkafarma", "mifarma", "boticasperu", "universal"]


# --- crudo: fotos / activo / laboratorio ------------------------------------------
def _leer_jsonl(ruta: str) -> Iterator[dict]:
    abrir = gzip.open if ruta.endswith(".gz") else open
    with abrir(ruta, "rt", encoding="utf-8") as fh:
        for linea in fh:
            try:
                yield json.loads(linea)
            except ValueError:
                continue


def indice_crudo(raw: Optional[Path]) -> Dict[str, Dict[str, dict]]:
    """cadena -> {sku|url: {imagen, activo, laboratorio}} desde el crudo grabado."""
    idx: Dict[str, Dict[str, dict]] = {c: {} for c in CADENAS_ORDEN}
    if raw is None or not raw.is_dir():
        return idx

    def poner(cad: str, clave: Optional[str], **campos) -> None:
        if not clave:
            return
        actual = idx[cad].setdefault(clave, {})
        for k, v in campos.items():
            if v and not actual.get(k):
                actual[k] = v

    # 1) volcados de catálogo (Producto.to_row)
    for f in glob.glob(str(raw / "*" / "*" / "catalogo.jsonl")):
        for r in _leer_jsonl(f):
            cad = r.get("cadena")
            if cad in idx:
                for clave in (r.get("sku"), r.get("url")):
                    poner(cad, str(clave) if clave else None, imagen=r.get("imagen"),
                          activo=r.get("principio_activo"), laboratorio=r.get("laboratorio"))

    # 2) respuestas HTTP grabadas (orden cronológico: lo más nuevo gana al final)
    from core.adapters.boticasperu import BoticasPeruAdapter
    from core.adapters.universal import UniversalAdapter
    bot = BoticasPeruAdapter(delay_range=(0, 0))
    uni = UniversalAdapter(delay_range=(0, 0))
    try:
        from selectolax.parser import HTMLParser
    except ImportError:  # pragma: no cover
        HTMLParser = None  # type: ignore
    for cad in CADENAS_ORDEN:
        for f in sorted(glob.glob(str(raw / cad / "*" / "respuestas_*.jsonl.gz"))):
            for r in _leer_jsonl(f):
                if r.get("status") != 200 or not r.get("cuerpo"):
                    continue
                url = r.get("url", "")
                try:
                    if cad in ("inkafarma", "mifarma") and url.endswith("/queries"):
                        for res in json.loads(r["cuerpo"]).get("results", []):
                            for h in res.get("hits", []):
                                act = h.get("activePrinciples")
                                if isinstance(act, list):
                                    act = ", ".join(a for a in act if a)
                                poner(cad, str(h.get("objectID")), imagen=h.get("image"),
                                      activo=act, laboratorio=h.get("laboratory") or h.get("lab"))
                    elif cad == "boticasperu" and "Search-UpdateGrid" in url and HTMLParser:
                        for node in HTMLParser(r["cuerpo"]).css("div.product[data-pid]"):
                            p = bot._parse_tile(node)
                            if p is not None:
                                poner(cad, p.url, imagen=p.imagen)
                    elif cad == "universal" and "/products/search" in url:
                        for prod in json.loads(r["cuerpo"]):
                            for p in uni._map_producto(prod):
                                poner(cad, p.url, imagen=p.imagen)
                except (ValueError, TypeError, AttributeError, KeyError):
                    continue
    bot.close()
    uni.close()
    return idx


# --- filas ------------------------------------------------------------------------
def slug(pid: str) -> str:
    """`108010:pack` -> `108010_pack` (':' no es válido en nombres de archivo Windows)."""
    return pid.replace(":", "_").replace("/", "_")


def ahorro(precios: Dict[str, float]) -> Optional[dict]:
    """Métrica principal: cuánto ahorras comprando en la más barata vs. la más cara."""
    if len(precios) < 2:
        return None
    lo, hi = min(precios.values()), max(precios.values())
    return {
        "soles": round(hi - lo, 2),
        "pct": round(100 * (hi - lo) / lo, 1) if lo else None,
        # lista: en un empate hay más de una cadena "más barata"
        "en": [c for c in CADENAS_ORDEN if precios.get(c) == lo],
    }


def fila(p: dict, idx: Dict[str, Dict[str, dict]]) -> dict:
    sku = p["id"].split(":")[0]
    precios = {c: p["precios"][c] for c in CADENAS_ORDEN if c in p.get("precios", {})}
    urls = p.get("urls", {})
    imagenes = dict(p.get("imagenes") or {})
    extra: Dict[str, Any] = {}
    for cad in precios:
        clave = sku if cad in ("inkafarma", "mifarma") else urls.get(cad)
        info = idx.get(cad, {}).get(clave or "", {})
        if info.get("imagen") and cad not in imagenes:
            imagenes[cad] = info["imagen"]
        for k in ("activo", "laboratorio"):
            if info.get(k) and not extra.get(k):
                extra[k] = info[k]
    ah = ahorro(precios)
    # Miniatura: la foto de la cadena más barata; si no hay, la de cualquier cadena.
    orden = (ah["en"] if ah else []) + CADENAS_ORDEN
    imagen = next((imagenes[c] for c in orden if imagenes.get(c)), None)
    tend = {c: {"dir": t.get("dir"), "delta_pct": t.get("delta_pct")}
            for c, t in (p.get("tendencia") or {}).items() if c in precios}
    return {
        "id": p["id"],
        "slug": slug(p["id"]),
        "nombre": p.get("nombre"),
        "activo": extra.get("activo"),
        "laboratorio": extra.get("laboratorio"),
        "marca": p.get("marca"),
        "cat": p.get("categoria"),
        "pres": p.get("presentacion"),
        "cantidad": p.get("cantidad"),
        "unidad": p.get("unidad"),
        "precios": precios,
        "ppu": {c: v for c, v in (p.get("precio_unidad") or {}).items() if c in precios},
        "ahorro": ah,
        "brecha_pct": p.get("brecha_pct"),
        "imagen": imagen,
        "imagenes": imagenes,
        "promos": [c for c in CADENAS_ORDEN if (p.get("promos") or {}).get(c)],
        "tendencia": tend,
        "urls": {c: u for c, u in urls.items() if c in precios},
        "nuevo": bool(p.get("nuevo")),
    }


# --- historial --------------------------------------------------------------------
def historial(snapshots: Optional[Path], ids: set) -> Dict[str, List[dict]]:
    series: Dict[str, List[dict]] = {i: [] for i in ids}
    if snapshots is None or not snapshots.is_dir():
        return series
    for f in sorted(snapshots.glob("snapshot_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d.get("productos", []):
            if p["id"] in series:
                series[p["id"]].append({
                    "fecha": d["generado"],
                    "precios": {c: p["precios"][c] for c in CADENAS_ORDEN if c in p["precios"]},
                    "promos": {c: bool(v) for c, v in (p.get("promos") or {}).items()},
                })
    return series


# --- KPIs -------------------------------------------------------------------------
def kpis(filas: List[dict]) -> dict:
    def calcular(grupo: List[dict]) -> Dict[str, dict]:
        out = {}
        comparables = [f for f in grupo if len(f["precios"]) >= 2]
        for cad in CADENAS_ORDEN:
            con = [f for f in comparables if cad in f["precios"]]
            if not con:
                continue
            brechas = [100 * (f["precios"][cad] / min(f["precios"].values()) - 1) for f in con]
            out[cad] = {
                "productos": len(con),
                "pct_mas_barata": round(100 * sum(cad in f["ahorro"]["en"] for f in con) / len(con), 1),
                "brecha_media_vs_lider": round(sum(brechas) / len(brechas), 1),
                "promos_activas": sum(cad in f["promos"] for f in grupo),
            }
        return out

    cats = sorted({f["cat"] for f in filas if f["cat"]})
    return {"global": calcular(filas),
            "por_categoria": {c: calcular([f for f in filas if f["cat"] == c]) for c in cats}}


# --- escritura --------------------------------------------------------------------
def _escribir(ruta: Path, obj: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _proporcion(ruta: Path) -> Optional[float]:
    """Ancho/alto de un logo (SVG por viewBox/width-height, raster por Pillow)."""
    if not ruta.exists():
        return None
    if ruta.suffix.lower() == ".svg":
        cab = ruta.read_text(encoding="utf-8", errors="replace")[:2000]
        m = re.search(r'viewBox="\s*[\d.-]+[\s,]+[\d.-]+[\s,]+([\d.]+)[\s,]+([\d.]+)', cab)
        if m and float(m.group(2)):
            return round(float(m.group(1)) / float(m.group(2)), 3)
        return None
    from PIL import Image
    with Image.open(ruta) as im:
        return round(im.width / im.height, 3)


def exportar(data: dict, salida: Path, *, snapshots: Optional[Path], raw: Optional[Path],
             logos: Optional[Path]) -> Dict[str, Any]:
    idx = indice_crudo(raw)
    filas = [fila(p, idx) for p in data["productos"]]
    gen = data["generado"]
    base = {"version": VERSION_ESQUEMA, "generado": gen}

    info_logos = json.loads(logos.read_text(encoding="utf-8")) if logos and logos.exists() else {}
    cadenas = []
    for c in data["cadenas"]:
        info = info_logos.get(c["id"]) or {}
        archivo = info.get("archivo")
        cadenas.append({
            "id": c["id"], "nombre": c["nombre"], "grupo": c.get("grupo"),
            "color": info.get("color"), "logo": archivo,
            # ancho/alto del logo: la UI reserva el hueco antes de que cargue (sin CLS)
            "logo_ratio": _proporcion(logos.parent / archivo) if archivo else None,
        })
    cats = sorted({f["cat"] for f in filas if f["cat"]})
    k = kpis(filas)

    if salida.exists():
        if any(salida.iterdir()) and not (salida / "meta.json").exists():
            raise SystemExit(f"{salida} no parece un web/data/ generado (sin meta.json): no lo borro")
        shutil.rmtree(salida)  # generado: se reescribe entero (no quedan cat_/hist_ viejos)
    _escribir(salida / "meta.json", {**base, "snapshot": gen, "cadenas": cadenas,
                                     "grupos": data.get("grupos", []),
                                     "categorias": [{"id": c, "n": sum(f["cat"] == c for f in filas)}
                                                    for c in cats],
                                     "kpis": {"productos": len(filas),
                                              "con_todas": sum(len(f["precios"]) == len(CADENAS_ORDEN)
                                                               for f in filas),
                                              "por_cadena": k["global"]}})
    _escribir(salida / "index.json", {**base, "productos": filas})
    for c in cats:
        _escribir(salida / f"cat_{c}.json", {**base, "categoria": c,
                                             "productos": [f for f in filas if f["cat"] == c]})
    series = historial(snapshots, {f["id"] for f in filas})
    for f in filas:
        _escribir(salida / "hist" / f"{f['slug']}.json",
                  {**base, "id": f["id"], "serie": series.get(f["id"], [])})
    _escribir(salida / "kpis.json", {**base, **k})
    return {
        "filas": len(filas),
        "con_imagen": sum(1 for f in filas if f["imagen"]),
        "con_activo": sum(1 for f in filas if f["activo"]),
        "puntos_hist": sum(len(s) for s in series.values()),
        "categorias": len(cats),
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Genera web/data/ (contrato UI v2).")
    ap.add_argument("--datos", default=str(ROOT / "web" / "data.json"))
    ap.add_argument("--snapshots", default=str(ROOT / "data" / "snapshots"))
    ap.add_argument("--raw", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--logos", default=str(ROOT / "web-v2" / "public" / "logos" / "logos.json"))
    ap.add_argument("--salida", default=str(ROOT / "web" / "data"))
    args = ap.parse_args(argv)

    data = json.loads(Path(args.datos).read_text(encoding="utf-8"))
    for nombre in ("snapshots", "raw"):
        if not Path(getattr(args, nombre)).is_dir():
            print(f"  ! {nombre}: {getattr(args, nombre)} no existe (se exporta sin él)", file=sys.stderr)
    r = exportar(data, Path(args.salida), snapshots=Path(args.snapshots), raw=Path(args.raw),
                 logos=Path(args.logos))
    print(f"web/data/ v{VERSION_ESQUEMA}: {r['filas']} filas · imagen {r['con_imagen']} · "
          f"activo {r['con_activo']} · {r['puntos_hist']} puntos de historial · "
          f"{r['categorias']} categorías -> {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
