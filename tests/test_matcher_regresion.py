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

from core.ficha import clave_rs, extrae_rs_texto, ficha_de, normaliza_rs
from core.matcher import comparar, UMBRAL_REVISION
from core.modelo import Producto
from pipeline.build_snapshot import _match_boticas


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
    ("Maltofer ≠ Maltofer Fol (modificador composición: + ácido fólico)",
     "Maltofer 100mg/5ml Solución Bebible", "Maltofer Fol 100MG - Blister 10 UN"),
    # --- sesión validación Universal dermo/vitaminas ---
    ("Vitamina D ≠ Vitamina C (letra)",
     "Vitamina D Tableta - Frasco 60 UN", "Vitamina C Zinc Gomitas - Frasco 60 UN"),
    ("Supradyn ≠ Supradyn Pronatal (variante)",
     "Supradyn Gragea - Caja 30 UN", "Supradyn Pronatal Comprimidos - Caja 30 UN"),
    ("Pediasure ≠ Pediasure Peptigro (variante)",
     "Pediasure Vainilla Polvo - Lata 850 G", "Pediasure Peptigro Polvo Vainilla - Lata 850 G"),
    ("Forma gomita ≠ tableta (misma vitamina)",
     "Vitamina C Tabletas - Frasco 30 UN", "Vitamina C Gomitas - Frasco 30 UN"),
    # --- corrida 2026-09-25: casó con fuzzy 75 porque solo compartían palabras de
    # vía de administración ("inyectable", "jeringa"), no el principio activo ---
    ("Suprahyal (ác. hialurónico) ≠ Mensille (anticonceptivo inyectable)",
     "Suprahyal 25 Mg/2.5 Ml Solución Inyectable Jeringa Pre-llenada",
     "Mensille 25mg/5mg Suspensión Inyectable + Jeringa - Caja 1 UN"),
    # --- F3, corrida 2026-09-25: se colaban por texto; antes los tapaba el veto por
    # imagen, que se apagó (fotos del mismo producto difieren entre cadenas) ---
    ("Aspirador Nasal Nuby ≠ Owawa Aspirador Nasal (dispositivo: manda la marca)",
     "Aspirador Nasal Nuby", "Owawa Aspirador Nasal - Blíster 1 und"),
    ("CeraVe limpiador en aceite ≠ CeraVe gel limpiador (aceite ≠ gel)",
     "Limpiador Corporal de Ducha en Aceite Espumoso CeraVe",
     "Cerave Gel Limpiador Espumoso - Frasco 473 ML"),
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
    ("Maltofer bebible ↔ Maltofer Bebible Ampolla (la fracción sí casa)",
     "Maltofer 100mg/5ml Solución Bebible", "Maltofer Bebible 5ML - Ampolla 1UN"),
    # --- sesión validación Universal dermo/vitaminas (no romper correctos) ---
    ("Farma D 5000UI ↔ Farma D (sin token 'vitamin' -> regla letra no aplica)",
     "Farma D 5000UI Cápsula Blanda - Caja 30 UN", "Farma D 5000 UI Capsulas - Caja 30 UN"),
    ("Vitamina C ↔ Vitamina C (misma letra y forma)",
     "Vitamina C 1000mg Tableta - Frasco 30 UN", "Vitamina C 1000 mg Tabletas - Frasco 30 UN"),
    ("Pediasure ↔ Pediasure (misma variante, distinta caja - solo tamaño)",
     "Pediasure Vainilla Polvo - Lata 850 G", "Pediasure Vainilla en Polvo - Lata 850 G"),
    # --- F3: las reglas nuevas no rompen el cruce correcto del mismo producto ---
    ("Aspirador Nasal Nuby ↔ Nuby Aspirador Nasal (misma marca)",
     "Aspirador Nasal Nuby", "Nuby Aspirador Nasal  - Unidad 1 UN"),
    ("CeraVe limpiador en aceite ↔ CeraVe limpiador en aceite (Universal)",
     "Limpiador Corporal de Ducha en Aceite Espumoso CeraVe",
     "Cerave Limpiador en Aceite Espumoso Hidratante Piel Normal a Seca - Frasco 473 ml"),
    # --- F3: los vetaba la imagen (foto distinta entre cadenas) y eran correctos ---
    ("Diclofenaco 1% gel ↔ gel tópico (foto de otra cadena, mismo producto)",
     "Diclofenaco 1% Gel", "Diclofenaco 1% Gel Tópico - Tubo 50 G"),
    ("Glucerna vainilla ↔ Glucerna vainilla lata (foto de otra cadena)",
     "Glucerna Sabor Vainilla", "Glucerna Sabor Vainilla - Lata 850 G"),
]


# Guarda de precio en la ruta real (_match_boticas): aunque nombre y cantidad
# pasen, un precio fuera de [1/3, 3] del de referencia delata otro producto.
# (descripción, nombre ref, precio ref, nombre candidato, precio candidato, ¿casa?)
GUARDA_PRECIO = [
    ("Suprahyal S/257.80 ↔ Mensille S/19.20 (13×): se descarta",
     "Suprahyal 25 Mg/2.5 Ml Solución Inyectable Jeringa Pre-llenada", 257.8,
     "Mensille 25mg/5mg Suspensión Inyectable + Jeringa - Caja 1 UN", 19.2, False),
    ("Desloratadina blíster 10 S/2.70 ↔ S/17.90 (6,6×): se descarta",
     "Desloratadina 5mg Tableta Recubierta", 2.7,
     "Desloratadina 5 mg Tabletas - Blister 10 UN", 17.9, False),
    ("Simeticona S/2.70 ↔ S/6.60 (2,4×, genérico vs marca): brecha real, casa",
     "Simeticona 80mg/ml Suspensión Oral", 2.7,
     "Simeticona 80mg/ml Suspensión Oral - Frasco 15 ML", 6.6, True),
]


# Casos reales por la ruta _match_boticas, con los atributos que da cada fuente
# (registro sanitario, presentación del detalle). (descripción, ref, candidato, ¿casa?)
def _oferta(cadena: str, sku: str, nombre: str, precio: float, **attrs) -> Producto:
    p = Producto(cadena=cadena, sku=sku, nombre_origen=nombre, precio=precio)
    for k, v in attrs.items():
        setattr(p, k, v)
    return p


_SUPRADYN_INKA = _oferta(
    "inkafarma", "403172", "Supradyn Gragea", 48.0,
    presentacion="FRASCO 30 UN", presentacion_kind="pack",
    cantidad_envase=30.0, unidad_envase="un", registro_sanitario="DE-0340")

CASOS_REALES = [
    # Corrida 2026-09-25: texto, cantidad (30) y precio (S/48) coinciden, pero es
    # OTRO producto: R.S. DE-3831 (comprimidos Energy) vs DE-0340 (grageas). Verificado a mano.
    ("Supradyn Gragea DE-0340 ≠ Boticas Supradyn Energy DE-3831 (R.S. distinto)",
     _SUPRADYN_INKA,
     _oferta("boticasperu", "38936", "Supradyn Energy - Caja 30 UN", 48.0,
             registro_sanitario="DE-3831"),
     False),
    ("Supradyn Gragea DE-0340 ↔ Universal Supradyn Grageas DE0340 (mismo R.S.)",
     _SUPRADYN_INKA,
     _oferta("universal", "u-supradyn", "Supradyn Multivitamínico Grageas - Caja 30 und", 48.0,
             registro_sanitario="DE0340"),
     True),
]


# Capa 3 (imagen) y R.S. sin cantidad, sobre `comparar` con fichas armadas a mano.
# Hashes sintéticos de 64 bits: _H0 base; _H_INTER a 12 bits (zona intermedia);
# _H_DIST a 64 bits (claramente distinta).
_H0 = "a5a5a5a5a5a5a5a5"
_H_INTER = format(int(_H0, 16) ^ 0xFFF, "016x")
_H_DIST = format(int(_H0, 16) ^ 0xFFFFFFFFFFFFFFFF, "016x")


def _con_foto(p: Producto, h: str):
    f = ficha_de(p)
    f.imagen_phash = f.imagen_dhash = h
    return f


_SUPRADYN_BOT_OK = _oferta("boticasperu", "b-ok", "Supradyn Multivitamínico Grageas - Caja 30 UN", 48.1)
_PARACETAMOL_INKA = _oferta("inkafarma", "p1", "Paracetamol 500mg Tableta", 5.0,
                            presentacion="CAJA 100 UN", cantidad_envase=100.0,
                            unidad_envase="un", fuentes={"cantidad": "atributo"})
_PARACETAMOL_BOT = _oferta("boticasperu", "p2", "Paracetamol 500mg Tableta - Caja 100 UN", 5.5)
_PARACETAMOL_NOMBRE = _oferta("inkafarma", "p3", "Paracetamol 500mg Tableta - Caja 100 UN", 5.0)

# (descripción, a, ficha a, b, ficha b, ¿casa?, método esperado o None)
CAPA_FICHA = [
    ("mismo R.S. pero otra cantidad (30 vs 60): la cantidad manda, no es llave",
     _SUPRADYN_INKA, None,
     _oferta("universal", "u60", "Supradyn Multivitamínico Grageas - Caja 60 und", 90.0,
             registro_sanitario="DE0340"), None, False, None),
    ("texto 69,6 (sin R.S.) + foto idéntica: la imagen confirma 60–85",
     _SUPRADYN_INKA, _con_foto(_SUPRADYN_INKA, _H0),
     _SUPRADYN_BOT_OK, _con_foto(_SUPRADYN_BOT_OK, _H0), True, "imagen"),
    ("texto 69,6 + foto en zona intermedia: no decide (sigue sin casar)",
     _SUPRADYN_INKA, _con_foto(_SUPRADYN_INKA, _H0),
     _SUPRADYN_BOT_OK, _con_foto(_SUPRADYN_BOT_OK, _H_INTER), False, "fuzzy"),
    # El veto por imagen está apagado (matcher.VETO_IMAGEN): fotos del mismo producto
    # difieren entre cadenas tanto como dos productos al azar.
    ("texto 100 + foto claramente distinta + cantidad de atributo: NO veta (veto apagado)",
     _PARACETAMOL_INKA, _con_foto(_PARACETAMOL_INKA, _H0),
     _PARACETAMOL_BOT, _con_foto(_PARACETAMOL_BOT, _H_DIST), True, "fuzzy"),
    ("texto 100 + foto en zona intermedia: no veta",
     _PARACETAMOL_INKA, _con_foto(_PARACETAMOL_INKA, _H0),
     _PARACETAMOL_BOT, _con_foto(_PARACETAMOL_BOT, _H_INTER), True, "fuzzy"),
    ("texto 100 + foto distinta, cantidades solo del nombre: no veta",
     _PARACETAMOL_NOMBRE, _con_foto(_PARACETAMOL_NOMBRE, _H0),
     _PARACETAMOL_BOT, _con_foto(_PARACETAMOL_BOT, _H_DIST), True, "fuzzy"),
]


# Parseo del registro sanitario: (descripción, entrada, R.S. normalizado esperado).
# Entrada str -> normaliza_rs (campo propio); tuple -> extrae_rs_texto (descripción).
RS_PARSEO = [
    ("DE-0340 tal cual", "DE-0340", "DE-0340"),
    ("DE0340 sin guion (Universal)", "DE0340", "DE-0340"),
    ("'DE 0340' con espacio", "DE 0340", "DE-0340"),
    ("minúsculas", "de-0340", "DE-0340"),
    ("texto que no es R.S.", "Caja 30 UN", None),
    ("descripción Inka: 'Registro Sanitario DE-0340'",
     ("<ul><li>Sabor a Naranja</li><li>Registro Sanitario DE-0340</li></ul>",), "DE-0340"),
    ("'Reg. San. DE-0340' seguido de un RUC (no agarra el RUC)",
     ("No superar la dosis. Reg. San. DE-0340. Bayer S.A – RUC 20100096341",), "DE-0340"),
    ("'R.S: EN-02157' (Inka, analgésicos)", ("<ul><li>R.S: EN-02157</li></ul>",), "EN-02157"),
    ("mismo R.S. repetido en dos secciones -> uno",
     ("Registro Sanitario DE-0340", "Reg. San. DE0340"), "DE-0340"),
    ("pack con DOS R.S. distintos -> ninguno",
     ("RS EN-00538 Mentholatum", "R.S. EN-07516"), None),
    ("RUC suelto sin etiqueta -> ninguno", ("Bayer S.A – RUC 20100096341",), None),
]


def _ref(nombre: str, precio: float, cantidad: float, unidad: str) -> Producto:
    p = Producto(cadena="inkafarma", sku="R:" + nombre[:20], nombre_origen=nombre, precio=precio)
    p.cantidad_envase, p.unidad_envase = cantidad, unidad
    return p


def _cand(nombre: str, precio: float) -> Producto:
    return Producto(cadena="boticasperu", sku="C:" + nombre[:20], nombre_origen=nombre, precio=precio)


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

    print("\n" + "=" * 78)
    print("GUARDA DE PRECIO (ruta real _match_boticas, cruce fuzzy)")
    print("=" * 78)
    cantidades = {"Suprahyal": (1, "un"), "Desloratadina": (10, "un"), "Simeticona": (15, "ml")}
    for desc, na, pa, nb, pb, esperado in GUARDA_PRECIO:
        q, u = cantidades[na.split()[0]]
        casa = _match_boticas(_ref(na, pa, q, u), [_cand(nb, pb)]) is not None
        ok = casa == esperado
        fallos += not ok
        print(f"  [{'OK' if ok else 'FALLA':5}] {'casa' if casa else 'no casa':8} {desc}")

    print("\n" + "=" * 78)
    print("CASOS REALES (ruta _match_boticas con atributos de la fuente)")
    print("=" * 78)
    for desc, ref, cand, esperado in CASOS_REALES:
        casa = _match_boticas(ref, [cand]) is not None
        ok = casa == esperado
        fallos += not ok
        print(f"  [{'OK' if ok else 'FALLA':5}] {'casa' if casa else 'no casa':8} {desc}")

    print("\n" + "=" * 78)
    print("FICHA: imagen (Capa 3) y R.S. sin cantidad, sobre comparar()")
    print("=" * 78)
    for desc, a, fa, b, fb, casa, metodo in CAPA_FICHA:
        r = comparar(a, b, fa=fa, fb=fb)
        ok = r.es_match == casa and (metodo is None or r.metodo == metodo)
        fallos += not ok
        print(f"  [{'OK' if ok else 'FALLA':5}] score={r.score:5.1f} {r.metodo:18} {desc}")
        if not ok:
            print(f"          ! {r.motivo}")

    print("\n" + "=" * 78)
    print("REGISTRO SANITARIO (parseo y normalización)")
    print("=" * 78)
    for desc, entrada, esperado in RS_PARSEO:
        got = normaliza_rs(entrada) if isinstance(entrada, str) else extrae_rs_texto(*entrada)
        ok = got == esperado
        fallos += not ok
        print(f"  [{'OK' if ok else 'FALLA':5}] {str(got):10} {desc}")
    ok = clave_rs("DE-340") == clave_rs("DE-0340") != clave_rs("DE-3401")
    fallos += not ok
    print(f"  [{'OK' if ok else 'FALLA':5}] {'':10} clave: DE-340 == DE-0340 ≠ DE-3401")

    total = len(CAPA_FICHA) + len(RS_PARSEO) + 1 + len(DEBEN_BLOQUEAR) + len(DEBEN_CASAR) + len(GUARDA_PRECIO) + len(CASOS_REALES)
    print("\n" + "-" * 78)
    if fallos:
        print(f"REGRESIÓN CON FALLOS: {fallos}/{total}")
    else:
        print(f"REGRESIÓN LIMPIA: {total}/{total} casos OK")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
