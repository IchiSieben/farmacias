"""pipeline/enriquecer.py — Completa la ficha de los candidatos que llegan a decidir (F3).

El matcher arma fichas sin red. Lo que cuesta requests se pide aquí, y solo para
los candidatos que pasan cantidad y precio con texto >= 60 (UMBRAL_IMAGEN):

  - Registro sanitario de Boticas: vive en el QuickView (uno por pid), no en el
    grid de búsqueda. Pasa por su propia `SesionHttp` y se guarda aparte del crudo
    principal (`boticasperu/<fecha>/quickview_<corrida>.jsonl.gz`): es una fuente
    OPCIONAL. Un faltante al reprocesar significa "sin R.S.", no una corrida rota,
    así que las corridas grabadas antes de F3 se siguen reprocesando igual.
  - Hashes de imagen: core.imagen.AlmacenImagenes (RAW_DIR/imagenes/).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from core.ficha import ATRIBUTO, Ficha, ficha_de, normaliza_rs
from core.imagen import AlmacenImagenes
from core.modelo import Producto

CADENA_QUICKVIEW = "boticasperu_quickview"


class Enriquecedor:
    def __init__(self, imagenes: Optional[AlmacenImagenes] = None, boticas=None) -> None:
        self.imagenes = imagenes
        self.boticas = boticas          # BoticasPeruAdapter con transporte del QuickView
        self._qv: Dict[str, Optional[str]] = {}
        self._fichas: Dict[Tuple[str, str, Optional[str]], Ficha] = {}
        self.stats = {"quickview_pedidos": 0, "quickview_con_rs": 0, "quickview_sin_dato": 0}

    def _rs_boticas(self, pid: str) -> Optional[str]:
        if pid not in self._qv:
            self.stats["quickview_pedidos"] += 1
            rs = None
            try:
                qv = self.boticas.get_object(pid)
                rs = qv.registro_sanitario if qv else None
            except Exception:  # FaltaEnCache al reprocesar, o red/HTTP al capturar
                rs = None
            self.stats["quickview_con_rs" if rs else "quickview_sin_dato"] += 1
            self._qv[pid] = rs
        return self._qv[pid]

    def ficha(self, p: Producto) -> Ficha:
        """Ficha completa. No modifica `p`: el R.S. del QuickView va solo a la ficha,
        así una comparación sin enriquecer nunca ve datos pedidos para otra (el
        resultado no depende del orden en que se comparan las referencias)."""
        k = (p.cadena, str(p.sku), p.presentacion_kind)
        if k not in self._fichas:
            f = ficha_de(p, hashes_fn=self.imagenes.hashes if self.imagenes else None)
            if (p.cadena == "boticasperu" and self.boticas is not None
                    and not f.registro_sanitario):
                rs = normaliza_rs(self._rs_boticas(str(p.sku)))
                if rs:
                    f.registro_sanitario = rs
                    f.fuentes["registro_sanitario"] = ATRIBUTO
            self._fichas[k] = f
        return self._fichas[k]
