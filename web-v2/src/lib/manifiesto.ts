// Solo para código de servidor (.astro en el build): importa el manifiesto entero.
// Los componentes React no deben importar este módulo: reciben la info ya resuelta por props.
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import manifiesto from '../data/imagenes.manifest.json';
import type { InfoImagen, Manifiesto } from './imagenes';

const todo = manifiesto as Manifiesto;

/** Las variantes no se versionan (public/img/p/ está en .gitignore): en un clon sin correr
 *  scripts/imagenes_web.mjs el manifiesto lista archivos que no existen. Entonces, sin info. */
export function infoImagen(url: string | null | undefined): InfoImagen | null {
  const info = url ? todo[url] : null;
  if (!info) return null;
  const primera = join(process.cwd(), 'public', 'img', 'p', `${info.hash}-${info.variantes.webp[0]}.webp`);
  return existsSync(primera) ? info : null;
}
