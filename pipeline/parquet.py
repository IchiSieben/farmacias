"""pipeline/parquet.py — Capa PROCESSED del data lake (V2_PLAN F1).

Aplana el snapshot de una corrida a dos tablas Parquet con tipos explícitos
(esquema documentado en docs/ESQUEMA_DATOS.md):

    ofertas   una fila por (producto_id, cadena) con precio en esa corrida
    eventos   cambios contra la corrida anterior (nuevo, sube/baja, promo)

`fichas` y `matches` NO se definen aquí: son construcciones de F3 (matcher v2) y
fijar su esquema ahora sería adivinar.

Layout en PROCESSED_DIR (default data/processed/):
    history/<YYYY-MM-DD>/{ofertas,eventos}.parquet   una corrida por día (la última gana)
    latest/{ofertas,eventos}.parquet                 solo si es la fecha más nueva

Usa pyarrow directo (sin pandas) para fijar el esquema sin inferencias.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR_DEFAULT = ROOT / "data" / "processed"
VERSION_ESQUEMA = "1"

_UTC = pa.timestamp("ms", tz="UTC")  # Parquet no tiene unidad "s"

ESQUEMA_OFERTAS = pa.schema([
    ("corrida", pa.string()),
    ("capturado_en", _UTC),
    ("producto_id", pa.string()),
    ("nombre", pa.string()),
    ("categoria", pa.string()),
    ("marca", pa.string()),
    ("presentacion", pa.string()),
    ("cantidad", pa.float64()),
    ("unidad", pa.string()),
    ("cadena", pa.string()),
    ("grupo", pa.string()),
    ("precio", pa.float64()),
    ("precio_unidad", pa.float64()),
    ("en_promocion", pa.bool_()),
    ("url", pa.string()),
    ("es_mas_barato", pa.bool_()),
    ("brecha_pct", pa.float64()),
    ("n_cadenas", pa.int8()),
    ("tendencia", pa.string()),
    ("precio_anterior", pa.float64()),
], metadata={"esquema": "ofertas", "version": VERSION_ESQUEMA})

ESQUEMA_EVENTOS = pa.schema([
    ("corrida", pa.string()),
    ("capturado_en", _UTC),
    ("tipo_evento", pa.string()),
    ("producto_id", pa.string()),
    ("producto", pa.string()),
    ("cadena", pa.string()),
    ("valor_anterior", pa.string()),
    ("valor_nuevo", pa.string()),
    ("delta_pct", pa.float64()),
], metadata={"esquema": "eventos", "version": VERSION_ESQUEMA})


def processed_dir_desde_entorno() -> Path:
    valor = os.getenv("PROCESSED_DIR", "").strip()
    return Path(valor).expanduser() if valor else PROCESSED_DIR_DEFAULT


def _ts(generado: str) -> datetime:
    return datetime.fromisoformat(generado)


def _vacio_a_none(v):
    return None if v == "" else v


def filas_ofertas(data: dict, corrida: str) -> List[Dict]:
    grupo_de = {c["id"]: c.get("grupo") for c in data.get("cadenas", [])}
    ts = _ts(data["generado"])
    filas = []
    for p in data["productos"]:
        precios = p.get("precios", {})
        for cadena, precio in precios.items():
            tend = (p.get("tendencia") or {}).get(cadena) or {}
            filas.append({
                "corrida": corrida,
                "capturado_en": ts,
                "producto_id": p["id"],
                "nombre": p.get("nombre"),
                "categoria": p.get("categoria"),
                "marca": p.get("marca"),
                "presentacion": p.get("presentacion"),
                "cantidad": p.get("cantidad"),
                "unidad": p.get("unidad"),
                "cadena": cadena,
                "grupo": grupo_de.get(cadena),
                "precio": precio,
                "precio_unidad": (p.get("precio_unidad") or {}).get(cadena),
                "en_promocion": bool((p.get("promos") or {}).get(cadena)),
                "url": (p.get("urls") or {}).get(cadena),
                "es_mas_barato": p.get("mas_barato") == cadena,
                "brecha_pct": p.get("brecha_pct"),
                "n_cadenas": len(precios),
                "tendencia": tend.get("dir"),
                "precio_anterior": tend.get("antes"),
            })
    return filas


def filas_eventos(eventos: List[dict], data: dict, corrida: str) -> List[Dict]:
    ts = _ts(data["generado"])
    filas = []
    for e in eventos:
        delta = _vacio_a_none(e.get("delta_pct"))
        filas.append({
            "corrida": corrida,
            "capturado_en": ts,
            "tipo_evento": e["tipo_evento"],
            "producto_id": e.get("producto_id"),
            "producto": e.get("producto"),
            "cadena": _vacio_a_none(e.get("cadena")),
            "valor_anterior": None if e.get("valor_anterior") in (None, "") else str(e["valor_anterior"]),
            "valor_nuevo": None if e.get("valor_nuevo") in (None, "") else str(e["valor_nuevo"]),
            "delta_pct": None if delta is None else float(delta),
        })
    return filas


class ProcessedStore:
    """Parquet por fecha (`history/<fecha>/`) + `latest/`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _fechas(self) -> List[str]:
        h = self.root / "history"
        return sorted(d.name for d in h.iterdir() if d.is_dir()) if h.is_dir() else []

    def write(self, nombre: str, tabla: pa.Table, fecha: str) -> List[Path]:
        escritos = []
        destinos = [self.root / "history" / fecha / f"{nombre}.parquet"]
        # Reprocesar una fecha vieja no debe pisar `latest/` con datos viejos.
        fechas = self._fechas()
        if not fechas or fecha >= fechas[-1]:
            destinos.append(self.root / "latest" / f"{nombre}.parquet")
        for d in destinos:
            d.parent.mkdir(parents=True, exist_ok=True)
            tmp = d.with_name(d.name + ".tmp")
            pq.write_table(tabla, tmp, compression="zstd")
            os.replace(tmp, d)
            escritos.append(d)
        return escritos

    def read(self, nombre: str, fecha: Optional[str] = None) -> pa.Table:
        p = (self.root / "history" / fecha if fecha else self.root / "latest") / f"{nombre}.parquet"
        return pq.read_table(p)


def exportar_parquet(data: dict, eventos: List[dict], corrida: str,
                     store: Optional[ProcessedStore] = None) -> List[Path]:
    store = store or ProcessedStore(processed_dir_desde_entorno())
    fecha = data["generado"][:10]
    ofertas = pa.Table.from_pylist(filas_ofertas(data, corrida), schema=ESQUEMA_OFERTAS)
    evs = pa.Table.from_pylist(filas_eventos(eventos, data, corrida), schema=ESQUEMA_EVENTOS)
    return store.write("ofertas", ofertas, fecha) + store.write("eventos", evs, fecha)
