import es from './es.json';
import en from './en.json';

export const IDIOMAS = ['es', 'en'] as const;
export type Idioma = (typeof IDIOMAS)[number];
export type Textos = typeof es;
export type Clave = keyof Textos;

const DICCIONARIOS: Record<Idioma, Textos> = { es, en };
const LOCALE: Record<Idioma, string> = { es: 'es-PE', en: 'en-US' };

export function textos(idioma: Idioma): Textos {
  return DICCIONARIOS[idioma];
}

/** Traduce una clave e interpola {variables}. */
export function t(dic: Textos, clave: Clave, vars: Record<string, string | number> = {}): string {
  return dic[clave].replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`));
}

/** Soles siempre como "S/", con separadores del idioma (el ICU escribe "PEN" en inglés). */
export function soles(idioma: Idioma, monto: number, decimales = 2): string {
  const n = new Intl.NumberFormat(LOCALE[idioma], {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  }).format(monto);
  return `S/ ${n}`;
}

export function porcentaje(idioma: Idioma, pct: number): string {
  return new Intl.NumberFormat(LOCALE[idioma], { maximumFractionDigits: 1 }).format(Math.abs(pct)) + ' %';
}

export function fecha(idioma: Idioma, iso: string): string {
  return new Intl.DateTimeFormat(LOCALE[idioma], { day: 'numeric', month: 'long', year: 'numeric' }).format(
    new Date(iso),
  );
}

/** "hace 3 meses" / "3 months ago". */
export function haceCuanto(idioma: Idioma, iso: string, ahora = Date.now()): string {
  const seg = (new Date(iso).getTime() - ahora) / 1000;
  const rtf = new Intl.RelativeTimeFormat(LOCALE[idioma], { numeric: 'auto' });
  const tramos: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31536000], ['month', 2592000], ['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60],
  ];
  for (const [unidad, s] of tramos) {
    if (Math.abs(seg) >= s) return rtf.format(Math.round(seg / s), unidad);
  }
  return rtf.format(0, 'minute');
}

export function otroIdioma(idioma: Idioma): Idioma {
  return idioma === 'es' ? 'en' : 'es';
}
