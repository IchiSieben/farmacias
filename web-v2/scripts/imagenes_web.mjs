// Fotos de producto -> variantes AVIF/WebP (96, 240, 480 px) + manifiesto para <Imagen>.
//
//   node scripts/imagenes_web.mjs            (desde web-v2/; requiere `npm i -D sharp`)
//   node scripts/imagenes_web.mjs --limite=5 (prueba con las primeras 5 URLs)
//
// Lee las URLs `imagen` de ../web/data/index.json, descarga cada una UNA vez (caché en disco
// fuera del repo: $IMAGENES_CACHE o ~/.cache/radar-precios/imagenes/, nunca se borra) y escribe
//   public/img/p/<hash>-<ancho>.<avif|webp>     y     src/data/imagenes.manifest.json
// Idempotente: lo que ya está en el manifiesto con todos sus archivos no se descarga ni se recodifica.
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ANCHOS = [96, 240, 480];
const FORMATOS = ['avif', 'webp'];
const CONCURRENCIA = 2; // en total, no por dominio
const PAUSA_MIN_MS = 500; // pausa aleatoria entre peticiones al MISMO host: 0,5-1 s
const PAUSA_MAX_MS = 1000;
const ESPERA_REINTENTO_MS = 30_000; // única repetición, solo en 429/503
const USER_AGENT = 'RadarPreciosBot/1.0 (+https://radar.ichisieben.dev; imagenes de catalogo publico; yoichi.palacios@gmail.com)';

const aqui = (ruta) => fileURLToPath(new URL(ruta, import.meta.url));
const ORIGEN = [aqui('../../web/data/index.json'), aqui('../public/data/index.json')].find(existsSync);
const SALIDA = aqui('../public/img/p/');
const MANIFIESTO = aqui('../src/data/imagenes.manifest.json');
const CACHE = process.env.IMAGENES_CACHE ?? join(homedir(), '.cache', 'radar-precios', 'imagenes');

const limite = Number((process.argv.find((a) => a.startsWith('--limite=')) ?? '').slice(9)) || Infinity;

const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
const hashDe = (url) => createHash('sha1').update(url).digest('hex').slice(0, 16);
const nombreVariante = (hash, ancho, fmt) => `${hash}-${ancho}.${fmt}`;

// --- anchos que corresponden a una fuente (sin agrandar) ------------------------
function anchosPara(anchoFuente) {
  const ok = ANCHOS.filter((a) => a <= anchoFuente);
  return ok.length ? ok : [anchoFuente]; // fuente más chica que 96: una sola variante, a su tamaño
}

function completo(entrada) {
  return Boolean(entrada) && FORMATOS.every((fmt) =>
    (entrada.variantes?.[fmt] ?? []).length > 0 &&
    entrada.variantes[fmt].every((a) => existsSync(join(SALIDA, nombreVariante(entrada.hash, a, fmt)))));
}

// --- descarga con cortesía: concurrencia 2 + pausa por host ---------------------
// Cada host tiene una cola: la salida de cada petición espera a la anterior y a su propia pausa.
const colaPorHost = new Map();
function turnoDeHost(host) {
  const previo = colaPorHost.get(host) ?? Promise.resolve();
  const mio = previo.then(() => dormir(PAUSA_MIN_MS + Math.random() * (PAUSA_MAX_MS - PAUSA_MIN_MS)));
  colaPorHost.set(host, mio);
  return mio;
}

async function pedir(url) {
  await turnoDeHost(new URL(url).host);
  return fetch(url, {
    headers: { 'User-Agent': USER_AGENT, Accept: 'image/avif,image/webp,image/*;q=0.8' },
    signal: AbortSignal.timeout(30_000),
  });
}

async function obtener(url, hash) {
  const enCache = join(CACHE, hash);
  if (existsSync(enCache)) return readFileSync(enCache);
  let r = await pedir(url);
  if (r.status === 429 || r.status === 503) {
    console.warn(`  ${r.status} en ${url}: reintento único en 30 s`);
    await dormir(ESPERA_REINTENTO_MS);
    r = await pedir(url);
  }
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  if (!(r.headers.get('content-type') ?? '').startsWith('image/')) throw new Error(`no es imagen (${r.headers.get('content-type')})`);
  const buf = Buffer.from(await r.arrayBuffer());
  mkdirSync(CACHE, { recursive: true });
  writeFileSync(enCache, buf);
  return buf;
}

// --- main ----------------------------------------------------------------------
if (!ORIGEN) {
  console.error('Falta web/data/index.json: corre antes `py -m pipeline.export_web`.');
  process.exit(1);
}
let sharp;
try {
  sharp = (await import('sharp')).default;
} catch {
  console.error('Falta `sharp`. Instálalo con:  npm i -D sharp  (desde web-v2/) y vuelve a correr este script.');
  process.exit(1);
}

const { productos } = JSON.parse(readFileSync(ORIGEN, 'utf-8'));
const urls = [...new Set(productos.map((p) => p.imagen).filter(Boolean))].slice(0, limite);
const manifiesto = existsSync(MANIFIESTO) ? JSON.parse(readFileSync(MANIFIESTO, 'utf-8')) : {};
mkdirSync(SALIDA, { recursive: true });

async function procesar(url) {
  const hash = hashDe(url);
  if (completo(manifiesto[url])) return 'omitida';
  const buf = await obtener(url, hash);
  const meta = await sharp(buf).metadata();
  const girada = (meta.orientation ?? 1) >= 5; // EXIF 5-8 intercambia ancho y alto
  const [w, h] = girada ? [meta.height, meta.width] : [meta.width, meta.height];
  const anchos = anchosPara(w);
  for (const fmt of FORMATOS) {
    for (const a of anchos) {
      const destino = join(SALIDA, nombreVariante(hash, a, fmt));
      if (existsSync(destino)) continue;
      const img = sharp(buf).rotate().resize({ width: a, withoutEnlargement: true });
      await (fmt === 'avif' ? img.avif({ quality: 50, effort: 4 }) : img.webp({ quality: 78 })).toFile(destino);
    }
  }
  const [r, g, b] = await sharp(buf).rotate().flatten({ background: '#ffffff' })
    .resize(1, 1, { fit: 'cover' }).removeAlpha().raw().toBuffer();
  manifiesto[url] = {
    hash, w, h,
    variantes: { avif: anchos, webp: anchos },
    placeholder: `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`,
  };
  return 'nueva';
}

const cuenta = { nueva: 0, omitida: 0, fallida: 0 };
const pendientes = [...urls];
const trabajador = async () => {
  for (let url; (url = pendientes.shift()); ) {
    try {
      cuenta[await procesar(url)]++;
    } catch (e) {
      cuenta.fallida++;
      console.warn(`  FALLO ${url}: ${e.message}`);
    }
  }
};

try {
  await Promise.all(Array.from({ length: CONCURRENCIA }, trabajador));
} finally {
  // Escritura atómica y con claves ordenadas: el diff del manifiesto solo muestra lo que cambió.
  const ordenado = Object.fromEntries(Object.entries(manifiesto).sort(([a], [b]) => a.localeCompare(b)));
  mkdirSync(join(MANIFIESTO, '..'), { recursive: true });
  writeFileSync(`${MANIFIESTO}.tmp`, JSON.stringify(ordenado, null, 1) + '\n');
  renameSync(`${MANIFIESTO}.tmp`, MANIFIESTO);
}
console.log(`${urls.length} URLs únicas: ${cuenta.nueva} procesadas, ${cuenta.omitida} ya estaban, ${cuenta.fallida} con fallo.`);
console.log(`caché: ${CACHE}\nmanifiesto: ${MANIFIESTO}`);
