// Variantes de foto de producto (las genera scripts/imagenes_web.mjs). Módulo puro, sin el manifiesto:
// lo comparten Imagen.astro (ficha) y Miniatura (React, inicio) sin meter el JSON en el bundle del cliente.
export interface InfoImagen {
  hash: string;
  w: number;
  h: number;
  variantes: { avif: number[]; webp: number[] };
  /** Color dominante (#rrggbb): fondo mientras carga la foto. */
  placeholder: string;
}

export type Manifiesto = Record<string, InfoImagen>;

export interface AtributosImagen {
  srcAvif: string;
  srcWebp: string;
  /** Respaldo del <img>: la variante WebP de ~240 px (o la mayor que exista). */
  src: string;
  width: number;
  height: number;
  placeholder: string;
}

const lista = (base: string, info: InfoImagen, fmt: 'avif' | 'webp') =>
  info.variantes[fmt].map((a) => `${base}img/p/${info.hash}-${a}.${fmt} ${a}w`).join(', ');

export function atributosImagen(info: InfoImagen, base: string): AtributosImagen {
  const anchos = info.variantes.webp;
  const medio = anchos.find((a) => a >= 240) ?? anchos[anchos.length - 1];
  return {
    srcAvif: lista(base, info, 'avif'),
    srcWebp: lista(base, info, 'webp'),
    src: `${base}img/p/${info.hash}-${medio}.webp`,
    width: info.w,
    height: info.h,
    placeholder: info.placeholder,
  };
}
