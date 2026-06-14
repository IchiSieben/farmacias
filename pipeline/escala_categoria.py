"""pipeline/escala_categoria.py — Escala una CATEGORÍA por facetas Algolia.

Crece el comparador categoría por categoría (no volcado total): toma todos los
productos de una o más subcategorías Algolia de Inka/Mifarma y los cruza con
Boticas Perú usando el MISMO matcher endurecido de build_snapshot (presentaciones
reales + búsqueda combinada + reglas duras). Reutiliza la lógica ya validada para
no divergir del pipeline de producción.

Modo por defecto = REPORTE (no escribe nada): imprime cuántos productos hay,
la cobertura con Boticas y una muestra de matches para validar a ojo. La
integración a web/data.json es un paso aparte (build_snapshot), tras el visto bueno.

Uso:
    # Reporte de la categoría analgésicos/antigripales (las 2 subcats):
    py -m pipeline.escala_categoria --subcats "Analgésico y Antipirético,Antigripales"
    py -m pipeline.escala_categoria --subcats "Antigripales" --muestra 15

Python 3.9+.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Dict, List, Optional, Tuple

from core.adapters.boticasperu import BoticasPeruAdapter
from core.adapters.inkafarma import InkafarmaAdapter
from core.adapters.mifarma import MifarmaAdapter
from core.matcher import comparar
from core.modelo import Producto
from pipeline.build_snapshot import (_buscar_boticas, _match_boticas,
                                     _ppu_boticas, _comparacion)


def _pull_subcats(adapter, subcats: List[str]) -> Dict[str, Producto]:
    """Productos de una cadena InRetail en las subcategorías dadas (dedup objectID)."""
    out: Dict[str, Producto] = {}
    for sc in subcats:
        filtros = adapter._filtros(True, [f"subCategory:{sc}"])
        for p in adapter._query_paged("", filtros):
            out.setdefault(p.sku, p)
    return out


def construir(subcats: List[str], pausa: float = 0.12) -> dict:
    ink = InkafarmaAdapter(delay_range=(0, 0))
    mif = MifarmaAdapter(delay_range=(0, 0))
    bot = BoticasPeruAdapter(delay_range=(0, 0))

    with ink, mif, bot:
        # 1) Set canónico = unión de objectIDs en esas subcats (Inka base + Mifa).
        print("Recolectando productos de las subcategorías...", file=sys.stderr)
        base = _pull_subcats(ink, subcats)
        solo_mifa = 0
        for sku, p in _pull_subcats(mif, subcats).items():
            if sku not in base:
                base[sku] = p
                solo_mifa += 1
        print(f"  {len(base)} productos (objectID distintos; +{solo_mifa} solo en Mifarma)",
              file=sys.stderr)

        # 2) Por producto: presentaciones reales + match Boticas (matcher endurecido).
        filas: List[dict] = []
        matches: List[dict] = []
        n_bot = 0
        for i, (sku, ip) in enumerate(base.items()):
            try:
                inka_pres = ink.get_presentaciones(sku) or [ip]
            except Exception:
                inka_pres = [ip]
            try:
                mif_pres = {p.presentacion_kind: p for p in mif.get_presentaciones(sku)}
            except Exception:
                mif_pres = {}
            try:
                cands = _buscar_boticas(bot, ip.nombre_origen)
            except Exception:
                cands = []

            for ipres in inka_pres:
                kind = ipres.presentacion_kind or "pack"
                precios = {"inkafarma": ipres.precio}
                mpres = mif_pres.get(kind)
                if mpres and mpres.precio is not None:
                    precios["mifarma"] = mpres.precio

                best = _match_boticas(ipres, cands)
                if best:
                    precios["boticasperu"] = best.precio
                    n_bot += 1
                    r = comparar(ipres, best)
                    matches.append({
                        "sku": sku, "kind": kind,
                        "inka_nombre": ipres.nombre_origen,
                        "inka_pres": ipres.presentacion,
                        "inka_precio": ipres.precio,
                        "cant": ipres.cantidad_envase, "uni": ipres.unidad_envase,
                        "bot_nombre": best.nombre_origen,
                        "bot_precio": best.precio,
                        "bot_sku": best.sku,
                        "score": round(r.score, 1), "metodo": r.metodo,
                    })
                mb, brecha = _comparacion(precios)
                filas.append({
                    "sku": sku, "kind": kind, "nombre": ipres.nombre_origen,
                    "cadenas": list(precios), "con_boticas": "boticasperu" in precios,
                })
            time.sleep(pausa)
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{len(base)} productos (filas: {len(filas)}, "
                      f"matches Boticas: {n_bot})", file=sys.stderr)

    filas_3 = sum(1 for f in filas if f["con_boticas"])
    return {
        "n_productos": len(base),
        "n_filas": len(filas),
        "filas_3cadenas": filas_3,
        "filas_inka_mifa": len(filas) - filas_3,
        "matches": matches,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Escala una categoría por facetas (modo reporte).")
    parser.add_argument("--subcats", required=True,
                        help="Subcategorías Algolia separadas por coma")
    parser.add_argument("--muestra", type=int, default=15,
                        help="Cuántos matches con Boticas mostrar para validar")
    args = parser.parse_args(argv)
    subcats = [s.strip() for s in args.subcats.split(",") if s.strip()]

    res = construir(subcats)

    print("\n" + "=" * 70)
    print(f"CATEGORÍA: {', '.join(subcats)}")
    print("=" * 70)
    print(f"Productos (objectID distintos Inka/Mifarma): {res['n_productos']}")
    print(f"Filas (una por presentación pack/fracción):  {res['n_filas']}")
    print(f"\nCOBERTURA:")
    print(f"  3 cadenas (Inka + Mifa + Boticas): {res['filas_3cadenas']}")
    print(f"  Solo Inka + Mifarma (sin Boticas): {res['filas_inka_mifa']}")
    pct = 100 * res["filas_3cadenas"] // max(res["n_filas"], 1)
    print(f"  Cobertura Boticas: {pct}%")

    print(f"\n=== MUESTRA DE MATCHES CON BOTICAS (validar a ojo) ===")
    muestra = sorted(res["matches"], key=lambda m: m["score"])  # peores score primero (los dudosos)
    n = args.muestra
    sel = muestra[:n // 2] + muestra[-(n - n // 2):] if len(muestra) > n else muestra
    vistos = set()
    for m in sel:
        key = (m["sku"], m["kind"])
        if key in vistos:
            continue
        vistos.add(key)
        print(f"\n  [{m['score']:>5} {m['metodo']:>6}]  cant={m['cant']}{m['uni'] or ''}")
        print(f"    INKA   S/{(m['inka_precio'] or 0):6.2f}  {m['inka_nombre']}")
        print(f"    BOTICA S/{(m['bot_precio'] or 0):6.2f}  {m['bot_nombre']}  (pid {m['bot_sku']})")
    print(f"\n(mostrando {len(vistos)} de {len(res['matches'])} matches; "
          f"ordenados por score ascendente: los primeros son los más dudosos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
