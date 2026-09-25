"""pipeline/run.py — Orquestador de la corrida v2 (V2_PLAN F1).

Pasos:
  capturar   red -> crudo. Cada respuesta HTTP se graba (core.http_cache) antes de
             que el adaptador la parsee; al terminar se publica comprimida en
             RAW_DIR/<cadena>/<fecha>/ junto a un manifiesto de la corrida.
  procesar   crudo -> snapshot. Normaliza + matchea (hoy es `construir()` de la v1,
             reproducido SIN red desde el crudo; F3 lo separa en dos pasos).
  exportar   snapshot -> data/publicar/data.json (staging, contrato v1) + histórico + Parquet
             (pipeline/parquet.py, esquema en docs/ESQUEMA_DATOS.md).
  sincronizar  RAW_DIR y Parquet -> Google Drive con `rclone copy` (nunca sync).
             Va al final de --todo, con todo ya escrito: si Drive falla la corrida
             queda completa y el copy de mañana sube lo pendiente (es incremental).
  publicar   aparte y a mano: py -m pipeline.publish (resumen + confirmación).

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
    py -m pipeline.run --completar 2026-09-25          # F3: baja lo que le falta a una
                                                       # corrida vieja (QuickView Boticas,
                                                       # fotos) y reprocesa sin red

Enriquecimiento (F3, pipeline/enriquecer.py): los candidatos con texto >= 60
piden el QuickView de Boticas (R.S.) y la foto. El QuickView es un complemento
OPCIONAL del crudo (`boticasperu/<fecha>/quickview_<corrida>.jsonl.gz`, en
`manifest.complementos`) y las fotos van a RAW_DIR/imagenes/. Al reprocesar, lo
que falte de ambos es "sin dato", no un error: las corridas previas a F3 se
reprocesan igual.
    py -m pipeline.run --sincronizar                   # solo copia el lake a Drive

Python 3.12 (pipeline/); core/ sigue siendo 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import http_cache as hc
from core.adapter_base import CredencialRechazada
from core.adapters.algolia_inretail import _load_dotenv
from core.adapters.boticasperu import BoticasPeruAdapter
from core.imagen import AlmacenImagenes
from core.storage import RawStore, StorageError, fecha_de, nuevo_id_corrida, raw_dir_desde_entorno
from pipeline import build_snapshot, cambios
from pipeline.enriquecer import CADENA_QUICKVIEW, Enriquecedor
from pipeline.parquet import exportar_parquet, processed_dir_desde_entorno

ROOT = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT / "data" / "staging"
LOG_DIR = ROOT / "data" / "logs"
# Staging de publicación: la corrida NUNCA escribe web/data.json (lo servido).
# Publicar es manual y con confirmación: py -m pipeline.publish
OUT_DEFAULT = ROOT / "data" / "publicar" / "data.json"
CADENAS = ["inkafarma", "mifarma", "boticasperu", "universal"]
_VARS_ALGOLIA = ["INKAFARMA_ALGOLIA_APP_ID", "INKAFARMA_ALGOLIA_API_KEY",
                 "MIFARMA_ALGOLIA_APP_ID", "MIFARMA_ALGOLIA_API_KEY"]


class ErrorCorrida(RuntimeError):
    pass


def _nombre_quickview(corrida: str) -> str:
    return f"quickview_{corrida}.jsonl.gz"


def _enriquecedor(raw: RawStore, sesion_qv: hc.SesionHttp, *, red: bool,
                  turnos: Optional[hc.SesionHttp] = None) -> Enriquecedor:
    """Enriquecedor F3. `red`: las fotos que falten se bajan (captura/--completar);
    sin red, una foto fuera del índice es "sin dato"."""
    turno = (turnos or sesion_qv).esperar_turno
    imagenes = AlmacenImagenes(raw.root / "imagenes", red=red, esperar_turno=turno)
    bot = BoticasPeruAdapter(delay_range=(0, 0),
                             transport=sesion_qv.transporte(CADENA_QUICKVIEW))
    return Enriquecedor(imagenes, bot)


def _cerrar_enriquecedor(enr: Enriquecedor) -> None:
    enr.imagenes.cerrar()
    enr.boticas.close()


def _publicar_quickview(raw: RawStore, corrida: str, sesion_qv: hc.SesionHttp,
                        manifest: Dict[str, Any]) -> None:
    """Staging del QuickView -> complemento del crudo (+ manifiesto)."""
    origen = sesion_qv.archivo_staging(CADENA_QUICKVIEW)
    if not origen.exists():
        return
    nombre = _nombre_quickview(corrida)
    destino = raw.publicar_archivo(origen, "boticasperu", fecha_de(corrida), nombre)
    manifest.setdefault("complementos", {})[CADENA_QUICKVIEW] = nombre
    log(f"  crudo {CADENA_QUICKVIEW}: {destino} ({destino.stat().st_size // 1024} KB)")


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

    modo = hc.REANUDAR if reanudar else hc.GRABAR
    sesion = hc.SesionHttp(modo, staging, delay=delay)
    sesion_qv = hc.SesionHttp(modo, staging / "quickview", delay=delay, turnos=sesion)
    enr = _enriquecedor(raw, sesion_qv, red=True, turnos=sesion)
    try:
        data = build_snapshot.construir(
            objetivo, adapter_kw=lambda cad: {"transport": sesion.transporte(cad)},
            semillas=semillas, enriquecedor=enr)
    except CredencialRechazada as exc:
        # Se corta en el PRIMER rechazo. El staging se conserva: tras recapturar la
        # key, --reanudar sigue sin repetir lo ya bajado.
        manifest.update({"estado": "abortada", "motivo": str(exc),
                         "requests": sesion.estadisticas()})
        raw.escribir_manifest(corrida, manifest)
        raise ErrorCorrida(f"{exc} (corrida {corrida})") from exc
    finally:
        sesion.cerrar()
        sesion_qv.cerrar()
        _cerrar_enriquecedor(enr)

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
    _publicar_quickview(raw, corrida, sesion_qv, manifest)

    manifest.update({
        "estado": "completa",
        "fin": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generado": data["generado"],
        "archivos": archivos,
        "requests": {**sesion.estadisticas(), **sesion_qv.estadisticas()},
        "enriquecimiento": {**enr.stats, "imagenes": dict(enr.imagenes.stats)},
        "duracion_captura_s": round(time.monotonic() - t0, 1)
            + float(manifest.get("duracion_captura_s", 0) if reanudar else 0),
    })
    raw.escribir_manifest(corrida, manifest)
    shutil.rmtree(staging, ignore_errors=True)  # el crudo ya está publicado en RAW_DIR
    return manifest


def procesar(raw: RawStore, corrida: str, *, completar: bool = False,
             delay: Tuple[float, float] = (2.0, 6.0)
             ) -> Tuple[dict, List[dict], Dict[str, Any]]:
    """Crudo -> snapshot, sin red. Un faltante en el crudo principal hace fallar la
    corrida; en el complemento F3 (QuickView, fotos) es "sin dato".

    `completar=True` (--completar): el crudo principal se reproduce igual, pero lo
    que falte del complemento se baja (delay por dominio) y se agrega al crudo.
    Esa pasada NO exporta: la salida sale de otra pasada sin red.
    """
    manifest = raw.leer_manifest(corrida)
    fecha = fecha_de(corrida)
    fuentes = {cad: raw.ruta(cad, fecha, nombre)
               for cad, nombre in manifest.get("archivos", {}).items()}
    nombre_qv = manifest.get("complementos", {}).get(CADENA_QUICKVIEW)
    ruta_qv = raw.ruta("boticasperu", fecha, nombre_qv) if nombre_qv else None
    # Los adaptadores Algolia exigen keys al construirse; reproduciendo no se usan
    # (la llave del caché no incluye host ni headers).
    for var in _VARS_ALGOLIA:
        os.environ.setdefault(var, "sin-red")

    sesion = hc.SesionHttp(hc.REPRODUCIR, STAGING_DIR / "_no_usar", fuentes=fuentes)
    if completar:
        sesion_qv = hc.SesionHttp(hc.REANUDAR, STAGING_DIR / corrida / "quickview_completar",
                                  delay=delay)
        semilla = sesion_qv.archivo_staging(CADENA_QUICKVIEW)
        semilla.parent.mkdir(parents=True, exist_ok=True)
        # REANUDAR lee y amplía el staging: se siembra con el complemento previo.
        semilla.write_bytes(raw.read("boticasperu", fecha, nombre_qv) if nombre_qv else b"")
    else:
        sesion_qv = hc.SesionHttp(hc.REPRODUCIR, STAGING_DIR / "_no_usar",
                                  fuentes={CADENA_QUICKVIEW: ruta_qv} if ruta_qv else {})
    enr = _enriquecedor(raw, sesion_qv, red=completar)
    try:
        data = build_snapshot.construir(
            manifest["args"]["objetivo"], pausa=0,
            adapter_kw=lambda cad: {"transport": sesion.transporte(cad)},
            semillas=manifest["args"]["semillas"], generado=manifest["generado"],
            enriquecedor=enr)
    finally:
        sesion.cerrar()
        sesion_qv.cerrar()
        _cerrar_enriquecedor(enr)
    fallos = sesion.fallos()
    if fallos:
        raise ErrorCorrida(
            f"{len(fallos)} requests no están en el crudo de {corrida} (no se tocó la red). "
            "Primeras: " + " | ".join(fallos[:5]))

    stats = {**sesion.estadisticas(), **sesion_qv.estadisticas()}
    enriq = {**enr.stats, "imagenes": dict(enr.imagenes.stats)}
    if completar:
        _publicar_quickview(raw, corrida, sesion_qv, manifest)
        manifest.setdefault("completado", []).append({
            "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "requests": sesion_qv.estadisticas(), "enriquecimiento": enriq})
        raw.escribir_manifest(corrida, manifest)
        shutil.rmtree(STAGING_DIR / corrida, ignore_errors=True)

    previo = raw.leer_json_corrida(corrida, "previo.json.gz")
    eventos = cambios.diff_snapshots(previo, data)  # anota tendencia/promo_cambio in-place
    stats["_enriquecimiento"] = enriq
    return data, eventos, stats


def validar(data: dict, requests: Dict[str, Dict[str, int]]) -> None:
    """Guarda antes de exportar: una corrida rota no pisa el staging ni el histórico.

    Si se exportara, el snapshot vacío sería el `previo` de mañana: todo saldría
    "nuevo" y se perderían las ▲▼. El crudo queda en RAW_DIR para diagnosticar.
    """
    auth = {c: s.get("http_auth", 0) for c, s in requests.items() if s.get("http_auth")}
    if auth:
        raise ErrorCorrida(
            f"respuestas 401/403 en {auth}: probable key Algolia rotada. Recapturarla "
            "(DevTools), actualizar .env y volver a capturar. No se exportó nada.")
    prods = data.get("productos", [])
    if not prods or not any("inkafarma" in p["precios"] for p in prods):
        raise ErrorCorrida(f"snapshot sin filas de Inkafarma ({len(prods)} filas): "
                           "no se exportó nada.")


def exportar(data: dict, eventos: List[dict], corrida: str, *, salida: Path,
             historial: bool) -> List[Path]:
    """Snapshot -> staging data.json (mismo formato que la v1) + histórico."""
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


def _rclone() -> str:
    """rclone no está en PATH en Windows (WinGet): RCLONE_EXE > PATH > ruta WinGet."""
    exe = os.getenv("RCLONE_EXE", "").strip() or shutil.which("rclone")
    if exe:
        return exe
    winget = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "rclone.exe"
    if winget.exists():
        return str(winget)
    raise ErrorCorrida("no encuentro rclone (define RCLONE_EXE en .env)")


def sincronizar(raw_root: Path, processed_root: Path, nombre_log: str) -> List[str]:
    """Copia el lake local a Drive con `rclone copy` (nunca sync: no borra en Drive).

    Destinos en .env: RCLONE_REMOTE (crudo) y RCLONE_REMOTE_PROCESSED (Parquet,
    opcional). Devuelve la lista de errores; no lanza: la corrida ya está completa.
    """
    pares = [(raw_root, os.getenv("RCLONE_REMOTE", "").strip()),
             (processed_root, os.getenv("RCLONE_REMOTE_PROCESSED", "").strip())]
    if not pares[0][1]:
        return ["RCLONE_REMOTE vacío en .env: el crudo no se archivó en Drive"]
    errores = []
    try:
        exe = _rclone()
    except ErrorCorrida as exc:
        return [str(exc)]
    for origen, destino in pares:
        if not destino or not origen.is_dir():
            continue
        log_rclone = LOG_DIR / f"rclone_{nombre_log}.log"
        cmd = [exe, "copy", str(origen), destino, "--transfers", "4",
               "--exclude", "*.tmp", "--log-file", str(log_rclone), "--log-level", "INFO"]
        log(f"  rclone copy {origen} -> {destino}")
        try:
            rc = subprocess.run(cmd, timeout=3600).returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            errores.append(f"rclone {destino}: {exc}")
            continue
        if rc != 0:
            errores.append(f"rclone copy -> {destino} terminó con código {rc} (ver {log_rclone}); "
                           "se reintenta en la próxima corrida")
    return errores


# --- resumen -----------------------------------------------------------------
def resumen(data: dict, eventos: List[dict], requests: Dict[str, Dict[str, int]],
            duracion: float, errores: List[str],
            replay: Optional[Dict[str, Dict[str, int]]] = None) -> str:
    """`requests` = lo que hizo la CAPTURA (manifest); `replay` = lo que leyó el
    procesado desde el crudo. Van en líneas separadas: en un --desde-cache, un
    "red=365" suelto parecía decir que el replay había tocado la red."""
    replay = dict(replay) if replay is not None else None
    enriq = replay.pop("_enriquecimiento", None) if replay is not None else None
    prods = data["productos"]
    por_cadena = {c: sum(1 for p in prods if c in p["precios"]) for c in CADENAS}
    metodos: Dict[str, int] = {}
    for p in prods:
        for ev in [*(p.get("evidencia") or {}).values(), *(p.get("equivalentes") or {}).values()]:
            metodos[ev["metodo"]] = metodos.get(ev["metodo"], 0) + 1
    multi = sum(1 for p in prods if len(p["precios"]) >= 2)
    todas = sum(1 for p in prods if len(p["precios"]) == len(CADENAS))
    lineas = [
        "=" * 64,
        f"RESUMEN corrida · generado {data['generado']} · {duracion:.0f} s",
        f"  filas: {len(prods)} · con >=2 cadenas: {multi} · con las 4: {todas}",
        "  por cadena: " + " · ".join(f"{c} {n}" for c, n in por_cadena.items()),
        "  eventos: " + (", ".join(f"{k} {v}" for k, v in
                                   sorted(cambios.resumen_eventos(eventos).items())) or "ninguno"),
        "  captura (manifest): " + " · ".join(
            f"{c} red={s.get('red', 0)} cache={s.get('cache', 0)} "
            f"404={s.get('http_404', 0)} err={s.get('http_error', 0) + s.get('red_error', 0)}"
            for c, s in requests.items()),
        *([f"  procesado desde el crudo: {sum(s.get('cache', 0) for s in replay.values())} "
           f"respuestas del caché · {sum(s.get('red', 0) for s in replay.values())} por red"]
          if replay is not None else []),
        *([f"  cruces Boticas/Universal por método (equivalente = no es match): "
           + ", ".join(f"{k} {v}" for k, v in sorted(metodos.items()))] if metodos else []),
        *([f"  enriquecimiento F3: QuickView {enriq['quickview_con_rs']} con R.S. / "
           f"{enriq['quickview_sin_dato']} sin dato · fotos {enriq['imagenes']}"]
          if enriq else []),
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
    modo.add_argument("--completar", metavar="FECHA|CORRIDA",
                      help="F3: baja QuickView/fotos que le faltan a una corrida y reprocesa")
    modo.add_argument("--sincronizar", action="store_true",
                      help="solo copia RAW_DIR y Parquet a Drive (rclone copy)")
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
        if args.desde_cache or args.completar:
            corrida = raw.resolver_corrida(args.desde_cache or args.completar)
        elif args.reanudar:
            corrida = args.reanudar
        else:
            corrida = nuevo_id_corrida()
    except StorageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.sincronizar:
        ruta_log, fh = _abrir_log(f"sync_{nuevo_id_corrida()}")
        try:
            errores = sincronizar(raw.root, processed_dir_desde_entorno(), ruta_log.stem[len("run_"):])
            for e in errores:
                log(f"ERROR: {e}")
            log("Sincronización " + ("con errores" if errores else "OK"))
            return 1 if errores else 0
        finally:
            sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
            fh.close()

    ruta_log, fh = _abrir_log(corrida)
    try:
        log(f"Corrida {corrida} · RAW_DIR={raw.root} · log={ruta_log}")
        if args.completar:
            log(f"Paso completar (QuickView Boticas + fotos de los candidatos >= 60, "
                f"delay por dominio {args.delay} s)")
            _, _, st = procesar(raw, corrida, completar=True, delay=_parse_delay(args.delay))
            log(f"  {st.get(CADENA_QUICKVIEW, {})} · {st['_enriquecimiento']}")
        elif not args.desde_cache:
            log("Paso capturar (red, delay por dominio "
                f"{args.delay} s, objetivo {args.objetivo}"
                f"{', sin semillas' if args.sin_semillas else ''})")
            man = capturar(raw, corrida, objetivo=args.objetivo,
                           semillas=not args.sin_semillas, delay=_parse_delay(args.delay),
                           reanudar=bool(args.reanudar))
            for cad, s in man["requests"].items():
                if s.get("http_error") or s.get("red_error"):
                    errores.append(f"{cad}: {s.get('http_error', 0)} HTTP>=400 (sin contar 404), "
                                   f"{s.get('red_error', 0)} errores de red")
            if args.solo_captura:
                log(f"Captura lista: {corrida}. Procesar con --desde-cache {corrida}")
                return 1 if errores else 0

        log("Paso procesar (desde el crudo, sin red)")
        data, eventos, replay = procesar(raw, corrida)
        requests = raw.leer_manifest(corrida).get("requests", {})
        validar(data, requests)
        log("Paso exportar")
        for p in exportar(data, eventos, corrida, salida=Path(args.salida),
                          historial=not args.sin_historial):
            log(f"  -> {p}")
        if args.todo or args.reanudar:
            # Después de snapshot y Parquet: si Drive falla, la corrida ya está completa.
            log("Paso sincronizar (rclone copy a Drive)")
            errores.extend(sincronizar(raw.root, processed_dir_desde_entorno(), corrida))
        print(resumen(data, eventos, requests, time.monotonic() - t0, errores, replay),
              file=sys.stderr)
        return 1 if errores else 0
    except (ErrorCorrida, StorageError) as exc:
        log(f"ERROR: {exc}")
        return 2
    finally:
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        fh.close()


if __name__ == "__main__":
    sys.exit(main())
