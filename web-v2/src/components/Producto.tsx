// Piezas de producto compartidas por el inicio (Explorador) y la ficha.
import { useState } from 'react';
import { t, soles, porcentaje, type Idioma, type Textos, type Clave } from '../i18n';
import { aRevisar, ahorroActivo, preciosActivos, type Cadena, type Producto } from '../lib/datos';

// --- piezas por producto --------------------------------------------------------
export interface PiezaProps {
  p: Producto;
  activas: Cadena[];
  idioma: Idioma;
  dic: Textos;
  base: string;
}

export function Miniatura({ p, dic, tam }: { p: Producto; dic: Textos; tam: number }) {
  const [roto, setRoto] = useState(false);
  const clase = 'shrink-0 rounded-lg border border-borde bg-white object-contain';
  if (!p.imagen || roto) {
    return (
      <div style={{ width: tam, height: tam }} className={`${clase} grid place-items-center bg-superficie-2 text-[10px] text-suave`}>
        {t(dic, 'producto.sinFoto')}
      </div>
    );
  }
  return (
    <img src={p.imagen} alt="" width={tam} height={tam} loading="lazy" decoding="async"
      referrerPolicy="no-referrer" onError={() => setRoto(true)} style={{ width: tam, height: tam }} className={clase} />
  );
}

export function Tendencia({ p, cadena, idioma, dic }: { p: Producto; cadena: string; idioma: Idioma; dic: Textos }) {
  const td = p.tendencia[cadena];
  if (!td || (td.dir !== 'sube' && td.dir !== 'baja') || td.delta_pct == null) return null;
  const sube = td.dir === 'sube';
  const etiqueta = t(dic, sube ? 'tendencia.sube' : 'tendencia.baja', { pct: porcentaje(idioma, td.delta_pct) });
  return (
    <span title={etiqueta} className={`num text-xs ${sube ? 'text-sube' : 'text-baja'}`}>
      <span aria-hidden="true">{sube ? '▲' : '▼'}</span>
      <span className="sr-only">{etiqueta}</span>
    </span>
  );
}

export function ResumenAhorro({ p, activas, idioma, dic, compacto }: Omit<PiezaProps, 'base'> & { compacto?: boolean }) {
  const ah = ahorroActivo(p, activas.map((c) => c.id));
  const nombres = (ids: string[]) => ids.map((id) => activas.find((c) => c.id === id)?.nombre ?? id).join(', ');
  if (!ah) {
    const unica = Object.keys(preciosActivos(p, activas.map((c) => c.id)))[0];
    return <span className="text-xs text-suave">{t(dic, 'producto.unaCadena', { cadena: nombres([unica]) })}</span>;
  }
  if (aRevisar(p, activas.map((c) => c.id))) {
    return (
      <span title={t(dic, 'producto.aRevisar.detalle')}
        className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-borde px-3 py-1 text-xs font-medium text-suave">
        <span aria-hidden="true">⚠</span>{t(dic, 'producto.aRevisar')}
      </span>
    );
  }
  if (ah.soles === 0) return <span className="text-xs text-suave">{t(dic, 'producto.empate', { cadenas: nombres(ah.en) })}</span>;
  const monto = soles(idioma, ah.soles);
  if (compacto) {
    return (
      <span className="inline-flex flex-col items-end">
        <span className="num font-semibold text-ahorro">{monto}</span>
        <span className="text-xs text-suave">{nombres(ah.en)}</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ahorro-fondo px-3 py-1 text-sm font-medium text-ahorro">
      <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true"><path d="M20 6 9 17l-5-5" /></svg>
      <span className="num">{t(dic, 'producto.ahorras', { monto, cadena: nombres(ah.en) })}</span>
    </span>
  );
}

export function Precio({ p, c, idioma, dic, masBarato }: { p: Producto; c: Cadena; idioma: Idioma; dic: Textos; masBarato: boolean }) {
  const precio = p.precios[c.id];
  if (precio == null) {
    return <span className="text-suave" aria-label={t(dic, 'producto.noDisponible')}>—</span>;
  }
  const ppu = p.ppu[c.id];
  const unidad = p.unidad ? (dic[`unidad.${p.unidad}` as Clave] as string | undefined) ?? p.unidad : null;
  return (
    <span className="inline-flex flex-col items-end whitespace-nowrap">
      <span className="flex items-center gap-1">
        <Tendencia p={p} cadena={c.id} idioma={idioma} dic={dic} />
        <a href={p.urls[c.id]} target="_blank" rel="noopener noreferrer" title={t(dic, 'producto.verEn', { cadena: c.nombre })}
          className={`num rounded px-1 hover:underline ${masBarato ? 'font-semibold text-ahorro' : ''}`}>
          {masBarato && <span className="sr-only">{t(dic, 'producto.masBarato')}: </span>}
          {soles(idioma, precio)}
        </a>
      </span>
      <span className="flex items-center gap-1.5 text-xs text-suave">
        {p.promos.includes(c.id) && (
          <span className="rounded bg-superficie-2 px-1 text-[10px] font-medium uppercase tracking-wide">{t(dic, 'producto.promo')}</span>
        )}
        {ppu != null && unidad && (
          <span className="num">{t(dic, 'producto.porUnidad', { monto: soles(idioma, ppu, ppu < 1 ? 3 : 2), unidad })}</span>
        )}
      </span>
    </span>
  );
}

export function enlaceFicha(p: Producto, idioma: Idioma, base: string) {
  return `${base}${idioma}/p/${p.slug}/`;
}
