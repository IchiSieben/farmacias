"""core/storage.py — Almacén del crudo (data lake, capa RAW) — V2_PLAN F1.

El crudo de cada corrida se guarda particionado por cadena y fecha:

    RAW_DIR/
      <cadena>/<YYYY-MM-DD>/respuestas_<corrida>.jsonl.gz   # respuestas HTTP (http_cache)
      _corridas/<corrida>/manifest.json                     # qué se corrió, con qué args
      _corridas/<corrida>/previo.json.gz                    # snapshot contra el que se difea

`RAW_DIR` es una carpeta local (default `data/raw/`). El archivo en Google Drive
se hace aparte, con `rclone copy` al final de la corrida (`pipeline.run
--sincronizar`), así que:

- se escribe primero a un temporal **en la misma carpeta destino** y se publica con
  `os.replace` (atómico; nunca queda un .gz a medias que rclone pueda subir);
- pocos archivos grandes y comprimidos (rclone sube mejor pocos archivos que miles);
- si `RAW_DIR` está configurado pero no existe (disco externo desconectado, typo)
  se falla de inmediato, en vez de crear una carpeta en otro lado.

Solo stdlib (Python 3.9+). El Parquet (capa PROCESSED) vive en `pipeline/`, porque
pandas no cabe en la regla de compatibilidad de `core/`.
"""

from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR_DEFAULT = ROOT / "data" / "raw"
DIR_CORRIDAS = "_corridas"


class StorageError(RuntimeError):
    """Error de configuración o de lectura del almacén crudo."""


def nuevo_id_corrida(ahora: Optional[datetime] = None) -> str:
    """Id de corrida = instante UTC, seguro como nombre en Windows: `2026-09-24T08-30-00Z`."""
    t = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return t.strftime("%Y-%m-%dT%H-%M-%SZ")


def fecha_de(corrida: str) -> str:
    """`2026-09-24T08-30-00Z` -> `2026-09-24` (partición por fecha UTC)."""
    return corrida[:10]


def raw_dir_desde_entorno() -> Path:
    """Resuelve `RAW_DIR` del entorno. Configurado pero inexistente -> error."""
    valor = os.getenv("RAW_DIR", "").strip()
    if not valor:
        return RAW_DIR_DEFAULT
    p = Path(valor).expanduser()
    if not p.is_dir():
        raise StorageError(
            f"RAW_DIR={valor} no existe o no es carpeta. Revisa la ruta en .env "
            "(o déjala vacía para usar data/raw/)."
        )
    return p


def _escribir_atomico(destino: Path, datos: bytes) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(datos)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, destino)


class RawStore:
    """Crudo particionado `<cadena>/<fecha>/`, gzip transparente por extensión."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # --- archivos por cadena ------------------------------------------------
    def ruta(self, cadena: str, fecha: str, nombre: str) -> Path:
        return self.root / cadena / fecha / nombre

    def write(self, cadena: str, fecha: str, nombre: str, datos: bytes) -> Path:
        """Escribe `datos`; si `nombre` termina en `.gz` se comprime."""
        if nombre.endswith(".gz"):
            datos = gzip.compress(datos, compresslevel=6, mtime=0)
        destino = self.ruta(cadena, fecha, nombre)
        _escribir_atomico(destino, datos)
        return destino

    def publicar_archivo(self, origen: Path, cadena: str, fecha: str, nombre: str) -> Path:
        """Comprime un archivo local (staging) directo hacia RAW_DIR, en streaming.

        Útil para el log HTTP de una corrida, que puede pesar decenas de MB: no se
        carga entero en memoria. Temporal en la carpeta destino + `os.replace`.
        """
        destino = self.ruta(cadena, fecha, nombre)
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + ".tmp")
        with open(origen, "rb") as src, open(tmp, "wb") as raw_fh:
            with gzip.GzipFile(fileobj=raw_fh, mode="wb", compresslevel=6, mtime=0) as gz:
                while True:
                    bloque = src.read(1 << 20)
                    if not bloque:
                        break
                    gz.write(bloque)
            raw_fh.flush()
            os.fsync(raw_fh.fileno())
        os.replace(tmp, destino)
        return destino

    def read(self, cadena: str, fecha: str, nombre: str) -> bytes:
        p = self.ruta(cadena, fecha, nombre)
        if not p.exists():
            raise StorageError(f"No existe en el crudo: {p}")
        datos = p.read_bytes()
        return gzip.decompress(datos) if nombre.endswith(".gz") else datos

    def read_latest(self, cadena: str, patron: str) -> Optional[bytes]:
        """El archivo más reciente de `cadena` que calce con `patron` (glob), o None."""
        base = self.root / cadena
        if not base.is_dir():
            return None
        candidatos = sorted(base.glob(f"*/{patron}"))
        if not candidatos:
            return None
        p = candidatos[-1]
        datos = p.read_bytes()
        return gzip.decompress(datos) if p.name.endswith(".gz") else datos

    # --- manifiesto de corrida ------------------------------------------------
    def dir_corrida(self, corrida: str) -> Path:
        return self.root / DIR_CORRIDAS / corrida

    def escribir_manifest(self, corrida: str, manifest: Dict[str, Any]) -> Path:
        destino = self.dir_corrida(corrida) / "manifest.json"
        datos = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True)
        _escribir_atomico(destino, datos.encode("utf-8"))
        return destino

    def leer_manifest(self, corrida: str) -> Dict[str, Any]:
        p = self.dir_corrida(corrida) / "manifest.json"
        if not p.exists():
            raise StorageError(f"Corrida sin manifiesto: {p}")
        return json.loads(p.read_text(encoding="utf-8"))

    def escribir_json_corrida(self, corrida: str, nombre: str, obj: Any) -> Path:
        """JSON (gz si el nombre lo pide) dentro de la carpeta de la corrida."""
        datos = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        if nombre.endswith(".gz"):
            datos = gzip.compress(datos, compresslevel=6, mtime=0)
        destino = self.dir_corrida(corrida) / nombre
        _escribir_atomico(destino, datos)
        return destino

    def leer_json_corrida(self, corrida: str, nombre: str) -> Optional[Any]:
        p = self.dir_corrida(corrida) / nombre
        if not p.exists():
            return None
        datos = p.read_bytes()
        if nombre.endswith(".gz"):
            datos = gzip.decompress(datos)
        return json.loads(datos.decode("utf-8"))

    def corridas(self, *, solo_completas: bool = True) -> List[str]:
        """Ids de corrida presentes, en orden cronológico."""
        base = self.root / DIR_CORRIDAS
        if not base.is_dir():
            return []
        out = []
        for d in sorted(base.iterdir()):
            m = d / "manifest.json"
            if not m.exists():
                continue
            if solo_completas:
                estado = json.loads(m.read_text(encoding="utf-8")).get("estado")
                if estado != "completa":
                    continue
            out.append(d.name)
        return out

    def resolver_corrida(self, ref: str) -> str:
        """`2026-09-24` -> última corrida completa de ese día; un id completo se valida tal cual."""
        todas = self.corridas()
        if ref in todas:
            return ref
        del_dia = [c for c in todas if fecha_de(c) == ref]
        if del_dia:
            return del_dia[-1]
        raise StorageError(
            f"No hay corrida completa '{ref}' en {self.root}. Disponibles: "
            + (", ".join(todas[-5:]) or "ninguna")
        )
