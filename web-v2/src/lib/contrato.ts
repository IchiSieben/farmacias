// Lectura del contrato web/data/ en el build (copiado a public/data/ por
// scripts/copiar-datos.mjs). Ruta desde la raíz de web-v2, no desde el chunk compilado.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export function leerDatos<T = unknown>(archivo: string): T {
  return JSON.parse(readFileSync(join(process.cwd(), 'public', 'data', archivo), 'utf-8')) as T;
}
