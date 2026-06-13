"""pipeline/build_snapshot.py — Genera el data.json del buscador estático.

Toma ~150 productos de categorías de alta rotación y arma un snapshot de precios
de las 3 cadenas, listo para la página estática (web/data.json):

  1. Inkafarma como catálogo base: busca por términos de alta rotación y junta
     los hits (dedup por objectID).
  2. Mifarma: precio por el MISMO objectID (llave InRetail compartida) -> exacto.
  3. Boticas Perú: match por nombre+specs (core.matcher) con verificación de
     tamaño de envase; solo se acepta si es_match (umbral + reglas duras). Si no,
     la cadena queda sin precio para ese producto (la web muestra "—").

Uso:
    py -m pipeline.build_snapshot
    py -m pipeline.build_snapshot --objetivo 150 --salida web/data.json

Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from core.adapters.boticasperu import BoticasPeruAdapter
from core.adapters.inkafarma import InkafarmaAdapter
from core.adapters.mifarma import MifarmaAdapter
from core.matcher import comparar
from core.modelo import Producto
from core.normalizer import extrae_specs, nucleo
from pipeline import cambios

ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = ROOT / "web" / "data.json"
SNAP_DIR = ROOT / "data" / "snapshots"          # histórico append-only (ANEXO §C)
EVENTOS_DIR = ROOT / "data" / "processed"

# Términos de alta rotación por categoría (Inkafarma como catálogo base).
TERMINOS: Dict[str, List[str]] = {
    "analgesico": ["paracetamol", "ibuprofeno", "naproxeno", "aspirina", "apronax",
                   "dolocordralan", "ketoprofeno", "diclofenaco", "tramadol"],
    "antigripal": ["panadol antigripal", "antigripal", "nastizol", "bisolvon",
                   "mucosolvan", "tabcin", "vick", "ambroxol"],
    "alergia": ["loratadina", "clorfenamina", "cetirizina", "desloratadina"],
    "gastro": ["omeprazol", "ranitidina", "sal de andrews", "enterogermina",
               "simeticona", "metoclopramida", "lactulosa", "hioscina"],
    "vitaminas": ["redoxon", "vitamina c", "centrum", "supradyn", "calcio",
                  "complejo b", "vitamina d", "hierro"],
    "nutricion": ["ensure", "pediasure", "magnesol", "glucerna"],
    "cuidado_personal": ["colgate", "head shoulders", "protex", "dove jabon",
                         "sedal", "rexona", "gillette"],
    "dermo": ["cerave", "cetaphil", "eucerin", "isdin", "la roche posay", "nivea"],
    "bebe": ["huggies", "babysec", "johnson baby", "pampers"],
    "femenino": ["kotex", "nosotras", "always"],
    "primeros_auxilios": ["alcohol 70", "agua oxigenada", "curitas", "gasa",
                          "algodon", "alcohol en gel"],
    "cronicos": ["metformina", "losartan", "atorvastatina", "enalapril",
                 "amoxicilina", "azitromicina", "glibenclamida", "levotiroxina"],
}


# Guard de plausibilidad: dos farmacias rara vez difieren >65% en el MISMO
# producto; un salto así casi siempre delata un envase/variante distinto que se
# coló pese a las reglas del matcher. Se descarta el match (mejor "—" que dato falso).
_RATIO_MIN, _RATIO_MAX = 0.60, 1.65


def _precio_plausible(precio_bot: float, precio_ref: float) -> bool:
    if not precio_ref:
        return True
    return _RATIO_MIN <= (precio_bot / precio_ref) <= _RATIO_MAX


def _query_boticas(nombre: str) -> str:
    sp = extrae_specs(nombre)
    q = " ".join(nucleo(nombre).split()[:3])
    if sp.concentracion:
        q += " " + sp.concentracion
    return q.strip() or nombre


def _comparacion(precios: Dict[str, float]):
    """(mas_barato, brecha_pct) sobre las cadenas con precio (>=2)."""
    if len(precios) < 2:
        return None, None
    lo, hi = min(precios.values()), max(precios.values())
    ganadores = [c for c, v in precios.items() if v == lo]
    mb = ganadores[0] if len(ganadores) == 1 else "empate"
    brecha = round(100 * (hi - lo) / lo, 1) if lo else None
    return mb, brecha


def construir(objetivo: int, pausa: float = 0.15) -> dict:
    ink = InkafarmaAdapter(delay_range=(0, 0))
    mif = MifarmaAdapter(delay_range=(0, 0))
    bot = BoticasPeruAdapter(delay_range=(0, 0))

    base: Dict[str, dict] = {}  # objectID -> {inka, categoria}
    with ink, mif, bot:
        # 1) Catálogo base desde Inkafarma.
        print("Recolectando catálogo base (Inkafarma)...", file=sys.stderr)
        for categoria, terminos in TERMINOS.items():
            for t in terminos:
                if len(base) >= objetivo:
                    break
                try:
                    hits = ink.search(t, limit=3)
                except Exception as exc:
                    print(f"  ! inka '{t}': {exc}", file=sys.stderr)
                    continue
                for p in hits:
                    if p.sku not in base and p.precio is not None:
                        base[p.sku] = {"inka": p, "categoria": categoria}
            if len(base) >= objetivo:
                break
        print(f"  {len(base)} productos base.", file=sys.stderr)

        # 2) + Mifarma (objectID) y 3) + Boticas (fuzzy + tamaño).
        productos = []
        n_bot = 0
        for i, (sku, rec) in enumerate(base.items()):
            ip: Producto = rec["inka"]
            precios = {"inkafarma": ip.precio}
            promos = {"inkafarma": bool(ip.en_promocion)}
            urls = {"inkafarma": ip.url}

            try:
                mp = mif.get_object(sku)
                if mp and mp.precio is not None:
                    precios["mifarma"] = mp.precio
                    promos["mifarma"] = bool(mp.en_promocion)
                    urls["mifarma"] = mp.url
            except Exception:
                pass

            try:
                cands = bot.search(_query_boticas(ip.nombre_origen), limit=10)
                best, best_r = None, None
                for c in cands:
                    r = comparar(ip, c)
                    if (r.es_match and c.precio is not None
                            and _precio_plausible(c.precio, ip.precio)
                            and (not best_r or r.score > best_r.score)):
                        best, best_r = c, r
                if best:
                    precios["boticasperu"] = best.precio
                    promos["boticasperu"] = bool(best.en_promocion)
                    urls["boticasperu"] = best.url
                    n_bot += 1
            except Exception:
                pass

            mb, brecha = _comparacion(precios)
            productos.append({
                "id": sku,
                "nombre": ip.nombre_origen,
                "categoria": rec["categoria"],
                "marca": ip.marca,
                "precios": {k: round(v, 2) for k, v in precios.items()},
                "promos": {k: promos[k] for k in precios},
                "mas_barato": mb,
                "brecha_pct": brecha,
                "urls": {k: v for k, v in urls.items() if v},
            })
            time.sleep(pausa)
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(base)} procesados (Boticas: {n_bot})", file=sys.stderr)

    productos.sort(key=lambda p: (p["categoria"], p["nombre"]))
    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cadenas": [
            {"id": "inkafarma", "nombre": "Inkafarma"},
            {"id": "mifarma", "nombre": "Mifarma"},
            {"id": "boticasperu", "nombre": "Boticas Perú"},
        ],
        "categorias": sorted({p["categoria"] for p in productos}),
        "total": len(productos),
        "con_boticas": n_bot,
        "productos": productos,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Genera web/data.json (snapshot de precios).")
    parser.add_argument("--objetivo", type=int, default=150, help="N° de productos objetivo")
    parser.add_argument("--salida", default=str(OUT_DEFAULT))
    args = parser.parse_args(argv)

    # Histórico (ANEXO §C): comparar contra el snapshot anterior ANTES de guardar
    # el de hoy, para no diff-earse contra sí mismo.
    previo = cambios.cargar_snapshot_previo(SNAP_DIR)
    data = construir(args.objetivo)
    eventos = cambios.diff_snapshots(previo, data)   # anota tendencia/promo_cambio in-place

    out = Path(args.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    snap_path = cambios.persistir_snapshot(data, SNAP_DIR)
    fecha = data["generado"][:10]
    ev_path = cambios.escribir_eventos_csv(eventos, fecha, EVENTOS_DIR)

    con_bot = data["con_boticas"]
    tot = data["total"]
    print(f"\nListo: {tot} productos -> {out}")
    print(f"  Cobertura Boticas Perú: {con_bot}/{tot} ({100*con_bot//max(tot,1)}%)")
    print(f"  Snapshot histórico -> {snap_path}")
    if previo is None:
        print("  (primera corrida: sin snapshot previo, sin eventos ni flechas)")
    else:
        res = cambios.resumen_eventos(eventos)
        comp = previo["generado"][:10]
        print(f"  Cambios vs {comp}: {sum(res.values())} eventos -> {ev_path}")
        for tipo in ("nuevo", "baja_precio", "sube_precio", "inicia_promo", "fin_promo"):
            if res.get(tipo):
                print(f"    {tipo:13} {res[tipo]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
