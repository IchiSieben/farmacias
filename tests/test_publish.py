"""tests/test_publish.py — Contrato de publicación (F1), sin red ni servidor.

    PYTHONIOENCODING=utf-8 py -m tests.test_publish
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

from pipeline import publish as pub


def _snap(n: int, precio: float = 10.0, generado: str = "2026-09-25T09:00:00+00:00") -> dict:
    return {"generado": generado, "productos": [
        {"id": f"{i}:pack", "nombre": f"Producto {i}", "precios": {"inkafarma": precio}}
        for i in range(n)]}


class _DestinoFalso(pub.Destino):
    def __init__(self, inicial: Optional[bytes], corromper: bool = False) -> None:
        self.archivos: Dict[str, bytes] = {} if inicial is None else {"data.json": inicial}
        self.operaciones = []
        self.corromper = corromper

    def leer(self, nombre):
        return self.archivos.get(nombre)

    def reemplazar(self, nombre, datos):
        self.operaciones.append(("reemplazar", nombre))
        self.archivos[nombre] = datos[:-1] if self.corromper else datos


def main() -> int:
    fallas = []

    def check(cond: bool, msg: str) -> None:
        print(f"  [{'OK  ' if cond else 'FAIL'}] {msg}")
        if not cond:
            fallas.append(msg)

    # 1) resumen: nuevos, desaparecidos, cambios de precio, tamaño
    antes = _snap(10)
    ahora = _snap(9, precio=12.0)
    ahora["productos"].append({"id": "nuevo:pack", "nombre": "Nuevo", "precios": {"mifarma": 5.0}})
    r = pub.comparar(antes, ahora, 1000, 900)
    check((r["productos_publicado"], r["productos_nuevo"], r["nuevos"], r["desaparecidos"])
          == (10, 10, 1, 1), "cuenta productos, nuevos y desaparecidos")
    check((r["precios_suben"], r["precios_bajan"]) == (9, 0), "cuenta cambios de precio")
    texto = pub.formatear(r, "prueba")
    check("desaparecidos: 1" in texto and "KB" in texto, "el resumen muestra desaparecidos y tamaño")

    # 2) umbral 20 %: 2/10 pasa, 3/10 se rechaza salvo --forzar
    pub.verificar_umbral(pub.comparar(_snap(10), _snap(8), 1, 1), forzar=False)
    check(True, "20 % exacto de desaparecidos se permite")
    try:
        pub.verificar_umbral(pub.comparar(_snap(10), _snap(7), 1, 1), forzar=False)
        check(False, "30 % de desaparecidos se rechaza")
    except pub.PublicacionRechazada as exc:
        check("30%" in str(exc) and "--forzar" in str(exc), "30 % de desaparecidos se rechaza")
    pub.verificar_umbral(pub.comparar(_snap(10), _snap(7), 1, 1), forzar=True)
    check(True, "--forzar permite el 30 %")
    pub.verificar_umbral(pub.comparar(None, _snap(3), None, 1), forzar=False)
    check(True, "sin nada publicado no hay umbral")

    # 3) confirmación: solo la palabra exacta; sin consola nunca publica
    check(pub.confirmar(lambda _: " Publicar ") is True, "confirma con 'publicar'")
    check(pub.confirmar(lambda _: "si") is False, "cualquier otra respuesta cancela")

    def _eof(_):
        raise EOFError
    check(pub.confirmar(_eof) is False, "sin consola (tarea programada) no publica")

    # 4) subida: respaldo local del remoto, reemplazo atómico, verificación
    with tempfile.TemporaryDirectory() as tmp:
        pub.RESPALDOS = Path(tmp) / "respaldos"
        viejo, nuevo = json.dumps(_snap(2)).encode(), json.dumps(_snap(3)).encode()
        d = _DestinoFalso(viejo)
        respaldo = pub.subir(d, nuevo, "g")
        check(respaldo.read_bytes() == viejo, "respalda localmente lo que estaba publicado")
        check(d.archivos["data.json"] == nuevo and d.operaciones == [("reemplazar", "data.json")],
              "reemplaza una sola vez (temporal + rename en el destino real)")
        try:
            pub.subir(_DestinoFalso(viejo, corromper=True), nuevo, "g")
            check(False, "detecta una subida que no coincide")
        except pub.PublicacionRechazada:
            check(True, "detecta una subida que no coincide")

        # 5) main --simular: no sube ni toca el espejo web/data.json
        staging = Path(tmp) / "data.json"
        staging.write_bytes(nuevo)
        pub.cargar_publicado = lambda url: (_snap(2), len(viejo), "falso")
        espejo_antes = pub.ESPEJO_WEB.read_bytes()
        rc = pub.main(["--staging", str(staging), "--simular"])
        check(rc == 0 and pub.ESPEJO_WEB.read_bytes() == espejo_antes,
              "--simular no sube ni toca web/data.json")
        pub.cargar_publicado = lambda url: (_snap(10), 1, "falso")
        check(pub.main(["--staging", str(staging), "--simular"]) == 3,
              "main se niega (código 3) con >20 % desaparecidos")

    print("-" * 60)
    if fallas:
        print(f"PUBLISH: {len(fallas)} FALLAS")
        return 1
    print("PUBLISH: todo OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
