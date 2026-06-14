"""recon/match_universal_demo.py — Validación de matches Inka↔Farmacia Universal.

Demo de SOLO LECTURA (no integra nada): cruza analgésicos/antigripales de
Inkafarma con Farmacia Universal usando el matcher endurecido.

NOTA sobre EAN: Universal SÍ expone EAN, pero Inkafarma/Mifarma NO (gtin/eanCode
vienen vacíos en su API). Como el match Capa 1 por EAN exige el código en AMBOS
lados, aquí NO aplica: todo va por fuzzy (Capa 2) con alineación por cantidad
exacta (misma lógica que Boticas). Se marca el método igualmente para evidenciarlo.

    py -m recon.match_universal_demo --muestra 15
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import List, Optional

from core.adapters.inkafarma import InkafarmaAdapter
from core.adapters.universal import UniversalAdapter
from core.matcher import comparar
from core.modelo import Producto
from core.normalizer import nucleo
from pipeline.build_snapshot import _match_boticas

SUBCATS = ["Analgésico y Antipirético", "Antigripales"]


def _query(nombre: str) -> str:
    """Término de búsqueda para Universal: núcleo (activo/marca), 1ros 2 tokens."""
    toks = nucleo(nombre).split()
    return " ".join(toks[:2]) or nombre


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Demo matches Inka↔Universal (no integra).")
    parser.add_argument("--muestra", type=int, default=15)
    args = parser.parse_args(argv)

    ink = InkafarmaAdapter(delay_range=(0, 0))
    uni = UniversalAdapter(delay_range=(0, 0))

    with ink, uni:
        # 1) productos Inka de las subcategorías.
        print("Recolectando analgésicos/antigripales de Inkafarma...", file=sys.stderr)
        refs = {}
        for sc in SUBCATS:
            for p in ink._query_paged("", ink._filtros(True, [f"subCategory:{sc}"])):
                refs.setdefault(p.sku, p)
        print(f"  {len(refs)} productos.", file=sys.stderr)

        # 2) por cada producto: presentaciones reales (precio+cantidad) + Universal.
        filas, matches = 0, []
        uni_con_ean = 0
        for i, (sku, ref) in enumerate(refs.items()):
            try:
                pres = ink.get_presentaciones(sku) or [ref]
            except Exception:
                pres = [ref]
            try:
                cands = uni.search(_query(ref.nombre_origen), limit=20)
            except Exception as exc:
                print(f"  ! universal '{ref.nombre_origen[:30]}': {exc}", file=sys.stderr)
                cands = []
            for ipres in pres:
                filas += 1
                best = _match_boticas(ipres, cands)   # alinea por cantidad exacta + reglas duras
                if best:
                    r = comparar(ipres, best)
                    if best.ean:
                        uni_con_ean += 1
                    matches.append({"ref": ipres, "uni": best,
                                    "metodo": r.metodo, "score": r.score})
            time.sleep(0.1)
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{len(refs)} (filas: {filas}, matches: {len(matches)})", file=sys.stderr)

    por_ean = [m for m in matches if m["metodo"] == "ean"]
    por_fuzzy = [m for m in matches if m["metodo"] != "ean"]
    print("\n" + "=" * 74)
    print("COBERTURA Inka↔Universal (analgésicos/antigripales)")
    print("=" * 74)
    print(f"Filas Inka (presentaciones): {filas} | con match en Universal: {len(matches)} "
          f"({100*len(matches)//max(filas,1)}%)")
    print(f"  método EAN (Capa 1): {len(por_ean)}   <- Inka/Mifa no exponen EAN, no aplica")
    print(f"  método fuzzy (Capa 2): {len(por_fuzzy)}")
    print(f"  (de esos matches, {uni_con_ean} traen EAN del lado Universal — disponible a futuro)")

    print(f"\n=== MUESTRA PARA VALIDAR A OJO ({args.muestra}) ===")
    por_fuzzy.sort(key=lambda m: m["score"])    # dudosos (score bajo) primero
    sel = por_fuzzy[: args.muestra]
    for m in sel:
        ref, uni_p = m["ref"], m["uni"]
        tag = "EAN " if m["metodo"] == "ean" else "fuzzy"
        eu = uni_p.ean or "—"
        print(f"\n  [{tag} score={m['score']:.0f}]  cant={ref.cantidad_envase}{ref.unidad_envase or ''}  (Universal EAN:{eu})")
        print(f"    INKA      S/{(ref.precio or 0):7.2f}  {ref.nombre_origen} · {ref.presentacion or ''}")
        print(f"    UNIVERSAL S/{(uni_p.precio or 0):7.2f}  {uni_p.nombre_origen}  (sku {uni_p.sku})")
    print(f"\n(mostrando {len(sel)} de {len(matches)} matches; ordenados por score asc)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
