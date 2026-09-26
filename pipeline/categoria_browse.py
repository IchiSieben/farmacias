"""pipeline/categoria_browse.py — Snapshot de UNA categoría por browse (V2_PLAN F2).

A diferencia de `pipeline.build_snapshot.construir` (candidatos de Boticas/Universal
por BÚSQUEDA de cada producto Inka), esto baja la categoría ENTERA de cada cadena
con `browse_categoria()` (core/adapters/*, config/categorias.yaml) y compara en
memoria (pool vs pool): cada producto InRetail contra TODOS los productos de la
categoría en Boticas/Universal, no solo lo que trae una búsqueda por nombre.
Ventaja de red: browse por categoría es ~10-15 requests (paginado), sin importar
cuántos productos tenga InRetail; una búsqueda por producto sería 1-2 requests
POR PRODUCTO a Boticas y a Universal.

Reutiliza el motor de comparación de `build_snapshot` (capas del matcher, reparto
uno a uno, equivalentes, laboratorio por R.S.) tal cual: cambia SOLO de dónde
salen los candidatos.

Decisiones de esta primera categoría (documentadas en docs/revision/F2_analgesicos.md):
  - SÍ se pide el detalle REST de Inka/Mifa (`get_presentaciones`, 1 request por
    objectID): es la única fuente confiable de `cantidad_envase`/`unidad_envase`
    (el nombre del hit casi nunca trae el tamaño del envase, p.ej. "Panadol 500mg
    Tableta" sin cuántas tabletas). Sin esto, `_cantidad_coincide` (que exige
    igual cantidad y unidad para aceptar CUALQUIER candidato) rechaza casi todo:
    la primera pasada sin detalle dio 2/55 con Boticas y 7/55 con Universal; con
    detalle, ver cifras reales en el archivo de revisión. Costo: ~1 request por
    objectID Inka y por objectID Mifa (categoría chica, no compite con el
    presupuesto de red).
  - Sin enriquecimiento (QuickView Boticas / fotos): el R.S. de Boticas no está
    disponible en esta pasada, así que el veto por R.S. de F3 no actúa del lado
    Boticas (si actúa del lado Universal, que trae R.S. como atributo). Consistente
    con el comportamiento pre-F3 para Boticas.

Uso:
    py -m pipeline.categoria_browse analgesico --salida data/f2/analgesicos.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.adapter_base import CredencialRechazada
from core.adapters.boticasperu import BoticasPeruAdapter
from core.adapters.inkafarma import InkafarmaAdapter
from core.adapters.mifarma import MifarmaAdapter
from core.adapters.universal import UniversalAdapter
from core.categorias import CategoriaDesconocida, cargar_categorias
from core.modelo import Producto
from core.normalizer import extrae_tamano
from pipeline.build_snapshot import (
    GRUPOS, _GRUPO_DE, _asignar, _candidatos, _comparacion, laboratorios_por_rs,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = ROOT / "data" / "f2" / "categoria.json"


def _con_tamano(p: Producto) -> Producto:
    """Cantidad/unidad de envase parseadas de `presentacion` (sin request extra).

    `_candidatos` de build_snapshot exige `cantidad_envase`/`unidad_envase` para
    aceptar CUALQUIER candidato (confirma la presentación): sin detalle REST, la
    única fuente es el texto de la etiqueta que ya trae el hit de búsqueda/browse
    ("CAJA 100 UN", "FRASCO 60 ML"). Si no es legible, la fila queda sin cruzar
    (como hoy con los bundles "SUPER PACK").
    """
    if p.cantidad_envase is not None or not p.presentacion:
        return p
    tam = extrae_tamano(p.presentacion)
    if not tam:
        return p
    return dataclasses.replace(p, cantidad_envase=tam[0], unidad_envase=tam[1],
                               presentacion_kind=p.presentacion_kind or "pack")


def construir(categoria: str, *, adapter_kw: Optional[Callable[[str], dict]] = None,
             generado: Optional[str] = None) -> dict:
    """Snapshot de una sola categoría canónica, por browse de las 4 cadenas."""
    cats = cargar_categorias()
    if categoria not in cats:
        raise CategoriaDesconocida(
            f"'{categoria}' no está en config/categorias.yaml. Disponibles: "
            + ", ".join(sorted(cats)))
    cfg = cats[categoria]
    kw = adapter_kw or (lambda cadena: {})
    ink = InkafarmaAdapter(delay_range=(0, 0), **kw("inkafarma"))
    mif = MifarmaAdapter(delay_range=(0, 0), **kw("mifarma"))
    bot = BoticasPeruAdapter(delay_range=(0, 0), **kw("boticasperu"))
    uni = UniversalAdapter(delay_range=(0, 0), **kw("universal"))

    with ink, mif, bot, uni:
        sub = cfg["inretail"]["subcategory"]
        print(f"Browse InRetail (subCategory={sub!r})...", file=sys.stderr)
        try:
            inka_hits = [p for p in ink.browse_categoria(sub) if p.precio is not None]
        except CredencialRechazada:
            raise
        mifa_hits = {p.sku: p for p in mif.browse_categoria(sub) if p.precio is not None}
        print(f"  Inka: {len(inka_hits)} · Mifa: {len(mifa_hits)}", file=sys.stderr)

        # Detalle REST (1 request/objectID): única fuente confiable de
        # cantidad_envase/unidad_envase (el nombre del hit casi nunca trae el
        # tamaño del envase). Sin esto `_cantidad_coincide` rechaza casi todo
        # (ver decisión en la cabecera del archivo).
        print(f"  Detalle Inka/Mifa ({len(inka_hits)} objectIDs)...", file=sys.stderr)
        inka_list: List[Producto] = []
        mifa_por_sku_kind: Dict[str, Dict[str, Producto]] = {}
        for ip in inka_hits:
            try:
                pres = ink.get_presentaciones(ip.sku)
            except Exception:
                pres = []
            inka_list.extend(_con_tamano(p) for p in (pres or [ip]))
            try:
                mpres = mif.get_presentaciones(ip.sku) if ip.sku in mifa_hits else []
            except Exception:
                mpres = []
            if mpres:
                mifa_por_sku_kind[ip.sku] = {p.presentacion_kind or "pack": p for p in mpres}
        print(f"  Filas Inka (por presentación): {len(inka_list)}", file=sys.stderr)

        cgid = cfg["boticasperu"]["cgid"]
        path = cfg["universal"]["path"]
        print(f"Browse Boticas Perú (cgid={cgid!r})...", file=sys.stderr)
        cands_bot = [p for p in bot.browse_categoria(cgid) if p.precio is not None]
        print(f"  Boticas: {len(cands_bot)}", file=sys.stderr)
        print(f"Browse Farmacia Universal (path={path!r})...", file=sys.stderr)
        cands_uni = [p for p in uni.browse_categoria(path) if p.precio is not None]
        print(f"  Universal: {len(cands_uni)}", file=sys.stderr)

        productos: List[dict] = []
        pendientes = []  # (fila, ref) — igual forma que build_snapshot, sin candidatos precomputados
        for ip in inka_list:
            kind = ip.presentacion_kind or "pack"
            mp = mifa_por_sku_kind.get(ip.sku, {}).get(kind)
            precios: Dict[str, float] = {"inkafarma": ip.precio}
            precio_unidad: Dict[str, Optional[float]] = {"inkafarma": ip.precio_por_unidad}
            promos: Dict[str, bool] = {"inkafarma": bool(ip.en_promocion)}
            urls: Dict[str, Optional[str]] = {"inkafarma": ip.url}
            if mp is not None and mp.precio is not None:
                precios["mifarma"] = mp.precio
                precio_unidad["mifarma"] = mp.precio_por_unidad
                promos["mifarma"] = bool(mp.en_promocion)
                urls["mifarma"] = mp.url
            fila = {
                "id": f"{ip.sku}:{ip.presentacion_kind or 'pack'}",
                "nombre": ip.nombre_origen,
                "categoria": categoria,
                "marca": ip.marca,
                "presentacion": ip.presentacion,
                "cantidad": ip.cantidad_envase,
                "unidad": ip.unidad_envase,
                "precios": precios,
                "precio_unidad": precio_unidad,
                "promos": promos,
                "mas_barato": None,
                "brecha_pct": None,
                "urls": urls,
                "evidencia": {},
                "equivalentes": {},
            }
            productos.append(fila)
            pendientes.append((fila, ip, None, None))

        print("Cruzando (pool vs pool, sin búsquedas por producto)...", file=sys.stderr)
        labs_rs = laboratorios_por_rs([ref for _, ref, _, _ in pendientes] + cands_uni)
        for cadena, cands in (("boticasperu", cands_bot), ("universal", cands_uni)):
            opciones = [_candidatos(ref, cands, None, labs_rs)
                       for _, ref, _, _ in pendientes]
            _asignar(cadena, pendientes, opciones)

        for fila in productos:
            fila["mas_barato"], fila["brecha_pct"] = _comparacion(fila["precios"])
            fila["precios"] = {k: round(v, 2) for k, v in fila["precios"].items()}
            fila["precio_unidad"] = {k: v for k, v in fila["precio_unidad"].items()
                                     if v is not None}
            fila["promos"] = {k: fila["promos"][k] for k in fila["precios"]}
            fila["urls"] = {k: v for k, v in fila["urls"].items() if v}

    productos.sort(key=lambda p: p["nombre"])
    n_bot = sum(1 for p in productos if "boticasperu" in p["precios"])
    n_uni = sum(1 for p in productos if "universal" in p["precios"])
    return {
        "generado": generado or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categoria": categoria,
        "cadenas": [
            {"id": "inkafarma", "nombre": "Inkafarma", "grupo": _GRUPO_DE.get("inkafarma")},
            {"id": "mifarma", "nombre": "Mifarma", "grupo": _GRUPO_DE.get("mifarma")},
            {"id": "boticasperu", "nombre": "Boticas Perú", "grupo": _GRUPO_DE.get("boticasperu")},
            {"id": "universal", "nombre": "Farmacia Universal", "grupo": _GRUPO_DE.get("universal")},
        ],
        "grupos": GRUPOS,
        "categorias": [categoria],
        "total": len(productos),
        "con_boticas": n_bot,
        "con_universal": n_uni,
        "productos": productos,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Snapshot de UNA categoría por browse_categoria (V2_PLAN F2).")
    ap.add_argument("categoria", help="Id de config/categorias.yaml, p.ej. 'analgesico'")
    ap.add_argument("--salida", default=str(OUT_DEFAULT))
    args = ap.parse_args(argv)

    data = construir(args.categoria)
    out = Path(args.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nListo: {data['total']} filas -> {out}")
    print(f"  con Boticas Perú:      {data['con_boticas']}")
    print(f"  con Farmacia Universal: {data['con_universal']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
