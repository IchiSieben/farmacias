// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

// Se publica en su subdominio, https://radar.ichisieben.dev/ (decisión del owner, 2026-10-07:
// un subdominio por demo). RADAR_BASE permite construirlo en una subcarpeta para pruebas:
// RADAR_BASE=/radar-precios-beta/ npm run build
export default defineConfig({
  site: 'https://radar.ichisieben.dev',
  base: process.env.RADAR_BASE ?? '/',
  trailingSlash: 'always',
  integrations: [react()],
  // CSS incrustado: sin petición que bloquee el primer pintado (Lighthouse móvil >= 90).
  build: { inlineStylesheets: 'always' },
  i18n: {
    defaultLocale: 'es',
    locales: ['es', 'en'],
    // /es/ y /en/; la raíz redirige según el navegador
    // (src/pages/index.astro), con la elección guardada en localStorage.
    routing: { prefixDefaultLocale: true, redirectToDefaultLocale: false },
  },
  vite: { plugins: [tailwindcss()] },
});
