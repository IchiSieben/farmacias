import { useState } from 'react';
import { textoSobre, type Cadena } from '../lib/datos';

// Logo oficial descargado por scripts/bajar_logos.py, tal cual. Si no hay archivo o
// falla, monograma (inicial) sobre el color de la cadena. Nunca una imitación.
const ALTO = { sm: 20, md: 24 } as const;

export function LogoCadena({ cadena, base, tam = 'sm' }: { cadena: Cadena; base: string; tam?: keyof typeof ALTO }) {
  const [roto, setRoto] = useState(false);
  const alto = ALTO[tam];
  const ancho = Math.round(alto * Math.min(cadena.logo_ratio ?? 4, 4.5));
  if (!cadena.logo || roto) {
    const fondo = cadena.color ?? '#5a626c';
    return (
      <span aria-hidden="true" style={{ width: alto, height: alto, background: fondo, color: textoSobre(fondo), fontSize: alto * 0.55 }}
        className="grid shrink-0 place-items-center rounded-md font-bold leading-none">
        {cadena.nombre.charAt(0)}
      </span>
    );
  }
  return (
    // Ancho explícito desde la proporción real: el hueco existe antes de que cargue (sin CLS).
    <img src={`${base}logos/${cadena.logo}`} alt="" height={alto} width={ancho} onError={() => setRoto(true)}
      style={{ height: alto, width: ancho }}
      className="shrink-0 rounded-sm object-contain dark:bg-white dark:px-0.5" />
  );
}
