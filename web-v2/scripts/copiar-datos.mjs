// Copia el contrato de datos (../web/data, generado por pipeline/export_web.py) a
// public/data para que Astro lo sirva tal cual. public/data no se versiona.
import { cpSync, existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs';

const origen = new URL('../../web/data/', import.meta.url);
const destino = new URL('../public/data/', import.meta.url);
if (!existsSync(new URL('meta.json', origen))) {
  console.error('Falta web/data/meta.json: corre antes `py -m pipeline.export_web`.');
  process.exit(1);
}
rmSync(destino, { recursive: true, force: true });
cpSync(origen, destino, { recursive: true });
console.log('web/data -> web-v2/public/data');

// Manifiesto de fotos para la isla del inicio (se trae junto con index.json, bajo demanda).
// Solo las entradas cuyas variantes existen en public/img/p/: lo que falte cae a la <img> original.
const manifiesto = new URL('../src/data/imagenes.manifest.json', import.meta.url);
if (existsSync(manifiesto)) {
  const todo = JSON.parse(readFileSync(manifiesto, 'utf-8'));
  const hay = (i) => ['avif', 'webp'].every((fmt) =>
    i.variantes[fmt].every((a) => existsSync(new URL(`../public/img/p/${i.hash}-${a}.${fmt}`, import.meta.url))));
  const util = Object.fromEntries(Object.entries(todo).filter(([, i]) => hay(i)));
  writeFileSync(new URL('imagenes.manifest.json', destino), JSON.stringify(util));
  console.log(`manifiesto de fotos: ${Object.keys(util).length}/${Object.keys(todo).length} con variantes -> public/data`);
}
