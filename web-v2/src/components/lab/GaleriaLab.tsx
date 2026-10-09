// Isla del laboratorio: junta buscador, filtros, tarjetas, skeletons y estado vacío sobre los 12
// productos. El estado vive aquí y en la URL (?cat=&cad=&brecha=&orden=&q=).
import { useEffect, useMemo, useRef, useState } from 'react';
import Fuse from 'fuse.js';
import { t, type Idioma, type Textos, type Clave } from '../../i18n';
import { ahorroActivo, ordenar, preciosActivos, type Cadena, type Producto } from '../../lib/datos';
import BuscadorLab, { FUSE_OPCIONES } from './BuscadorLab';
import FiltrosLab, { ORDENES, type Orden } from './FiltrosLab';
import TarjetaLab, { TarjetaSkeleton } from './TarjetaLab';
import { useMovil, useReducida } from './Movimiento';
import './lab.css';

interface Props {
  idioma: Idioma;
  dic: Textos;
  cadenas: Cadena[];
  productos: Producto[];
  base: string;
}

interface Estado {
  q: string;
  cat: string | null;
  cadenas: string[];
  brecha: number;
  orden: Orden;
}

const LOCALE = { es: 'es-PE', en: 'en-US' } as const;
const ORDEN_INICIAL: Orden = 'ahorro';

// --- estado <-> URL ------------------------------------------------------------------------
function inicial(todas: string[]): Estado {
  return { q: '', cat: null, cadenas: todas, brecha: 0, orden: ORDEN_INICIAL };
}

function leerUrl(todas: string[], brechaMax: number): Estado {
  const e = inicial(todas);
  const u = new URLSearchParams(window.location.search);
  e.q = u.get('q') ?? '';
  e.cat = u.get('cat');
  const cad = u.get('cad')?.split(',') ?? [];
  const validas = todas.filter((c) => cad.includes(c));
  if (validas.length) e.cadenas = validas;
  e.brecha = Math.min(brechaMax, Math.max(0, Math.round(Number(u.get('brecha')) || 0)));
  const o = u.get('orden');
  if ((ORDENES as readonly string[]).includes(o ?? '')) e.orden = o as Orden;
  return e;
}

function escribirUrl(e: Estado, todas: string[]) {
  const u = new URLSearchParams();
  if (e.cat) u.set('cat', e.cat);
  if (e.cadenas.length !== todas.length) u.set('cad', e.cadenas.join(','));
  if (e.brecha) u.set('brecha', String(e.brecha));
  if (e.orden !== ORDEN_INICIAL) u.set('orden', e.orden);
  if (e.q) u.set('q', e.q);
  const qs = u.toString();
  // Se conserva history.state: ClientRouter guarda ahí el índice y el scroll de la entrada.
  history.replaceState(history.state, '', qs ? `?${qs}` : window.location.pathname);
}

const precioMin = (p: Producto, ids: string[]) => Math.min(...Object.values(preciosActivos(p, ids)));

export default function GaleriaLab({ idioma, dic, cadenas, productos, base }: Props) {
  const todas = useMemo(() => cadenas.map((c) => c.id), [cadenas]);
  const brechaMax = useMemo(
    () => Math.ceil(Math.max(0, ...productos.map((p) => ahorroActivo(p, todas)?.pct ?? 0))),
    [productos, todas],
  );
  const [e, setE] = useState<Estado>(() => inicial(todas));
  const [cargando, setCargando] = useState(true);
  const montado = useRef(false);
  const movil = useMovil();
  const reducida = useReducida();

  // Estado desde la URL al montar (un enlace reproduce la vista); skeletons un instante.
  useEffect(() => {
    setE(leerUrl(todas, brechaMax));
    montado.current = true;
    const id = setTimeout(() => setCargando(false), 600);
    return () => clearTimeout(id);
  }, []);
  useEffect(() => { if (montado.current) escribirUrl(e, todas); }, [e]);

  const cambiar = (parcial: Partial<Estado>) => setE((prev) => ({ ...prev, ...parcial }));
  const tx = (clave: Clave, vars?: Record<string, string | number>) => t(dic, clave, vars);

  const fuse = useMemo(() => new Fuse(productos, FUSE_OPCIONES), [productos]);
  const idsBusqueda = useMemo(
    () => (e.q.trim() ? new Set(fuse.search(e.q.trim()).map((r) => r.item.id)) : null),
    [fuse, e.q],
  );
  const activas = useMemo(() => cadenas.filter((c) => e.cadenas.includes(c.id)), [cadenas, e.cadenas]);

  // Todo menos la categoría: de ahí salen los conteos de los chips.
  const sinCategoria = useMemo(
    () => productos.filter((p) =>
      (!idsBusqueda || idsBusqueda.has(p.id)) &&
      Object.keys(preciosActivos(p, e.cadenas)).length > 0 &&
      (ahorroActivo(p, e.cadenas)?.pct ?? 0) >= e.brecha),
    [productos, idsBusqueda, e.cadenas, e.brecha],
  );
  const resultado = useMemo(() => {
    const lista = e.cat ? sinCategoria.filter((p) => p.cat === e.cat) : sinCategoria;
    const loc = LOCALE[idioma];
    if (e.orden === 'precio') return [...lista].sort((a, b) => precioMin(a, e.cadenas) - precioMin(b, e.cadenas));
    if (e.orden === 'brecha') {
      return [...lista].sort((a, b) => (ahorroActivo(b, e.cadenas)?.pct ?? -1) - (ahorroActivo(a, e.cadenas)?.pct ?? -1));
    }
    return ordenar(lista, e.orden === 'nombre' ? 'nombre' : 'ahorro', e.cadenas, loc);
  }, [sinCategoria, e.cat, e.orden, e.cadenas, idioma]);

  const categorias = useMemo(() => {
    const nombre = (id: string) => (dic[`cat.${id}` as Clave] as string | undefined) ?? id;
    const ids = [...new Set(productos.map((p) => p.cat).filter((c): c is string => Boolean(c)))]
      .sort((a, b) => nombre(a).localeCompare(nombre(b), LOCALE[idioma]));
    return [
      { id: null as string | null, n: sinCategoria.length },
      ...ids.map((id) => ({ id, n: sinCategoria.filter((p) => p.cat === id).length })),
    ];
  }, [productos, sinCategoria, dic, idioma]);

  const toggleCadena = (id: string) => {
    const nuevas = e.cadenas.includes(id) ? e.cadenas.filter((c) => c !== id) : todas.filter((c) => c === id || e.cadenas.includes(c));
    if (nuevas.length) cambiar({ cadenas: nuevas }); // siempre queda al menos una
  };
  const hayFiltros = Boolean(e.q || e.cat || e.brecha || e.cadenas.length !== todas.length);
  const limpiar = () => setE((prev) => ({ ...inicial(todas), orden: prev.orden }));

  // Botón de demostración: vuelve a mostrar los skeletons un momento.
  const simularCarga = () => { setCargando(true); setTimeout(() => setCargando(false), reducida ? 900 : 1400); };

  return (
    <div className="space-y-4">
      <BuscadorLab productos={productos} q={e.q} onQ={(q) => cambiar({ q })} dic={dic} />
      <FiltrosLab
        dic={dic} base={base} cadenas={cadenas} categorias={categorias} cat={e.cat} onCat={(cat) => cambiar({ cat })}
        activas={e.cadenas} onCadena={toggleCadena} brecha={e.brecha} brechaMax={brechaMax}
        onBrecha={(brecha) => cambiar({ brecha })} orden={e.orden} onOrden={(orden) => cambiar({ orden })}
      />

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <p className="font-medium" aria-live="polite">
          {cargando ? tx('lab.cargando') : tx('lab.resultados', { n: resultado.length, total: productos.length })}
        </p>
        {hayFiltros && (
          <button type="button" onClick={limpiar} className="text-acento underline underline-offset-2">{tx('filtros.limpiar')}</button>
        )}
        <button type="button" onClick={simularCarga}
          className="ml-auto rounded-md border border-borde px-2 py-1 hover:bg-superficie-2">{tx('lab.skeleton.simular')}</button>
      </div>

      {cargando ? (
        <ul className="grid list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-busy="true">
          {productos.map((p) => <li key={p.id}><TarjetaSkeleton /></li>)}
        </ul>
      ) : resultado.length === 0 ? (
        <div className="rounded-xl border border-dashed border-borde bg-superficie px-6 py-10 text-center" role="status">
          <p className="text-lg font-semibold">{tx('lab.vacio.titulo')}</p>
          <p className="mt-1 text-suave">{tx('lab.vacio.texto')}</p>
          <button type="button" onClick={limpiar}
            className="mt-4 rounded-lg border border-borde bg-acento px-4 py-2 text-sm font-medium text-acento-texto">
            {tx('lab.vacio.limpiar')}
          </button>
        </div>
      ) : (
        <ul className="grid list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {resultado.map((p, i) => (
            <li key={p.id}>
              <TarjetaLab p={p} cadenas={cadenas} activas={activas} idioma={idioma} dic={dic} base={base}
                movil={movil} retraso={Math.min(i, 8) * 20} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
