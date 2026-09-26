"""pipeline/publish.py — Publica el data.json de staging en Hostinger, con confirmación.

Contrato (F1): `pipeline.run` exporta SIEMPRE a staging (`data/publicar/data.json`);
nada automático toca lo que está servido. Publicar es un acto manual:

  1. Compara staging contra LO PUBLICADO (la URL pública; si no responde, la copia
     local `web/data.json`, que es el espejo de la última publicación).
  2. Muestra el resumen: productos, cambios de precio, desaparecidos, nuevos, tamaño.
  3. Se niega si desaparece > 20 % de los productos publicados, salvo --forzar.
  4. Pide escribir `publicar` para confirmar (no hay flag para saltarse esto).
  5. Respalda localmente el data.json remoto, sube a un temporal y renombra
     (atómico en el servidor), y actualiza `web/data.json` como espejo.

Credenciales solo en .env (ver .env.example, PUBLISH_*). FTPS/FTP con ftplib;
SFTP con paramiko (opcional, solo si PUBLISH_PROTOCOL=sftp).

Uso:
    py -m pipeline.publish --simular            # solo el resumen, no sube
    py -m pipeline.publish                      # resumen + confirmación + subida
    py -m pipeline.publish --forzar             # permite >20 % de desaparecidos
"""

from __future__ import annotations

import argparse
import ftplib
import io
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

from core.adapter_base import USER_AGENTS
from core.adapters.algolia_inretail import _load_dotenv

ROOT = Path(__file__).resolve().parent.parent
STAGING_DEFAULT = ROOT / "data" / "publicar" / "data.json"
ESPEJO_WEB = ROOT / "web" / "data.json"
RESPALDOS = ROOT / "data" / "publicar" / "respaldos"
URL_PUBLICA_DEFAULT = "https://ichisieben.dev/radar-precios/data.json"
UMBRAL_DESAPARECIDOS = 0.20
NOMBRE_REMOTO = "data.json"


class PublicacionRechazada(RuntimeError):
    pass


# --- comparación -------------------------------------------------------------
def comparar(publicado: Optional[dict], nuevo: dict,
             bytes_publicado: Optional[int], bytes_nuevo: int) -> Dict:
    """Resumen de lo que cambiaría para quien visita la página."""
    prev = {p["id"]: p for p in (publicado or {}).get("productos", [])}
    act = {p["id"]: p for p in nuevo.get("productos", [])}
    suben = bajan = 0
    for pid, p in act.items():
        if pid not in prev:
            continue
        for cad, precio in p.get("precios", {}).items():
            antes = prev[pid].get("precios", {}).get(cad)
            if antes is None or antes == precio:
                continue
            if precio > antes:
                suben += 1
            else:
                bajan += 1
    desaparecidos = sorted(set(prev) - set(act))
    return {
        "generado_publicado": (publicado or {}).get("generado"),
        "generado_nuevo": nuevo.get("generado"),
        "productos_publicado": len(prev),
        "productos_nuevo": len(act),
        "nuevos": len(set(act) - set(prev)),
        "desaparecidos": len(desaparecidos),
        "desaparecidos_pct": (len(desaparecidos) / len(prev)) if prev else 0.0,
        "ejemplos_desaparecidos": [prev[i].get("nombre", i) for i in desaparecidos[:5]],
        "precios_suben": suben,
        "precios_bajan": bajan,
        "bytes_publicado": bytes_publicado,
        "bytes_nuevo": bytes_nuevo,
    }


def verificar_umbral(resumen: Dict, forzar: bool) -> None:
    if resumen["desaparecidos_pct"] > UMBRAL_DESAPARECIDOS and not forzar:
        raise PublicacionRechazada(
            f"desaparecería el {resumen['desaparecidos_pct']:.0%} de los productos "
            f"publicados ({resumen['desaparecidos']} de {resumen['productos_publicado']}); "
            f"el tope es {UMBRAL_DESAPARECIDOS:.0%}. Revisa la corrida o usa --forzar.")


def formatear(r: Dict, origen: str) -> str:
    kb = lambda b: "?" if b is None else f"{b / 1024:.0f} KB"
    lineas = [
        "=" * 64,
        f"PUBLICAR · comparado contra: {origen}",
        f"  publicado: {r['generado_publicado'] or '—'} · {r['productos_publicado']} productos · {kb(r['bytes_publicado'])}",
        f"  nuevo:     {r['generado_nuevo']} · {r['productos_nuevo']} productos · {kb(r['bytes_nuevo'])}",
        f"  nuevos: {r['nuevos']} · desaparecidos: {r['desaparecidos']} ({r['desaparecidos_pct']:.1%})",
        f"  cambios de precio: {r['precios_suben']} suben · {r['precios_bajan']} bajan",
    ]
    if r["ejemplos_desaparecidos"]:
        lineas.append("  ej. desaparecidos: " + " | ".join(r["ejemplos_desaparecidos"]))
    lineas.append("=" * 64)
    return "\n".join(lineas)


def cargar_publicado(url: str) -> Tuple[Optional[dict], Optional[int], str]:
    """Lo publicado: la URL pública; si no responde, el espejo local web/data.json."""
    try:
        # El CDN de Hostinger (hcdn) responde 403 al UA por defecto de httpx.
        resp = httpx.get(url, timeout=20, follow_redirects=True,
                         headers={"User-Agent": USER_AGENTS[0], "Accept": "application/json"})
        resp.raise_for_status()
        return resp.json(), len(resp.content), url
    except (httpx.HTTPError, ValueError) as exc:
        print(f"  ! no se pudo leer {url} ({exc}); uso el espejo local", file=sys.stderr)
    if ESPEJO_WEB.exists():
        datos = ESPEJO_WEB.read_bytes()
        return json.loads(datos), len(datos), f"{ESPEJO_WEB} (espejo local)"
    return None, None, "nada publicado"


# --- subida ------------------------------------------------------------------
class Destino:
    """Interfaz mínima de subida: leer lo actual y reemplazarlo de forma atómica."""

    def leer(self, nombre: str) -> Optional[bytes]:
        raise NotImplementedError

    def reemplazar(self, nombre: str, datos: bytes) -> None:
        raise NotImplementedError

    def cerrar(self) -> None:
        pass


class DestinoFTP(Destino):
    def __init__(self, host: str, port: int, user: str, password: str, remoto: str,
                 tls: bool = True) -> None:
        self.ftp = ftplib.FTP_TLS() if tls else ftplib.FTP()
        self.ftp.connect(host, port, timeout=30)
        self.ftp.login(user, password)
        if tls:
            self.ftp.prot_p()
        self.ftp.cwd(remoto)

    def leer(self, nombre: str) -> Optional[bytes]:
        buf = io.BytesIO()
        try:
            self.ftp.retrbinary(f"RETR {nombre}", buf.write)
        except ftplib.error_perm:
            return None
        return buf.getvalue()

    def reemplazar(self, nombre: str, datos: bytes) -> None:
        tmp = nombre + ".subiendo"
        self.ftp.storbinary(f"STOR {tmp}", io.BytesIO(datos))
        self.ftp.rename(tmp, nombre)

    def cerrar(self) -> None:
        try:
            self.ftp.quit()
        except ftplib.all_errors:
            self.ftp.close()


class DestinoSFTP(Destino):
    def __init__(self, host: str, port: int, user: str, password: str, remoto: str) -> None:
        import paramiko  # opcional: solo para PUBLISH_PROTOCOL=sftp

        self.transport = paramiko.Transport((host, port))
        self.transport.connect(username=user, password=password)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        self.sftp.chdir(remoto)

    def leer(self, nombre: str) -> Optional[bytes]:
        try:
            with self.sftp.open(nombre, "rb") as fh:
                return fh.read()
        except IOError:
            return None

    def reemplazar(self, nombre: str, datos: bytes) -> None:
        tmp = nombre + ".subiendo"
        with self.sftp.open(tmp, "wb") as fh:
            fh.write(datos)
        self.sftp.posix_rename(tmp, nombre)

    def cerrar(self) -> None:
        self.sftp.close()
        self.transport.close()


def destino_desde_entorno() -> Destino:
    faltan = [v for v in ("PUBLISH_HOST", "PUBLISH_USER", "PUBLISH_PASS", "PUBLISH_REMOTE_DIR")
              if not os.getenv(v, "").strip()]
    if faltan:
        raise PublicacionRechazada("faltan en .env: " + ", ".join(faltan))
    proto = os.getenv("PUBLISH_PROTOCOL", "ftps").strip().lower()
    host, user = os.environ["PUBLISH_HOST"].strip(), os.environ["PUBLISH_USER"].strip()
    pw, remoto = os.environ["PUBLISH_PASS"], os.environ["PUBLISH_REMOTE_DIR"].strip()
    port = os.getenv("PUBLISH_PORT", "").strip()
    if proto == "sftp":
        return DestinoSFTP(host, int(port or 22), user, pw, remoto)
    if proto in ("ftps", "ftp"):
        return DestinoFTP(host, int(port or 21), user, pw, remoto, tls=proto == "ftps")
    raise PublicacionRechazada(f"PUBLISH_PROTOCOL desconocido: {proto} (ftps|ftp|sftp)")


def subir(destino: Destino, datos: bytes, generado: str) -> Path:
    """Respalda lo remoto en local, reemplaza atómicamente y verifica."""
    RESPALDOS.mkdir(parents=True, exist_ok=True)
    actual = destino.leer(NOMBRE_REMOTO)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    respaldo = RESPALDOS / f"data_remoto_{stamp}.json"
    if actual is not None:
        respaldo.write_bytes(actual)
    destino.reemplazar(NOMBRE_REMOTO, datos)
    if destino.leer(NOMBRE_REMOTO) != datos:
        raise PublicacionRechazada(
            f"la verificación post-subida no coincide; respaldo del anterior en {respaldo}")
    return respaldo


def probar_conexion() -> bool:
    """Solo lectura: login y lectura del data.json remoto. No escribe nada."""
    try:
        destino = destino_desde_entorno()
        try:
            actual = destino.leer(NOMBRE_REMOTO)
        finally:
            destino.cerrar()
    except Exception as exc:  # credenciales, red, ruta remota
        print(f"  conexión: FALLA ({type(exc).__name__}: {exc})")
        return False
    if actual is None:
        print(f"  conexión: OK, pero no hay {NOMBRE_REMOTO} en PUBLISH_REMOTE_DIR (¿ruta correcta?)")
        return False
    print(f"  conexión: OK · {NOMBRE_REMOTO} remoto = {len(actual)} bytes, "
          f"generado {json.loads(actual).get('generado', '?')}")
    return True


def confirmar(entrada=input) -> bool:
    try:
        return entrada("Escribe 'publicar' para subirlo: ").strip().lower() == "publicar"
    except EOFError:  # sin consola (p.ej. tarea programada): nunca se publica
        return False


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Publica el data.json de staging (con confirmación).")
    ap.add_argument("--staging", default=str(STAGING_DEFAULT))
    ap.add_argument("--simular", action="store_true", help="solo muestra el resumen")
    ap.add_argument("--forzar", action="store_true",
                    help=f"permite que desaparezca más del {UMBRAL_DESAPARECIDOS:.0%} de productos")
    args = ap.parse_args(argv)
    _load_dotenv()

    staging = Path(args.staging)
    if not staging.exists():
        print(f"ERROR: no hay staging en {staging} (corre antes pipeline.run)", file=sys.stderr)
        return 2
    datos = staging.read_bytes()
    nuevo = json.loads(datos)
    url = os.getenv("PUBLISH_PUBLIC_URL", "").strip() or URL_PUBLICA_DEFAULT
    publicado, bytes_pub, origen = cargar_publicado(url)
    r = comparar(publicado, nuevo, bytes_pub, len(datos))
    print(formatear(r, origen))
    try:
        verificar_umbral(r, args.forzar)
    except PublicacionRechazada as exc:
        print(f"RECHAZADO: {exc}", file=sys.stderr)
        return 3
    if args.simular:
        if os.getenv("PUBLISH_HOST", "").strip():
            probar_conexion()
        print("(simulación: no se subió nada)")
        return 0
    if not confirmar():
        print("Cancelado: no se subió nada.")
        return 1
    try:
        destino = destino_desde_entorno()
        try:
            respaldo = subir(destino, datos, nuevo.get("generado", ""))
        finally:
            destino.cerrar()
    except Exception as exc:  # ftplib, paramiko, red: cualquier fallo = no publicado
        print(f"ERROR al subir: {exc}", file=sys.stderr)
        return 2
    shutil.copyfile(staging, ESPEJO_WEB)  # web/data.json = espejo de lo publicado
    print(f"Publicado. Respaldo del anterior: {respaldo}. Espejo local: {ESPEJO_WEB}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
