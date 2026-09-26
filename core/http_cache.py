"""core/http_cache.py — Graba y reproduce el tráfico HTTP de los adaptadores (F1).

Por qué a nivel de transporte y no "volcado de catálogo": la v1 descubre productos
por *consultas* (búsqueda Inka → detalle por SKU → búsquedas en Boticas/Universal)
y lo que devuelve cada consulta decide el match. Para reprocesar una corrida sin red
y obtener exactamente la misma salida hay que poder responder *las mismas
consultas*. Un `httpx.BaseTransport` intercepta todo lo que pasa por
`AdapterBase._client` sin tocar la lógica de ningún adaptador.

Modos:
  grabar      red + se anota cada respuesta ANTES de devolverla al parser.
  reanudar    responde desde lo ya grabado; lo que falta va a la red y se anota
              (una corrida cortada sigue donde quedó, sin repetir requests).
  reproducir  solo caché. Un faltante NO toca la red: se cuenta y lanza
              `FaltaEnCache` (la corrida falla al final, ver `SesionHttp.fallos`).

La llave de una request es método + ruta + query ordenada + cuerpo JSON canónico,
**sin host ni headers**: las llaves Algolia van en headers (nunca llegan al
crudo) y el host Algolia se deriva del app id, que puede rotar. El archivo es por
cadena, así que no hay choques entre cadenas.

Cortesía con los sitios: el delay por dominio se aplica aquí, justo antes de cada
request que de verdad sale a la red (nunca en caché).

Python 3.9+ (stdlib + httpx).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import random
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import httpx

GRABAR = "grabar"
REANUDAR = "reanudar"
REPRODUCIR = "reproducir"
MODOS = (GRABAR, REANUDAR, REPRODUCIR)

# Nunca se guardan ni entran a la llave (por si alguna cadena pasa la key en la URL).
_PARAMS_SECRETOS = {"x-algolia-api-key", "x-algolia-application-id", "apikey", "api_key"}
# Headers de respuesta que se conservan (el cuerpo se guarda ya decodificado).
_HEADERS_UTILES = ("content-type", "location")


class FaltaEnCache(httpx.TransportError):
    """Modo reproducir: la request no está en el crudo grabado."""


def _query_limpia(url: httpx.URL) -> List[Tuple[str, str]]:
    return sorted((k, v) for k, v in url.params.multi_items()
                  if k.lower() not in _PARAMS_SECRETOS)


def _cuerpo_canonico(request: httpx.Request) -> Optional[str]:
    contenido = request.content
    if not contenido:
        return None
    texto = contenido.decode("utf-8", errors="replace")
    try:
        return json.dumps(json.loads(texto), sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"))
    except ValueError:
        return texto


def llave(request: httpx.Request) -> str:
    """Huella estable de la request (sin host ni headers)."""
    partes = [request.method.upper(), request.url.path,
              json.dumps(_query_limpia(request.url), ensure_ascii=False),
              _cuerpo_canonico(request) or ""]
    return hashlib.sha1("\n".join(partes).encode("utf-8")).hexdigest()


def _content_type_utf8(ct: Optional[str]) -> str:
    """El cuerpo se re-codifica en UTF-8 al guardarlo: el charset debe decirlo."""
    mime = (ct or "application/octet-stream").split(";")[0].strip()
    return f"{mime}; charset=utf-8"


def _respuesta_desde(registro: Dict[str, Any], request: httpx.Request) -> httpx.Response:
    if registro.get("error"):
        clase = getattr(httpx, registro["error"].get("tipo", ""), None)
        if not (isinstance(clase, type) and issubclass(clase, httpx.TransportError)):
            clase = httpx.TransportError
        raise clase(registro["error"].get("mensaje", "error grabado"), request=request)
    headers = {k: v for k, v in (registro.get("headers") or {}).items()}
    headers["content-type"] = _content_type_utf8(headers.get("content-type"))
    return httpx.Response(
        registro["status"], headers=headers,
        content=(registro.get("cuerpo") or "").encode("utf-8"), request=request,
    )


def cargar_registros(ruta: Path) -> Dict[str, Deque[Dict[str, Any]]]:
    """Lee un log (`.jsonl` o `.jsonl.gz`) a llave -> cola de respuestas en orden."""
    colas: Dict[str, Deque[Dict[str, Any]]] = {}
    if not ruta.exists():
        return colas
    abrir = gzip.open if ruta.name.endswith(".gz") else open
    with abrir(ruta, "rt", encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                reg = json.loads(linea)
            except ValueError:
                break  # última línea cortada por un corte de la corrida: se ignora
            colas.setdefault(reg["k"], deque()).append(reg)
    return colas


def _limpiar_staging(ruta: Path) -> None:
    """Corta el staging en el último salto de línea.

    Si la corrida murió a mitad de un `write`, la última línea queda a medias; sin
    esto, lo que se anote al reanudar quedaría pegado a ese fragmento y se perdería.
    Además descarta las respuestas 401/403: se reanuda después de recapturar la key,
    y reproducir el rechazo grabado volvería a abortar la corrida.
    """
    if not ruta.exists():
        return
    datos = ruta.read_bytes()
    lineas = datos[:datos.rfind(b"\n") + 1].splitlines(keepends=True)
    utiles = [ln for ln in lineas
              if json.loads(ln).get("status") not in (401, 403)]
    if len(utiles) == len(lineas) and datos.endswith(b"\n"):
        return
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_bytes(b"".join(utiles))
    os.replace(tmp, ruta)


class SesionHttp:
    """Una corrida: un transporte por cadena, delays por dominio compartidos."""

    def __init__(self, modo: str, staging: Path, *,
                 fuentes: Optional[Dict[str, Path]] = None,
                 delay: Tuple[float, float] = (2.0, 6.0),
                 red: Optional[httpx.BaseTransport] = None,
                 turnos: Optional["SesionHttp"] = None) -> None:
        if modo not in MODOS:
            raise ValueError(f"modo inválido: {modo}")
        self.modo = modo
        self.staging = Path(staging)
        self.fuentes = fuentes or {}
        self.delay = delay
        self.red = red  # transporte "de red" inyectable (tests); None -> HTTPTransport real
        self._ultimo_por_host: Dict[str, float] = {}
        self._lock = threading.Lock()
        if turnos is not None:
            # Otra sesión al mismo dominio (el QuickView de F3 junto al grid de
            # Boticas): el delay por dominio se cuenta una sola vez para ambas.
            self._ultimo_por_host = turnos._ultimo_por_host
            self._lock = turnos._lock
        self.transportes: Dict[str, "TransporteCache"] = {}

    @property
    def offline(self) -> bool:
        return self.modo == REPRODUCIR

    def archivo_staging(self, cadena: str) -> Path:
        return self.staging / f"{cadena}.jsonl"

    def transporte(self, cadena: str) -> "TransporteCache":
        if cadena not in self.transportes:
            if self.modo == REPRODUCIR:
                previas = cargar_registros(self.fuentes.get(cadena, Path("__sin_fuente__")))
            elif self.modo == REANUDAR:
                _limpiar_staging(self.archivo_staging(cadena))
                previas = cargar_registros(self.archivo_staging(cadena))
            else:
                previas = {}
            self.transportes[cadena] = TransporteCache(self, cadena, previas)
        return self.transportes[cadena]

    def esperar_turno(self, host: str) -> None:
        """Delay aleatorio por dominio desde la última request a ese dominio."""
        lo, hi = self.delay
        if hi <= 0:
            return
        with self._lock:
            ultimo = self._ultimo_por_host.get(host)
            if ultimo is not None:
                falta = ultimo + random.uniform(lo, hi) - time.monotonic()
                if falta > 0:
                    time.sleep(falta)
            self._ultimo_por_host[host] = time.monotonic()

    def estadisticas(self) -> Dict[str, Dict[str, int]]:
        return {c: dict(t.stats) for c, t in sorted(self.transportes.items())}

    def fallos(self) -> List[str]:
        out: List[str] = []
        for t in self.transportes.values():
            out.extend(t.faltantes)
        return out

    def cerrar(self) -> None:
        for t in self.transportes.values():
            t.close()


class TransporteCache(httpx.BaseTransport):
    """Transporte httpx de UNA cadena dentro de una `SesionHttp`."""

    def __init__(self, sesion: SesionHttp, cadena: str,
                 previas: Dict[str, Deque[Dict[str, Any]]]) -> None:
        self.sesion = sesion
        self.cadena = cadena
        self._previas = previas
        self._red: Optional[httpx.BaseTransport] = None
        self._fh = None
        self.faltantes: List[str] = []
        # http_404 es informativo (p.ej. detalle InRetail inexistente = "sin
        # presentaciones", caso normal). http_auth (401/403) suele ser key rotada.
        self.stats = {"red": 0, "cache": 0, "http_error": 0, "http_404": 0, "http_auth": 0,
                      "red_error": 0, "faltantes": 0}

    # --- caché ----------------------------------------------------------------
    def _desde_cache(self, k: str) -> Optional[Dict[str, Any]]:
        cola = self._previas.get(k)
        if not cola:
            return None
        # En orden de grabación (reintentos 429 -> 200 se reproducen igual); el
        # último registro se reusa si la request se repite más veces.
        return cola.popleft() if len(cola) > 1 else cola[0]

    def _anotar(self, registro: Dict[str, Any]) -> None:
        if self._fh is None:
            ruta = self.sesion.archivo_staging(self.cadena)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(ruta, "a", encoding="utf-8")
        self._fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
        self._fh.flush()

    # --- httpx ----------------------------------------------------------------
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        k = llave(request)
        if self.sesion.modo in (REANUDAR, REPRODUCIR):
            reg = self._desde_cache(k)
            if reg is not None:
                self.stats["cache"] += 1
                return _respuesta_desde(reg, request)
            if self.sesion.modo == REPRODUCIR:
                self.stats["faltantes"] += 1
                self.faltantes.append(f"{self.cadena} {request.method} {request.url.path}"
                                      f"?{request.url.query.decode('utf-8', 'replace')}")
                raise FaltaEnCache(f"no está en el crudo: {request.url.path}", request=request)

        base = {
            "k": k,
            "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "metodo": request.method.upper(),
            "url": str(request.url.copy_with(query=None)),
            "query": _query_limpia(request.url),
            "body": _cuerpo_canonico(request),
        }
        self.sesion.esperar_turno(request.url.host)
        if self._red is None:
            self._red = self.sesion.red or httpx.HTTPTransport()
        self.stats["red"] += 1
        try:
            resp = self._red.handle_request(request)
            resp.read()  # decodifica gzip/br: se guarda el cuerpo ya legible
        except httpx.TransportError as exc:
            self.stats["red_error"] += 1
            self._anotar({**base, "error": {"tipo": type(exc).__name__, "mensaje": str(exc)}})
            raise
        if resp.status_code == 404:
            self.stats["http_404"] += 1
        elif resp.status_code >= 400:
            self.stats["http_error"] += 1
            if resp.status_code in (401, 403):
                self.stats["http_auth"] += 1
        registro = {
            **base,
            "status": resp.status_code,
            "headers": {h: resp.headers[h] for h in _HEADERS_UTILES if h in resp.headers},
            "cuerpo": resp.text,
        }
        # Crudo primero, parseo después: la respuesta queda en disco antes de que
        # el adaptador la lea. Y el parser recibe exactamente lo grabado.
        self._anotar(registro)
        resp.close()
        return _respuesta_desde(registro, request)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        if self._red is not None and self.sesion.red is None:
            self._red.close()
        self._red = None
