// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

// Se publica en ichisieben.dev/radar-precios/ (misma URL que la v1).
export default defineConfig({
  site: 'https://ichisieben.dev',
  base: '/radar-precios/',
  trailingSlash: 'always',
  integrations: [react()],
  // CSS incrustado: sin petición que bloquee el primer pintado (Lighthouse móvil >= 90).
  build: { inlineStylesheets: 'always' },
  i18n: {
    defaultLocale: 'es',
    locales: ['es', 'en'],
    // /radar-precios/es/ y /radar-precios/en/; la raíz redirige según el navegador
    // (src/pages/index.astro), con la elección guardada en localStorage.
    routing: { prefixDefaultLocale: true, redirectToDefaultLocale: false },
  },
  vite: { plugins: [tailwindcss()] },
});
