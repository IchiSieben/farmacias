"""scripts/grafica_readme.py — Gráfica del README a partir de web/data.json.

Para cada cadena: en qué % de los productos donde tiene precio es la más barata
(empates incluidos). Una sola serie, un solo tono, etiqueta directa en cada barra.

    py scripts/grafica_readme.py            # escribe docs/img/mas_barato_{es,en}.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "web" / "data.json"
SALIDA = RAIZ / "docs" / "img"

TINTA, TINTA_2, GRILLA, BARRA = "#1f2328", "#59636e", "#d8dee4", "#2f6fb0"

TEXTOS = {
    "es": {
        "titulo": "¿En qué % de sus productos es la cadena más barata?",
        "sub": "Snapshot {fecha} · {total} productos con precio en ≥ 2 cadenas · empates cuentan para todas",
        "n": "{gana} de {n}",
    },
    "en": {
        "titulo": "Share of its products where the chain is cheapest",
        "sub": "Snapshot {fecha} · {total} products priced in ≥ 2 chains · ties count for every chain",
        "n": "{gana} of {n}",
    },
}


def contar(datos: dict):
    gana, tiene = {}, {}
    for p in datos["productos"]:
        precios = {k: v for k, v in p["precios"].items() if v}
        minimo = min(precios.values())
        for cadena, precio in precios.items():
            tiene[cadena] = tiene.get(cadena, 0) + 1
            if precio == minimo:
                gana[cadena] = gana.get(cadena, 0) + 1
    nombres = {c["id"]: c["nombre"] for c in datos["cadenas"]}
    filas = [(nombres[c], gana.get(c, 0), tiene[c]) for c in tiene]
    return sorted(filas, key=lambda f: f[1] / f[2])


def dibujar(filas, datos: dict, idioma: str) -> Path:
    t = TEXTOS[idioma]
    fig, ax = plt.subplots(figsize=(8, 3.4), dpi=150)
    pct = [100 * g / n for _, g, n in filas]
    y = range(len(filas))
    ax.barh(y, pct, height=0.55, color=BARRA)
    for i, ((nombre, g, n), v) in enumerate(zip(filas, pct)):
        ax.text(v + 1.5, i, f"{v:.0f} %  ·  " + t["n"].format(gana=g, n=n),
                va="center", fontsize=9, color=TINTA_2)
    ax.set_yticks(list(y), [f[0] for f in filas], fontsize=10, color=TINTA)
    ax.set_xlim(0, 125)
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100 %"], fontsize=8, color=TINTA_2)
    ax.grid(axis="x", color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRILLA)
    ax.tick_params(length=0)
    fig.suptitle(t["titulo"], x=0.02, ha="left", fontsize=12, fontweight="bold", color=TINTA)
    ax.set_title(t["sub"].format(fecha=datos["generado"][:10], total=len(datos["productos"])),
                 loc="left", fontsize=8.5, color=TINTA_2, pad=8)
    fig.tight_layout()
    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / f"mas_barato_{idioma}.png"
    fig.savefig(destino, facecolor="white")
    plt.close(fig)
    return destino


def main() -> None:
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    filas = contar(datos)
    for idioma in TEXTOS:
        print(dibujar(filas, datos, idioma))


if __name__ == "__main__":
    main()
