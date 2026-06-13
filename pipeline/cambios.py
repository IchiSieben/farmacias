"""pipeline/cambios.py — Histórico de snapshots y detección de cambios (ANEXO §C).

Persiste un snapshot por corrida (append-only, nunca sobrescribe) y compara la
corrida de hoy contra la anterior para derivar eventos que NO vienen en el API y
solo se ven comparando en el tiempo:

    nuevo · baja_precio · sube_precio · inicia_promo · fin_promo

La comparación es por `(id, cadena)`: el `id` es el objectID InRetail (estable
entre corridas) y el precio/promo es por cadena. El resultado se "hornea" en el
mismo `data.json` como `tendencia` (flecha ▲▼ por celda) y `promo_cambio` (marca
de promo), para que el buscador web siga siendo 100% estático: una sola carga,
sin lógica de histórico en el navegador.

El histórico crudo se guarda en `data/snapshots/snapshot_<stamp>.json` (una copia
íntegra del data.json de esa corrida) y los eventos en
`data/processed/eventos_<fecha>.csv` (formato pestaña `eventos` del ANEXO §C).

Python 3.9+.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def cargar_snapshot_previo(dir_snapshots: Path) -> Optional[dict]:
    """Devuelve el snapshot persistido más reciente, o None si no hay ninguno.

    Los archivos se nombran `snapshot_<stamp>.json` con `<stamp>` lexicográfica-
    mente ordenable (UTC), así que el último por nombre es el más reciente.
    """
    if not dir_snapshots.exists():
        return None
    archivos = sorted(dir_snapshots.glob("snapshot_*.json"))
    if not archivos:
        return None
    try:
        return json.loads(archivos[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _delta_pct(antes: float, ahora: float) -> Optional[float]:
    if not antes:
        return None
    return round(100 * (ahora - antes) / antes, 1)


def diff_snapshots(previo: Optional[dict], actual: dict) -> List[dict]:
    """Anota `actual['productos']` con `tendencia` y `promo_cambio` (in-place) y
    devuelve la lista de eventos detectados.

    En la PRIMERA corrida (sin `previo`) no hay con qué comparar: no se anota nada
    y se devuelven 0 eventos (el web no muestra flechas).
    """
    eventos: List[dict] = []
    if previo is None:
        return eventos

    prev_idx: Dict[str, dict] = {p["id"]: p for p in previo.get("productos", [])}

    for prod in actual.get("productos", []):
        pid = prod["id"]
        prev = prev_idx.get(pid)
        precios: Dict[str, float] = prod.get("precios", {})
        promos: Dict[str, bool] = prod.get("promos", {})
        tendencia: Dict[str, dict] = {}
        promo_cambio: Dict[str, str] = {}

        # SKU nuevo: presente hoy, ausente en el snapshot previo (evento a nivel
        # producto, una sola fila).
        if prev is None:
            eventos.append({
                "tipo_evento": "nuevo", "cadena": "", "producto": prod.get("nombre", ""),
                "valor_anterior": "", "valor_nuevo": "", "delta_pct": "",
            })

        for cadena, precio in precios.items():
            antes = prev["precios"].get(cadena) if prev else None
            if antes is None:
                # Cadena sin precio previo (SKU nuevo, o esta cadena recién lo lista).
                tendencia[cadena] = {"dir": "nuevo", "antes": None, "delta_pct": None}
            else:
                if precio < antes:
                    direccion = "baja"
                elif precio > antes:
                    direccion = "sube"
                else:
                    direccion = "igual"
                delta = _delta_pct(antes, precio)
                tendencia[cadena] = {"dir": direccion, "antes": antes, "delta_pct": delta}
                if direccion in ("baja", "sube"):
                    eventos.append({
                        "tipo_evento": "baja_precio" if direccion == "baja" else "sube_precio",
                        "cadena": cadena, "producto": prod.get("nombre", ""),
                        "valor_anterior": antes, "valor_nuevo": precio,
                        "delta_pct": delta if delta is not None else "",
                    })

            # Cambio de estado de promoción (solo si conocemos el estado previo).
            promo_now = promos.get(cadena)
            promo_prev = prev.get("promos", {}).get(cadena) if prev else None
            if promo_prev is not None and promo_now is not None and bool(promo_now) != bool(promo_prev):
                if promo_now:
                    promo_cambio[cadena] = "inicia"
                    tipo = "inicia_promo"
                else:
                    promo_cambio[cadena] = "fin"
                    tipo = "fin_promo"
                eventos.append({
                    "tipo_evento": tipo, "cadena": cadena, "producto": prod.get("nombre", ""),
                    "valor_anterior": "sí" if promo_prev else "no",
                    "valor_nuevo": "sí" if promo_now else "no", "delta_pct": "",
                })

        if tendencia:
            prod["tendencia"] = tendencia
        if promo_cambio:
            prod["promo_cambio"] = promo_cambio

    return eventos


def _stamp_archivo(generado: str) -> str:
    """`2026-06-13T13:26:00+00:00` -> `2026-06-13T13-26-00Z` (nombre seguro en Windows)."""
    s = generado.replace("+00:00", "Z")
    # los ':' no son válidos en nombres de archivo Windows
    fecha, _, hora = s.partition("T")
    return fecha + "T" + hora.replace(":", "-")


def persistir_snapshot(data: dict, dir_snapshots: Path) -> Path:
    """Guarda una copia íntegra del snapshot de esta corrida (append-only)."""
    dir_snapshots.mkdir(parents=True, exist_ok=True)
    destino = dir_snapshots / f"snapshot_{_stamp_archivo(data['generado'])}.json"
    destino.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return destino


_COLS_EVENTOS = ["fecha", "tipo_evento", "cadena", "producto",
                 "valor_anterior", "valor_nuevo", "delta_pct"]


def escribir_eventos_csv(eventos: List[dict], fecha: str, out_dir: Path) -> Path:
    """Escribe los eventos en formato pestaña `eventos` del ANEXO §C."""
    out_dir.mkdir(parents=True, exist_ok=True)
    destino = out_dir / f"eventos_{fecha}.csv"
    with destino.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_COLS_EVENTOS)
        for e in eventos:
            w.writerow([fecha, e["tipo_evento"], e["cadena"], e["producto"],
                        e["valor_anterior"], e["valor_nuevo"], e["delta_pct"]])
    return destino


def resumen_eventos(eventos: List[dict]) -> Dict[str, int]:
    """Cuenta de eventos por tipo, para el log de la corrida."""
    out: Dict[str, int] = {}
    for e in eventos:
        out[e["tipo_evento"]] = out.get(e["tipo_evento"], 0) + 1
    return out
