// Copia el contrato de datos (../web/data, generado por pipeline/export_web.py) a
// public/data para que Astro lo sirva tal cual. public/data no se versiona.
import { cpSync, existsSync, rmSync } from 'node:fs';

const origen = new URL('../../web/data/', import.meta.url);
const destino = new URL('../public/data/', import.meta.url);
if (!existsSync(new URL('meta.json', origen))) {
  console.error('Falta web/data/meta.json: corre antes `py -m pipeline.export_web`.');
  process.exit(1);
}
rmSync(destino, { recursive: true, force: true });
cpSync(origen, destino, { recursive: true });
console.log('web/data -> web-v2/public/data');
