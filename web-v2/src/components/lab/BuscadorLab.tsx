// Buscador instantáneo: Fuse.js (misma configuración que Explorador.tsx), coincidencias resaltadas
// con <mark> y patrón combobox/listbox (↑ ↓ Enter Esc, aria-activedescendant).
import { Fragment, useId, useMemo, useState, type KeyboardEvent } from 'react';
import Fuse, { type IFuseOptions } from 'fuse.js';
import { t, type Textos } from '../../i18n';
import type { Producto } from '../../lib/datos';

/** Misma configuración que el índice de `Explorador.tsx`. */
export const FUSE_OPCIONES: IFuseOptions<Producto> = {
  keys: [{ name: 'nombre', weight: 3 }, 'activo', 'marca', 'laboratorio'],
  threshold: 0.32,
  ignoreLocation: true,
};

type Rango = readonly [number, number];

/** Parte `texto` en trozos normales y <mark> según los rangos [ini, fin] (inclusivos) de Fuse. */
function Resaltado({ texto, rangos }: { texto: string; rangos: readonly Rango[] }) {
  const orden = [...rangos].sort((a, b) => a[0] - b[0]);
  const trozos: { t: string; marca: boolean }[] = [];
  let pos = 0;
  for (const [ini, fin] of orden) {
    if (ini < pos) continue; // solapado con el anterior
    if (ini > pos) trozos.push({ t: texto.slice(pos, ini), marca: false });
    trozos.push({ t: texto.slice(ini, fin + 1), marca: true });
    pos = fin + 1;
  }
  if (pos < texto.length) trozos.push({ t: texto.slice(pos), marca: false });
  return (
    <>
      {trozos.map((x, i) => (x.marca ? <mark key={i}>{x.t}</mark> : <Fragment key={i}>{x.t}</Fragment>))}
    </>
  );
}

interface Props {
  productos: Producto[];
  q: string;
  onQ: (q: string) => void;
  dic: Textos;
}

export default function BuscadorLab({ productos, q, onQ, dic }: Props) {
  const id = useId();
  const listaId = `${id}-lista`;
  const [abierto, setAbierto] = useState(false);
  const [activo, setActivo] = useState(-1);

  const fuse = useMemo(
    () => new Fuse(productos, { ...FUSE_OPCIONES, includeMatches: true, minMatchCharLength: 2 }),
    [productos],
  );
  const sugerencias = useMemo(() => (q.trim() ? fuse.search(q.trim(), { limit: 6 }) : []), [fuse, q]);
  const visible = abierto && q.trim().length > 0;

  const elegir = (p: Producto) => { onQ(p.nombre); setAbierto(false); setActivo(-1); };
  const mover = (d: 1 | -1) => {
    if (!sugerencias.length) return;
    setAbierto(true);
    setActivo((i) => (i + d + sugerencias.length) % sugerencias.length);
  };

  const teclas = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); mover(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); mover(-1); }
    else if (e.key === 'Enter' && visible && activo >= 0) { e.preventDefault(); elegir(sugerencias[activo].item); }
    else if (e.key === 'Escape') {
      if (visible) { e.preventDefault(); setAbierto(false); setActivo(-1); } // 1.º Esc cierra, 2.º limpia
      else if (q) onQ('');
    }
  };

  return (
    <div className="lab-buscador relative">
      <label htmlFor={`${id}-q`} className="sr-only">{t(dic, 'lab.buscar.etiqueta')}</label>
      <svg className="pointer-events-none absolute left-3.5 top-1/2 size-5 -translate-y-1/2 text-suave" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
      <input
        id={`${id}-q`} type="search" autoComplete="off" value={q}
        role="combobox" aria-expanded={visible} aria-controls={listaId} aria-autocomplete="list"
        aria-activedescendant={visible && activo >= 0 ? `${id}-op-${activo}` : undefined}
        placeholder={t(dic, 'lab.buscar.placeholder')}
        onChange={(e) => { onQ(e.target.value); setAbierto(true); setActivo(-1); }}
        onFocus={() => setAbierto(true)}
        onBlur={() => setTimeout(() => setAbierto(false), 120)}
        onKeyDown={teclas}
        className="h-12 w-full rounded-xl border border-borde bg-superficie pl-11 pr-4 text-base shadow-sm placeholder:text-suave focus:border-acento focus:outline-none focus:ring-2 focus:ring-acento/30"
      />
      <ul id={listaId} role="listbox" aria-label={t(dic, 'buscar.sugerencias')} hidden={!visible}
        className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-borde bg-superficie shadow-lg">
        {visible && sugerencias.length === 0 && (
          <li role="presentation" className="px-4 py-3 text-sm text-suave">{t(dic, 'lab.buscar.sinResultados')}</li>
        )}
        {visible && sugerencias.map((r, i) => {
          const rangos = (r.matches?.find((m) => m.key === 'nombre')?.indices ?? []) as readonly Rango[];
          return (
            <li key={r.item.id} id={`${id}-op-${i}`} role="option" aria-selected={i === activo}
              className="lab-opcion flex cursor-pointer items-center gap-3 px-4 py-2 text-sm"
              onMouseDown={(e) => e.preventDefault()} onMouseEnter={() => setActivo(i)} onClick={() => elegir(r.item)}>
              <span className="truncate"><Resaltado texto={r.item.nombre} rangos={rangos} /></span>
              {r.item.laboratorio && <span className="ml-auto shrink-0 text-xs text-suave">{r.item.laboratorio}</span>}
            </li>
          );
        })}
      </ul>
      <p className="sr-only" aria-live="polite">
        {visible ? t(dic, 'lab.buscar.resultados', { n: sugerencias.length }) : ''}
      </p>
      <p className="mt-1 text-xs text-suave">{t(dic, 'lab.buscar.ayuda')}</p>
    </div>
  );
}
