"""core/adapter_base.py — Interfaz común de adaptadores.

Todo adaptador de cadena hereda de `AdapterBase` y expone, como mínimo,
`search(query) -> List[Producto]` (SPEC §4). Los adaptadores de Nivel A (API
JSON) que además puedan recorrer el catálogo completo implementan `browse()`.

Esta base aporta lo transversal: cliente HTTP con headers/UA realistas, delays
aleatorios para no saturar al sitio (SPEC §3), y reintentos con backoff ante
429/503. No conoce ninguna cadena en concreto.

Python 3.9+.
"""

from __future__ import annotations

import abc
import random
import time
from typing import Dict, Iterator, List, Optional

import httpx

from .modelo import Producto

# UA realistas (espejo de farmacias.yaml / recon). Se rota uno por sesión.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class AdapterBase(abc.ABC):
    """Clase base para los adaptadores por cadena."""

    cadena: str = "?"  # los subclases lo sobreescriben ("inkafarma", ...)

    def __init__(
        self,
        *,
        delay_range=(2.0, 6.0),
        timeout: float = 30.0,
        user_agent: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.delay_range = delay_range
        self.timeout = timeout
        self.user_agent = user_agent or random.choice(USER_AGENTS)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        }
        if extra_headers:
            headers.update(extra_headers)
        self._client = client or httpx.Client(
            headers=headers, timeout=timeout, follow_redirects=True
        )
        self._owns_client = client is None

    # --- ciclo de vida ------------------------------------------------------
    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "AdapterBase":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- utilidades transversales ------------------------------------------
    def _sleep(self, rango=None) -> None:
        """Delay aleatorio entre requests (cortesía con el sitio)."""
        lo, hi = rango or self.delay_range
        if hi > 0:
            time.sleep(random.uniform(lo, hi))

    def _post_json(self, url: str, body: dict, *, intentos: int = 4) -> dict:
        """POST con reintentos y backoff exponencial ante 429/503."""
        ultimo: Optional[httpx.Response] = None
        for i in range(intentos):
            resp = self._client.post(url, json=body)
            ultimo = resp
            if resp.status_code in (429, 503):
                time.sleep(min(2 ** i, 30))
                continue
            resp.raise_for_status()
            return resp.json()
        assert ultimo is not None
        ultimo.raise_for_status()
        return ultimo.json()

    # --- interfaz que deben implementar los adaptadores ---------------------
    @abc.abstractmethod
    def search(self, query: str, *, limit: Optional[int] = None) -> List[Producto]:
        """Busca un término y devuelve las ofertas normalizadas."""

    def browse(self) -> Iterator[Producto]:
        """Recorre el catálogo completo. Solo Nivel A con volcado disponible."""
        raise NotImplementedError(
            f"El adaptador de '{self.cadena}' no soporta browse (volcado completo)."
        )
