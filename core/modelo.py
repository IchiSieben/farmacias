"""core/modelo.py — Modelo de datos normalizado.

`Producto` es una *oferta* de una cadena en un instante: el registro que cada
adaptador devuelve, ya unificado, sin importar si vino de una API JSON o de HTML.
Es la fila que luego alimenta el matcher (§4 SPEC), el histórico de snapshots
(ANEXO §C) y el dashboard.

Diseñado para Python 3.9+ (sin `slots=`, sin uniones `X | Y` en runtime).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _ahora_iso() -> str:
    """Timestamp UTC en ISO-8601 (segundos), para sellar cada captura."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Producto:
    """Una oferta normalizada de una cadena.

    Campos obligatorios: `cadena`, `sku`, `nombre_origen`. El resto es opcional
    porque no todas las fuentes exponen todo. Los precios son float en soles (S/).
    """

    # --- identidad ---
    cadena: str                       # "inkafarma", "mifarma", ...
    sku: str                          # id estable en la cadena de origen
    nombre_origen: str                # nombre tal cual aparece en esa web

    # --- precios (S/) ---
    precio: Optional[float] = None            # precio efectivo a pagar (oferta si la hay)
    precio_regular: Optional[float] = None    # precio de lista (para medir descuento)
    precio_tarjeta: Optional[float] = None     # precio con tarjeta de fidelidad, si aplica
    en_promocion: bool = False
    etiqueta_promo: Optional[str] = None       # "2x1", "-30%", "Día del Padre" (si la fuente la da)

    # --- specs para el matcher (ANEXO §A) ---
    marca: Optional[str] = None
    laboratorio: Optional[str] = None
    principio_activo: Optional[str] = None
    presentacion: Optional[str] = None         # "BLISTER 10 UN", "CAJA 100 UN", "FRASCO 60 ML"
    presentacion_kind: Optional[str] = None    # "pack" | "fraccion" (InRetail: caja vs blíster)
    cantidad_envase: Optional[float] = None    # unidades/volumen del envase: 100 (un), 60 (ml)
    unidad_envase: Optional[str] = None        # "un" | "ml" | "g"
    precio_por_unidad: Optional[float] = None  # precio / cantidad_envase (S//un o S//ml)
    categoria: Optional[str] = None
    subcategoria: Optional[str] = None
    prescripcion: Optional[str] = None         # "Venta Libre" / con receta

    # --- disponibilidad / enlaces ---
    stock: Optional[bool] = None               # None = desconocido en esta fuente
    url: Optional[str] = None
    imagen: Optional[str] = None

    # --- llaves de cruce ---
    ean: Optional[str] = None                  # código de barras / gtin (matching Capa 1)
    sku_mifarma: Optional[str] = None          # cruce directo Inkafarma↔Mifarma (mismo grupo InRetail)
    sku_sap: Optional[str] = None              # id interno SAP del grupo

    # --- metadatos de captura ---
    capturado_en: str = field(default_factory=_ahora_iso)
    raw: Optional[Dict[str, Any]] = field(default=None, repr=False)  # hit crudo (opcional, para depurar)

    def to_row(self, *, incluir_raw: bool = False) -> Dict[str, Any]:
        """Devuelve un dict plano apto para JSONL / fila de tabla / Sheets."""
        d = asdict(self)
        if not incluir_raw:
            d.pop("raw", None)
        return d


# Orden de columnas sugerido para exports tabulares (CSV/Sheets), alineado con
# la pestaña `snapshots` del ANEXO §C.
COLUMNAS_SNAPSHOT: List[str] = [
    "capturado_en", "cadena", "sku", "nombre_origen",
    "precio", "precio_regular", "precio_tarjeta", "en_promocion", "etiqueta_promo",
    "marca", "laboratorio", "principio_activo", "presentacion",
    "categoria", "subcategoria", "prescripcion",
    "stock", "url", "imagen", "ean", "sku_mifarma", "sku_sap",
]
