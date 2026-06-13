"""core/matcher.py — "¿es el mismo producto?" entre cadenas (ANEXO §A).

Estrategia en capas, de la más confiable a la más cara:

  Capa 1 — Identificador duro: mismo `objectID` (llave InRetail compartida) o
           mismo `ean`. Match 1:1, score 100, sin ambigüedad.
  Capa 2 — Nombre + specs normalizados: fuzzy sobre el texto, con REGLAS DURAS
           (concentración y cantidad deben coincidir; 250mg ≠ 500mg).
  Capa 3 — Imagen (pHash/embeddings): hook para más adelante; hoy aporta 0.

Para el piloto Inkafarma↔Mifarma basta la Capa 1 (objectID compartido). La Capa 2
queda lista para cuando entre Boticas Perú (sin objectID InRetail).

Fuzzy: usa rapidfuzz si está instalado; si no, cae a difflib (stdlib). Python 3.9+.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .modelo import Producto
from .normalizer import extrae_specs, extrae_tamano, normaliza_texto, nucleo

# Tolerancia relativa para considerar dos tamaños de envase equivalentes
# (cubre redondeos: "1600 GR" vs "1.6 KG"). Más allá -> envases distintos.
_TOL_TAMANO = 0.10


# Comparación SEMÁNTICA de concentración. Las cadenas escriben la misma fuerza de
# distinta forma: Inkafarma como ratio "2.5mg/5ml" (mg por dosis), Boticas como
# numerador suelto "2.5mg" (omite el "/5ml"). Comparar strings crudos da falsos
# negativos. Reglas:
#   - mismas unidades (mg/mcg/g se unifican a mg; % y ui aparte).
#   - mismo numerador (strength): 2.5 == 2.5 ; 250 ≠ 500 -> distinto.
#   - dos ratios -> además mismo denominador: 2.5mg/5ml ≠ 2.5mg/10ml (concentración real distinta).
#   - ratio vs suelto con mismo numerador -> compatible (convención de Boticas).
_RE_CONC_PARSE = re.compile(r"(\d+(?:\.\d+)?)(mg|mcg|g|ui|%)(?:/(\d+(?:\.\d+)?)ml)?")
_FACTOR_MG = {"mg": 1.0, "g": 1000.0, "mcg": 0.001}


def _parse_conc(c: str):
    """'2.5mg/5ml' -> (2.5,'mg',5.0) ; '2.5mg' -> (2.5,'mg',None). None si no parsea."""
    m = _RE_CONC_PARSE.fullmatch(c)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    denom = float(m.group(3)) if m.group(3) else None
    if unit in _FACTOR_MG:                 # unifica masa a mg (1g == 1000mg)
        val *= _FACTOR_MG[unit]
        unit = "mg"
    return (val, unit, denom)


def _concentracion_compatible(ca: str, cb: str) -> bool:
    if ca == cb:
        return True
    pa, pb = _parse_conc(ca), _parse_conc(cb)
    if not pa or not pb:
        return ca == cb                    # no parseable -> exige igualdad literal (conservador)
    (va, ua, da), (vb, ub, db) = pa, pb
    if ua != ub:
        return False                       # unidades distintas (mg vs mcg vs %)
    if abs(va - vb) > 1e-6:
        return False                       # strength distinto (250 ≠ 500)
    if da is not None and db is not None:
        return abs(da - db) <= 1e-6        # dos ratios -> mismo denominador (5ml vs 10ml)
    return True                            # ratio vs suelto, mismo numerador -> compatible


def _tamano_incompatible(ta, tb) -> bool:
    """True si ambos tamaños existen, son de la misma clase y diferen > tolerancia."""
    if not ta or not tb:
        return False
    if ta[1] != tb[1]:          # distinta clase (ml vs g): no comparable -> no bloquea
        return False
    mayor = max(ta[0], tb[0]) or 1
    return abs(ta[0] - tb[0]) / mayor > _TOL_TAMANO

# Umbrales (ANEXO §A): >=85 match, 70–85 revisar a mano, <70 descartar.
UMBRAL_MATCH = 85.0
UMBRAL_REVISION = 70.0

# El núcleo (principio activo/marca) pesa más que el nombre completo, porque las
# cadenas nombran el empaque de forma muy distinta ("Tableta" vs "Caja 100 UN").
_W_NOMBRE = 0.35
_W_NUCLEO = 0.65

# Solo se bloquea por forma cuando es galénicamente incompatible (sólido vs
# líquido). NO entre polvo/efervescente/crema, que suelen coexistir ("polvo
# efervescente") y harían falsos negativos.
_FORMAS_SOLIDAS = {"tableta", "capsula"}
_FORMAS_LIQUIDAS = {"jarabe", "suspension", "solucion", "gotas"}


def _forma_incompatible(fa: Optional[str], fb: Optional[str]) -> bool:
    if not fa or not fb:
        return False
    return ((fa in _FORMAS_SOLIDAS and fb in _FORMAS_LIQUIDAS) or
            (fa in _FORMAS_LIQUIDAS and fb in _FORMAS_SOLIDAS))


# --- fuzzy: rapidfuzz si existe, si no difflib ------------------------------
# token_set_ratio: tolera que un nombre sea superconjunto del otro (empaque extra).
try:
    from rapidfuzz.fuzz import token_set_ratio as _ratio  # type: ignore

    def _sim(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return float(_ratio(a, b))
except ImportError:  # fallback stdlib (aprox: intersección de tokens)
    from difflib import SequenceMatcher

    def _sim(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        ta, tb = set(a.split()), set(b.split())
        inter = " ".join(sorted(ta & tb))
        resto_a = " ".join(sorted(ta - tb))
        resto_b = " ".join(sorted(tb - ta))
        s1 = SequenceMatcher(None, inter, (inter + " " + resto_a).strip()).ratio()
        s2 = SequenceMatcher(None, inter, (inter + " " + resto_b).strip()).ratio()
        return max(s1, s2) * 100.0


@dataclass
class Resultado:
    es_match: bool
    score: float
    metodo: str                # "id" | "ean" | "fuzzy" | "regla_dura"
    revisar: bool = False      # zona gris 70–85
    motivo: Optional[str] = None


def _clave_ean(p: Producto) -> Optional[str]:
    e = (p.ean or "").strip()
    return e or None


def match_por_id(a: Producto, b: Producto) -> Optional[str]:
    """Capa 1. Devuelve el método si hay identificador duro coincidente."""
    if a.sku and b.sku and str(a.sku) == str(b.sku):
        return "id"
    ea, eb = _clave_ean(a), _clave_ean(b)
    if ea and eb and ea == eb:
        return "ean"
    return None


def comparar(a: Producto, b: Producto) -> Resultado:
    """Decide si `a` y `b` son el mismo producto (ANEXO §A)."""
    # Capa 1: identificador duro.
    metodo = match_por_id(a, b)
    if metodo:
        return Resultado(True, 100.0, metodo)

    # Capa 2: specs + nombre, con reglas duras. (250mg ≠ 500mg, tableta ≠ jarabe.)
    sa, sb = extrae_specs(a.nombre_origen), extrae_specs(b.nombre_origen)
    if (sa.concentracion and sb.concentracion
            and not _concentracion_compatible(sa.concentracion, sb.concentracion)):
        return Resultado(False, 0.0, "regla_dura",
                         motivo=f"concentración distinta ({sa.concentracion} ≠ {sb.concentracion})")
    if sa.cantidad and sb.cantidad and sa.cantidad != sb.cantidad:
        return Resultado(False, 0.0, "regla_dura",
                         motivo=f"cantidad distinta ({sa.cantidad} ≠ {sb.cantidad})")
    if _forma_incompatible(sa.forma, sb.forma):
        return Resultado(False, 0.0, "regla_dura",
                         motivo=f"forma incompatible ({sa.forma} ≠ {sb.forma})")
    # Tamaño de envase: el size suele estar en `presentacion` (InRetail) o en el
    # nombre (Boticas) -> se combinan ambos para extraerlo.
    ta = extrae_tamano(f"{a.nombre_origen} {a.presentacion or ''}")
    tb = extrae_tamano(f"{b.nombre_origen} {b.presentacion or ''}")
    if _tamano_incompatible(ta, tb):
        return Resultado(False, 0.0, "regla_dura",
                         motivo=f"envase distinto ({ta[0]:g}{ta[1]} ≠ {tb[0]:g}{tb[1]})")

    # Score: núcleo (principio activo/marca) pesa más que el nombre completo.
    sim_nombre = _sim(sa.texto_norm, sb.texto_norm)
    sim_nucleo = _sim(nucleo(a.nombre_origen), nucleo(b.nombre_origen))
    score = _W_NOMBRE * sim_nombre + _W_NUCLEO * sim_nucleo

    if score >= UMBRAL_MATCH:
        return Resultado(True, score, "fuzzy")
    if score >= UMBRAL_REVISION:
        return Resultado(False, score, "fuzzy", revisar=True,
                         motivo="zona gris: revisar a mano")
    return Resultado(False, score, "fuzzy", motivo="bajo umbral")
