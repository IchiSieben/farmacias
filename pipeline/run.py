"""pipeline/run.py — Orquestador de la corrida v2 (V2_PLAN F1).

Pasos:
  capturar   red -> crudo. Cada respuesta HTTP se graba (core.http_cache) antes de
             que el adaptador la parsee; al terminar se publica comprimida en
             RAW_DIR/<cadena>/<fecha>/ junto a un manifiesto de la corrida.
  procesar   crudo -> snapshot. Normaliza + matchea (hoy es `construir()` de la v1,
             reproducido SIN red desde el crudo; F3 lo separa en dos pasos).
  exportar   snapshot -> web/data.json (contrato v1) + histórico + Parquet
             (pipeline/parquet.py, esquema en docs/ESQUEMA_DATOS.md).
  publicar   pendiente (ver ESTADO): subir a Hostinger exige confirmación explícita.

La salida oficial SIEMPRE sale del crudo, también en `--todo`: la captura en vivo
solo graba, y el procesado se hace reproduciendo lo grabado. Así el camino
`--desde-cache` se ejercita en cada corrida diaria, no solo cuando se necesita.

Uso:
    py -m pipeline.run --todo                          # captura + procesa + exporta
    py -m pipeline.run --todo --objetivo 20 --sin-semillas --delay 2-6
    py -m pipeline.run --solo-captura
    py -m pipeline.run --desde-cache 2026-09-24        # reprocesa sin red (fecha o id)
    py -m pipeline.run --desde-cache 2026-09-24 --salida /tmp/x.json --sin-historial
    py -m pipeline.run --reanudar 2026-09-24T08-30-00Z # sigue una captura cortada

Python 3.12 (pipeline/); core/ sigue siendo 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import http_cache as hc
from core.adapters.algolia_inretail import _load_dotenv
from core.storage import RawStore, StorageError, fecha_de, nuevo_id_corrida, raw_dir_desde_entorno
from pipeline import build_snapshot, cambios
from pipeline.parquet import exportar_parquet

ROOT = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT / "data" / "staging"
LOG_DIR = ROOT / "data" / "logs"
OUT_DEFAULT = ROOT / "web" / "data.json"
CADENAS = ["inkafarma", "mifarma", "boticasperu", "universal"]
_VARS_ALGOLIA = ["INKAFARMA_ALGOLIA_APP_ID", "INKAFARMA_ALGOLIA_API_KEY",
                 "MIFARMA_ALGOLIA_APP_ID", "MIFARMA_ALGOLIA_API_KEY"]


class ErrorCorrida(RuntimeError):
    pass


# --- log a archivo -----------------------------------------------------------
class _Tee:
    """Duplica stdout/stderr a un archivo de log (construir() imprime a stderr)."""

    def __init__(self, original, fh) -> None:
        self.original, self.fh = original, fh

    def write(self, s: str) -> int:
        self.fh.write(s)
        self.fh.flush()
        return self.original.write(s)

    def flush(self) -> None:
        self.original.flush()
        self.fh.flush()


def _abrir_log(nombre: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ruta = LOG_DIR / f"run_{nombre}.log"
    fh = open(ruta, "a", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, fh)
    sys.stderr = _Tee(sys.__stderr__, fh)
    return ruta, fh


def log(msg: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", file=sys.stderr)


def _parse_delay(txt: str) -> Tuple[float, float]:
    if "-" in txt:
        lo, hi = txt.split("-", 1)
        return float(lo), float(hi)
    v = float(txt)
    return v, v


# --- pasos -------------------------------------------------------------------
def capturar(raw: RawStore, corrida: str, *, objetivo: int, semillas: bool,
             delay: Tuple[float, float], reanudar: bool = False) -> Dict[str, Any]:
    """Red -> crudo. Devuelve el manifiesto de la corrida (estado `completa`)."""
    t0 = time.monotonic()
    staging = STAGING_DIR / corrida
    if reanudar:
        manifest = raw.leer_manifest(corrida)
        objetivo, semillas = manifest["args"]["objetivo"], manifest["args"]["semillas"]
        log(f"Reanudando captura {corrida} (staging: {staging})")
    else:
        # El snapshot contra el que se difea se congela AHORA, antes de capturar,
        # y viaja con el crudo: el reproceso da las mismas ▲▼ en cualquier máquina.
        previo = cambios.cargar_snapshot_previo(build_snapshot.SNAP_DIR)
        if previo is not None:
            raw.escribir_json_corrida(corrida, "previo.json.gz", previo)
        manifest = {
            "corrida": corrida,
            "estado": "en_curso",
            "inicio": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "args": {"objetivo": objetivo, "semillas": semillas, "delay": list(delay)},
            "previo": previo.get("generado") if previo else None,
        }
        raw.escribir_manifest(corrida, manifest)

    sesion = hc.SesionHttp(hc.REANUDAR if reanudar else hc.GRABAR, staging, delay=delay)
    try:
        data = build_snapshot.construir(
            objetivo, adapter_kw=lambda cad: {"transport": sesion.transporte(cad)},
            semillas=semillas)
    finally:
        sesion.cerrar()

    fecha = fecha_de(corrida)
    archivos: Dict[str, str] = {}
    for cad in CADENAS:
        origen = sesion.archivo_staging(cad)
        if not origen.exists():
            continue
        nombre = f"respuestas_{corrida}.jsonl.gz"
        destino = raw.publicar_archivo(origen, cad, fecha, nombre)
        archivos[cad] = nombre
        log(f"  crudo {cad}: {destino} ({destino.stat().st_size // 1024} KB)")

    manifest.update({
        "estado": "completa",
        "fin": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generado": data["generado"],
        "archivos": archivos,
        "requests": sesion.estadisticas(),
        "duracion_captura_s": round(time.monotonic() - t0, 1)
            + float(manifest.get("duracion_captura_s", 0) if reanudar else 0),
    })
    raw.escribir_manifest(corrida, manifest)
    shutil.rmtree(staging, ignore_errors=True)  # el crudo ya está publicado en RAW_DIR
    return manifest


def procesar(raw: RawStore, corrida: str) -> Tuple[dict, List[dict], Dict[str, Any]]:
    """Crudo -> snapshot, sin red. Un faltante en el caché hace fallar la corrida."""
    manifest = raw.leer_manifest(corrida)
    fecha = fecha_de(corrida)
    fuentes = {cad: raw.ruta(cad, fecha, nombre)
               for cad, nombre in manifest.get("archivos", {}).items()}
    # Los adaptadores Algolia exigen keys al construirse; reproduciendo no se usan
    # (la llave del caché no incluye host ni headers).
    for var in _VARS_ALGOLIA:
        os.environ.setdefault(var, "sin-red")

    sesion = hc.SesionHttp(hc.REPRODUCIR, STAGING_DIR / "_no_usar", fuentes=fuentes)
    try:
        data = build_snapshot.construir(
            manifest["args"]["objetivo"], pausa=0,
            adapter_kw=lambda cad: {"transport": sesion.transporte(cad)},
            semillas=manifest["args"]["semillas"], generado=manifest["generado"])
    finally:
        sesion.cerrar()
    fallos = sesion.fallos()
    if fallos:
        raise ErrorCorrida(
            f"{len(fallos)} requests no están en el crudo de {corrida} (no se tocó la red). "
            "Primeras: " + " | ".join(fallos[:5]))

    previo = raw.leer_json_corrida(corrida, "previo.json.gz")
    eventos = cambios.diff_snapshots(previo, data)  # anota tendencia/promo_cambio in-place
    return data, eventos, sesion.estadisticas()


def exportar(data: dict, eventos: List[dict], corrida: str, *, salida: Path,
             historial: bool) -> List[Path]:
    """Snapshot -> web/data.json (mismo formato que la v1) + histórico."""
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    escritos = [salida]
    if historial:
        # Nombre derivado de `generado` (fijo por corrida): reprocesar no duplica.
        escritos.append(cambios.persistir_snapshot(data, build_snapshot.SNAP_DIR))
        escritos.append(cambios.escribir_eventos_csv(
            eventos, data["generado"][:10], build_snapshot.EVENTOS_DIR))
        escritos.extend(exportar_parquet(data, eventos, corrida))
    return escritos


# --- resumen -----------------------------------------------------------------
def resumen(data: dict, eventos: List[dict], requests: Dict[str, Dict[str, int]],
            duracion: float, errores: List[str]) -> str:
    prods = data["productos"]
    por_cadena = {c: sum(1 for p in prods if c in p["precios"]) for c in CADENAS}
    multi = sum(1 for p in prods if len(p["precios"]) >= 2)
    todas = sum(1 for p in prods if len(p["precios"]) == len(CADENAS))
    lineas = [
        "=" * 64,
        f"RESUMEN corrida · generado {data['generado']} · {duracion:.0f} s",
        f"  filas: {len(prods)} · con >=2 cadenas: {multi} · con las 4: {todas}",
        "  por cadena: " + " · ".join(f"{c} {n}" for c, n in por_cadena.items()),
        "  eventos: " + (", ".join(f"{k} {v}" for k, v in
                                   sorted(cambios.resumen_eventos(eventos).items())) or "ninguno"),
        "  requests: " + " · ".join(
            f"{c} red={s.get('red', 0)} cache={s.get('cache', 0)} "
            f"err={s.get('http_error', 0) + s.get('red_error', 0)}"
            for c, s in requests.items()),
        f"  errores: {len(errores)}" + ("".join(f"\n    - {e}" for e in errores)),
        "=" * 64,
    ]
    return "\n".join(lineas)


# --- CLI ---------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Corrida v2: capturar -> procesar -> exportar.")
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--todo", action="store_true", help="captura en vivo + procesa + exporta")
    modo.add_argument("--solo-captura", action="store_true", help="solo graba el crudo")
    modo.add_argument("--desde-cache", metavar="FECHA|CORRIDA",
                      help="reprocesa una corrida grabada, sin red")
    modo.add_argument("--reanudar", metavar="CORRIDA",
                      help="continúa una captura cortada y luego procesa + exporta")
    ap.add_argument("--objetivo", type=int, default=150)
    ap.add_argument("--sin-semillas", action="store_true",
                    help="omite SUBCATS_SEED (captura chica de prueba)")
    ap.add_argument("--delay", default="2-6",
                    help="segundos entre requests al mismo dominio, 'min-max' (default 2-6)")
    ap.add_argument("--salida", default=str(OUT_DEFAULT))
    ap.add_argument("--sin-historial", action="store_true",
                    help="no escribe snapshot/eventos/Parquet (solo --salida)")
    args = ap.parse_args(argv)

    _load_dotenv()
    t0 = time.monotonic()
    errores: List[str] = []
    try:
        raw = RawStore(raw_dir_desde_entorno())
        if args.desde_cache:
            corrida = raw.resolver_corrida(args.desde_cache)
        elif args.reanudar:
            corrida = args.reanudar
        else:
            corrida = nuevo_id_corrida()
    except StorageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    ruta_log, fh = _abrir_log(corrida)
    try:
        log(f"Corrida {corrida} · RAW_DIR={raw.root} · log={ruta_log}")
        if not args.desde_cache:
            log("Paso capturar (red, delay por dominio "
                f"{args.delay} s, objetivo {args.objetivo}"
                f"{', sin semillas' if args.sin_semillas else ''})")
            man = capturar(raw, corrida, objetivo=args.objetivo,
                           semillas=not args.sin_semillas, delay=_parse_delay(args.delay),
                           reanudar=bool(args.reanudar))
            for cad, s in man["requests"].items():
                if s.get("http_error") or s.get("red_error"):
                    errores.append(f"{cad}: {s.get('http_error', 0)} HTTP>=400, "
                                   f"{s.get('red_error', 0)} errores de red")
            if args.solo_captura:
                log(f"Captura lista: {corrida}. Procesar con --desde-cache {corrida}")
                return 1 if errores else 0

        log("Paso procesar (desde el crudo, sin red)")
        data, eventos, _ = procesar(raw, corrida)
        requests = raw.leer_manifest(corrida).get("requests", {})
        log("Paso exportar")
        for p in exportar(data, eventos, corrida, salida=Path(args.salida),
                          historial=not args.sin_historial):
            log(f"  -> {p}")
        print(resumen(data, eventos, requests, time.monotonic() - t0, errores), file=sys.stderr)
        return 1 if errores else 0
    except (ErrorCorrida, StorageError) as exc:
        log(f"ERROR: {exc}")
        return 2
    finally:
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        fh.close()


if __name__ == "__main__":
    sys.exit(main())
