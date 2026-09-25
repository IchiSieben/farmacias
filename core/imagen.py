"""core/imagen.py — Hashes perceptuales de la foto de cada oferta (F3, V2_PLAN §3.3).

Las cadenas suelen reusar la foto del proveedor para el mismo producto. pHash y
dHash (64 bits) dan distancia de Hamming ~0 para la misma foto reescalada, a coste
de milisegundos y sin IA. Se calculan UNA vez por URL y quedan en disco:

    RAW_DIR/imagenes/indice.jsonl        url -> {phash, dhash, archivo | error}
    RAW_DIR/imagenes/<aa>/<sha1(url)>    la imagen tal cual se bajó

Reproceso sin red (`red=False`): una URL que no está en el índice devuelve None
("sin dato", el matcher no decide por imagen). Con red, la descarga respeta el
delay por dominio (misma cortesía que los adaptadores) y un fallo también se anota
para no reintentarlo en cada corrida.

Degradación elegante: sin imagehash/Pillow, `hashes` devuelve None. Nunca rompe el
pipeline. Python 3.9+.
"""

from __future__ import annotations

import hashlib
import io
import json
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlsplit

from .adapter_base import USER_AGENTS

# Umbrales de Hamming (64 bits), calibrados con la corrida del 2026-09-25: ver
# `veredicto`. Entre ambos queda la zona intermedia, que no decide.
IDENTICA_MAX = 6
DISTINTA_MIN = 22

# Hash casi constante (foto en blanco, "sin imagen"): no identifica nada.
_BITS_MIN, _BITS_MAX = 4, 60


def distancia(h1: Optional[str], h2: Optional[str]) -> Optional[int]:
    """Distancia de Hamming entre dos hashes hex de 64 bits."""
    if not h1 or not h2:
        return None
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def _informativo(h: str) -> bool:
    return _BITS_MIN <= bin(int(h, 16)).count("1") <= _BITS_MAX


def veredicto(fa: Tuple[Optional[str], Optional[str]],
              fb: Tuple[Optional[str], Optional[str]]) -> Dict[str, object]:
    """Compara (phash, dhash) de dos fotos. pHash y dHash deben coincidir en el
    veredicto: 'identica' (ambos <= IDENTICA_MAX), 'distinta' (ambos >=
    DISTINTA_MIN), 'intermedia' (el resto: no decide) o 'sin_dato'."""
    dp, dd = distancia(fa[0], fb[0]), distancia(fa[1], fb[1])
    if dp is None or dd is None:
        v = "sin_dato"
    elif dp <= IDENTICA_MAX and dd <= IDENTICA_MAX:
        v = "identica"
    elif dp >= DISTINTA_MIN and dd >= DISTINTA_MIN:
        v = "distinta"
    else:
        v = "intermedia"
    return {"phash": dp, "dhash": dd, "veredicto": v}


def _sha1(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


class AlmacenImagenes:
    """Caché en disco de imágenes y sus hashes, por URL."""

    def __init__(self, root: Path, *, red: bool = False,
                 delay: Tuple[float, float] = (2.0, 6.0), timeout: float = 15.0,
                 esperar_turno: Optional[Callable[[str], None]] = None) -> None:
        self.root = Path(root)
        self.red = red
        self.delay = delay
        self.timeout = timeout
        # Si se inyecta (SesionHttp.esperar_turno), las fotos comparten el delay por
        # dominio con los adaptadores: las de Boticas salen del mismo host que el sitio.
        self._turno_externo = esperar_turno
        self.indice: Dict[str, Dict[str, object]] = {}
        self.stats = {"cache": 0, "red": 0, "error": 0, "sin_dato": 0}
        self._ultimo_por_host: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._cliente = None
        ruta = self.root / "indice.jsonl"
        if ruta.exists():
            with open(ruta, encoding="utf-8") as fh:
                for linea in fh:
                    try:
                        reg = json.loads(linea)
                    except ValueError:
                        continue  # línea cortada por un corte de la corrida
                    self.indice[reg["url"]] = reg

    def _anotar(self, reg: Dict[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / "indice.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(reg, ensure_ascii=False) + "\n")
        self.indice[str(reg["url"])] = reg

    def _esperar_turno(self, host: str) -> None:
        if self._turno_externo is not None:
            self._turno_externo(host)
            return
        lo, hi = self.delay
        with self._lock:
            ultimo = self._ultimo_por_host.get(host)
            if ultimo is not None and hi > 0:
                falta = ultimo + random.uniform(lo, hi) - time.monotonic()
                if falta > 0:
                    time.sleep(falta)
            self._ultimo_por_host[host] = time.monotonic()

    def _bajar(self, url: str) -> Dict[str, object]:
        import httpx
        import imagehash          # type: ignore
        from PIL import Image     # type: ignore

        if self._cliente is None:
            self._cliente = httpx.Client(
                headers={"User-Agent": random.choice(USER_AGENTS)},
                timeout=self.timeout, follow_redirects=True)
        reg: Dict[str, object] = {
            "url": url, "t": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self._esperar_turno(urlsplit(url).netloc)
        self.stats["red"] += 1
        try:
            resp = self._cliente.get(url)
            resp.raise_for_status()
            with Image.open(io.BytesIO(resp.content)) as img:
                rgb = img.convert("RGB")
                reg["phash"] = str(imagehash.phash(rgb))
                reg["dhash"] = str(imagehash.dhash(rgb))
                reg["tam"] = list(img.size)
            sha = _sha1(url)
            destino = self.root / sha[:2] / sha
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(resp.content)
            reg["archivo"] = f"{sha[:2]}/{sha}"
        except Exception as exc:  # red, HTTP o imagen corrupta: se anota y no decide
            self.stats["error"] += 1
            reg["error"] = f"{type(exc).__name__}: {exc}"[:200]
        return reg

    def hashes(self, url: Optional[str]) -> Optional[Tuple[str, str]]:
        """(phash_hex, dhash_hex) de la foto, o None si no hay dato."""
        if not url:
            return None
        reg = self.indice.get(url)
        if reg is not None:
            self.stats["cache"] += 1
        elif self.red:
            try:
                reg = self._bajar(url)
            except ImportError:
                return None
            self._anotar(reg)
        if reg is None or "phash" not in reg:
            self.stats["sin_dato"] += 1
            return None
        ph, dh = str(reg["phash"]), str(reg["dhash"])
        if not (_informativo(ph) and _informativo(dh)):
            self.stats["sin_dato"] += 1
            return None
        return ph, dh

    def cerrar(self) -> None:
        if self._cliente is not None:
            self._cliente.close()
            self._cliente = None
