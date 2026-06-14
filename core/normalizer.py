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

# Concentración = fuerza del fármaco: ratio "120mg/5ml" o strength suelta
# "500mg"/"50mcg"/"4%". OJO: un volumen/peso SUELTO del envase ("Frasco 120 ML",
# "Lata 850 G") NO es concentración -> se excluyen ml/l/g sueltos para no
# confundir el tamaño con la dosis (si no, "120ml" se leía como concentración y
# bloqueaba matches legítimos de jarabes). El ratio (…/Yml) sí se conserva.
_RE_CONC = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ui)\s*/\s*\d+(?:[.,]\d+)?\s*ml"   # ratio: 120mg/5ml
    r"|\d+(?:[.,]\d+)?\s*(?:mg|mcg|ui|%)",                            # strength: 500mg, 50mcg, 4%
    re.IGNORECASE,
)
# Solo "fuerza de fármaco" (strength), para quitarla SIN comerse el tamaño del
# envase. A diferencia de _RE_CONC, NO matchea g/ml/l/kg sueltos ("850 G",
# "60 ML" son envase, no concentración). El ratio (Xmg/Yml) va PRIMERO en la
# alternancia para consumir el "/Yml" entero y no dejar "Yml" suelto.
_RE_STRENGTH = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ui)\s*/\s*\d+(?:[.,]\d+)?\s*ml"  # ratio: 2.5mg/5ml
    r"|\d+(?:[.,]\d+)?\s*(?:mg|mcg|ui|%)",                            # strength suelta: 500mg, 4%
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


# Tamaño de envase: volumen, peso o conteo. Clases comparables entre sí: ml, g, un.
_UNID_TAMANO = {
    "ml": ("ml", 1), "l": ("ml", 1000),
    "g": ("g", 1), "gr": ("g", 1), "kg": ("g", 1000),
    "un": ("un", 1), "und": ("un", 1), "unid": ("un", 1), "unidades": ("un", 1),
    "tab": ("un", 1), "tabs": ("un", 1), "tabletas": ("un", 1), "tableta": ("un", 1),
    "comprimido": ("un", 1), "comprimidos": ("un", 1), "comp": ("un", 1),
    "caps": ("un", 1), "capsulas": ("un", 1), "capsula": ("un", 1),
    "ampolla": ("un", 1), "ampollas": ("un", 1), "amp": ("un", 1),
    "sobre": ("un", 1), "sobres": ("un", 1),
}
# Incluye las formas SINGULARES canónicas (normaliza_texto pasa "tabletas"->"tableta",
# "comprimidos"->"tableta", "capsulas"->"capsula"): si solo se aceptaran los plurales,
# "Caja 30 tabletas" -> "30 tableta" no matchearía y la cantidad se perdería.
_RE_TAMANO = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(ml|l|kg|gr|g|und|unidades|unid|un|"
    r"tabletas|tableta|tabs|tab|comprimidos|comprimido|comp|"
    r"capsulas|capsula|caps|ampollas|ampolla|amp|sobres|sobre)\b",
    re.IGNORECASE,
)


def extrae_tamano(texto: Optional[str]) -> Optional[tuple]:
    """Tamaño de envase como (valor_canónico, clase) -> (220.0, 'ml'), (1600.0, 'g').

    Quita primero la concentración (120mg/5ml) para no confundirla con el envase.
    Devuelve el ÚLTIMO match (el envase suele ir al final: "Frasco 220 ML").
    """
    # OJO: se quita solo la STRENGTH (mg/mcg/ui/% y ratios), no g/ml/l/kg sueltos,
    # porque "Frasco 60 ML" / "Lata 850 G" SON el tamaño del envase y deben quedar.
    t = _RE_STRENGTH.sub(" ", normaliza_texto(texto))
    ultimo = None
    for m in _RE_TAMANO.finditer(t):
        unidad = m.group(2).lower()
        clase, factor = _UNID_TAMANO[unidad]
        valor = float(m.group(1).replace(",", ".")) * factor
        ultimo = (valor, clase)
    return ultimo


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


# Palabras de empaque/forma que NO discriminan el producto (se quitan del núcleo).
_STOP_NUCLEO = set(
    "caja cajas frasco frascos blister blisters tableta capsula un und unid unidades "
    "x sobre sobres polvo solucion jarabe suspension gotas crema gel locion jabon "
    "shampoo barra efervescente ampolla supositorio spray ml mg mcg ui kg "
    "de del para con sin y o el la las los".split()
)
_RE_NUM_TODO = re.compile(r"\d+(?:[.,]\d+)?(?:mg|g|mcg|ui|ml|kg|%)?(?:/\d+(?:[.,]\d+)?\s*ml)?")


def nucleo(nombre: Optional[str]) -> str:
    """Núcleo discriminante: principio activo / marca, sin números ni empaque.

    "Paracetamol 500mg Tableta - Caja 100 UN" -> "paracetamol".
    Es la señal fuerte para emparejar entre cadenas con nomenclaturas distintas.
    """
    t = _RE_NUM_TODO.sub(" ", normaliza_texto(nombre))
    toks = [w for w in t.split() if w not in _STOP_NUCLEO and len(w) > 2]
    return " ".join(toks)


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
