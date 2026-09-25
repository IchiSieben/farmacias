"""core/matcher.py — "¿es el mismo producto?" entre cadenas (ANEXO §A).

Estrategia en capas, de la más confiable a la más cara:

  Capa 1 — Llave dura: mismo `objectID` (InRetail), mismo `ean`, o mismo registro
           sanitario + misma cantidad (F3) -> score 100. R.S. distintos, ambos
           presentes -> 0 con motivo (veto): un R.S. identifica producto,
           laboratorio, forma y concentración. Un mismo R.S. cubre varias
           presentaciones, así que sin la cantidad no decide.
  Capa 2 — Nombre + specs normalizados: fuzzy sobre el texto, con REGLAS DURAS
           (concentración y cantidad deben coincidir; 250mg ≠ 500mg).
  Capa 3 — Imagen (pHash + dHash, ver core.imagen) para todo candidato >= 60:
           foto idéntica confirma 60–85; foto claramente distinta veta >= 85 si
           la cantidad de al menos un lado viene de un atributo. La zona
           intermedia no decide, y nunca se decide solo por imagen.

Cada `Resultado` lleva `evidencia`: señales, valores y de dónde salió cada dato
(ver core.ficha), para matches.parquet y el panel "¿Por qué se emparejó?".

Fuzzy: usa rapidfuzz si está instalado; si no, cae a difflib (stdlib). Python 3.9+.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .ficha import ATRIBUTO, Ficha, clave_rs, ficha_de
from .imagen import veredicto
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
    "acido vitamina complejo sales sal "
    # vía/dispositivo: "Suprahyal ... Inyectable Jeringa" y "Mensille ... Inyectable
    # + Jeringa" compartían SOLO estas palabras y casaban como mismo activo
    "inyectable inyectables jeringa jeringas prellenada pre llenada ampolla ampollas vial".split()
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
# Desde aquí se consulta la imagen (Capa 3): una foto idéntica confirma 60–85.
UMBRAL_IMAGEN = 60.0

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
    metodo: str   # "id" | "ean" | "registro_sanitario" | "fuzzy" | "regla_dura" | "imagen"
    revisar: bool = False      # zona gris 70–85
    motivo: Optional[str] = None
    evidencia: Dict[str, Any] = field(default_factory=dict)


def _misma_cantidad(fa: Ficha, fb: Ficha, tol: float = 0.10) -> bool:
    if fa.cantidad is None or fb.cantidad is None or fa.unidad != fb.unidad:
        return False
    mayor = max(fa.cantidad, fb.cantidad) or 1
    return abs(fa.cantidad - fb.cantidad) / mayor <= tol


def _evidencia_base(fa: Ficha, fb: Ficha) -> Dict[str, Any]:
    """Qué datos entraron a la decisión y de dónde salió cada uno (a = referencia)."""
    return {
        "rs": [fa.registro_sanitario, fb.registro_sanitario],
        "rs_fuente": [fa.fuente("registro_sanitario"), fb.fuente("registro_sanitario")],
        "cantidad": [fa.cantidad, fb.cantidad],
        "unidad": [fa.unidad, fb.unidad],
        "cantidad_fuente": [fa.fuente("cantidad"), fb.fuente("cantidad")],
    }


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


def comparar(a: Producto, b: Producto, *, fa: Optional[Ficha] = None,
             fb: Optional[Ficha] = None) -> Resultado:
    """Decide si `a` y `b` son el mismo producto (ANEXO §A, V2_PLAN §3.4).

    `fa`/`fb` (opcionales): fichas ya armadas (core.ficha), con R.S. y hashes de
    imagen. Sin ellas se arman del `Producto` sin imagen: el matcher nunca toca la
    red (las fotos las baja y cachea core.imagen.AlmacenImagenes).
    """
    fa = fa or ficha_de(a)
    fb = fb or ficha_de(b)
    ev = _evidencia_base(fa, fb)

    def res(es_match, score, metodo, revisar=False, motivo=None) -> Resultado:
        ev["decision"] = metodo
        return Resultado(es_match, score, metodo, revisar=revisar, motivo=motivo,
                         evidencia=ev)

    # Capa 1: identificador duro.
    metodo = match_por_id(a, b)
    if metodo:
        return res(True, 100.0, metodo, motivo=(
            f"mismo EAN ({fa.ean})" if metodo == "ean" else "mismo id de producto"))
    # Registro sanitario: llave si coincide con la cantidad; veto si difiere.
    ka, kb = clave_rs(fa.registro_sanitario), clave_rs(fb.registro_sanitario)
    if ka and kb:
        if ka != kb:
            return res(False, 0.0, "registro_sanitario",
                       motivo=f"registro sanitario distinto ({fa.registro_sanitario} ≠ "
                              f"{fb.registro_sanitario})")
        if _misma_cantidad(fa, fb):
            return res(True, 100.0, "registro_sanitario",
                       motivo=f"mismo registro sanitario ({fa.registro_sanitario}) "
                              f"y misma cantidad ({fa.cantidad:g} {fa.unidad})")
        # Mismo R.S. sin cantidad confirmada: otra presentación posible, sigue.

    # Capa 2: specs + nombre, con reglas duras. (250mg ≠ 500mg, tableta ≠ jarabe.)
    sa, sb = extrae_specs(a.nombre_origen), extrae_specs(b.nombre_origen)
    if (sa.concentracion and sb.concentracion
            and not _concentracion_compatible(sa.concentracion, sb.concentracion)):
        return res(False, 0.0, "regla_dura",
                   motivo=f"concentración distinta ({sa.concentracion} ≠ {sb.concentracion})")
    if sa.cantidad and sb.cantidad and sa.cantidad != sb.cantidad:
        return res(False, 0.0, "regla_dura",
                   motivo=f"cantidad distinta ({sa.cantidad} ≠ {sb.cantidad})")
    if _forma_incompatible(sa.forma, sb.forma):
        return res(False, 0.0, "regla_dura",
                   motivo=f"forma incompatible ({sa.forma} ≠ {sb.forma})")
    if _presentacion_incompatible(a, b):
        return res(False, 0.0, "regla_dura",
                   motivo="presentación distinta (efervescente vs tableta normal)")
    # Tamaño de envase: el size suele estar en `presentacion` (InRetail) o en el
    # nombre (Boticas) -> se combinan ambos para extraerlo.
    ta = extrae_tamano(f"{a.nombre_origen} {a.presentacion or ''}")
    tb = extrae_tamano(f"{b.nombre_origen} {b.presentacion or ''}")
    if _tamano_incompatible(ta, tb):
        return res(False, 0.0, "regla_dura",
                   motivo=f"envase distinto ({ta[0]:g}{ta[1]} ≠ {tb[0]:g}{tb[1]})")
    # Principio activo / variante: no basta con parecerse por palabras genéricas.
    if not _activo_compatible(a, b):
        return res(False, 0.0, "regla_dura", motivo="principio activo o variante distinta")
    # Audiencia: pediátrico vs adulto/sin marcar -> producto distinto.
    if _es_pediatrico(a) != _es_pediatrico(b):
        return res(False, 0.0, "regla_dura", motivo="audiencia distinta (pediátrico vs adulto)")
    # Vitaminas: letra distinta (D ≠ C) -> producto distinto.
    if _vitamina_incompatible(a, b):
        return res(False, 0.0, "regla_dura", motivo="vitamina distinta (letra)")
    # Forma gomita vs tableta/cápsula -> presentación distinta.
    if _gomita_incompatible(a, b):
        return res(False, 0.0, "regla_dura", motivo="forma distinta (gomita vs tableta)")

    # Score: núcleo (principio activo/marca) pesa más que el nombre completo.
    sim_nombre = _sim(sa.texto_norm, sb.texto_norm)
    sim_nucleo = _sim(nucleo(a.nombre_origen), nucleo(b.nombre_origen))
    score = _W_NOMBRE * sim_nombre + _W_NUCLEO * sim_nucleo
    ev["texto"] = {"score": round(score, 1), "sim_nombre": round(sim_nombre, 1),
                   "sim_nucleo": round(sim_nucleo, 1)}

    # Capa 3: imagen, para todo candidato desde UMBRAL_IMAGEN.
    img = None
    if score >= UMBRAL_IMAGEN and fa.imagen_phash and fb.imagen_phash:
        img = veredicto((fa.imagen_phash, fa.imagen_dhash), (fb.imagen_phash, fb.imagen_dhash))
        ev["imagen"] = img

    if score >= UMBRAL_MATCH:
        # Veto: 85+ por texto con foto claramente distinta suele ser otra variante
        # o envase. Solo si la cantidad de algún lado viene de un atributo (no del
        # nombre): la cantidad ya está confirmada y lo que difiere es el producto.
        if (img and img["veredicto"] == "distinta"
                and ATRIBUTO in (fa.fuente("cantidad"), fb.fuente("cantidad"))):
            return res(False, 0.0, "imagen",
                       motivo=f"foto claramente distinta (pHash {img['phash']}, dHash "
                              f"{img['dhash']}) con texto {score:.0f}")
        return res(True, score, "fuzzy", motivo=(
            f"texto {score:.0f} >= {UMBRAL_MATCH:.0f} (núcleo {sim_nucleo:.0f}, "
            f"nombre {sim_nombre:.0f})"))
    if img and img["veredicto"] == "identica":
        return res(True, max(score, UMBRAL_MATCH), "imagen",
                   motivo=f"foto idéntica (pHash {img['phash']}, dHash {img['dhash']}) "
                          f"confirma texto {score:.0f}")
    if score >= UMBRAL_REVISION:
        return res(False, score, "fuzzy", revisar=True,
                   motivo=f"zona gris: revisar a mano (texto {score:.0f}, núcleo "
                          f"{sim_nucleo:.0f}, nombre {sim_nombre:.0f})")
    return res(False, score, "fuzzy", motivo="bajo umbral")
