"""pipeline/build_comparativa.py — Primera tabla comparativa (Inkafarma + Mifarma).

Flujo end-to-end:
  1. Lee la canasta ancla (productos_objetivo.yaml).
  2. Para cada SKU, trae el producto en cada cadena (getObject; objectID = llave
     InRetail compartida) y confirma el match con core.matcher (Capa 1, score 100).
  3. Arma la tabla comparativa: precio por cadena, cuál es más barata y la brecha.
  4. Calcula KPIs (SPEC §6) y escribe salidas a data/processed/:
       - comparativa_<fecha>.csv   (formato ancho, una fila por producto)
       - snapshots_<fecha>.csv     (formato largo, una fila por cadena — histórico)
       - comparativa_<fecha>.html  (tabla visible para portafolio/demo)

Uso:
    py -m pipeline.build_comparativa
    py -m pipeline.build_comparativa --cadenas inkafarma,mifarma

Python 3.9+. Dependencias: httpx, pyyaml.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from core.adapters.boticasperu import BoticasPeruAdapter
from core.adapters.inkafarma import InkafarmaAdapter
from core.adapters.mifarma import MifarmaAdapter
from core.modelo import Producto

ROOT = Path(__file__).resolve().parent.parent
CANASTA_YAML = ROOT / "productos_objetivo.yaml"
OUT_DIR = ROOT / "data" / "processed"

# Registro de adaptadores disponibles.
ADAPTERS = {
    "inkafarma": InkafarmaAdapter,
    "mifarma": MifarmaAdapter,
    "boticasperu": BoticasPeruAdapter,
}
NOMBRE_CADENA = {
    "inkafarma": "Inkafarma", "mifarma": "Mifarma", "boticasperu": "Boticas Perú",
}
# Cadenas que comparten el objectID InRetail (un solo sku sirve para ambas).
_INRETAIL = ("inkafarma", "mifarma")


def cargar_canasta() -> List[dict]:
    import yaml
    data = yaml.safe_load(CANASTA_YAML.read_text(encoding="utf-8")) or {}
    return data.get("productos", [])


class Fila:
    """Una fila de la tabla: un producto ancla con su oferta en cada cadena."""

    def __init__(self, match_id: str, categoria: str, nombre: str,
                 cadenas: List[str], skus: Dict[str, str]):
        self.sku = match_id          # id del producto canónico (para outputs)
        self.categoria = categoria
        self.nombre = nombre
        self.cadenas = cadenas
        self.skus = skus             # sku por cadena
        self.ofertas: Dict[str, Optional[Producto]] = {c: None for c in cadenas}

    def precio(self, cadena: str) -> Optional[float]:
        p = self.ofertas.get(cadena)
        return p.precio if p else None

    @property
    def disponibles(self) -> Dict[str, float]:
        return {c: self.precio(c) for c in self.cadenas if self.precio(c) is not None}

    @property
    def mas_barato(self) -> Optional[str]:
        d = self.disponibles
        if len(d) < 2:
            return None
        lo = min(d.values())
        ganadores = [c for c, v in d.items() if v == lo]
        return ganadores[0] if len(ganadores) == 1 else "empate"

    @property
    def brecha_abs(self) -> Optional[float]:
        d = self.disponibles
        if len(d) < 2:
            return None
        return round(max(d.values()) - min(d.values()), 2)

    @property
    def brecha_pct(self) -> Optional[float]:
        d = self.disponibles
        if len(d) < 2 or min(d.values()) == 0:
            return None
        return round(100 * (max(d.values()) - min(d.values())) / min(d.values()), 1)


def _skus_de(item: dict) -> Dict[str, str]:
    """Extrae el mapa sku-por-cadena, aceptando el atajo `sku` (InRetail)."""
    skus = dict(item.get("skus") or {})
    if "sku" in item:  # compat: un solo objectID InRetail
        for c in _INRETAIL:
            skus.setdefault(c, str(item["sku"]))
    return {c: str(v) for c, v in skus.items() if v}


def construir(cadenas: List[str], pausa: float = 0.12) -> List[Fila]:
    canasta = cargar_canasta()
    adapters = {c: ADAPTERS[c].from_yaml(delay_range=(0, 0)) for c in cadenas}
    filas: List[Fila] = []
    try:
        for item in canasta:
            skus = _skus_de(item)
            match_id = skus.get("inkafarma") or next(iter(skus.values()), "")
            fila = Fila(match_id, item.get("categoria", ""), item.get("nombre", ""),
                        cadenas, skus)
            for c in cadenas:
                sku = skus.get(c)
                if not sku:
                    continue  # sin equivalente en esta cadena -> "—"
                try:
                    fila.ofertas[c] = adapters[c].get_object(sku)
                except Exception as exc:
                    print(f"  ! {c} sku={sku}: {type(exc).__name__}: {exc}", file=sys.stderr)
                time.sleep(pausa)
            filas.append(fila)
    finally:
        for a in adapters.values():
            a.close()
    return filas


# --- KPIs (SPEC §6) ---------------------------------------------------------
def kpis(filas: List[Fila], cadenas: List[str]) -> dict:
    comparables = [f for f in filas if len(f.disponibles) >= 2]
    ganadas = {c: 0 for c in cadenas}
    empates = 0
    brechas = []
    for f in comparables:
        mb = f.mas_barato
        if mb == "empate":
            empates += 1
        elif mb:
            ganadas[mb] += 1
        if f.brecha_pct:
            brechas.append(f.brecha_pct)
    n = len(comparables)
    return {
        "total_canasta": len(filas),
        "comparables": n,
        "ganadas": ganadas,
        "empates": empates,
        "brecha_prom_pct": round(sum(brechas) / len(brechas), 1) if brechas else 0.0,
        "brecha_max_pct": max(brechas) if brechas else 0.0,
    }


# --- salidas ----------------------------------------------------------------
def _fmt(v: Optional[float]) -> str:
    return "" if v is None else f"{v:.2f}"


def imprimir_tabla(filas: List[Fila], cadenas: List[str], k: dict) -> None:
    col_prod = 38
    cabecera = "%-13s %-*s" % ("categoria", col_prod, "producto")
    cabecera += "".join("%9s" % NOMBRE_CADENA[c][:9] for c in cadenas)
    cabecera += "  %-11s %7s" % ("+ barato", "brecha%")
    print("\n" + cabecera)
    print("-" * len(cabecera))
    cat_prev = None
    for f in filas:
        cat = f.categoria if f.categoria != cat_prev else ""
        cat_prev = f.categoria
        fila = "%-13s %-*s" % (cat[:13], col_prod, (f.nombre or "")[:col_prod])
        fila += "".join("%9s" % (_fmt(f.precio(c)) or "—") for c in cadenas)
        mb = f.mas_barato or ""
        mb_lbl = "empate" if mb == "empate" else (NOMBRE_CADENA.get(mb, "—"))
        bp = f.brecha_pct
        fila += "  %-11s %7s" % (mb_lbl, "" if bp is None else f"{bp:+.1f}")
        print(fila)
    print("-" * len(cabecera))
    print("\n=== KPIs ===")
    print(f"Canasta: {k['total_canasta']} productos | comparables en ambas: {k['comparables']}")
    for c in cadenas:
        n = k["ganadas"][c]
        pct = 100 * n / k["comparables"] if k["comparables"] else 0
        print(f"  {NOMBRE_CADENA[c]} más barata en: {n}/{k['comparables']} ({pct:.0f}%)")
    print(f"  Empates: {k['empates']}")
    print(f"  Brecha de precio promedio (donde difieren): {k['brecha_prom_pct']}%")
    print(f"  Brecha máxima: {k['brecha_max_pct']}%")

    # Alertas: top brechas (lo que vende el dashboard, SPEC §6 vista #5).
    top = sorted([f for f in filas if f.brecha_pct], key=lambda f: -f.brecha_pct)[:5]
    if top:
        print("\n=== Mayores brechas (oportunidad de contraoferta) ===")
        for f in top:
            d = f.disponibles
            caro = max(d, key=d.get)
            print(f"  {f.nombre[:42]:42} +{f.brecha_pct:.1f}%  "
                  f"({NOMBRE_CADENA[caro]} S/{max(d.values()):.2f} vs "
                  f"S/{min(d.values()):.2f})")


def escribir_csv(filas: List[Fila], cadenas: List[str], ts: str, fecha: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ancho = OUT_DIR / f"comparativa_{fecha}.csv"
    cols = ["match_id", "categoria", "nombre_canonico"]
    for c in cadenas:
        cols += [f"{c}_precio", f"{c}_regular", f"{c}_promo"]
    cols += ["mas_barato", "brecha_abs", "brecha_pct", "capturado_en"]
    with ancho.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for f in filas:
            row = [f.sku, f.categoria, f.nombre]
            for c in cadenas:
                p = f.ofertas.get(c)
                row += [
                    _fmt(p.precio) if p else "",
                    _fmt(p.precio_regular) if p else "",
                    "si" if (p and p.en_promocion) else "",
                ]
            row += [f.mas_barato or "", _fmt(f.brecha_abs), f.brecha_pct if f.brecha_pct is not None else "", ts]
            w.writerow(row)

    # Formato largo (histórico / ANEXO §C, pestaña snapshots).
    largo = OUT_DIR / f"snapshots_{fecha}.csv"
    with largo.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["capturado_en", "cadena", "match_id", "nombre_origen",
                    "precio", "precio_regular", "en_promo", "url"])
        for f in filas:
            for c in cadenas:
                p = f.ofertas.get(c)
                if not p:
                    continue
                w.writerow([ts, c, f.sku, p.nombre_origen, _fmt(p.precio),
                            _fmt(p.precio_regular), "si" if p.en_promocion else "", p.url or ""])
    return ancho


def escribir_html(filas: List[Fila], cadenas: List[str], k: dict, ts: str, fecha: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"comparativa_{fecha}.html"

    def celda(f: Fila, c: str) -> str:
        p = f.ofertas.get(c)
        if not p:
            return '<td class="na">—</td>'
        clases = "precio"
        if f.mas_barato == c:
            clases += " barato"
        promo = ' <span class="promo">promo</span>' if p.en_promocion else ""
        return f'<td class="{clases}">S/ {p.precio:.2f}{promo}</td>'

    filas_html = []
    cat_prev = None
    for f in filas:
        cat = ""
        if f.categoria != cat_prev:
            cat = f'<tr class="cat"><td colspan="{len(cadenas)+3}">{f.categoria.replace("_"," ").title()}</td></tr>'
            cat_prev = f.categoria
        celdas = "".join(celda(f, c) for c in cadenas)
        bp = "" if f.brecha_pct is None else f"+{f.brecha_pct:.1f}%"
        filas_html.append(
            f'{cat}<tr><td class="prod">{f.nombre}</td>{celdas}'
            f'<td class="brecha">{bp}</td></tr>'
        )

    ths = "".join(f"<th>{NOMBRE_CADENA[c]}</th>" for c in cadenas)
    kpi_cards = "".join(
        f'<div class="kpi"><div class="num">{100*k["ganadas"][c]//max(k["comparables"],1)}%</div>'
        f'<div class="lbl">{NOMBRE_CADENA[c]} más barata</div></div>'
        for c in cadenas
    )
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Radar de Precios — Farmacias Perú</title>
<style>
 :root {{ --azul:#0a5; --gris:#f4f5f7; }}
 body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin:0; color:#1a1a1a; background:#fafafa; }}
 header {{ background:#0d2b45; color:#fff; padding:24px 32px; }}
 header h1 {{ margin:0 0 4px; font-size:22px; }}
 header p {{ margin:0; opacity:.8; font-size:13px; }}
 .kpis {{ display:flex; gap:16px; padding:20px 32px; flex-wrap:wrap; }}
 .kpi {{ background:#fff; border:1px solid #e3e6ea; border-radius:10px; padding:14px 20px; min-width:140px; }}
 .kpi .num {{ font-size:26px; font-weight:700; color:var(--azul); }}
 .kpi .lbl {{ font-size:12px; color:#667; }}
 table {{ border-collapse:collapse; width:calc(100% - 64px); margin:8px 32px 40px; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
 th, td {{ padding:9px 14px; text-align:left; font-size:14px; border-bottom:1px solid #eef0f2; }}
 th {{ background:var(--gris); font-size:12px; text-transform:uppercase; letter-spacing:.4px; color:#556; }}
 td.precio {{ text-align:right; font-variant-numeric:tabular-nums; }}
 td.barato {{ background:#e7f7ee; color:#077a3d; font-weight:600; }}
 td.na {{ text-align:right; color:#bbb; }}
 td.brecha {{ text-align:right; color:#c0392b; font-weight:600; }}
 tr.cat td {{ background:#0d2b45; color:#fff; font-size:12px; text-transform:uppercase; letter-spacing:.5px; }}
 .promo {{ background:#ffe08a; color:#7a5b00; font-size:10px; padding:1px 5px; border-radius:4px; }}
 footer {{ padding:0 32px 32px; color:#889; font-size:12px; }}
</style></head>
<body>
<header>
  <h1>📡 Radar de Precios — Farmacias Perú</h1>
  <p>Canasta de {k['total_canasta']} productos · {len(cadenas)} cadenas · captura {ts}</p>
</header>
<div class="kpis">
  {kpi_cards}
  <div class="kpi"><div class="num">{k['brecha_prom_pct']}%</div><div class="lbl">brecha promedio</div></div>
  <div class="kpi"><div class="num">{k['empates']}</div><div class="lbl">empates</div></div>
</div>
<table>
  <thead><tr><th>Producto</th>{ths}<th>Brecha</th></tr></thead>
  <tbody>
  {"".join(filas_html)}
  </tbody>
</table>
<footer>Verde = precio más bajo. Brecha = diferencia % sobre el más barato. Datos públicos de catálogo · monitoreo de precios.</footer>
</body></html>"""
    out.write_text(html, encoding="utf-8")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Arma la tabla comparativa de la canasta ancla.")
    parser.add_argument("--cadenas", default="inkafarma,mifarma,boticasperu",
                        help="Cadenas a comparar (coma). Default: las 3")
    args = parser.parse_args(argv)
    cadenas = [c.strip() for c in args.cadenas.split(",") if c.strip()]
    desconocidas = [c for c in cadenas if c not in ADAPTERS]
    if desconocidas:
        parser.error(f"cadenas sin adapter: {desconocidas}. Disponibles: {list(ADAPTERS)}")

    fecha = date.today().isoformat()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print(f"Construyendo comparativa de {len(cadenas)} cadenas...", file=sys.stderr)
    filas = construir(cadenas)
    k = kpis(filas, cadenas)
    imprimir_tabla(filas, cadenas, k)

    csv_path = escribir_csv(filas, cadenas, ts, fecha)
    html_path = escribir_html(filas, cadenas, k, ts, fecha)
    print(f"\nSalidas:\n  {csv_path}\n  {OUT_DIR / f'snapshots_{fecha}.csv'}\n  {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
