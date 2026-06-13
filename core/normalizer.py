"""core/normalizer.py — Normalización de nombres y extracción de specs.

Convierte un nombre de producto crudo ("Paracetamol 500mg Tableta x 100") en
piezas comparables entre cadenas: texto normalizado + specs estructuradas
(concentración, forma farmacéutica, cantidad). Alimenta al matcher (ANEXO §A,
Capa 2) y sirve para construir un nombre canónico legible.

Sin dependencias externas. Python 3.9+.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

# Sinónimos de forma farmacéutica -> forma canónica.
_FORMAS = {
    "tableta": "tableta", "tabletas": "tableta", "tab": "tableta",
    "comprimido": "tableta", "comprimidos": "tableta", "comp": "tableta",
    "capsula": "capsula", "capsulas": "capsula", "cap": "capsula",
    "jarabe": "jarabe",
    "suspension": "suspension",
    "solucion": "solucion",
    "gotas": "gotas",
    "polvo": "polvo",
    "efervescente": "efervescente",
    "crema": "crema", "gel": "gel", "locion": "locion",
    "jabon": "jabon", "shampoo": "shampoo", "champu": "shampoo",
    "ampolla": "ampolla", "ampollas": "ampolla",
    "supositorio": "supositorio",
    "spray": "spray",
}

# Concentraciones: "500 mg", "120mg/5ml", "1 g", "50 mcg", "4%".
_RE_CONC = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|g|mcg|ui|ml|%)(?:\s*/\s*\d+(?:[.,]\d+)?\s*ml)?",
    re.IGNORECASE,
)
# Cantidad por envase: "x 100", "caja 100", "100 un", "frasco 120 ml".
_RE_CANT = re.compile(
    r"(?:x\s*(\d+)|caja\s*(?:de\s*)?(\d+)|(\d+)\s*(?:un|und|unidades|tabletas|capsulas|comprimidos))",
    re.IGNORECASE,
)


def quitar_tildes(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Unidades cuyo espacio previo se colapsa ("500 mg" -> "500mg").
_RE_UNIDAD = re.compile(r"(\d)\s+(mg|g|mcg|ui|ml|%)\b", re.IGNORECASE)


def normaliza_texto(s: Optional[str]) -> str:
    """minúsculas, sin tildes, sin puntuación, unidades y sinónimos canónicos."""
    if not s:
        return ""
    s = quitar_tildes(str(s)).lower()
    s = re.sub(r"[^a-z0-9%./ ]+", " ", s)
    s = _RE_UNIDAD.sub(r"\1\2", s)            # "500 mg" -> "500mg"
    s = re.sub(r"\s+", " ", s).strip()
    # Canoniza sinónimos de forma palabra a palabra (comprimido -> tableta, etc.).
    s = " ".join(_FORMAS.get(tok, tok) for tok in s.split())
    return s


def _norm_conc(raw: str) -> str:
    """Normaliza una concentración: quita espacios, coma->punto."""
    return re.sub(r"\s+", "", raw.lower()).replace(",", ".")


@dataclass
class Specs:
    texto_norm: str               # nombre completo normalizado
    concentracion: Optional[str]  # "500mg", "120mg/5ml" (None si no se detecta)
    forma: Optional[str]          # forma canónica ("tableta", "jarabe", ...)
    cantidad: Optional[int]       # unidades por envase (None si no se detecta)

    def clave_specs(self) -> str:
        """Firma corta para comparación dura: concentración|forma|cantidad."""
        return "|".join([
            self.concentracion or "",
            self.forma or "",
            str(self.cantidad or ""),
        ])


def extrae_specs(nombre: Optional[str]) -> Specs:
    texto = normaliza_texto(nombre)

    m = _RE_CONC.search(texto)
    concentracion = _norm_conc(m.group(0)) if m else None

    forma = None
    for token in texto.split():
        if token in _FORMAS:
            forma = _FORMAS[token]
            break

    cantidad = None
    mc = _RE_CANT.search(texto)
    if mc:
        for g in mc.groups():
            if g:
                cantidad = int(g)
                break

    return Specs(texto_norm=texto, concentracion=concentracion,
                 forma=forma, cantidad=cantidad)
