"""tests/test_matcher_regresion.py — Casos de control del matcher (regresión).

Congela las decisiones del matcher que costó afinar (ver memoria
matching-quirks-cadenas): pares que DEBEN bloquearse (fármacos/variantes/envases
distintos) y pares legítimos que DEBEN casar pese a nomenclaturas distintas entre
cadenas. Correr SIEMPRE tras tocar core/matcher.py o core/normalizer.py.

    py -m tests.test_matcher_regresion      # imprime tabla y sale 0 si todo OK

Sin dependencias externas (no requiere pytest). Python 3.9+.
"""

from __future__ import annotations

import sys

from core.matcher import comparar, UMBRAL_REVISION
from core.modelo import Producto


def _p(nombre: str, sku: str) -> Producto:
    return Producto(cadena="x", sku=sku, nombre_origen=nombre, precio=1.0)


def _resultado(a: str, b: str):
    return comparar(_p(a, "A:" + a[:24]), _p(b, "B:" + b[:24]))


# Pipeline real (_match_boticas, ruta de cantidad exacta) acepta cualquier
# candidato con score >= UMBRAL_REVISION que no choque con una regla dura.
def _aceptaria(r) -> bool:
    return r.metodo != "regla_dura" and r.score >= UMBRAL_REVISION


def _bloqueado(r) -> bool:
    return r.metodo == "regla_dura" or r.score < UMBRAL_REVISION


# (descripción, nombre A, nombre B)
DEBEN_BLOQUEAR = [
    # --- memoria matching-quirks-cadenas ---
    ("250mg ≠ 500mg (concentración)",
     "Naproxeno 250mg Tableta", "Naproxeno 550mg Tableta - Caja 100 UN"),
    ("ratio distinto 2.5mg/5ml ≠ 2.5mg/10ml",
     "Desloratadina 2.5mg/5ml Jarabe", "Desloratadina 2.5mg/10ml Jarabe - Frasco 60 ML"),
    ("envase 60ml ≠ 120ml",
     "Clorfenamina 2mg/5ml Jarabe Frasco 60 ML", "Clorfenamina 2mg/5ml Jarabe - Frasco 120 ML"),
    ("forma tableta ≠ jarabe",
     "Paracetamol 500mg Tableta", "Paracetamol 500mg Solución oral - Frasco 120 ML"),
    ("Aeridin blíster 10 ≠ caja 30",
     "Aeridin 10mg Tableta x 10", "Aeridin 10mg Tableta - Caja 30 UN"),
    ("Norprazole(omeprazol) ≠ Dolocordralan(diclofenaco)",
     "Norprazole 20mg Cápsula de Liberación Retardada",
     "Dolocordralan Retard Comprimido de Liberación Retardada"),
    ("Bisolol ≠ Desloratadina",
     "Bisolol 5mg Tableta", "Desloratadina 5mg Tableta - Caja 10 UN"),
    ("Findaler ≠ Ciruelax",
     "Findaler Jarabe Frasco 60 ML", "Ciruelax Jarabe - Frasco 60 ML"),
    ("Panadol Antigripal ≠ Panadol (modificador composición)",
     "Panadol Antigripal Tableta", "Panadol 500mg Tableta - Caja 100 UN"),
    # --- nuevos de esta sesión (escalado analgésicos/antigripales) ---
    ("Paracetamol 500mg ≠ 1g (dosis en gramos)",
     "Paracetamol 500mg Tableta", "Paracetamol 1g Tableta - Caja 100 UN"),
    ("Fulgrip ≠ Ressfril (activo distinto, comparten 'gránulos')",
     "Fulgrip Noche Gránulos para Solución Oral",
     "Ressfril Noches Gránulos Para Solución Oral - Sobre 1 UN"),
    ("Panadol adulto ≠ Panadol Infantil (audiencia)",
     "Panadol 500mg Tableta", "Panadol Infantil 2+ años - Caja 100 UN"),
    ("Tableta normal ≠ Tableta Efervescente (presentación)",
     "Panadol 500mg Tableta", "Panadol 500 Mg Tableta Efervescente - Sobre 1 UN"),
]

DEBEN_CASAR = [
    # --- memoria matching-quirks-cadenas ---
    ("Aeridin caja 30 ↔ caja 30",
     "Aeridin 10mg Tableta - Caja 30 UN", "Aeridin 10mg Tableta Caja 30 UN"),
    ("Clorfenamina jarabe 120 ↔ 120 (ratio vs numerador suelto)",
     "Clorfenamina Maleato 2mg/5ml Jarabe Frasco 120 ML",
     "Clorfenamina Maleato 2 Mg Jarabe - Frasco 120 ML"),
    ("Clorfenamina jarabe 60 ↔ 60",
     "Clorfenamina Maleato 2mg/5ml Jarabe Frasco 60 ML",
     "Clorfenamina Maleato 2 Mg Jarabe - Frasco 60 ML"),
    ("Desloratadina ratio ↔ numerador suelto (líquido)",
     "Desloratadina 2.5mg/5ml Jarabe Frasco 60 ML",
     "Desloratadina 2.5 Mg Jarabe - Frasco 60 ML"),
    # --- nuevos de esta sesión (deben seguir casando tras los fixes) ---
    ("Paracetamol 1g ↔ 1g",
     "Paracetamol 1g Tableta", "Paracetamol 1g Tableta - Caja 100 UN"),
    ("Supracalm 1G ↔ 1 Gr (gramos misma dosis)",
     "Supracalm 1G Comprimido - Caja 100 UN", "Supracalm 1 Gr Comprimido - Caja 100 UN"),
    ("Tapsin SC 1g efervescente ↔ Tapsin efervescente 1G",
     "Tapsin SC 1g Polvo efervescente", "Tapsin efervescente 1G sabor Limón - Caja 20 UN"),
    ("Panadol Niños ↔ Panadol para Niños Infantil (ambos pediátricos)",
     "Panadol Niños 160mg/5ml Jarabe", "Panadol para Niños 2+ 160Mg Infantil Jarabe - Frasco 60 ML"),
    ("Efetamol Gránulos Efervescentes ↔ Efetamol (Boticas omite efervescente)",
     "Efetamol 1G Gránulos Efervescentes", "Efetamol - Caja 20 UN"),
    ("Bonadol Cápsulas Blandas ↔ Bonadol Capsulas Blandas",
     "Bonadol Cápsulas Blandas", "Bonadol Capsulas Blandas 500 G - Caja 100 UN"),
]


def main() -> int:
    fallos = 0
    print("=" * 78)
    print("DEBEN BLOQUEAR (fármaco/variante/envase/presentación distinta)")
    print("=" * 78)
    for desc, a, b in DEBEN_BLOQUEAR:
        r = _resultado(a, b)
        ok = _bloqueado(r)
        fallos += not ok
        print(f"  [{'OK' if ok else 'FALLA':5}] score={r.score:5.1f} {r.metodo:10} {desc}")
        if not ok:
            print(f"          ! NO bloqueó: {a!r} <> {b!r}")

    print("\n" + "=" * 78)
    print("DEBEN CASAR (legítimos pese a nomenclatura distinta entre cadenas)")
    print("=" * 78)
    for desc, a, b in DEBEN_CASAR:
        r = _resultado(a, b)
        ok = _aceptaria(r)
        fallos += not ok
        print(f"  [{'OK' if ok else 'FALLA':5}] score={r.score:5.1f} {r.metodo:10} {desc}")
        if not ok:
            print(f"          ! NO casó ({r.motivo}): {a!r} <> {b!r}")

    total = len(DEBEN_BLOQUEAR) + len(DEBEN_CASAR)
    print("\n" + "-" * 78)
    if fallos:
        print(f"REGRESIÓN CON FALLOS: {fallos}/{total}")
    else:
        print(f"REGRESIÓN LIMPIA: {total}/{total} casos OK")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
