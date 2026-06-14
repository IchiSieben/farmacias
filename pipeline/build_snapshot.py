"""pipeline/build_snapshot.py — Genera el data.json del buscador estático.

Toma ~150 productos de categorías de alta rotación y arma un snapshot de precios
de las 3 cadenas, listo para la página estática (web/data.json):

  1. Inkafarma como catálogo base: busca por términos de alta rotación y junta
     los hits (dedup por objectID).
  2. Mifarma: precio por el MISMO objectID (llave InRetail compartida) -> exacto.
  3. Boticas Perú: match por nombre+specs (core.matcher) con verificación de
     tamaño de envase; solo se acepta si es_match (umbral + reglas duras). Si no,
     la cadena queda sin precio para ese producto (la web muestra "—").

Uso:
    py -m pipeline.build_snapshot
    py -m pipeline.build_snapshot --objetivo 150 --salida web/data.json

Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from core.adapters.boticasperu import BoticasPeruAdapter
from core.adapters.inkafarma import InkafarmaAdapter
from core.adapters.mifarma import MifarmaAdapter
from core.matcher import comparar, UMBRAL_REVISION
from core.modelo import Producto
from core import imagen
from core.normalizer import extrae_specs, extrae_tamano, nucleo
from pipeline import cambios

ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = ROOT / "web" / "data.json"
SNAP_DIR = ROOT / "data" / "snapshots"          # histórico append-only (ANEXO §C)
EVENTOS_DIR = ROOT / "data" / "processed"

# Términos de alta rotación por categoría (Inkafarma como catálogo base).
TERMINOS: Dict[str, List[str]] = {
    "analgesico": ["paracetamol", "ibuprofeno", "naproxeno", "aspirina", "apronax",
                   "dolocordralan", "ketoprofeno", "diclofenaco", "tramadol"],
    "antigripal": ["panadol antigripal", "antigripal", "nastizol", "bisolvon",
                   "mucosolvan", "tabcin", "vick", "ambroxol"],
    "alergia": ["loratadina", "clorfenamina", "cetirizina", "desloratadina"],
    "gastro": ["omeprazol", "ranitidina", "sal de andrews", "enterogermina",
               "simeticona", "metoclopramida", "lactulosa", "hioscina"],
    "vitaminas": ["redoxon", "vitamina c", "centrum", "supradyn", "calcio",
                  "complejo b", "vitamina d", "hierro"],
    "nutricion": ["ensure", "pediasure", "magnesol", "glucerna"],
    "cuidado_personal": ["colgate", "head shoulders", "protex", "dove jabon",
                         "sedal", "rexona", "gillette"],
    "dermo": ["cerave", "cetaphil", "eucerin", "isdin", "la roche posay", "nivea"],
    "bebe": ["huggies", "babysec", "johnson baby", "pampers"],
    "femenino": ["kotex", "nosotras", "always"],
    "primeros_auxilios": ["alcohol 70", "agua oxigenada", "curitas", "gasa",
                          "algodon", "alcohol en gel"],
    "cronicos": ["metformina", "losartan", "atorvastatina", "enalapril",
                 "amoxicilina", "azitromicina", "glibenclamida", "levotiroxina"],
}


# Guard de plausibilidad: dos farmacias rara vez difieren >65% en el MISMO
# producto; un salto así casi siempre delata un envase/variante distinto que se
# coló pese a las reglas del matcher. Se descarta el match (mejor "—" que dato falso).
_RATIO_MIN, _RATIO_MAX = 0.60, 1.65


def _precio_plausible(precio_bot: float, precio_ref: float) -> bool:
    if not precio_ref:
        return True
    return _RATIO_MIN <= (precio_bot / precio_ref) <= _RATIO_MAX


def _query_boticas(nombre: str) -> str:
    sp = extrae_specs(nombre)
    q = " ".join(nucleo(nombre).split()[:3])
    if sp.concentracion:
        q += " " + sp.concentracion
    return q.strip() or nombre


def _comparacion(precios: Dict[str, float]):
    """(mas_barato, brecha_pct) sobre las cadenas con precio (>=2)."""
    if len(precios) < 2:
        return None, None
    lo, hi = min(precios.values()), max(precios.values())
    ganadores = [c for c, v in precios.items() if v == lo]
    mb = ganadores[0] if len(ganadores) == 1 else "empate"
    brecha = round(100 * (hi - lo) / lo, 1) if lo else None
    return mb, brecha


def _qty_boticas(cand: Producto):
    """Cantidad del envase de un candidato Boticas como (valor, clase).

    Primero por tamaño ("Frasco 120 ML" -> 120 ml, "Caja 30 tabletas" -> 30 un);
    si no, por la cantidad de specs ("Caja 30" -> 30 un). None si no es legible.
    """
    tam = extrae_tamano(cand.nombre_origen)
    if tam:
        return tam
    sp = extrae_specs(cand.nombre_origen)
    if sp.cantidad:
        return (float(sp.cantidad), "un")
    return None


def _ppu_boticas(precio, cand: Producto):
    """Precio por unidad de un candidato Boticas: precio / cantidad del envase."""
    q = _qty_boticas(cand)
    if precio and q and q[0]:
        return round(precio / q[0], 4)
    return None


def _cantidad_coincide(ref: Producto, cand: Producto, tol: float = 0.10):
    """¿La cantidad del candidato Boticas coincide con la de ESTA presentación?

    Cada fila Inka/Mifarma trae cantidad_envase exacta (API de detalle): se exige
    que Boticas tenga la MISMA cantidad y clase (blíster 10 solo casa con x10,
    caja 30 solo con x30). Si Boticas no expone cantidad legible -> no se confirma.
    """
    q = _qty_boticas(cand)
    if not q or q[1] != ref.unidad_envase:
        return False
    mayor = max(q[0], ref.cantidad_envase) or 1
    return abs(q[0] - ref.cantidad_envase) / mayor <= tol


def _match_boticas(ref: Producto, cands):
    """Mejor candidato Boticas para ESA presentación.

    Si la presentación Inka tiene cantidad exacta (caso normal, del API de
    detalle), se EXIGE que la cantidad de Boticas coincida — esto, no el precio,
    decide la presentación. Así blíster 10 nunca casa con caja 30, y una brecha de
    precio grande entre presentaciones idénticas es señal válida (no se descarta).
    Solo en el fallback sin cantidad conocida se usa el viejo guard de plausibilidad.
    """
    exige_qty = ref.cantidad_envase is not None and ref.unidad_envase is not None
    best, best_r = None, None
    for c in cands:
        if c.precio is None:
            continue
        if exige_qty:
            # La cantidad exacta confirma la presentación: si coincide, basta con
            # que pase las reglas duras y la similitud de nombre llegue a la zona
            # gris (>=70). No se usa imagen aquí (las fotos difieren entre vendors)
            # ni plausibilidad de precio (una brecha grande es señal válida).
            if not _cantidad_coincide(ref, c):
                continue
            r = comparar(ref, c)
            if r.score >= UMBRAL_REVISION and (not best_r or r.score > best_r.score):
                best, best_r = c, r
        else:
            # Fallback (presentación sin cantidad conocida): match estricto + plausibilidad.
            if not _precio_plausible(c.precio, ref.precio):
                continue
            r = comparar(ref, c, phash_fn=imagen.phash)   # Capa 3 solo en zona gris
            if r.es_match and (not best_r or r.score > best_r.score):
                best, best_r = c, r
    return best


def construir(objetivo: int, pausa: float = 0.15) -> dict:
    ink = InkafarmaAdapter(delay_range=(0, 0))
    mif = MifarmaAdapter(delay_range=(0, 0))
    bot = BoticasPeruAdapter(delay_range=(0, 0))

    base: Dict[str, dict] = {}  # objectID -> {inka, categoria}
    with ink, mif, bot:
        # 1) Catálogo base desde Inkafarma (descubrimiento por búsqueda Algolia).
        print("Recolectando catálogo base (Inkafarma)...", file=sys.stderr)
        for categoria, terminos in TERMINOS.items():
            for t in terminos:
                if len(base) >= objetivo:
                    break
                try:
                    hits = ink.search(t, limit=3)
                except Exception as exc:
                    print(f"  ! inka '{t}': {exc}", file=sys.stderr)
                    continue
                for p in hits:
                    if p.sku not in base and p.precio is not None:
                        base[p.sku] = {"inka": p, "categoria": categoria}
            if len(base) >= objetivo:
                break
        print(f"  {len(base)} productos base.", file=sys.stderr)

        # 2) Por cada objectID, expandir a UNA FILA POR PRESENTACIÓN (pack/fracción)
        #    con precio real de cada cadena (API de detalle) + Boticas (matcher).
        productos = []
        n_bot = 0
        for i, (sku, rec) in enumerate(base.items()):
            ip: Producto = rec["inka"]

            # Presentaciones reales (precio por pack/fracción) de cada cadena InRetail.
            try:
                inka_pres = ink.get_presentaciones(sku)
            except Exception:
                inka_pres = []
            if not inka_pres:   # fallback: detalle falló -> 1 fila con el precio del search
                inka_pres = [ip]
            try:
                mif_pres = {p.presentacion_kind: p for p in mif.get_presentaciones(sku)}
            except Exception:
                mif_pres = {}

            # Boticas: una sola búsqueda por producto; cada presentación elige su match.
            try:
                cands = bot.search(_query_boticas(ip.nombre_origen), limit=10)
            except Exception:
                cands = []

            for ipres in inka_pres:
                kind = ipres.presentacion_kind or "pack"
                precios = {"inkafarma": ipres.precio}
                precio_unidad = {"inkafarma": ipres.precio_por_unidad}
                promos = {"inkafarma": bool(ipres.en_promocion)}
                urls = {"inkafarma": ipres.url}

                mpres = mif_pres.get(kind)
                if mpres and mpres.precio is not None:
                    precios["mifarma"] = mpres.precio
                    precio_unidad["mifarma"] = mpres.precio_por_unidad
                    promos["mifarma"] = bool(mpres.en_promocion)
                    urls["mifarma"] = mpres.url

                best = _match_boticas(ipres, cands)
                if best:
                    precios["boticasperu"] = best.precio
                    precio_unidad["boticasperu"] = _ppu_boticas(best.precio, best)
                    promos["boticasperu"] = bool(best.en_promocion)
                    urls["boticasperu"] = best.url
                    n_bot += 1

                mb, brecha = _comparacion(precios)
                productos.append({
                    "id": f"{sku}:{kind}",
                    "nombre": ipres.nombre_origen,
                    "categoria": rec["categoria"],
                    "marca": ipres.marca,
                    "presentacion": ipres.presentacion,
                    "cantidad": ipres.cantidad_envase,
                    "unidad": ipres.unidad_envase,
                    "precios": {k: round(v, 2) for k, v in precios.items()},
                    "precio_unidad": {k: v for k, v in precio_unidad.items() if v is not None},
                    "promos": {k: promos[k] for k in precios},
                    "mas_barato": mb,
                    "brecha_pct": brecha,
                    "urls": {k: v for k, v in urls.items() if v},
                })
            time.sleep(pausa)
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(base)} productos (filas: {len(productos)}, Boticas: {n_bot})",
                      file=sys.stderr)

    productos.sort(key=lambda p: (p["categoria"], p["nombre"], p.get("presentacion") or ""))
    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cadenas": [
            {"id": "inkafarma", "nombre": "Inkafarma"},
            {"id": "mifarma", "nombre": "Mifarma"},
            {"id": "boticasperu", "nombre": "Boticas Perú"},
        ],
        "categorias": sorted({p["categoria"] for p in productos}),
        "total": len(productos),
        "con_boticas": n_bot,
        "productos": productos,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Genera web/data.json (snapshot de precios).")
    parser.add_argument("--objetivo", type=int, default=150, help="N° de productos objetivo")
    parser.add_argument("--salida", default=str(OUT_DEFAULT))
    args = parser.parse_args(argv)

    # Histórico (ANEXO §C): comparar contra el snapshot anterior ANTES de guardar
    # el de hoy, para no diff-earse contra sí mismo.
    previo = cambios.cargar_snapshot_previo(SNAP_DIR)
    data = construir(args.objetivo)
    eventos = cambios.diff_snapshots(previo, data)   # anota tendencia/promo_cambio in-place

    out = Path(args.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    snap_path = cambios.persistir_snapshot(data, SNAP_DIR)
    fecha = data["generado"][:10]
    ev_path = cambios.escribir_eventos_csv(eventos, fecha, EVENTOS_DIR)

    con_bot = data["con_boticas"]
    tot = data["total"]
    print(f"\nListo: {tot} productos -> {out}")
    print(f"  Cobertura Boticas Perú: {con_bot}/{tot} ({100*con_bot//max(tot,1)}%)")
    print(f"  Snapshot histórico -> {snap_path}")
    if previo is None:
        print("  (primera corrida: sin snapshot previo, sin eventos ni flechas)")
    else:
        res = cambios.resumen_eventos(eventos)
        comp = previo["generado"][:10]
        print(f"  Cambios vs {comp}: {sum(res.values())} eventos -> {ev_path}")
        for tipo in ("nuevo", "baja_precio", "sube_precio", "inicia_promo", "fin_promo"):
            if res.get(tipo):
                print(f"    {tipo:13} {res[tipo]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
