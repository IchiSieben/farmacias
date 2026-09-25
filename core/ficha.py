"""core/ficha.py — Ficha canónica por oferta (F3, V2_PLAN §3.1).

Antes de comparar, cada `Producto` se convierte en una `Ficha`: los datos que
identifican el producto (activos, concentración, forma, cantidad, laboratorio,
registro sanitario, EAN, hashes de imagen), cada uno con la fuente de la que salió.

Regla: un atributo estructurado de la API gana sobre lo que se parsea del nombre.
La cantidad de InRetail sale de la etiqueta del detalle ("FRASCO 30 UN"), la de
Universal de su especificación "Presentación"; Boticas solo la da en el nombre.

Registro sanitario (DIGEMID): se normaliza a `LETRAS-DIGITOS` ("DE-0340" ==
"DE0340" == "DE 0340"). Para comparar se ignoran los ceros a la izquierda
(`clave_rs`: DE-340 == DE-0340): son el mismo número escrito con o sin relleno, y
un veto por relleno distinto sería un falso negativo sin motivo.

Python 3.9+ (sin `X | Y` en runtime, sin `slots=`). Sin red: los hashes de imagen
llegan ya calculados por una función inyectada (ver core.imagen.AlmacenImagenes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .modelo import Producto
from .normalizer import extrae_specs, extrae_tamano, normaliza_texto, nucleo

ATRIBUTO = "atributo"
DESCRIPCION = "descripcion"
NOMBRE = "nombre"

# Código R.S.: prefijo de letras (EE, EN, N, NG, DE, NSOC...) + número, con o sin
# guion/espacio/punto entre ambos. El sufijo opcional (año, país: "-15CO") no
# entra a la clave.
_RE_CODIGO = r"([A-Z]{1,6})\s*[-.]?\s*(\d{3,6})"
_RE_RS_SOLO = re.compile(r"^\s*" + _RE_CODIGO + r"(?:\s*[-/ ]\s*[A-Z0-9]{2,10})?\s*$", re.I)
# En texto libre solo se acepta un código precedido de su etiqueta: el mismo texto
# de InRetail trae "Reg. San. DE-0340. Bayer S.A – RUC 20100096341" y un patrón
# suelto de letras+dígitos agarraría el RUC.
_RE_RS_TEXTO = re.compile(
    r"(?:registro\s+sanitario|reg\.?\s*san(?:itario)?\.?|\bR\.?\s?S\b\.?|"
    r"notificaci[oó]n\s+sanitaria(?:\s+obligatoria)?)"
    r"\s*(?:n[°º]|nro\.?|:|#)?\s*:?\s*" + _RE_CODIGO,
    re.I,
)
_RE_TAG = re.compile(r"<[^>]+>")


def normaliza_rs(valor: Optional[str]) -> Optional[str]:
    """'DE0340' / 'de 0340' / 'DE-0340' -> 'DE-0340'. None si no es un código R.S."""
    if not valor:
        return None
    m = _RE_RS_SOLO.match(str(valor))
    if not m:
        return None
    return f"{m.group(1).upper()}-{m.group(2)}"


def clave_rs(rs: Optional[str]) -> Optional[str]:
    """Clave de comparación: 'DE-0340' -> 'DE-340' (sin ceros a la izquierda)."""
    n = normaliza_rs(rs)
    if not n:
        return None
    letras, num = n.split("-")
    return f"{letras}-{int(num)}"


def extrae_rs_texto(*textos: Optional[str]) -> Optional[str]:
    """R.S. de la descripción (HTML) de una ficha. None si no hay o si aparecen DOS
    códigos distintos (packs con varios productos): mejor sin dato que uno ajeno."""
    vistos: Dict[str, str] = {}
    for t in textos:
        if not t:
            continue
        plano = _RE_TAG.sub(" ", str(t))
        for m in _RE_RS_TEXTO.finditer(plano):
            rs = f"{m.group(1).upper()}-{m.group(2)}"
            vistos.setdefault(clave_rs(rs), rs)
    return next(iter(vistos.values())) if len(vistos) == 1 else None


def _activos(principio: Optional[str]) -> List[str]:
    if not principio:
        return []
    partes = re.split(r"[,;+/]| y ", principio)
    return sorted({normaliza_texto(p).strip(" .") for p in partes if normaliza_texto(p).strip(" .")})


@dataclass
class Ficha:
    """Lo que se sabe de una oferta para decidir "mismo producto", con su fuente."""

    cadena: str
    sku: str
    activos: List[str] = field(default_factory=list)
    concentracion: Optional[str] = None
    forma: Optional[str] = None
    cantidad: Optional[float] = None
    unidad: Optional[str] = None
    laboratorio: Optional[str] = None
    marca: Optional[str] = None
    registro_sanitario: Optional[str] = None
    ean: Optional[str] = None
    imagen_url: Optional[str] = None
    imagen_phash: Optional[str] = None     # hex de 64 bits
    imagen_dhash: Optional[str] = None
    fuentes: Dict[str, str] = field(default_factory=dict)
    texto_norm: str = ""
    nucleo: str = ""

    def fuente(self, campo: str) -> Optional[str]:
        return self.fuentes.get(campo)


# callable(url) -> (phash_hex, dhash_hex) | None
HashesFn = Callable[[Optional[str]], Optional[Tuple[str, str]]]


def ficha_de(p: Producto, *, hashes_fn: Optional[HashesFn] = None) -> Ficha:
    """Arma la ficha de una oferta. Atributo estructurado > descripción > nombre."""
    specs = extrae_specs(p.nombre_origen)
    f = Ficha(cadena=p.cadena, sku=str(p.sku), texto_norm=specs.texto_norm,
              nucleo=nucleo(p.nombre_origen), marca=p.marca, laboratorio=p.laboratorio,
              ean=(p.ean or "").strip() or None, imagen_url=p.imagen)
    origen = p.fuentes or {}

    def poner(campo: str, valor, fuente: str) -> None:
        if valor not in (None, "", []) and getattr(f, campo) in (None, "", []):
            setattr(f, campo, valor)
            f.fuentes[campo] = fuente

    # Cantidad: detalle InRetail (cantidad_envase) > presentación de la API > nombre.
    if p.cantidad_envase is not None and p.unidad_envase:
        poner("cantidad", float(p.cantidad_envase), origen.get("cantidad", ATRIBUTO))
        f.unidad = p.unidad_envase
    tam = extrae_tamano(p.presentacion) if p.presentacion else None
    if f.cantidad is None and tam:
        poner("cantidad", float(tam[0]), ATRIBUTO)
        f.unidad = tam[1]
    if f.cantidad is None:
        tam = extrae_tamano(p.nombre_origen)
        if tam:
            poner("cantidad", float(tam[0]), NOMBRE)
            f.unidad = tam[1]
        elif specs.cantidad:
            poner("cantidad", float(specs.cantidad), NOMBRE)
            f.unidad = "un"

    poner("registro_sanitario", normaliza_rs(p.registro_sanitario),
          origen.get("registro_sanitario", ATRIBUTO))
    poner("activos", _activos(p.principio_activo), origen.get("principio_activo", ATRIBUTO))
    poner("concentracion", specs.concentracion, NOMBRE)
    poner("forma", specs.forma, NOMBRE)
    if f.ean:
        f.fuentes["ean"] = ATRIBUTO

    if hashes_fn is not None and p.imagen:
        h = hashes_fn(p.imagen)
        if h:
            f.imagen_phash, f.imagen_dhash = h
    return f
