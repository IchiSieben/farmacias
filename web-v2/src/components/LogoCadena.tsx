import { useState } from 'react';
import { textoSobre, type Cadena } from '../lib/datos';

// Logo oficial descargado por scripts/bajar_logos.py, tal cual. Si no hay archivo o
// falla, monograma (inicial) sobre el color de la cadena. Nunca una imitación.
const ALTO = { sm: 20, md: 24 } as const;

export function LogoCadena({ cadena, base, tam = 'sm' }: { cadena: Cadena; base: string; tam?: keyof typeof ALTO }) {
  const [roto, setRoto] = useState(false);
  const alto = ALTO[tam];
  if (!cadena.logo || roto) {
    const fondo = cadena.color ?? '#5a626c';
    return (
      <span aria-hidden="true" style={{ width: alto, height: alto, background: fondo, color: textoSobre(fondo), fontSize: alto * 0.55 }}
        className="grid shrink-0 place-items-center rounded-md font-bold leading-none">
        {cadena.nombre.charAt(0)}
      </span>
    );
  }
  // Los 4 logos van en la misma píldora (mismo alto y padding) para verse parejos en
  // claro y oscuro: blanca para los transparentes; del color de su propio fondo para un
  // raster opaco (Boticas sirve el logo en blanco sobre azul). Ancho tope 5× el alto: los
  // logos muy apaisados (Inkafarma, Boticas) no invaden la columna vecina.
  const interior = alto - 6;
  const ancho = Math.round(interior * Math.min(cadena.logo_ratio ?? 4, 5));
  return (
    <span style={{ height: alto, background: cadena.logo_fondo ?? '#ffffff' }}
      className="inline-flex shrink-0 items-center rounded-md px-1.5 ring-1 ring-black/10">
      {/* Ancho explícito desde la proporción real: el hueco existe antes de que cargue (sin CLS). */}
      <img src={`${base}logos/${cadena.logo}`} alt="" height={interior} width={ancho} onError={() => setRoto(true)}
        style={{ height: interior, width: ancho }} className="object-contain" />
    </span>
  );
}
