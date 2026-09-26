"""core/categorias.py — Carga `config/categorias.yaml` (V2_PLAN F2).

Una categoría canónica -> id/nombre por cadena, para `browse_categoria()`. Ver el
comentario de cabecera de `config/categorias.yaml` para cómo se obtuvo cada id.

Python 3.9+.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
CATEGORIAS_YAML = ROOT / "config" / "categorias.yaml"


class CategoriaDesconocida(KeyError):
    pass


def cargar_categorias(path: Path = CATEGORIAS_YAML) -> Dict[str, Dict[str, Any]]:
    """Devuelve {categoria_canonica: {inretail:{...}, boticasperu:{...}, universal:{...}}}."""
    import yaml
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("categorias", {}) or {}


def id_cadena(categoria: str, cadena: str, *, path: Path = CATEGORIAS_YAML) -> Optional[Dict[str, Any]]:
    """El bloque de config de una cadena para una categoría canónica, o None."""
    cats = cargar_categorias(path)
    if categoria not in cats:
        raise CategoriaDesconocida(
            f"'{categoria}' no está en {path}. Categorías disponibles: "
            + ", ".join(sorted(cats)) or "(ninguna)"
        )
    return cats[categoria].get(cadena)
