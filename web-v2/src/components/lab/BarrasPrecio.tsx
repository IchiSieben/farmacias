// Una barra por cadena; el largo es proporcional al precio máximo de la fila (escala, no width).
import type { CSSProperties } from 'react';
import { t, soles, type Idioma, type Textos, type Clave } from '../../i18n';
import { aRevisar, ahorroActivo, type Cadena, type Producto } from '../../lib/datos';
import { LogoCadena } from '../LogoCadena';

interface Props {
  p: Producto;
  activas: Cadena[];
  idioma: Idioma;
  dic: Textos;
  base: string;
}

export default function BarrasPrecio({ p, activas, idioma, dic, base }: Props) {
  const ids = activas.map((c) => c.id);
  const filas = activas.filter((c) => p.precios[c.id] != null);
  const maximo = Math.max(...filas.map((c) => p.precios[c.id]), 0);
  const ah = ahorroActivo(p, ids);
  const revisar = aRevisar(p, ids);
  const unidad = p.unidad ? (dic[`unidad.${p.unidad}` as Clave] as string | undefined) ?? p.unidad : null;

  return (
    <ul className="m-0 list-none p-0" aria-label={t(dic, 'lab.barras.etiqueta')}>
      {filas.map((c) => {
        const precio = p.precios[c.id];
        const ppu = p.ppu[c.id];
        const barato = Boolean(ah && ah.soles > 0 && ah.en.includes(c.id) && !revisar);
        return (
          <li key={c.id} className="lab-barra-fila">
            <span className="flex items-center">
              <LogoCadena cadena={c} base={base} />
              {!c.logo && <span className="ml-1.5 text-sm">{c.nombre}</span>}
              {c.logo && <span className="sr-only">{c.nombre}</span>}
            </span>
            <span className="lab-barra-pista" aria-hidden="true">
              <span
                className="lab-barra block"
                data-barato={barato}
                style={{ '--r': maximo ? precio / maximo : 0, '--cad': `var(--cad-${c.id})` } as CSSProperties}
              />
            </span>
            <span className="lab-precio">
              <span className={barato ? 'font-semibold' : ''}>
                {barato && <span className="sr-only">{t(dic, 'producto.masBarato')}: </span>}
                {soles(idioma, precio)}
              </span>
              {ppu != null && unidad && (
                <span className="lab-precio__ppu">
                  {t(dic, 'producto.porUnidad', { monto: soles(idioma, ppu, ppu < 1 ? 3 : 2), unidad })}
                </span>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
