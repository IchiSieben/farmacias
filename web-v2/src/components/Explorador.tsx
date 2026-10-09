import { useEffect, useMemo, useRef, useState } from 'react';
import Fuse from 'fuse.js';
import { t, soles, type Idioma, type Textos, type Clave } from '../i18n';
import {
  FILTROS_INICIALES, aCsv, aRevisar, ahorroActivo, filtrar, normLab, ordenar,
  type Cadena, type Filtros, type Producto,
} from '../lib/datos';
import type { Manifiesto } from '../lib/imagenes';
import { LogoCadena } from './LogoCadena';
import { Miniatura, Precio, ResumenAhorro, enlaceFicha, type PiezaProps } from './Producto';

interface Props {
  idioma: Idioma;
  dic: Textos;
  cadenas: Cadena[];
  categorias: { id: string; n: number }[];
  iniciales: Producto[];
  /** Variantes de foto de las `iniciales`; el resto del manifiesto llega con el catálogo completo. */
  imagenesIniciales: Manifiesto;
  total: number;
  base: string;
  /** Tooltip de "Nuevo": contra qué corrida es nuevo. */
  nuevoDetalle: string;
}

const PAGINA = 30;
const LOCALE = { es: 'es-PE', en: 'en-US' } as const;

// --- estado <-> URL (?q=&cat=&cad=&orden=) ------------------------------------
function leerUrl(todas: string[]): Filtros {
  const f = FILTROS_INICIALES(todas);
  if (typeof window === 'undefined') return f;
  const u = new URLSearchParams(window.location.search);
  f.q = u.get('q') ?? '';
  f.cat = u.get('cat');
  const cad = u.get('cad');
  if (cad) f.cadenas = todas.filter((c) => cad.split(',').includes(c));
  if (!f.cadenas.length) f.cadenas = todas;
  f.soloTodas = u.get('todas') === '1';
  f.ahorroMin = Number(u.get('min') ?? 0) || 0;
  f.posCadena = u.get('pos');
  f.lab = u.get('lab');
  f.posTipo = u.get('tipo') === 'cara' ? 'cara' : 'barata';
  f.orden = u.get('orden') ?? 'ahorro';
  return f;
}

function escribirUrl(f: Filtros, todas: string[]) {
  const u = new URLSearchParams();
  if (f.q) u.set('q', f.q);
  if (f.cat) u.set('cat', f.cat);
  if (f.cadenas.length !== todas.length) u.set('cad', f.cadenas.join(','));
  if (f.soloTodas) u.set('todas', '1');
  if (f.ahorroMin) u.set('min', String(f.ahorroMin));
  if (f.posCadena) { u.set('pos', f.posCadena); u.set('tipo', f.posTipo); }
  if (f.lab) u.set('lab', f.lab);
  if (f.orden !== 'ahorro') u.set('orden', f.orden);
  const qs = u.toString();
  history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname);
}

function descargar(nombre: string, contenido: string, tipo: string) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement('a'), { href: url, download: nombre });
  a.click();
  URL.revokeObjectURL(url);
}

export default function Explorador({ idioma, dic, cadenas, categorias, iniciales, imagenesIniciales, total, base, nuevoDetalle }: Props) {
  const ids = cadenas.map((c) => c.id);
  const porId = Object.fromEntries(cadenas.map((c) => [c.id, c]));
  const [productos, setProductos] = useState<Producto[]>(iniciales);
  const [imagenes, setImagenes] = useState<Manifiesto>(imagenesIniciales);
  const [completo, setCompleto] = useState(false);
  const [f, setF] = useState<Filtros>(() => FILTROS_INICIALES(ids));
  const [visibles, setVisibles] = useState(PAGINA);
  const [sugerir, setSugerir] = useState(false);
  const montado = useRef(false);

  // Estado desde la URL al montar. El catálogo completo (index.json + manifiesto de fotos) se trae
  // bajo demanda: a la primera interacción (tocar, teclear, desplazar, enfocar), o enseguida si la URL
  // ya trae filtros. Quien solo mira el inicio no descarga ~300 KB que no va a usar.
  useEffect(() => {
    setF(leerUrl(ids));
    montado.current = true;
    const eventos = ['pointerdown', 'keydown', 'touchstart', 'scroll', 'focusin'] as const;
    const quitar = () => eventos.forEach((e) => window.removeEventListener(e, cargar));
    let pedido = false;
    function cargar() {
      if (pedido) return;
      pedido = true;
      quitar();
      Promise.all([
        fetch(`${base}data/index.json`).then((r) => r.json()),
        fetch(`${base}data/imagenes.manifest.json`).then((r) => r.json()).catch(() => ({})),
      ])
        .then(([d, m]) => { setImagenes((prev) => ({ ...prev, ...m })); setProductos(d.productos); setCompleto(true); })
        .catch(() => setCompleto(true));
    }
    eventos.forEach((e) => window.addEventListener(e, cargar, { passive: true }));
    if (window.location.search) {
      if ('requestIdleCallback' in window) requestIdleCallback(cargar, { timeout: 2000 });
      else setTimeout(cargar, 200);
    }
    return quitar;
  }, []);
  useEffect(() => { if (montado.current) escribirUrl(f, ids); }, [f]);
  useEffect(() => setVisibles(PAGINA), [f]);

  const fuse = useMemo(
    () => new Fuse(productos, {
      keys: [{ name: 'nombre', weight: 3 }, 'activo', 'marca', 'laboratorio'],
      threshold: 0.32, ignoreLocation: true,
    }),
    [productos],
  );
  const busqueda = useMemo(
    () => (f.q.trim() ? fuse.search(f.q.trim()).map((r) => r.item) : null),
    [fuse, f.q],
  );
  const resultado = useMemo(() => {
    const filtrados = filtrar(productos, f, busqueda ? new Set(busqueda.map((p) => p.id)) : null);
    return ordenar(filtrados, f.orden, f.cadenas, LOCALE[idioma]);
  }, [productos, f, busqueda, idioma]);
  // Laboratorios presentes en los datos, con su conteo (el filtro solo ofrece lo que existe).
  const laboratorios = useMemo(() => {
    const n = new Map<string, number>();
    for (const p of productos) {
      const l = normLab(p.laboratorio);
      if (l) n.set(l, (n.get(l) ?? 0) + 1);
    }
    return [...n.entries()].sort((a, b) => a[0].localeCompare(b[0], LOCALE[idioma]));
  }, [productos, idioma]);
  const sugerencias = useMemo(() => {
    const vistos = new Set<string>();
    return (busqueda ?? []).filter((p) => !vistos.has(p.nombre) && vistos.add(p.nombre)).slice(0, 6);
  }, [busqueda]);

  const cambiar = (parcial: Partial<Filtros>) => setF((prev) => ({ ...prev, ...parcial }));
  const tx = (clave: Clave, vars?: Record<string, string | number>) => t(dic, clave, vars);
  const nombreCat = (id: string) => (dic[`cat.${id}` as Clave] as string | undefined) ?? id;
  const hayFiltros = f.q || f.cat || f.lab || f.soloTodas || f.ahorroMin || f.posCadena || f.cadenas.length !== ids.length;
  const activas = cadenas.filter((c) => f.cadenas.includes(c.id));
  const pagina = resultado.slice(0, visibles);
  const conteo = completo || hayFiltros ? resultado.length : total;

  const toggleCadena = (id: string) => {
    const nuevas = f.cadenas.includes(id) ? f.cadenas.filter((c) => c !== id) : ids.filter((c) => c === id || f.cadenas.includes(c));
    if (nuevas.length) cambiar({ cadenas: nuevas, posCadena: nuevas.includes(f.posCadena ?? '') ? f.posCadena : null });
  };
  const ordenarPor = (orden: string) => cambiar({ orden });
  const ariaSort = (orden: string) => (f.orden === orden ? (orden === 'nombre' || orden.startsWith('precio:') ? 'ascending' : 'descending') : undefined);

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16">
      {/* Buscador */}
      <div className="relative mt-5">
        <label htmlFor="buscar" className="sr-only">{tx('buscar.etiqueta')}</label>
        <svg className="pointer-events-none absolute left-3.5 top-1/2 size-5 -translate-y-1/2 text-suave" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
        <input
          id="buscar" type="search" autoComplete="off" value={f.q}
          role="combobox" aria-expanded={sugerir && sugerencias.length > 0} aria-controls="sugerencias" aria-autocomplete="list"
          placeholder={tx('buscar.placeholder')}
          onChange={(e) => { cambiar({ q: e.target.value }); setSugerir(true); }}
          onFocus={() => setSugerir(true)}
          onBlur={() => setTimeout(() => setSugerir(false), 150)}
          onKeyDown={(e) => e.key === 'Escape' && setSugerir(false)}
          className="h-13 w-full rounded-xl border border-borde bg-superficie pl-11 pr-4 text-base shadow-sm placeholder:text-suave focus:border-acento focus:outline-none focus:ring-2 focus:ring-acento/30"
        />
        {sugerir && f.q && sugerencias.length > 0 && (
          <ul id="sugerencias" role="listbox" aria-label={tx('buscar.sugerencias')}
            className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-borde bg-superficie shadow-lg">
            {sugerencias.map((p) => (
              <li key={p.id} role="option" aria-selected="false">
                <button type="button" className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm hover:bg-superficie-2"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { cambiar({ q: p.nombre }); setSugerir(false); }}>
                  <span className="truncate">{p.nombre}</span>
                  {p.activo && <span className="ml-auto shrink-0 text-xs text-suave">{p.activo}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Categorías */}
      <div className="mt-4" role="group" aria-label={tx('filtros.categorias')}>
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none]">
          {[{ id: null as string | null, n: total }, ...categorias].map((c) => {
            const on = f.cat === c.id;
            return (
              <button key={c.id ?? 'todas'} type="button" aria-pressed={on} onClick={() => cambiar({ cat: c.id })}
                className={`shrink-0 rounded-full border px-3.5 py-1.5 text-sm transition-colors ${on ? 'border-acento bg-acento text-acento-texto' : 'border-borde bg-superficie hover:bg-superficie-2'}`}>
                {c.id ? nombreCat(c.id) : tx('filtros.todas')} <span className={`num ${on ? 'opacity-90' : 'text-suave'}`}>{c.n}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Cadenas + toggle principal */}
      <div className="mt-3 flex flex-wrap items-center gap-2" role="group" aria-label={tx('filtros.cadenas')}>
        {cadenas.map((c) => {
          const on = f.cadenas.includes(c.id);
          return (
            <button key={c.id} type="button" aria-pressed={on} onClick={() => toggleCadena(c.id)}
              title={tx(on ? 'filtros.cadena.activa' : 'filtros.cadena.inactiva', { cadena: c.nombre })}
              className={`flex items-center gap-2 rounded-lg border py-1 pl-1.5 pr-3 text-sm transition ${on ? 'border-texto/30 bg-superficie' : 'border-dashed border-borde bg-transparent opacity-55'}`}>
              <LogoCadena cadena={c} base={base} tam="sm" />
              <span className={c.logo ? 'sr-only' : on ? '' : 'line-through'}>{c.nombre}</span>
            </button>
          );
        })}
        <label className="flex w-full cursor-pointer items-center gap-2 text-sm sm:ml-auto sm:w-auto">
          <input type="checkbox" checked={f.soloTodas} onChange={(e) => cambiar({ soloTodas: e.target.checked })} className="size-4 accent-[var(--acento)]" />
          {tx('filtros.soloTodas')}
        </label>
      </div>

      {/* Más filtros */}
      <details className="group mt-3 rounded-xl border border-borde bg-superficie" open={Boolean(f.ahorroMin || f.posCadena || f.lab) || undefined}>
        <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 text-sm font-medium">
          <svg className="size-4 transition-transform group-open:rotate-90" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
          {tx('filtros.mas')}
        </summary>
        <div className="flex flex-wrap items-end gap-4 border-t border-borde px-4 py-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-suave">{tx('filtros.ahorroMin')}</span>
            <input type="number" min={0} step={0.5} value={f.ahorroMin || ''} inputMode="decimal"
              onChange={(e) => cambiar({ ahorroMin: Number(e.target.value) || 0 })}
              className="num w-28 rounded-md border border-borde bg-superficie px-2 py-1.5" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-suave">{tx('filtros.laboratorio')}</span>
            <select value={f.lab ?? ''} onChange={(e) => cambiar({ lab: e.target.value || null })}
              className="max-w-64 rounded-md border border-borde bg-superficie px-2 py-1.5">
              <option value="">{tx('filtros.laboratorio.todos')}</option>
              {f.lab && !laboratorios.some(([l]) => l === f.lab) && <option value={f.lab}>{f.lab}</option>}
              {laboratorios.map(([l, n]) => <option key={l} value={l}>{`${l} (${n})`}</option>)}
            </select>
          </label>
          <fieldset className="flex flex-col gap-1">
            <legend className="mb-1 text-suave">{tx('filtros.posicion')}</legend>
            <div className="flex gap-2">
              <select aria-label={tx('filtros.posicion')} value={f.posCadena ?? ''} onChange={(e) => cambiar({ posCadena: e.target.value || null })}
                className="rounded-md border border-borde bg-superficie px-2 py-1.5">
                <option value="">{tx('filtros.posicion.cualquiera')}</option>
                {activas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
              <select aria-label={tx('filtros.posicion')} value={f.posTipo} disabled={!f.posCadena}
                onChange={(e) => cambiar({ posTipo: e.target.value as 'barata' | 'cara' })}
                className="rounded-md border border-borde bg-superficie px-2 py-1.5 disabled:opacity-50">
                <option value="barata">{tx('filtros.posicion.barata')}</option>
                <option value="cara">{tx('filtros.posicion.cara')}</option>
              </select>
            </div>
          </fieldset>
        </div>
      </details>

      {/* Barra de resultados */}
      <div className="mt-5 flex flex-wrap items-center gap-3 text-sm">
        <p className="font-medium" aria-live="polite">
          {/* Hasta tener el catálogo completo: el total real sin filtros (mismo texto que el SSR,
              sin repintado ni salto) y un marcador neutro con filtros. */}
          {!completo && hayFiltros ? tx('resultados.cargando')
            : conteo === 1 ? tx('resultados.conteo.uno') : tx('resultados.conteo', { n: conteo })}
        </p>
        {hayFiltros && (
          <button type="button" onClick={() => setF({ ...FILTROS_INICIALES(ids), orden: f.orden })} className="text-acento underline underline-offset-2">
            {tx('filtros.limpiar')}
          </button>
        )}
        <label className="flex w-full items-center gap-2 md:hidden">
          <span className="text-suave">{tx('resultados.ordenar')}</span>
          <select value={f.orden} onChange={(e) => ordenarPor(e.target.value)} className="rounded-md border border-borde bg-superficie px-2 py-1.5">
            <option value="ahorro">{tx('orden.ahorro')}</option>
            <option value="nombre">{tx('orden.nombre')}</option>
            {activas.map((c) => <option key={c.id} value={`precio:${c.id}`}>{tx('orden.precio', { cadena: c.nombre })}</option>)}
          </select>
        </label>
        <div className="flex items-center gap-2 md:ml-auto">
          <span className="text-suave">{tx('resultados.descargar')}</span>
          <button type="button" className="rounded-md border border-borde px-2 py-1 hover:bg-superficie-2"
            onClick={() => descargar('radar-precios.csv', aCsv(resultado, activas), 'text/csv;charset=utf-8')}>CSV</button>
          <button type="button" className="rounded-md border border-borde px-2 py-1 hover:bg-superficie-2"
            onClick={() => descargar('radar-precios.json', JSON.stringify(resultado, null, 1), 'application/json')}>JSON</button>
        </div>
      </div>

      {resultado.length === 0 ? (
        <div className="mt-8 rounded-xl border border-dashed border-borde bg-superficie px-6 py-10 text-center">
          <p className="text-lg font-semibold">{tx('vacio.titulo')}</p>
          <p className="mt-1 text-suave">{tx('vacio.texto')}</p>
          <p className="mt-4 flex flex-wrap items-center justify-center gap-2 text-sm">
            <span className="text-suave">{tx('vacio.prueba')}</span>
            {tx('vacio.sugeridos').split('|').map((s) => (
              <button key={s} type="button" onClick={() => setF({ ...FILTROS_INICIALES(ids), q: s })}
                className="rounded-full border border-borde px-3 py-1 hover:bg-superficie-2">{s}</button>
            ))}
          </p>
        </div>
      ) : (
        <>
          {/* Móvil: tarjetas */}
          <ul className="mt-3 grid gap-3 md:hidden">
            {pagina.map((p, i) => (
              <li key={p.id}><Tarjeta p={p} activas={activas} idioma={idioma} dic={dic} base={base} imagenes={imagenes} prioritaria={i === 0} nuevoDetalle={nuevoDetalle} /></li>
            ))}
          </ul>

          {/* Escritorio: tabla */}
          <div className="mt-3 hidden overflow-hidden rounded-xl border border-borde bg-superficie md:block">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">{tx('tabla.caption')}</caption>
              <thead className="bg-superficie-2 text-left">
                <tr>
                  <th scope="col" aria-sort={ariaSort('nombre')} className="px-4 py-2.5 font-medium">
                    <button type="button" onClick={() => ordenarPor('nombre')} className="hover:underline">{tx('tabla.producto')}</button>
                  </th>
                  {activas.map((c) => (
                    <th key={c.id} scope="col" aria-sort={ariaSort(`precio:${c.id}`)} className="px-3 py-2.5 text-right font-medium">
                      <button type="button" onClick={() => ordenarPor(`precio:${c.id}`)} className="ml-auto flex items-center justify-end gap-2 hover:underline">
                        <LogoCadena cadena={c} base={base} tam="md" />
                        <span className="sr-only">{c.nombre}</span>
                      </button>
                    </th>
                  ))}
                  <th scope="col" aria-sort={ariaSort('ahorro')} className="px-4 py-2.5 text-right font-medium">
                    <button type="button" onClick={() => ordenarPor('ahorro')} className="hover:underline">{tx('tabla.ahorro')}</button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {pagina.map((p, i) => <Fila key={p.id} p={p} activas={activas} idioma={idioma} dic={dic} base={base} imagenes={imagenes} prioritaria={i === 0} nuevoDetalle={nuevoDetalle} />)}
              </tbody>
            </table>
          </div>

          {resultado.length > visibles && (
            <div className="mt-5 text-center">
              <button type="button" onClick={() => setVisibles((v) => v + PAGINA)}
                className="rounded-lg border border-borde bg-superficie px-5 py-2.5 text-sm font-medium hover:bg-superficie-2">
                {tx('resultados.mostrarMas', { n: Math.min(PAGINA, resultado.length - visibles) })}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Tarjeta({ p, activas, idioma, dic, base, imagenes, prioritaria, nuevoDetalle }: PiezaProps & { nuevoDetalle: string }) {
  const ah = ahorroActivo(p, activas.map((c) => c.id));
  const conPrecio = activas.filter((c) => p.precios[c.id] != null);
  return (
    <article className="rounded-xl border border-borde bg-superficie p-3.5">
      <div className="flex gap-3">
        <Miniatura p={p} dic={dic} tam={64} base={base} info={p.imagen ? imagenes[p.imagen] : null} prioritaria={prioritaria} />
        <div className="min-w-0">
          <h2 className="font-medium leading-snug">
            <a href={enlaceFicha(p, idioma, base)} className="hover:underline">{p.nombre}</a>
            {p.nuevo && <span title={nuevoDetalle} className="ml-2 rounded bg-acento px-1.5 py-0.5 align-middle text-[10px] font-semibold uppercase text-acento-texto">{t(dic, 'producto.nuevo')}</span>}
          </h2>
          <p className="mt-0.5 text-xs text-suave">{[p.pres, p.marca].filter(Boolean).join(' · ')}</p>
        </div>
      </div>
      <ul className="mt-3 divide-y divide-borde">
        {conPrecio.map((c) => {
          const mejor = Boolean(ah && ah.soles > 0 && ah.en.includes(c.id) && !aRevisar(p, activas.map((x) => x.id)));
          return (
            <li key={c.id} className={`flex items-center justify-between gap-3 py-1.5 ${mejor ? '-mx-1.5 rounded-md bg-ahorro-fondo px-1.5' : ''}`}>
              <span className="flex items-center gap-2 text-sm">
                <LogoCadena cadena={c} base={base} tam="sm" />
                <span className={c.logo ? 'sr-only' : ''}>{c.nombre}</span>
                {mejor && <span className="text-xs font-medium text-ahorro">✓ {t(dic, 'producto.masBarato')}</span>}
              </span>
              <Precio p={p} c={c} idioma={idioma} dic={dic} masBarato={mejor} />
            </li>
          );
        })}
      </ul>
      <div className="mt-3"><ResumenAhorro p={p} activas={activas} idioma={idioma} dic={dic} /></div>
    </article>
  );
}

function Fila({ p, activas, idioma, dic, base, imagenes, prioritaria, nuevoDetalle }: PiezaProps & { nuevoDetalle: string }) {
  const ah = ahorroActivo(p, activas.map((c) => c.id));
  return (
    <tr className="border-t border-borde align-middle hover:bg-superficie-2/60">
      <th scope="row" className="px-4 py-2.5 text-left font-normal">
        <div className="flex items-center gap-3">
          <Miniatura p={p} dic={dic} tam={48} base={base} info={p.imagen ? imagenes[p.imagen] : null} prioritaria={prioritaria} />
          <div className="min-w-0">
            <a href={enlaceFicha(p, idioma, base)} className="font-medium hover:underline">{p.nombre}</a>
            {p.nuevo && <span title={nuevoDetalle} className="ml-2 rounded bg-acento px-1.5 py-0.5 text-[10px] font-semibold uppercase text-acento-texto">{t(dic, 'producto.nuevo')}</span>}
            <p className="text-xs text-suave">{[p.pres, p.marca].filter(Boolean).join(' · ')}</p>
          </div>
        </div>
      </th>
      {activas.map((c) => {
        const mejor = Boolean(ah && ah.soles > 0 && ah.en.includes(c.id) && !aRevisar(p, activas.map((x) => x.id)));
        return (
          <td key={c.id} className={`px-3 py-2.5 text-right ${mejor ? 'bg-ahorro-fondo' : ''}`}>
            <Precio p={p} c={c} idioma={idioma} dic={dic} masBarato={mejor} />
          </td>
        );
      })}
      <td className="px-4 py-2.5 text-right"><ResumenAhorro p={p} activas={activas} idioma={idioma} dic={dic} compacto /></td>
    </tr>
  );
}
