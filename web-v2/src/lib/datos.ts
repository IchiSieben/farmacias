// Contrato web/data/ (F4_UI_BRIEF §4, generado por pipeline/export_web.py).
export const VERSION_ESQUEMA = 1;

export interface Cadena {
  id: string;
  nombre: string;
  grupo: string | null;
  color: string | null;
  logo: string | null;
  logo_ratio?: number | null;
}

export interface Ahorro {
  soles: number;
  pct: number | null;
  en: string[];
}

export interface Producto {
  id: string;
  slug: string;
  nombre: string;
  activo: string | null;
  laboratorio: string | null;
  marca: string | null;
  cat: string | null;
  pres: string | null;
  cantidad: number | null;
  unidad: string | null;
  precios: Record<string, number>;
  ppu: Record<string, number>;
  ahorro: Ahorro | null;
  brecha_pct: number | null;
  imagen: string | null;
  imagenes: Record<string, string>;
  promos: string[];
  tendencia: Record<string, { dir: string | null; delta_pct: number | null }>;
  urls: Record<string, string>;
  nuevo: boolean;
}

export interface Meta {
  version: number;
  generado: string;
  snapshot: string;
  cadenas: Cadena[];
  categorias: { id: string; n: number }[];
  kpis: { productos: number; con_todas: number };
}

export interface Filtros {
  q: string;
  cat: string | null;
  cadenas: string[]; // activas
  soloTodas: boolean;
  ahorroMin: number;
  posCadena: string | null;
  posTipo: 'barata' | 'cara';
  orden: string; // 'ahorro' | 'nombre' | 'precio:<cadena>'
}

export const FILTROS_INICIALES = (cadenas: string[]): Filtros => ({
  q: '',
  cat: null,
  cadenas,
  soloTodas: false,
  ahorroMin: 0,
  posCadena: null,
  posTipo: 'barata',
  orden: 'ahorro',
});

/** Precios solo de las cadenas activas. */
export function preciosActivos(p: Producto, activas: string[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const c of activas) if (p.precios[c] != null) out[c] = p.precios[c];
  return out;
}

/** Ahorro recalculado sobre las cadenas activas (el del JSON asume las cuatro). */
export function ahorroActivo(p: Producto, activas: string[]): Ahorro | null {
  const precios = preciosActivos(p, activas);
  const valores = Object.values(precios);
  if (valores.length < 2) return null;
  const lo = Math.min(...valores);
  const hi = Math.max(...valores);
  return {
    soles: Math.round((hi - lo) * 100) / 100,
    pct: lo ? Math.round((1000 * (hi - lo)) / lo) / 10 : null,
    en: activas.filter((c) => precios[c] === lo),
  };
}

/** Diferencia inusual (>3× entre la más cara y la más barata): casi siempre delata
 *  un cruce entre productos distintos que se coló. Se marca "a revisar" y no
 *  compite en el orden por ahorro (mejor abajo que en el escaparate). */
export const RATIO_REVISAR = 3;

export function aRevisar(p: Producto, activas: string[]): boolean {
  const valores = Object.values(preciosActivos(p, activas));
  if (valores.length < 2) return false;
  const lo = Math.min(...valores);
  return lo > 0 && Math.max(...valores) / lo > RATIO_REVISAR;
}

export function filtrar(productos: Producto[], f: Filtros, idsBusqueda: Set<string> | null): Producto[] {
  return productos.filter((p) => {
    if (idsBusqueda && !idsBusqueda.has(p.id)) return false;
    if (f.cat && p.cat !== f.cat) return false;
    const precios = preciosActivos(p, f.cadenas);
    const n = Object.keys(precios).length;
    if (n === 0) return false;
    if (f.soloTodas && n < f.cadenas.length) return false;
    const ah = ahorroActivo(p, f.cadenas);
    if (f.ahorroMin > 0 && (!ah || ah.soles < f.ahorroMin)) return false;
    if (f.posCadena) {
      if (precios[f.posCadena] == null || n < 2) return false;
      const extremo = f.posTipo === 'barata' ? Math.min(...Object.values(precios)) : Math.max(...Object.values(precios));
      if (precios[f.posCadena] !== extremo) return false;
    }
    return true;
  });
}

export function ordenar(productos: Producto[], orden: string, activas: string[], locale: string): Producto[] {
  const copia = [...productos];
  if (orden === 'nombre') return copia.sort((a, b) => a.nombre.localeCompare(b.nombre, locale));
  if (orden.startsWith('precio:')) {
    const c = orden.slice(7);
    return copia.sort((a, b) => (a.precios[c] ?? Infinity) - (b.precios[c] ?? Infinity));
  }
  return copia.sort(
    (a, b) => Number(aRevisar(a, activas)) - Number(aRevisar(b, activas)) ||
      (ahorroActivo(b, activas)?.soles ?? -1) - (ahorroActivo(a, activas)?.soles ?? -1) ||
      a.nombre.localeCompare(b.nombre, locale),
  );
}

/** CSV del filtro actual (una columna de precio por cadena activa). */
export function aCsv(productos: Producto[], cadenas: Cadena[]): string {
  const esc = (v: unknown) => {
    const s = v == null ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const cab = ['id', 'nombre', 'presentacion', 'categoria', ...cadenas.map((c) => c.id), 'ahorro_soles', 'mas_barato_en'];
  const filas = productos.map((p) => [
    p.id, p.nombre, p.pres, p.cat, ...cadenas.map((c) => p.precios[c.id]),
    p.ahorro?.soles, p.ahorro?.en.join('|'),
  ]);
  return [cab, ...filas].map((f) => f.map(esc).join(',')).join('\n');
}

/** Texto legible (negro o blanco) sobre un color de marca, por contraste WCAG. */
export function textoSobre(hex: string | null): string {
  if (!hex) return '#ffffff';
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return (lum + 0.05) / 0.05 > 1.05 / (lum + 0.05) ? '#111111' : '#ffffff';
}
