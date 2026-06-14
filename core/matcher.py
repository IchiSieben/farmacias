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


# Principio activo / token discriminante: el fuzzy de núcleo se infla cuando dos
# productos comparten palabras GENÉRICAS (galénicas/sal/forma) aunque el activo
# difiera ("Norprazole ... liberación retardada" vs "Dolocordralan ... liberación
# retardada" -> set=80). Estas palabras NO identifican el producto y se excluyen
# del "token clave".
_GENERICO_NUCLEO = set(
    "liberacion retardada retard prolongada modificada lenta rapida controlada "
    "recubierta recubiertas recubierto recubiertos gragea grageas "
    "oral sublingual masticable bucal dispersable bebible "
    "sodico sodica potasico potasica calcico calcica magnesico "
    "maleato sulfato fosfato nitrato bromuro clorhidrato dihidrato monohidrato "
    "besilato base micronizado anhidro trihidrato "
    "acido vitamina complejo sales sal".split()
)
# Modificadores de COMPOSICIÓN: indican un producto DISTINTO porque cambian la
# fórmula (Panadol Antigripal ≠ Panadol; Dolocordralan Forte ≠ Dolocordralan;
# X Compuesto/Plus ≠ X simple). Si uno los tiene y el otro no -> productos
# distintos. NO se incluyen calificadores de AUDIENCIA/MARKETING (adulto,
# pediátrico, noche, extra, max…) porque un catálogo los omite y romperían
# matches legítimos (la concentración/forma ya discrimina adulto vs pediátrico).
_MODIFICADOR_NUCLEO = set(
    "antigripal compuesto compositum plus duo forte fuerte "
    "expectorante descongestionante gripa "
    "fol "          # "Maltofer Fol" (hierro + ácido fólico) ≠ "Maltofer" (hierro solo)
    "pronatal prenatal peptigro".split()   # Supradyn Pronatal ≠ Supradyn; Pediasure Peptigro ≠ Pediasure
)


def _tokens_clave(nombre: Optional[str]) -> set:
    """Tokens del núcleo que identifican el producto (principio activo / marca):
    sin palabras genéricas ni modificadores de variante."""
    return {t for t in nucleo(nombre).split()
            if t not in _GENERICO_NUCLEO and t not in _MODIFICADOR_NUCLEO}


# Audiencia PEDIÁTRICA: un producto para niños/bebés es distinto del de adulto
# (Panadol Infantil ≠ Panadol 500mg adulto). Se usa como flag BOOLEANO simétrico
# (no como modificador de núcleo): bloquea solo cuando un lado es pediátrico y el
# otro NO. Así "Panadol Niños" ↔ "Panadol para Niños Infantil" (ambos pediátricos)
# sigue casando, pero "Panadol 500mg" (adulto) ↔ "Panadol Infantil" se descarta.
_PEDIATRICO = set(
    "infantil infantiles pediatrico pediatrica pediatricos pediatricas "
    "ninos nino nina ninas bebe bebes".split()
)


def _es_pediatrico(p: Producto) -> bool:
    return bool(_PEDIATRICO & set(nucleo(p.nombre_origen).split()))


def _activo_compatible(a: Producto, b: Producto) -> bool:
    """¿Comparten principio activo/marca y la MISMA variante?

    Bloquea matches donde el núcleo se parece solo por palabras genéricas: exige
    (1) compartir al menos un token clave y (2) los mismos modificadores de
    variante (antigripal/forte/plus…). Si algún lado no tiene token clave, no se
    bloquea (no hay con qué discriminar)."""
    ka = _tokens_clave(a.nombre_origen)
    kb = _tokens_clave(b.nombre_origen)
    if ka and kb and not (ka & kb):
        return False
    ma = {t for t in nucleo(a.nombre_origen).split() if t in _MODIFICADOR_NUCLEO}
    mb = {t for t in nucleo(b.nombre_origen).split() if t in _MODIFICADOR_NUCLEO}
    return ma == mb

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


# Efervescente vs tableta normal = presentaciones distintas (como blíster≠caja).
# Se bloquea solo el CONFLICTO EXPLÍCITO (un lado es tableta/cápsula plana y el
# otro dice "efervescente"); NO "efervescente vs forma sin especificar", porque
# Boticas a veces omite "efervescente" (p.ej. "Efetamol - Caja 20") y eso rompería
# matches legítimos. Polvo/gránulos efervescentes tampoco cuentan como tableta plana.
_NO_PLANA = {"polvo", "granulos", "granulado", "granulada",
             "jarabe", "solucion", "suspension", "gotas"}


def _es_efervescente(nombre: Optional[str]) -> bool:
    return "efervescente" in normaliza_texto(nombre)


def _es_tableta_plana(nombre: Optional[str]) -> bool:
    """¿Es explícitamente un sólido oral NO efervescente (tableta/cápsula seca)?"""
    toks = set(normaliza_texto(nombre).split())
    if "efervescente" in toks or toks & _NO_PLANA:
        return False
    return bool(toks & {"tableta", "capsula"})


def _presentacion_incompatible(a: Producto, b: Producto) -> bool:
    return ((_es_efervescente(a.nombre_origen) and _es_tableta_plana(b.nombre_origen)) or
            (_es_efervescente(b.nombre_origen) and _es_tableta_plana(a.nombre_origen)))


# Vitaminas: la LETRA identifica el producto (Vitamina D ≠ Vitamina C), pero es de
# 1 carácter y el núcleo la descarta -> "vitamin"/"vitamina" como token rescataba
# falsos (Vitamin D ↔ Vitamin C+Zinc). Se extrae la letra que sigue a "vitamin[a]"
# y, si ambos lados la declaran y no comparten ninguna, se bloquea.
_RE_VITAMINA = re.compile(r"\bvitamin[a]?\s+([a-k])(?=\b|\d)")


def _vitamina_letras(nombre: Optional[str]) -> set:
    return set(_RE_VITAMINA.findall(normaliza_texto(nombre)))


def _vitamina_incompatible(a: Producto, b: Producto) -> bool:
    la, lb = _vitamina_letras(a.nombre_origen), _vitamina_letras(b.nombre_origen)
    return bool(la and lb and not (la & lb))


# Forma gomita (masticable/gummy) ≠ tableta/cápsula seca: presentaciones distintas
# (común en vitaminas). Bloquea solo el conflicto explícito gomita vs pastilla.
def _es_gomita(nombre: Optional[str]) -> bool:
    return "gomita" in normaliza_texto(nombre)


def _gomita_incompatible(a: Producto, b: Producto) -> bool:
    ga, gb = _es_gomita(a.nombre_origen), _es_gomita(b.nombre_origen)
    if ga == gb:
        return False
    otro = b if ga else a               # el que NO es gomita
    return extrae_specs(otro.nombre_origen).forma in {"tableta", "capsula"}


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
    metodo: str                # "id" | "ean" | "fuzzy" | "regla_dura" | "imagen"
    revisar: bool = False      # zona gris 70–85
    motivo: Optional[str] = None


# Distancia de Hamming máxima entre pHash para aceptar "misma foto" (Capa 3).
_UMBRAL_HAMMING = 10


def _imagenes_coinciden(url_a, url_b, phash_fn) -> Optional[bool]:
    """True/False según pHash; None si falta alguna imagen o hash (no decide)."""
    if not url_a or not url_b:
        return None
    ha, hb = phash_fn(url_a), phash_fn(url_b)
    if ha is None or hb is None:
        return None
    return (ha - hb) <= _UMBRAL_HAMMING      # imagehash: '-' = distancia de Hamming


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


def comparar(a: Producto, b: Producto, *, phash_fn=None) -> Resultado:
    """Decide si `a` y `b` son el mismo producto (ANEXO §A).

    `phash_fn` (opcional): callable(url)->hash perceptual (ver core.imagen.phash).
    Si se inyecta, activa la Capa 3 SOLO en la zona gris (score 70–85): se compara
    la foto de cada producto y, si coinciden, se confirma el match. Sin inyectar,
    el matcher no toca la red (comportamiento por defecto).
    """
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
    if _presentacion_incompatible(a, b):
        return Resultado(False, 0.0, "regla_dura",
                         motivo="presentación distinta (efervescente vs tableta normal)")
    # Tamaño de envase: el size suele estar en `presentacion` (InRetail) o en el
    # nombre (Boticas) -> se combinan ambos para extraerlo.
    ta = extrae_tamano(f"{a.nombre_origen} {a.presentacion or ''}")
    tb = extrae_tamano(f"{b.nombre_origen} {b.presentacion or ''}")
    if _tamano_incompatible(ta, tb):
        return Resultado(False, 0.0, "regla_dura",
                         motivo=f"envase distinto ({ta[0]:g}{ta[1]} ≠ {tb[0]:g}{tb[1]})")
    # Principio activo / variante: no basta con parecerse por palabras genéricas.
    if not _activo_compatible(a, b):
        return Resultado(False, 0.0, "regla_dura",
                         motivo="principio activo o variante distinta")
    # Audiencia: pediátrico vs adulto/sin marcar -> producto distinto.
    if _es_pediatrico(a) != _es_pediatrico(b):
        return Resultado(False, 0.0, "regla_dura",
                         motivo="audiencia distinta (pediátrico vs adulto)")
    # Vitaminas: letra distinta (D ≠ C) -> producto distinto.
    if _vitamina_incompatible(a, b):
        return Resultado(False, 0.0, "regla_dura",
                         motivo="vitamina distinta (letra)")
    # Forma gomita vs tableta/cápsula -> presentación distinta.
    if _gomita_incompatible(a, b):
        return Resultado(False, 0.0, "regla_dura",
                         motivo="forma distinta (gomita vs tableta)")

    # Score: núcleo (principio activo/marca) pesa más que el nombre completo.
    sim_nombre = _sim(sa.texto_norm, sb.texto_norm)
    sim_nucleo = _sim(nucleo(a.nombre_origen), nucleo(b.nombre_origen))
    score = _W_NOMBRE * sim_nombre + _W_NUCLEO * sim_nucleo

    if score >= UMBRAL_MATCH:
        return Resultado(True, score, "fuzzy")
    if score >= UMBRAL_REVISION:
        # Capa 3 (solo zona gris): si las fotos coinciden, confirma el match.
        if phash_fn is not None:
            coincide = _imagenes_coinciden(a.imagen, b.imagen, phash_fn)
            if coincide is True:
                return Resultado(True, max(score, UMBRAL_MATCH), "imagen",
                                 motivo=f"zona gris confirmada por imagen (fuzzy {score:.0f})")
            if coincide is False:
                return Resultado(False, score, "imagen",
                                 motivo=f"zona gris descartada por imagen (fuzzy {score:.0f})")
            # coincide is None (sin imágenes/deps) -> cae a revisión manual.
        return Resultado(False, score, "fuzzy", revisar=True,
                         motivo="zona gris: revisar a mano")
    return Resultado(False, score, "fuzzy", motivo="bajo umbral")
