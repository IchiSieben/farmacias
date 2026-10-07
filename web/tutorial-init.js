// Tutorial de apertura (compartido, upstream en Portfolio/shared/tutorial/).
// Vive en un archivo y no inline para que la CSP pueda ser `script-src 'self'`.
// Rutas relativas para que funcione igual en /radar-precios/ que en la raíz.
import { createTutorial } from './tutorial/tutorial.js';

createTutorial({
  id: 'radar-precios',
  steps: [
    {
      title: 'Radar de Precios',
      body: 'Compara el precio del <b>mismo medicamento</b> entre cadenas de farmacias peruanas. El problema difícil no es mostrar precios: es decidir que dos SKU distintos son el mismo producto.',
    },
    {
      target: '#q',
      title: 'Busca un producto',
      body: 'Por nombre comercial o por <b>principio activo</b>. El buscador cruza ambos, porque las cadenas no nombran igual al mismo fármaco.',
      placement: 'bottom',
    },
    {
      target: '#cadenasSel',
      title: 'Elige las cadenas',
      body: 'Filtra qué cadenas entran en la comparación.',
      placement: 'bottom',
    },
    {
      target: '#brechaRange',
      title: 'La brecha',
      body: 'Cuánta diferencia hay entre el precio más caro y el más barato del mismo producto. Sube el mínimo para ver solo los casos donde <b>de verdad conviene</b> comparar.',
      placement: 'bottom',
    },
    {
      target: '#tabla',
      title: 'El resultado',
      body: 'Una fila por producto, una columna por cadena. Verde es el más barato. El botón <b>⤓ JSON</b> te baja lo que estás viendo.',
      placement: 'top',
    },
  ],
});
