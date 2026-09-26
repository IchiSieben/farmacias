"""pipeline/parquet.py — Capa PROCESSED del data lake (V2_PLAN F1).

Aplana el snapshot de una corrida a dos tablas Parquet con tipos explícitos
(esquema documentado en docs/ESQUEMA_DATOS.md):

    ofertas   una fila por (producto_id, cadena) con precio en esa corrida
    eventos   cambios contra la corrida anterior (nuevo, sube/baja, promo)
    matches   F3: una fila por cruce (producto_id, cadena, tipo) con su evidencia
              (método, score, R.S., cantidad y su fuente, imagen, precio). tipo =
              "match" (el precio de la fila) o "equivalente" (mismo activo,
              concentración, forma y cantidad, otro R.S.: no se muestra como match)

Layout en PROCESSED_DIR (default data/processed/):
    history/<YYYY-MM-DD>/{ofertas,eventos,matches}.parquet   una corrida por día (la última gana)
    latest/{ofertas,eventos,matches}.parquet                 solo si es la fecha más nueva

Usa pyarrow directo (sin pandas) para fijar el esquema sin inferencias.
"""

from __future__ import annotations

import json
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


ESQUEMA_MATCHES = pa.schema([
    ("corrida", pa.string()),
    ("capturado_en", _UTC),
    ("producto_id", pa.string()),
    ("cadena", pa.string()),
    ("tipo", pa.string()),              # match | equivalente
    ("sku_cadena", pa.string()),
    ("metodo", pa.string()),            # id|ean|registro_sanitario|fuzzy|imagen|curado|equivalente
    ("score", pa.float64()),
    ("revisar", pa.bool_()),
    ("motivo", pa.string()),
    ("rs_ref", pa.string()),
    ("rs_cadena", pa.string()),
    ("cantidad_ref", pa.float64()),
    ("cantidad_cadena", pa.float64()),
    ("unidad", pa.string()),
    ("cantidad_fuente_ref", pa.string()),
    ("cantidad_fuente_cadena", pa.string()),
    ("texto_score", pa.float64()),
    ("imagen_veredicto", pa.string()),  # identica | intermedia | distinta | NULL sin dato
    ("imagen_dist_phash", pa.int16()),
    ("imagen_dist_dhash", pa.int16()),
    ("ratio_precio", pa.float64()),
    ("precio", pa.float64()),
    ("url", pa.string()),
    ("evidencia", pa.string()),         # JSON completo (lo mismo que data.json)
], metadata={"esquema": "matches", "version": "1"})

# Inkafarma <-> Mifarma comparten objectID (grupo InRetail): llave dura sin más señal.
_EVIDENCIA_INRETAIL = {"metodo": "id", "score": 100.0, "revisar": False,
                       "motivo": "mismo objectID InRetail"}


def _lado(ev: dict, campo: str, i: int):
    """La evidencia guarda pares [referencia Inkafarma, cadena]."""
    par = ev.get(campo) or [None, None]
    return par[i]


def filas_matches(data: dict, corrida: str) -> List[Dict]:
    ts = _ts(data["generado"])
    filas = []
    for p in data["productos"]:
        evs = dict(p.get("evidencia") or {})
        if "mifarma" in p.get("precios", {}):
            evs.setdefault("mifarma", {**_EVIDENCIA_INRETAIL, "sku": p["id"].split(":")[0]})
        cruces = [("match", c, ev) for c, ev in sorted(evs.items())]
        cruces += [("equivalente", c, ev)
                   for c, ev in sorted((p.get("equivalentes") or {}).items())]
        for tipo, cadena, ev in cruces:
            img = ev.get("imagen") or {}
            filas.append({
                "corrida": corrida,
                "capturado_en": ts,
                "producto_id": p["id"],
                "cadena": cadena,
                "tipo": tipo,
                "sku_cadena": ev.get("sku"),
                "metodo": ev["metodo"],
                "score": ev.get("score"),
                "revisar": bool(ev.get("revisar")),
                "motivo": ev.get("motivo"),
                "rs_ref": _lado(ev, "rs", 0),
                "rs_cadena": _lado(ev, "rs", 1),
                "cantidad_ref": _lado(ev, "cantidad", 0),
                "cantidad_cadena": _lado(ev, "cantidad", 1),
                "unidad": _lado(ev, "unidad", 0),
                "cantidad_fuente_ref": _lado(ev, "cantidad_fuente", 0),
                "cantidad_fuente_cadena": _lado(ev, "cantidad_fuente", 1),
                "texto_score": (ev.get("texto") or {}).get("score"),
                "imagen_veredicto": img.get("veredicto"),
                "imagen_dist_phash": img.get("phash"),
                "imagen_dist_dhash": img.get("dhash"),
                "ratio_precio": ev.get("ratio_precio"),
                "precio": ev.get("precio") if tipo == "equivalente" else p["precios"].get(cadena),
                "url": ev.get("url") if tipo == "equivalente" else (p.get("urls") or {}).get(cadena),
                "evidencia": json.dumps(ev, ensure_ascii=False, sort_keys=True),
            })
    return filas


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
    matches = pa.Table.from_pylist(filas_matches(data, corrida), schema=ESQUEMA_MATCHES)
    return (store.write("ofertas", ofertas, fecha) + store.write("eventos", evs, fecha)
            + store.write("matches", matches, fecha))
