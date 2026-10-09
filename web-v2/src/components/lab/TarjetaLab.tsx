// Tarjeta de producto del laboratorio: fotos por cadena (crossfade en hover, carrusel en móvil),
// barras a escala y la ficha enlazada con View Transitions (foto y nombre con nombre propio).
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { t, soles, type Idioma, type Textos } from '../../i18n';
import { aRevisar, ahorroActivo, type Cadena, type Producto } from '../../lib/datos';
import { enlaceFicha } from '../Producto';
import BarrasPrecio from './BarrasPrecio';
import { useReducida } from './Movimiento';

export interface PropsTarjeta {
  p: Producto;
  /** Todas las cadenas (para ordenar las fotos); `activas` son las del filtro. */
  cadenas: Cadena[];
  activas: Cadena[];
  idioma: Idioma;
  dic: Textos;
  base: string;
  movil: boolean;
  /** Retraso de entrada (ms) para escalonar la aparición. */
  retraso?: number;
}

interface Foto { url: string; cadena: string }

/** Una foto por URL distinta: Mifarma comparte la de Inkafarma, no se repite. */
function fotosDe(p: Producto, cadenas: Cadena[]): Foto[] {
  const vistos = new Set<string>();
  const out: Foto[] = [];
  for (const c of cadenas) {
    const url = p.imagenes[c.id];
    if (url && !vistos.has(url)) { vistos.add(url); out.push({ url, cadena: c.nombre }); }
  }
  if (!out.length && p.imagen) out.push({ url: p.imagen, cadena: '' });
  return out;
}

/** Dos <img> superpuestos; solo cambia `opacity` (transición en lab.css). La capa de atrás carga
 *  la foto siguiente y recién entonces pasa al frente, para no mostrar un hueco. */
function FotoRotativa({ fotos, activo }: { fotos: Foto[]; activo: boolean }) {
  const reducida = useReducida();
  const [capas, setCapas] = useState<[string, string]>([fotos[0]?.url ?? '', '']);
  const [frente, setFrente] = useState<0 | 1>(0);
  const frenteRef = useRef<0 | 1>(0);
  const idx = useRef(0);

  const ir = (destino: number) => {
    const atras = (1 - frenteRef.current) as 0 | 1;
    const url = fotos[destino].url;
    const pre = new Image();
    pre.referrerPolicy = 'no-referrer';
    pre.onload = () => {
      setCapas((c) => (atras === 0 ? [url, c[1]] : [c[0], url]));
      frenteRef.current = atras;
      idx.current = destino;
      setFrente(atras);
    };
    pre.src = url;
  };

  useEffect(() => {
    if (!activo || reducida || fotos.length < 2) return;
    const avanzar = () => ir((idx.current + 1) % fotos.length);
    const primero = setTimeout(avanzar, 150);
    const ciclo = setInterval(avanzar, 1100);
    return () => {
      clearTimeout(primero);
      clearInterval(ciclo);
      if (idx.current !== 0) ir(0); // al salir, vuelve a la primera foto con el mismo crossfade
    };
  }, [activo, reducida, fotos]);

  if (!fotos.length) return null;
  return (
    <>
      {[0, 1].map((k) => capas[k] && (
        <img key={k} src={capas[k]} alt="" data-frente={frente === k} className="lab-foto-capa"
          loading="lazy" decoding="async" referrerPolicy="no-referrer" />
      ))}
    </>
  );
}

/** Móvil: carrusel con scroll-snap y puntitos. */
function Carrusel({ fotos, dic }: { fotos: Foto[]; dic: Textos }) {
  const ref = useRef<HTMLDivElement>(null);
  const reducida = useReducida();
  const [i, setI] = useState(0);
  const ir = (n: number) =>
    ref.current?.scrollTo({ left: n * ref.current.clientWidth, behavior: reducida ? 'auto' : 'smooth' });
  return (
    <>
      <div ref={ref} className="lab-carrusel" tabIndex={0} role="group" aria-label={t(dic, 'lab.foto.grupo')}
        onScroll={(e) => setI(Math.round(e.currentTarget.scrollLeft / e.currentTarget.clientWidth))}>
        {fotos.map((f) => (
          <img key={f.url} src={f.url} alt={f.cadena ? t(dic, 'lab.foto.de', { cadena: f.cadena }) : ''}
            loading="lazy" decoding="async" referrerPolicy="no-referrer" />
        ))}
      </div>
      {fotos.length > 1 && (
        <div className="lab-puntos">
          {fotos.map((f, n) => (
            <button key={f.url} type="button" className="lab-punto" aria-current={n === i}
              aria-label={t(dic, 'lab.foto.ir', { n: n + 1, total: fotos.length })} onClick={() => ir(n)} />
          ))}
        </div>
      )}
    </>
  );
}

export default function TarjetaLab({ p, cadenas, activas, idioma, dic, base, movil, retraso = 0 }: PropsTarjeta) {
  const [hover, setHover] = useState(false);
  const fotos = useMemo(() => fotosDe(p, cadenas), [p, cadenas]);
  const ids = activas.map((c) => c.id);
  const ah = ahorroActivo(p, ids);
  const revisar = aRevisar(p, ids);
  const nombres = (en: string[]) => en.map((id) => activas.find((c) => c.id === id)?.nombre ?? id).join(', ');
  const hayAhorro = Boolean(ah && ah.soles > 0 && !revisar);
  const conPromo = activas.some((c) => p.promos.includes(c.id) && p.precios[c.id] != null);
  const detalle = [p.pres, p.laboratorio].filter(Boolean).join(' · ');

  return (
    <article className="lab-card" style={{ animationDelay: `${retraso}ms` } as CSSProperties}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)} onBlur={() => setHover(false)}>
      <div className="lab-card__foto" style={{ viewTransitionName: `foto-${p.slug}` }}>
        {movil ? <Carrusel fotos={fotos} dic={dic} /> : <FotoRotativa fotos={fotos} activo={hover} />}
        {!fotos.length && (
          <span className="absolute inset-0 grid place-items-center text-xs text-suave">{t(dic, 'producto.sinFoto')}</span>
        )}
        {(conPromo || hayAhorro) && (
          <div className="lab-card__insignias">
            {conPromo && <span className="lab-badge lab-badge--promo">{t(dic, 'producto.promo')}</span>}
            {hayAhorro && ah && <span className="lab-badge lab-badge--barato">{t(dic, 'producto.masBarato')}</span>}
          </div>
        )}
      </div>
      <div className="lab-card__body">
        <h3 className="lab-card__nombre line-clamp-2" style={{ viewTransitionName: `nombre-${p.slug}` }}>
          <a href={enlaceFicha(p, idioma, base)} className="hover:underline">{p.nombre}</a>
        </h3>
        <p className="lab-card__meta truncate" title={detalle}>{detalle}</p>
        <div className="lab-card__barras">
          <BarrasPrecio p={p} activas={activas} idioma={idioma} dic={dic} base={base} />
        </div>
        <p className="lab-card__pie text-xs text-suave">
          {hayAhorro && ah
            ? t(dic, 'producto.ahorras', { monto: soles(idioma, ah.soles), cadena: nombres(ah.en) })
            : ''}
        </p>
      </div>
    </article>
  );
}

/** Misma geometría que la tarjeta (mismas clases de bloque); el shimmer es un pseudo-elemento
 *  que se desplaza con `transform` (ver lab.css). */
export function TarjetaSkeleton() {
  return (
    <div className="lab-card" aria-hidden="true">
      <div className="lab-card__foto"><div className="lab-sk lab-sk--foto" /></div>
      <div className="lab-card__body">
        <div className="lab-card__nombre"><div className="lab-sk h-4 w-11/12" /><div className="lab-sk mt-1.5 h-4 w-2/3" /></div>
        <div className="lab-card__meta"><div className="lab-sk h-3 w-1/2" /></div>
        <div className="lab-card__barras">
          {[0, 1, 2, 3].map((k) => <div key={k} className="lab-barra-fila"><div className="lab-sk h-5 w-20" /><div className="lab-sk h-2.5 w-full" /><div className="lab-sk h-4 w-14" /></div>)}
        </div>
        <div className="lab-card__pie"><div className="lab-sk h-3 w-3/4" /></div>
      </div>
    </div>
  );
}
