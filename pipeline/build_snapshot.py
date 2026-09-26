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
import dataclasses
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from core.adapter_base import CredencialRechazada
from core.adapters.boticasperu import BoticasPeruAdapter
from core.adapters.inkafarma import InkafarmaAdapter
from core.adapters.mifarma import MifarmaAdapter
from core.adapters.universal import UniversalAdapter
from core.ficha import clave_rs, ficha_de
from core import matcher
from core.matcher import comparar, Resultado, UMBRAL_IMAGEN, UMBRAL_REVISION
from core.modelo import Producto
from core.normalizer import nucleo
from pipeline import cambios

ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = ROOT / "web" / "data.json"
SNAP_DIR = ROOT / "data" / "snapshots"          # histórico append-only (ANEXO §C)
EVENTOS_DIR = ROOT / "data" / "processed"

# Conglomerados (grupos económicos): cadenas del mismo grupo comparten política
# de precios -> para el usuario, comparar Inkafarma vs Mifarma es comparar contra
# UN solo competidor. Fuente única del mapeo cadena->grupo (se hornea en data.json).
# Extensible: Fasa/BTL son InRetail (no se suman); Boticas Perú y Farmacia
# Universal son independientes (cada una su propio grupo).
GRUPOS: List[dict] = [
    {"id": "inretail", "nombre": "InRetail", "cadenas": ["inkafarma", "mifarma"]},
    {"id": "boticasperu", "nombre": "Boticas Perú", "cadenas": ["boticasperu"],
     "independiente": True},
    {"id": "universal", "nombre": "Farmacia Universal", "cadenas": ["universal"],
     "independiente": True},
]
_GRUPO_DE = {cad: g["id"] for g in GRUPOS for cad in g["cadenas"]}

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

# Semillas por SUBCATEGORÍA (facetas Algolia): traen la categoría COMPLETA, no solo
# los términos de alta rotación. Se siembran ANTES que TERMINOS (no las recorta el
# tope `objetivo`). Escalado validado categoría por categoría (ver
# pipeline.escala_categoria + regresión del matcher).
SUBCATS_SEED: Dict[str, List[str]] = {
    "analgesico": ["Analgésico y Antipirético"],
    "antigripal": ["Antigripales"],
}

# Categorías EXCLUIDAS del match cross-cadena (Boticas/Universal). El matcher
# empareja por PRINCIPIO ACTIVO; en cosmética/cuidado personal no existe (marca
# compartida + modelo distinto + sin concentración que discrimine: Gillette
# Sensor3 ↔ Mach3, Rexona Clinical ↔ Men V8), así que produciría falsos. En estas
# categorías solo se comparan las cadenas InRetail (Inka/Mifarma). Decisión de
# diseño: el comparador cubre medicamentos/suplementos/dermo, no cosmética.
SIN_CROSS_MATCH = {"cuidado_personal"}


def _seed_subcats(adapter, subcats: List[str]) -> Dict[str, Producto]:
    """ObjectIDs de una cadena InRetail en las subcategorías dadas (dedup)."""
    out: Dict[str, Producto] = {}
    for sc in subcats:
        for p in adapter._query_paged("", adapter._filtros(True, [f"subCategory:{sc}"])):
            if p.precio is not None:
                out.setdefault(p.sku, p)
    return out


# Guard de plausibilidad para TODO cruce fuzzy (Boticas, Universal): con la misma
# cantidad, más de 3× de diferencia delata otro producto que pasó las reglas
# (Suprahyal S/257.80 ↔ Mensille S/19.20). Mejor "—" que dato falso. El límite
# 0.60–1.65 de antes descartaba brechas reales genérico vs marca (2–2,6× en la
# corrida del 2026-09-25: Simeticona, Diclofenaco gel), por eso [1/3, 3].
_RATIO_MIN, _RATIO_MAX = 1 / 3, 3.0


def _precio_plausible(precio_cand: float, precio_ref: Optional[float]) -> bool:
    if not precio_ref:
        return True
    return _RATIO_MIN <= (precio_cand / precio_ref) <= _RATIO_MAX


def _query_boticas(nombre: str) -> str:
    """Query PRECISA: núcleo (principio activo + marca), SIN la concentración.

    Antes se anexaba la concentración ("2mg/5ml"), que Boticas suele omitir, y
    dejaba la búsqueda tan estrecha que no traía variantes nombradas distinto.
    """
    return " ".join(nucleo(nombre).split()[:3]) or nombre


def _query_boticas_amplia(nombre: str) -> str:
    """Query AMPLIA: solo el primer token del núcleo (principio activo / marca).

    Recupera variantes que Boticas nombra distinto (p.ej. "Clorfenamina Maleato
    ... oral" ↔ "Clorfenamina Maleto Jarabe C/C"). Trae más ruido, pero el matcher
    endurecido (cantidad exacta + principio activo) descarta los irrelevantes."""
    toks = nucleo(nombre).split()
    return toks[0] if toks else nombre


def _buscar_boticas(bot, nombre: str):
    """Candidatos Boticas combinando la query precisa y la amplia (dedup por sku)."""
    cands = bot.search(_query_boticas(nombre), limit=10)
    vistos = {c.sku for c in cands}
    qa = _query_boticas_amplia(nombre)
    if qa != _query_boticas(nombre):
        for c in bot.search(qa, limit=12):
            if c.sku not in vistos:
                vistos.add(c.sku)
                cands.append(c)
    return cands


def _buscar_universal(uni, nombre: str):
    """Candidatos de Farmacia Universal (VTEX) combinando query precisa + amplia.

    Mismo criterio que Boticas: precisa (núcleo, conserva marca) + amplia (1er
    token = activo/marca), dedup. El matcher endurecido filtra los irrelevantes.
    Universal NO expone EAN cruzable con Inka/Mifa -> match por fuzzy + cantidad.
    """
    cands = uni.search(_query_boticas(nombre), limit=12)
    vistos = {c.sku for c in cands}
    qa = _query_boticas_amplia(nombre)
    if qa != _query_boticas(nombre):
        for c in uni.search(qa, limit=12):
            if c.sku not in vistos:
                vistos.add(c.sku)
                cands.append(c)
    return cands


def _comparacion(precios: Dict[str, float]):
    """(mas_barato, brecha_pct) sobre las cadenas con precio (>=2)."""
    if len(precios) < 2:
        return None, None
    lo, hi = min(precios.values()), max(precios.values())
    ganadores = [c for c, v in precios.items() if v == lo]
    mb = ganadores[0] if len(ganadores) == 1 else "empate"
    brecha = round(100 * (hi - lo) / lo, 1) if lo else None
    return mb, brecha


def _qty_boticas(cand: Producto):
    """Cantidad del envase de un candidato (Boticas/Universal) como (valor, clase).

    La de la ficha (core.ficha): atributo de la API si existe (la "Presentación"
    de Universal), si no el nombre ("Frasco 120 ML" -> 120 ml, "Caja 30" -> 30 un).
    None si no es legible.
    """
    f = ficha_de(cand)
    return (f.cantidad, f.unidad) if f.cantidad is not None else None


def _ppu_boticas(precio, cand: Producto):
    """Precio por unidad de un candidato Boticas: precio / cantidad del envase."""
    q = _qty_boticas(cand)
    if precio and q and q[0]:
        return round(precio / q[0], 4)
    return None


def _cantidad_coincide(ref: Producto, cand: Producto, tol: float = 0.10):
    """¿La cantidad del candidato Boticas coincide con la de ESTA presentación?

    Cada fila Inka/Mifarma trae cantidad_envase exacta (API de detalle): se exige
    que Boticas tenga la MISMA cantidad y clase (blíster 10 solo casa con x10,
    caja 30 solo con x30). Si Boticas no expone cantidad legible -> no se confirma.
    """
    q = _qty_boticas(cand)
    if not q or q[1] != ref.unidad_envase:
        return False
    mayor = max(q[0], ref.cantidad_envase) or 1
    return abs(q[0] - ref.cantidad_envase) / mayor <= tol


_CAPA_1 = ("id", "ean", "registro_sanitario")

# Capa 4 (V2_PLAN §3.4): pares decididos a mano, mandan sobre todo lo anterior.
CURADOS_YAML = ROOT / "tests" / "matches_curados.yaml"
_curados_cache: Optional[Dict[Tuple[str, str, str], dict]] = None


def _curados() -> Dict[Tuple[str, str, str], dict]:
    """(ref "<objectID>:<pack|fraccion>", cadena, sku) -> entrada curada."""
    global _curados_cache
    if _curados_cache is None:
        filas = []
        if CURADOS_YAML.exists():
            filas = yaml.safe_load(CURADOS_YAML.read_text(encoding="utf-8")) or []
        _curados_cache = {(str(f["ref"]), f["cadena"], str(f["sku"])): f for f in filas}
    return _curados_cache


def _sin_rs(f):
    """La misma ficha sin registro sanitario: ¿casaría si el R.S. no existiera?"""
    return dataclasses.replace(
        f, registro_sanitario=None,
        fuentes={k: v for k, v in f.fuentes.items() if k != "registro_sanitario"})


# Fuerza de la evidencia para ordenar candidatos y repartir SKUs uno a uno: una
# llave dura gana a cualquier texto; a igual fuerza decide el score.
_FUERZA = {"curado": 0, "id": 1, "ean": 1, "registro_sanitario": 2}


def _fuerza(r: Resultado) -> int:
    if r.metodo in _FUERZA:
        return _FUERZA[r.metodo]
    return 4 if (r.revisar or not r.es_match) else 3


def _orden(c: Producto, r: Resultado):
    return (_fuerza(r), -round(r.score, 6), str(c.sku))


def _con_laboratorio(f, labs_rs):
    """Ficha con el laboratorio deducido de su R.S. (`labs_rs`: R.S. -> laboratorio,
    armado con Universal). Boticas no trae laboratorio: si su R.S. es el de un
    genérico Farmindustria en Universal, ese producto es de Farmindustria."""
    if not labs_rs or f.laboratorio:
        return f
    lab = labs_rs.get(clave_rs(f.registro_sanitario))
    if not lab:
        return f
    return dataclasses.replace(f, laboratorio=lab,
                               fuentes={**f.fuentes, "laboratorio": "rs_cruzado"})


def laboratorios_por_rs(productos) -> Dict[str, str]:
    """R.S. -> laboratorio conocido, desde ofertas que traen ambos: Universal (su
    `brand`) e InRetail cuando la `marca` es un laboratorio (PORTUGAL). Un R.S. con dos
    laboratorios distintos no se usa."""
    out: Dict[str, Optional[str]] = {}
    for p in productos:
        k = clave_rs(ficha_de(p).registro_sanitario)
        labs = matcher.laboratorio_canonico(p.laboratorio or p.marca)
        if not k or len(labs) != 1:
            continue
        lab = next(iter(labs))
        out[k] = lab if out.get(k, lab) == lab else None
    return {k: v for k, v in out.items() if v}


def _candidatos(ref: Producto, cands, enr=None, labs_rs=None):
    """Candidatos aceptables (Boticas o Universal) para ESA presentación.

    Devuelve (aceptables, equivalente, resultado_equivalente):
      - aceptables: [(candidato, resultado)] con score >= UMBRAL_REVISION, del más
        fuerte al más débil (`_orden`). La asignación uno a uno (`_asignar`) toma el
        primero que no se haya llevado otra fila. Con `enr`
        (pipeline.enriquecer.Enriquecedor), los candidatos con texto >= 60 que no
        decidió una llave dura se vuelven a comparar con la ficha completa: R.S. de
        Boticas (QuickView), hashes de foto y laboratorio deducido por R.S.
      - equivalente: el mejor candidato que cae SOLO por R.S. o laboratorio distinto y
        que sin ellos casaría (mismo activo, concentración, forma y cantidad; otro
        producto registrado, p.ej. genérico de otro laboratorio). No es un match: se
        guarda aparte (docs/MATCHING.md).
    Los pares de tests/matches_curados.yaml mandan sobre todo lo anterior.
    """
    if ref.cantidad_envase is None or ref.unidad_envase is None:
        return [], None, None
    ref_id = f"{ref.sku}:{ref.presentacion_kind or 'pack'}"
    curados = _curados()
    aceptables, eq, eq_r = [], None, None
    for c in cands:
        if c.precio is None:
            continue
        curado = curados.get((ref_id, c.cadena, str(c.sku)))
        if curado and curado.get("decision") == "veto":
            continue
        # Las fichas completas cuestan requests (QuickView, fotos): solo se piden para
        # los curados y para los candidatos que pasan cantidad, precio y texto >= 60.
        def fichas():
            if enr is None:
                return {}
            return {"fa": _con_laboratorio(enr.ficha(ref), labs_rs),
                    "fb": _con_laboratorio(enr.ficha(c), labs_rs)}

        if curado:
            base = comparar(ref, c, **fichas())  # solo para la evidencia
            r = Resultado(True, 100.0, "curado",
                          motivo=f"curado a mano: {curado.get('motivo', '')}",
                          evidencia={**base.evidencia, "decision": "curado",
                                     "revisado": curado.get("revisado")})
        else:
            # La cantidad exacta confirma la presentación: si coincide, basta con que
            # pase las reglas duras y la similitud de nombre llegue a la zona gris
            # (>=70). El precio solo veta lo absurdo (>3×).
            if not _cantidad_coincide(ref, c) or not _precio_plausible(c.precio, ref.precio):
                continue
            r = comparar(ref, c)
            # Veto por R.S. que la foto puede levantar (matcher.VETO_RS = "salvo_foto").
            veto_rs = (not r.es_match and r.metodo == "registro_sanitario"
                       and matcher.VETO_RS == "salvo_foto")
            if enr is not None and (veto_rs or (
                    r.metodo not in _CAPA_1 and r.metodo not in ("regla_dura", "laboratorio")
                    and r.score >= UMBRAL_IMAGEN)):
                r = comparar(ref, c, **fichas())
            if not r.es_match and r.metodo in ("registro_sanitario", "laboratorio"):
                # El veto ya pidió lo que hacía falta (Boticas: QuickView); Universal
                # trae el R.S. en la búsqueda y no pide nada.
                completas = fichas() if enr is not None and c.cadena == "boticasperu" else {}
                fa = completas.get("fa") or ficha_de(ref)
                fb = completas.get("fb") or ficha_de(c)
                r2 = comparar(ref, c, fa=_sin_rs(fa), fb=_sin_rs(fb), laboratorio=False)
                # Equivalente solo si sin el R.S. casaría de verdad (>= 85 o foto
                # idéntica), no por zona gris: Supradyn Energy (texto 72) no lo es.
                if r2.es_match and (not eq_r or r2.score > eq_r.score):
                    r2.evidencia.update(rs=[fa.registro_sanitario, fb.registro_sanitario],
                                        rs_fuente=[fa.fuente("registro_sanitario"),
                                                   fb.fuente("registro_sanitario")])
                    r2.motivo = f"otro producto registrado: {r.motivo}; {r2.motivo}"
                    eq, eq_r = c, r2
        if r.score >= UMBRAL_REVISION:
            aceptables.append((c, r))
    aceptables.sort(key=lambda cr: _orden(*cr))
    return aceptables, eq, eq_r


def _mejor_match(ref: Producto, cands, enr=None, labs_rs=None):
    """Mejor candidato para ESA presentación, sin mirar otras filas.

    Devuelve (match, resultado, equivalente, resultado_equivalente). `construir` no
    lo usa: reparte los SKUs uno a uno entre todas las filas (`_asignar`).
    """
    aceptables, eq, eq_r = _candidatos(ref, cands, enr, labs_rs)
    best, best_r = aceptables[0] if aceptables else (None, None)
    if eq is not None and best is not None and str(eq.sku) == str(best.sku):
        eq, eq_r = None, None
    return best, best_r, eq, eq_r


def _grupos_mismo_producto(pendientes) -> List[int]:
    """Grupo de cada fila: las filas Inkafarma que son el MISMO producto (mismo R.S. o
    EAN, misma presentación y cantidad) comparten grupo y reciben el mismo cruce. Un
    R.S. cubre varias presentaciones: sin la cantidad no se agrupa."""
    padre = list(range(len(pendientes)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    vista: Dict[Tuple, int] = {}
    for i, (_, ref, _, _) in enumerate(pendientes):
        if ref.cantidad_envase is None:
            continue
        f = ficha_de(ref)   # R.S./EAN de InRetail vienen en la oferta: sin red ni fotos
        pres = (ref.presentacion_kind or "pack", float(ref.cantidad_envase), ref.unidad_envase)
        for llave in (("rs", clave_rs(f.registro_sanitario)), ("ean", f.ean)):
            if not llave[1]:
                continue
            j = vista.setdefault(llave + pres, i)
            ri, rj = raiz(i), raiz(j)
            if ri != rj:
                padre[max(ri, rj)] = min(ri, rj)
    return [raiz(i) for i in range(len(pendientes))]


def _asignar(cadena: str, pendientes, opciones, enr=None) -> None:
    """Reparto uno a uno (greedy, decisión iC7): todos los pares (grupo, SKU) de
    mayor a menor fuerza y score; se acepta un par si ni el grupo ni el SKU tienen ya
    cruce. Un SKU no queda en dos filas salvo filas gemelas del mismo producto.
    Escribe precio, URL, evidencia y equivalente en cada fila."""
    grupos = _grupos_mismo_producto(pendientes)
    pares = []
    for i, (aceptables, _, _) in enumerate(opciones):
        fila_id = pendientes[i][0]["id"]
        for c, r in aceptables:
            pares.append((_orden(c, r), fila_id, i, c, r))
    pares.sort(key=lambda t: (t[0], t[1]))
    tomado_sku, cruce_grupo = set(), {}
    for _, _, i, c, r in pares:
        g = grupos[i]
        if g in cruce_grupo or str(c.sku) in tomado_sku:
            continue
        cruce_grupo[g] = (i, c, r)
        tomado_sku.add(str(c.sku))
    for i, (fila, ref, _, _) in enumerate(pendientes):
        _, eq, eq_r = opciones[i]
        elegido = cruce_grupo.get(grupos[i])
        if elegido is not None:
            j, c, r = elegido
            if j != i:   # fila gemela: solo si el SKU también es aceptable para ELLA
                r = next((rr for cc, rr in opciones[i][0] if str(cc.sku) == str(c.sku)), None)
                if r is None:
                    elegido = None
        if elegido is not None:
            fila["evidencia"][cadena] = _evidencia(ref, c, r)
            fila["precios"][cadena] = c.precio
            fila["precio_unidad"][cadena] = _ppu_boticas(c.precio, c)
            fila["promos"][cadena] = bool(c.en_promocion)
            fila["urls"][cadena] = c.url
        if eq is not None and not (elegido and str(eq.sku) == str(elegido[1].sku)):
            fila["equivalentes"][cadena] = _equivalente(ref, eq, eq_r)


def _evidencia(ref: Producto, cand: Producto, r: Resultado) -> Dict[str, Any]:
    """Evidencia compacta de un cruce (data.json y matches.parquet)."""
    ev = {"sku": str(cand.sku), "metodo": r.metodo, "score": round(r.score, 1),
          "revisar": r.revisar, "motivo": r.motivo,
          "ratio_precio": round(cand.precio / ref.precio, 2) if ref.precio else None}
    ev.update({k: v for k, v in r.evidencia.items() if k != "decision"})
    return ev


def _equivalente(ref: Producto, cand: Producto, r: Resultado) -> Dict[str, Any]:
    """Un equivalente (mismo activo/concentración/forma/cantidad, otro R.S.): no es
    precio de la fila; lleva su propio nombre, precio y enlace."""
    return {**_evidencia(ref, cand, r), "metodo": "equivalente", "nombre": cand.nombre_origen,
            "precio": round(cand.precio, 2), "url": cand.url}


def _match_boticas(ref: Producto, cands, enr=None):
    """Mejor candidato (Boticas o Universal) para ESA presentación.

    Se EXIGE que la presentación Inka tenga cantidad exacta (caso normal, del API
    de detalle) y que el candidato la iguale — esto, no el precio, decide la
    presentación. Así blíster 10 nunca casa con caja 30, y una brecha de precio
    moderada entre presentaciones idénticas es señal válida (solo >3× se descarta).

    Si la fila Inka NO tiene cantidad conocida (los "SUPER PACK"/bundles, donde el
    tamaño no es parseable), NO se empareja: un bundle no se alinea de forma fiable
    y antes colaba falsos (Pack 02 ↔ pack x3, polvo ↔ 20 botellas). Mejor "—".

    Con `enr`, las llaves y vetos de F3 (registro sanitario, imagen) deciden
    además de las reglas duras; un veto deja score 0 y nunca se acepta.
    """
    return _mejor_match(ref, cands, enr)[0]


def construir(objetivo: int, pausa: float = 0.15, *, adapter_kw=None,
              semillas: bool = True, generado: Optional[str] = None,
              enriquecedor=None) -> dict:
    """Arma el snapshot. Los kwargs opcionales los usa `pipeline.run` (F1):

    - `adapter_kw(cadena) -> dict`: kwargs extra por adaptador (p.ej. el
      transporte que graba/reproduce el crudo, ver core.http_cache).
    - `semillas=False`: omite SUBCATS_SEED (captura chica de prueba).
    - `generado`: fija el sello de la corrida (reproceso desde caché byte a byte).
    - `enriquecedor`: completa la ficha de los candidatos (F3, pipeline.enriquecer).
    """
    kw = adapter_kw or (lambda cadena: {})
    ink = InkafarmaAdapter(delay_range=(0, 0), **kw("inkafarma"))
    mif = MifarmaAdapter(delay_range=(0, 0), **kw("mifarma"))
    bot = BoticasPeruAdapter(delay_range=(0, 0), **kw("boticasperu"))
    uni = UniversalAdapter(delay_range=(0, 0), **kw("universal"))

    base: Dict[str, dict] = {}  # objectID -> {inka, categoria}
    with ink, mif, bot, uni:
        # 1) Catálogo base desde Inkafarma (descubrimiento por búsqueda Algolia).
        print("Recolectando catálogo base (Inkafarma)...", file=sys.stderr)
        for categoria, terminos in TERMINOS.items():
            for t in terminos:
                if len(base) >= objetivo:
                    break
                try:
                    hits = ink.search(t, limit=3)
                except CredencialRechazada:
                    raise  # key rotada: seguir solo repite el 403 con cada término
                except Exception as exc:
                    print(f"  ! inka '{t}': {exc}", file=sys.stderr)
                    continue
                for p in hits:
                    if p.sku not in base and p.precio is not None:
                        base[p.sku] = {"inka": p, "categoria": categoria}
            if len(base) >= objetivo:
                break
        print(f"  {len(base)} productos base (términos).", file=sys.stderr)

        # 1b) Semillas por SUBCATEGORÍA: se añaden ENCIMA del barrido por términos
        #     (sin contar contra `objetivo`) para escalar SOLO las categorías ya
        #     validadas a su subcategoría completa, sin arrastrar otras nuevas.
        print("Sembrando categorías escaladas (facetas de subcategoría)...", file=sys.stderr)
        for categoria, subcats in (SUBCATS_SEED.items() if semillas else []):
            for sku, p in _seed_subcats(ink, subcats).items():
                base.setdefault(sku, {"inka": p, "categoria": categoria})
        print(f"  {len(base)} productos base (con semillas de subcategoría).", file=sys.stderr)

        # 2) Por cada objectID, expandir a UNA FILA POR PRESENTACIÓN (pack/fracción)
        #    con precio real de cada cadena (API de detalle), y juntar los candidatos
        #    de Boticas y Universal. El cruce se decide después, entre todas las filas.
        productos = []
        pendientes = []   # (fila, presentación Inka, candidatos Boticas, candidatos Universal)
        for i, (sku, rec) in enumerate(base.items()):
            ip: Producto = rec["inka"]

            # Presentaciones reales (precio por pack/fracción) de cada cadena InRetail.
            try:
                inka_pres = ink.get_presentaciones(sku)
            except Exception:
                inka_pres = []
            if not inka_pres:   # fallback: detalle falló -> 1 fila con el precio del search
                inka_pres = [ip]
            try:
                mif_pres = {p.presentacion_kind: p for p in mif.get_presentaciones(sku)}
            except Exception:
                mif_pres = {}

            # Boticas y Universal: búsqueda combinada (precisa + amplia) por
            # producto; cada presentación elige su match (el matcher filtra).
            # Las categorías sin principio activo (cosmética) no se cruzan.
            if rec["categoria"] in SIN_CROSS_MATCH:
                cands, cands_uni = [], []
            else:
                try:
                    cands = _buscar_boticas(bot, ip.nombre_origen)
                except Exception:
                    cands = []
                try:
                    cands_uni = _buscar_universal(uni, ip.nombre_origen)
                except Exception:
                    cands_uni = []

            for ipres in inka_pres:
                kind = ipres.presentacion_kind or "pack"
                precios = {"inkafarma": ipres.precio}
                precio_unidad = {"inkafarma": ipres.precio_por_unidad}
                promos = {"inkafarma": bool(ipres.en_promocion)}
                urls = {"inkafarma": ipres.url}

                mpres = mif_pres.get(kind)
                if mpres and mpres.precio is not None:
                    precios["mifarma"] = mpres.precio
                    precio_unidad["mifarma"] = mpres.precio_por_unidad
                    promos["mifarma"] = bool(mpres.en_promocion)
                    urls["mifarma"] = mpres.url

                fila = {
                    "id": f"{sku}:{kind}",
                    "nombre": ipres.nombre_origen,
                    "categoria": rec["categoria"],
                    "marca": ipres.marca,
                    "presentacion": ipres.presentacion,
                    "cantidad": ipres.cantidad_envase,
                    "unidad": ipres.unidad_envase,
                    "precios": precios,
                    "precio_unidad": precio_unidad,
                    "promos": promos,
                    "mas_barato": None,
                    "brecha_pct": None,
                    "urls": urls,
                    "evidencia": {},
                    "equivalentes": {},
                }
                productos.append(fila)
                pendientes.append((fila, ipres, cands, cands_uni))
            time.sleep(pausa)
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(base)} productos (filas: {len(productos)})", file=sys.stderr)

        # 3) Cruce: candidatos aceptables por fila y reparto uno a uno de los SKUs.
        #    El laboratorio de un R.S. sale de Universal e InRetail y alcanza a Boticas.
        labs_rs = laboratorios_por_rs([ref for _, ref, _, _ in pendientes]
                                      + [c for _, _, _, cu in pendientes for c in cu])
        for cadena, idx in (("boticasperu", 2), ("universal", 3)):
            opciones = [_candidatos(pend[1], pend[idx], enriquecedor, labs_rs)
                        for pend in pendientes]
            _asignar(cadena, pendientes, opciones, enriquecedor)
        for fila in productos:
            fila["mas_barato"], fila["brecha_pct"] = _comparacion(fila["precios"])
            fila["precios"] = {k: round(v, 2) for k, v in fila["precios"].items()}
            fila["precio_unidad"] = {k: v for k, v in fila["precio_unidad"].items()
                                     if v is not None}
            fila["promos"] = {k: fila["promos"][k] for k in fila["precios"]}
            fila["urls"] = {k: v for k, v in fila["urls"].items() if v}

    # Dedup de filas GEMELAS: mismo nombre+categoría+presentación+cantidad y
    # precios idénticos en todas las cadenas (p.ej. genéricos con dos objectID
    # distintos pero idénticos para el usuario). Conserva la primera.
    vistos = set()
    dedup = []
    for p in productos:
        clave = (p["nombre"], p["categoria"], p.get("presentacion"),
                 p.get("cantidad"), p.get("unidad"),
                 tuple(sorted(p["precios"].items())))
        if clave in vistos:
            continue
        vistos.add(clave)
        dedup.append(p)
    n_dedup = len(productos) - len(dedup)
    if n_dedup:
        print(f"  Dedup: {n_dedup} filas gemelas eliminadas.", file=sys.stderr)
    productos = dedup
    n_bot = sum(1 for p in productos if "boticasperu" in p["precios"])
    n_uni = sum(1 for p in productos if "universal" in p["precios"])

    productos.sort(key=lambda p: (p["categoria"], p["nombre"], p.get("presentacion") or ""))
    return {
        "generado": generado or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cadenas": [
            {"id": "inkafarma", "nombre": "Inkafarma", "grupo": _GRUPO_DE.get("inkafarma")},
            {"id": "mifarma", "nombre": "Mifarma", "grupo": _GRUPO_DE.get("mifarma")},
            {"id": "boticasperu", "nombre": "Boticas Perú", "grupo": _GRUPO_DE.get("boticasperu")},
            {"id": "universal", "nombre": "Farmacia Universal", "grupo": _GRUPO_DE.get("universal")},
        ],
        "grupos": GRUPOS,
        "categorias": sorted({p["categoria"] for p in productos}),
        "total": len(productos),
        "con_boticas": n_bot,
        "con_universal": n_uni,
        "productos": productos,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Genera web/data.json (snapshot de precios).")
    parser.add_argument("--objetivo", type=int, default=150,
                        help="N° de productos por TÉRMINOS (las semillas de subcategoría se suman aparte)")
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
    con_uni = data.get("con_universal", 0)
    tot = data["total"]
    print(f"\nListo: {tot} productos -> {out}")
    print(f"  Cobertura Boticas Perú:     {con_bot}/{tot} ({100*con_bot//max(tot,1)}%)")
    print(f"  Cobertura Farmacia Universal: {con_uni}/{tot} ({100*con_uni//max(tot,1)}%)")
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
