"""core/imagen.py — Capa 3 del matcher: hash perceptual de imágenes (ANEXO §A).

Las cadenas suelen reusar la MISMA foto del proveedor para el mismo producto.
Un pHash (perceptual hash) da hashes con distancia de Hamming ~0 para imágenes
iguales o reescaladas, a coste de milisegundos y sin IA. Se usa SOLO para
desempatar la zona gris del matcher (score 70–85), no para todo (ANEXO: "solo
para los casos que la Capa 2 deja dudosos").

Degradación elegante: si faltan las dependencias (imagehash/Pillow) o la imagen
no se puede bajar/abrir, `phash` devuelve None y el matcher se queda con su
veredicto previo (revisar a mano). Nunca rompe el pipeline.

Python 3.9+. Dependencias opcionales: imagehash, Pillow, httpx.
"""

from __future__ import annotations

import io
from typing import Any, Dict, Optional

# Caché en memoria por URL (una imagen puede compararse contra varias): evita
# re-descargas dentro de una misma corrida. Guarda también los None (fallos).
_cache: Dict[str, Any] = {}

# Distancia de Hamming máxima entre pHash para considerarlos la misma foto.
# pHash de 64 bits: idénticas/reescaladas ~0–6; distintas suelen ser >12.
UMBRAL_HAMMING = 10


def phash(url: Optional[str], *, timeout: float = 10.0) -> Optional[Any]:
    """pHash de la imagen en `url`, o None si no se puede (deps/desc/decode)."""
    if not url:
        return None
    if url in _cache:
        return _cache[url]
    try:
        import imagehash          # type: ignore
        from PIL import Image     # type: ignore
        import httpx
    except ImportError:
        _cache[url] = None
        return None
    h = None
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        with Image.open(io.BytesIO(resp.content)) as img:
            h = imagehash.phash(img.convert("RGB"))
    except Exception:
        h = None
    _cache[url] = h
    return h


def imagenes_coinciden(url_a: Optional[str], url_b: Optional[str],
                       *, umbral: int = UMBRAL_HAMMING) -> Optional[bool]:
    """True/False si las fotos coinciden por pHash; None si no se puede evaluar."""
    ha, hb = phash(url_a), phash(url_b)
    if ha is None or hb is None:
        return None
    return (ha - hb) <= umbral      # imagehash soporta '-' = distancia de Hamming
