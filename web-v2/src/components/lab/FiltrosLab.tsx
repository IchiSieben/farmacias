// Barra de filtros del laboratorio: categorías con contador animado, cadenas con logo
// (multi-select), brecha mínima y orden. Es controlada: el estado vive en GaleriaLab (y en la URL).
import { t, type Textos, type Clave } from '../../i18n';
import type { Cadena } from '../../lib/datos';
import { LogoCadena } from '../LogoCadena';
import { Contador } from './Movimiento';

export const ORDENES = ['ahorro', 'nombre', 'precio', 'brecha'] as const;
export type Orden = (typeof ORDENES)[number];

interface Props {
  dic: Textos;
  base: string;
  cadenas: Cadena[];
  /** Categorías presentes con su conteo (ya aplicados los demás filtros). `null` = Todas. */
  categorias: { id: string | null; n: number }[];
  cat: string | null;
  onCat: (id: string | null) => void;
  activas: string[];
  onCadena: (id: string) => void;
  brecha: number;
  brechaMax: number;
  onBrecha: (v: number) => void;
  orden: Orden;
  onOrden: (o: Orden) => void;
}

export default function FiltrosLab({
  dic, base, cadenas, categorias, cat, onCat, activas, onCadena, brecha, brechaMax, onBrecha, orden, onOrden,
}: Props) {
  const nombreCat = (id: string) => (dic[`cat.${id}` as Clave] as string | undefined) ?? id;
  return (
    <div className="space-y-3">
      <div role="group" aria-label={t(dic, 'filtros.categorias')} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none]">
        {categorias.map((c) => (
          <button key={c.id ?? 'todas'} type="button" className="lab-chip" aria-pressed={cat === c.id} onClick={() => onCat(c.id)}>
            {c.id ? nombreCat(c.id) : t(dic, 'filtros.todas')}{' '}
            <span className={cat === c.id ? 'opacity-90' : 'text-suave'}><Contador valor={c.n} /></span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <div role="group" aria-label={t(dic, 'filtros.cadenas')} className="flex flex-wrap items-center gap-2">
          {cadenas.map((c) => {
            const on = activas.includes(c.id);
            return (
              <button key={c.id} type="button" className="lab-cadena" aria-pressed={on} onClick={() => onCadena(c.id)}
                title={t(dic, on ? 'filtros.cadena.activa' : 'filtros.cadena.inactiva', { cadena: c.nombre })}>
                <LogoCadena cadena={c} base={base} />
                <span className={c.logo ? 'sr-only' : on ? '' : 'line-through'}>{c.nombre}</span>
              </button>
            );
          })}
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-suave">
            {t(dic, 'lab.brecha', { pct: brecha })}
          </span>
          <input type="range" className="lab-brecha" min={0} max={brechaMax} step={1} value={brecha}
            aria-valuetext={t(dic, 'lab.brecha', { pct: brecha })}
            onChange={(e) => onBrecha(Number(e.target.value))} />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-suave">{t(dic, 'lab.orden')}</span>
          <select value={orden} onChange={(e) => onOrden(e.target.value as Orden)}
            className="rounded-md border border-borde bg-superficie px-2 py-1.5">
            {ORDENES.map((o) => <option key={o} value={o}>{t(dic, `lab.orden.${o}` as Clave)}</option>)}
          </select>
        </label>
      </div>
    </div>
  );
}
