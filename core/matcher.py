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

from dataclasses import dataclass
from typing import Optional

from .modelo import Producto
from .normalizer import extrae_specs, normaliza_texto

# Umbrales (ANEXO §A): >=85 match, 70–85 revisar a mano, <70 descartar.
UMBRAL_MATCH = 85.0
UMBRAL_REVISION = 70.0

# Ponderación del score compuesto (sin imagen aún -> se reparte nombre/marca).
_W_NOMBRE = 0.80
_W_MARCA = 0.20


# --- fuzzy: rapidfuzz si existe, si no difflib ------------------------------
try:
    from rapidfuzz.fuzz import token_sort_ratio as _ratio  # type: ignore

    def _sim(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return float(_ratio(a, b))
except ImportError:  # fallback stdlib
    from difflib import SequenceMatcher

    def _sim(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        # token_sort: ordenar palabras para tolerar reordenamientos
        a2 = " ".join(sorted(a.split()))
        b2 = " ".join(sorted(b.split()))
        return SequenceMatcher(None, a2, b2).ratio() * 100.0


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

    # Capa 2: specs + nombre, con reglas duras.
    sa, sb = extrae_specs(a.nombre_origen), extrae_specs(b.nombre_origen)
    if sa.concentracion and sb.concentracion and sa.concentracion != sb.concentracion:
        return Resultado(False, 0.0, "regla_dura",
                         motivo=f"concentración distinta ({sa.concentracion} ≠ {sb.concentracion})")
    if sa.cantidad and sb.cantidad and sa.cantidad != sb.cantidad:
        return Resultado(False, 0.0, "regla_dura",
                         motivo=f"cantidad distinta ({sa.cantidad} ≠ {sb.cantidad})")

    sim_nombre = _sim(sa.texto_norm, sb.texto_norm)
    sim_marca = _sim(normaliza_texto(a.marca), normaliza_texto(b.marca))
    score = _W_NOMBRE * sim_nombre + _W_MARCA * sim_marca

    if score >= UMBRAL_MATCH:
        return Resultado(True, score, "fuzzy")
    if score >= UMBRAL_REVISION:
        return Resultado(False, score, "fuzzy", revisar=True,
                         motivo="zona gris: revisar a mano")
    return Resultado(False, score, "fuzzy", motivo="bajo umbral")
