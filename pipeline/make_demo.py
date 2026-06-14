"""pipeline/make_demo.py — Genera web/data.demo.json con cambios SIMULADOS.

El histórico real solo muestra flechas a partir de la 2ª corrida (necesita un
snapshot previo con precios distintos). Para el portafolio, este script fabrica
un escenario realista de cambios SOBRE LOS PRODUCTOS REALES del último
web/data.json y lo hornea en web/data.demo.json, marcado claramente como demo
(`"demo": true` + banner en el web). NO toca el data.json real.

Cómo: toma el data.json real como "hoy" (actual) y construye un snapshot "previo"
sintético con precios/promos distintos en productos elegidos; luego reutiliza el
MISMO motor de diff de producción (pipeline.cambios) para anotar tendencia,
promo_cambio y el flag `nuevo`. Así la demo ejercita exactamente el código real.

Escenario: varias bajas y subidas de precio, 2 promos que inician y 1 SKU nuevo.

Uso:
    py -m pipeline.make_demo
    py -m pipeline.make_demo --base web/data.json --salida web/data.demo.json

Python 3.9+.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import List, Optional

from pipeline import cambios

ROOT = Path(__file__).resolve().parent.parent
BASE_DEFAULT = ROOT / "web" / "data.json"
OUT_DEFAULT = ROOT / "web" / "data.demo.json"


def _idx_con_cadena(prods: List[dict], cadena: str) -> List[int]:
    """Índices de productos que tienen precio en `cadena` (para perturbar)."""
    return [i for i, p in enumerate(prods) if p.get("precios", {}).get(cadena) is not None]


def _previo_precio(actual: float, delta: float) -> float:
    """Precio previo tal que (actual - previo) / previo == delta. delta<0 => bajó hoy."""
    return round(actual / (1 + delta), 2)


def construir_demo(base: dict) -> dict:
    actual = copy.deepcopy(base)
    previo = copy.deepcopy(base)
    previo["generado"] = "2026-06-12T20:00:00+00:00"   # "ayer"
    pa = actual["productos"]
    pp = previo["productos"]

    # Plan: (cadena, delta_hoy). delta<0 => ▼ bajó ; delta>0 => ▲ subió.
    bajas = [("inkafarma", -0.12), ("inkafarma", -0.22), ("mifarma", -0.08), ("boticasperu", -0.15)]
    subas = [("inkafarma", +0.09), ("inkafarma", +0.18), ("mifarma", +0.06)]
    promos = ["inkafarma", "mifarma"]   # inician promo hoy

    usados = set()

    def elegir(cadena: str) -> Optional[int]:
        # Reparte por la tabla: toma índices espaciados entre los candidatos.
        cands = [i for i in _idx_con_cadena(pa, cadena) if i not in usados]
        if not cands:
            return None
        i = cands[len(cands) // 3]   # algo hacia el inicio, determinista
        usados.add(i)
        return i

    notas = []
    # Bajas y subidas: el precio PREVIO se ajusta para que hoy muestre el delta.
    for cadena, d in bajas + subas:
        i = elegir(cadena)
        if i is None:
            continue
        hoy = pa[i]["precios"][cadena]
        pp[i]["precios"][cadena] = _previo_precio(hoy, d)
        notas.append((pa[i]["nombre"], cadena, f"{'baja' if d < 0 else 'sube'} {d:+.0%}", hoy))

    # Promos que inician hoy: actual=True, previo=False (en producto distinto a los de precio).
    for cadena in promos:
        i = elegir(cadena)
        if i is None:
            continue
        pa[i].setdefault("promos", {})[cadena] = True
        pp[i].setdefault("promos", {})[cadena] = False
        notas.append((pa[i]["nombre"], cadena, "inicia promo", pa[i]["precios"][cadena]))

    # SKU nuevo: existe hoy, ausente "ayer" (se quita del previo).
    cand_nuevo = next((i for i in range(len(pa)) if i not in usados), None)
    if cand_nuevo is not None:
        nuevo_id = pa[cand_nuevo]["id"]
        previo["productos"] = [p for p in pp if p["id"] != nuevo_id]
        notas.append((pa[cand_nuevo]["nombre"], "—", "nuevo (SKU)", None))

    # Recalcula el precio/unidad de las filas perturbadas para que sea coherente
    # con el precio simulado (precio ÷ cantidad de la presentación).
    for p in pa:
        cant = p.get("cantidad")
        if not cant:
            continue
        ppu = p.get("precio_unidad") or {}
        for c, precio in p.get("precios", {}).items():
            ppu[c] = round(precio / cant, 4)
        if ppu:
            p["precio_unidad"] = ppu

    # Motor de producción: anota tendencia/promo_cambio/nuevo en `actual`.
    eventos = cambios.diff_snapshots(previo, actual)

    actual["demo"] = True
    actual["demo_nota"] = ("Datos de DEMO: cambios de precio y promociones simulados "
                           "sobre productos reales para mostrar ▲▼ y badges.")
    actual["_demo_resumen_eventos"] = cambios.resumen_eventos(eventos)
    actual["_demo_cambios"] = [
        {"producto": n[0], "cadena": n[1], "cambio": n[2]} for n in notas
    ]
    return actual, notas, eventos


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Genera web/data.demo.json con cambios simulados.")
    parser.add_argument("--base", default=str(BASE_DEFAULT), help="data.json real de origen")
    parser.add_argument("--salida", default=str(OUT_DEFAULT))
    args = parser.parse_args(argv)

    base = json.loads(Path(args.base).read_text(encoding="utf-8"))
    demo, notas, eventos = construir_demo(base)

    out = Path(args.salida)
    out.write_text(json.dumps(demo, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Demo generada -> {out}")
    print(f"  Eventos simulados: {cambios.resumen_eventos(eventos)}")
    print("  Cambios aplicados:")
    for nombre, cadena, cambio, _ in notas:
        print(f"    {cambio:14} {cadena:11} {nombre[:42]}")
    print("\n  Ábrela con:  py -m http.server -d web 8000   y visita")
    print("  http://localhost:8000/index.html?demo=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
