// Historial de precios de la ficha: eventos y geometría del gráfico. Todo se calcula
// en el build (la ficha es estática): aquí no hay DOM ni React.

export interface Punto {
  fecha: string; // AAAA-MM-DD, día de Lima (export_web.historial)
  precios: Record<string, number>;
  promos: Record<string, boolean>;
}

export interface Historial {
  version: number;
  generado: string;
  id: string;
  serie: Punto[];
}

const DIA_MS = 86_400_000;
export const HUECO_DIAS = 7; // más separados que esto: tramo punteado, no "precio observado"

export const dias = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / DIA_MS);

// --- eventos ------------------------------------------------------------------------
export type TipoEvento = 'baja' | 'sube' | 'iniciaPromo' | 'finPromo';

export interface Evento {
  tipo: TipoEvento;
  cadena: string;
  desde: string; // última observación anterior de ESA cadena
  hasta: string;
  antes?: number;
  despues?: number;
  pct?: number;
}

/** Cambios entre observaciones consecutivas de cada cadena, del más reciente al más viejo. */
export function eventos(serie: Punto[], cadenas: string[]): Evento[] {
  const out: Evento[] = [];
  for (const c of cadenas) {
    let previo: Punto | null = null;
    for (const p of serie) {
      if (p.precios[c] == null) continue;
      if (previo) {
        const antes = previo.precios[c];
        const despues = p.precios[c];
        const base = { cadena: c, desde: previo.fecha, hasta: p.fecha };
        if (Math.abs(despues - antes) >= 0.005) {
          out.push({ ...base, tipo: despues < antes ? 'baja' : 'sube', antes, despues,
            pct: Math.round((1000 * (despues - antes)) / antes) / 10 });
        }
        if (!previo.promos[c] && p.promos[c]) out.push({ ...base, tipo: 'iniciaPromo' });
        if (previo.promos[c] && !p.promos[c]) out.push({ ...base, tipo: 'finPromo' });
      }
      previo = p;
    }
  }
  return out.sort((a, b) => b.hasta.localeCompare(a.hasta) || cadenas.indexOf(a.cadena) - cadenas.indexOf(b.cadena));
}

// --- rangos ---------------------------------------------------------------------------
export type Rango = 'todo' | '90' | '30';
export const RANGOS: Rango[] = ['todo', '90', '30'];

export function recortar(serie: Punto[], rango: Rango): Punto[] {
  if (rango === 'todo' || !serie.length) return serie;
  const ultimo = serie[serie.length - 1].fecha;
  return serie.filter((p) => dias(p.fecha, ultimo) < Number(rango));
}

// --- geometría --------------------------------------------------------------------------
// Estilo propio por cadena (trazo + marcador): Boticas y Universal tienen azules casi
// iguales; el color solo no alcanza, y en oscuro menos.
export const ESTILO: Record<string, { trazo: string; marcador: 'circulo' | 'cuadrado' | 'triangulo' | 'rombo' }> = {
  inkafarma: { trazo: '', marcador: 'circulo' },
  mifarma: { trazo: '7 4', marcador: 'cuadrado' },
  boticasperu: { trazo: '2 3', marcador: 'triangulo' },
  universal: { trazo: '10 3 2 3', marcador: 'rombo' },
};

export interface Medidas {
  ancho: number;
  alto: number;
  m: { izq: number; der: number; arr: number; aba: number };
  etiquetas: boolean; // etiquetas directas a la derecha (escritorio) o leyenda aparte (móvil)
}
// Escritorio: etiquetas directas al final de cada línea. Móvil: viewBox angosto para que
// el texto no se escale a 5 px; la leyenda va en HTML debajo.
export const ESCRITORIO: Medidas = { ancho: 760, alto: 280, m: { izq: 60, der: 200, arr: 16, aba: 32 }, etiquetas: true };
export const MOVIL: Medidas = { ancho: 360, alto: 230, m: { izq: 58, der: 14, arr: 14, aba: 30 }, etiquetas: false };

export interface Tramo {
  d: string;
  hueco: boolean;
}

export interface Serie {
  cadena: string;
  tramos: Tramo[];
  puntos: { x: number; y: number; promo: boolean; fecha: string; precio: number }[];
  etiquetaY: number; // y de la etiqueta directa, ya separada de las demás
}

export interface Grafico {
  series: Serie[];
  ejeY: { y: number; valor: number }[];
  ejeX: { x: number; fecha: string }[];
  huecos: { x1: number; x2: number }[];
}

function ticks(lo: number, hi: number, n = 4): number[] {
  const paso0 = (hi - lo) / n || 1;
  const mag = 10 ** Math.floor(Math.log10(paso0));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => p >= paso0) ?? paso0;
  const out: number[] = [];
  for (let v = Math.ceil(lo / paso) * paso; v <= hi + 1e-9; v += paso) out.push(Math.round(v * 100) / 100);
  return out;
}

export function geometria(serie: Punto[], cadenas: string[], med: Medidas = ESCRITORIO): Grafico {
  const { ancho: ANCHO, alto: ALTO, m: M } = med;
  const fechas = serie.map((p) => p.fecha);
  const valores = serie.flatMap((p) => cadenas.map((c) => p.precios[c]).filter((v): v is number => v != null));
  let lo = Math.min(...valores);
  let hi = Math.max(...valores);
  const pad = (hi - lo) * 0.12 || hi * 0.1 || 1;
  lo = Math.max(0, lo - pad);
  hi += pad;
  const t0 = Date.parse(fechas[0]);
  const t1 = Date.parse(fechas[fechas.length - 1]);
  const anchoUtil = ANCHO - M.izq - M.der;
  const x = (f: string) => M.izq + (t1 === t0 ? anchoUtil / 2 : ((Date.parse(f) - t0) / (t1 - t0)) * anchoUtil);
  const y = (v: number) => M.arr + (1 - (v - lo) / (hi - lo)) * (ALTO - M.arr - M.aba);

  const series: Serie[] = cadenas
    .map((c) => {
      const pts = serie.filter((p) => p.precios[c] != null)
        .map((p) => ({ x: x(p.fecha), y: y(p.precios[c]), promo: Boolean(p.promos[c]), fecha: p.fecha, precio: p.precios[c] }));
      const tramos: Tramo[] = [];
      for (let i = 1; i < pts.length; i++) {
        const hueco = dias(pts[i - 1].fecha, pts[i].fecha) > HUECO_DIAS;
        // Escalón: el precio se mantiene hasta la captura siguiente (si no hay hueco).
        const d = hueco
          ? `M${pts[i - 1].x},${pts[i - 1].y} L${pts[i].x},${pts[i].y}`
          : `M${pts[i - 1].x},${pts[i - 1].y} H${pts[i].x} V${pts[i].y}`;
        tramos.push({ d, hueco });
      }
      return { cadena: c, tramos, puntos: pts, etiquetaY: pts.length ? pts[pts.length - 1].y : 0 };
    })
    .filter((s) => s.puntos.length);

  // Etiquetas directas sin encimarse (Inkafarma y Mifarma suelen tener el mismo precio).
  const orden = [...series].sort((a, b) => a.etiquetaY - b.etiquetaY);
  for (let i = 1; i < orden.length; i++) {
    orden[i].etiquetaY = Math.max(orden[i].etiquetaY, orden[i - 1].etiquetaY + 15);
  }
  const desborde = orden.length ? orden[orden.length - 1].etiquetaY - (ALTO - M.aba) : 0;
  if (desborde > 0) orden.forEach((s) => (s.etiquetaY -= desborde));

  const huecos: { x1: number; x2: number }[] = [];
  for (let i = 1; i < fechas.length; i++) {
    if (dias(fechas[i - 1], fechas[i]) > HUECO_DIAS) huecos.push({ x1: x(fechas[i - 1]), x2: x(fechas[i]) });
  }

  // Eje X: cada fecha observada, salvo las que quedarían encimadas.
  const ejeX: { x: number; fecha: string }[] = [];
  for (const f of fechas) {
    if (!ejeX.length || x(f) - ejeX[ejeX.length - 1].x > 48) ejeX.push({ x: x(f), fecha: f });
  }
  return { series, ejeY: ticks(lo, hi).map((v) => ({ y: y(v), valor: v })), ejeX, huecos };
}

/** Path de un marcador centrado en (x, y). */
export function marcador(forma: string, x: number, y: number, r = 4.5): string {
  switch (forma) {
    case 'cuadrado':
      return `M${x - r},${y - r}h${2 * r}v${2 * r}h${-2 * r}Z`;
    case 'triangulo':
      return `M${x},${y - r * 1.2}L${x + r * 1.1},${y + r * 0.9}L${x - r * 1.1},${y + r * 0.9}Z`;
    case 'rombo':
      return `M${x},${y - r * 1.3}L${x + r * 1.1},${y}L${x},${y + r * 1.3}L${x - r * 1.1},${y}Z`;
    default:
      return `M${x - r},${y}a${r},${r} 0 1,0 ${2 * r},0a${r},${r} 0 1,0 ${-2 * r},0`;
  }
}
