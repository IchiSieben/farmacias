// Utilidades de movimiento del laboratorio: preferencias del usuario y contador animado.
import { useEffect, useRef, useState } from 'react';

function useMedia(consulta: string, inicial = false): boolean {
  const [ok, setOk] = useState(inicial);
  useEffect(() => {
    const mq = window.matchMedia(consulta);
    const al = () => setOk(mq.matches);
    al();
    mq.addEventListener('change', al);
    return () => mq.removeEventListener('change', al);
  }, [consulta]);
  return ok;
}

/** `prefers-reduced-motion: reduce`. En SSR se asume reducido: el primer pintado nunca anima. */
export const useReducida = () => useMedia('(prefers-reduced-motion: reduce)', true);

/** Móvil: puntero táctil o ancho < 640 px (carrusel en vez de hover). */
export const useMovil = () => useMedia('(pointer: coarse), (max-width: 639px)');

/** Número que hace tween al cambiar (requestAnimationFrame, sin librerías). Escribe en el DOM
 *  directamente: 60 cuadros no pasan por el render de React. Con `reduce` salta al valor final. */
export function Contador({ valor, duracion = 240 }: { valor: number; duracion?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const mostrado = useRef(valor);
  const reducida = useReducida();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const desde = mostrado.current;
    if (reducida || desde === valor) {
      mostrado.current = valor;
      el.textContent = String(valor);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const paso = (ahora: number) => {
      const k = Math.min(1, (ahora - t0) / duracion);
      const suave = 1 - (1 - k) * (1 - k); // ease-out
      mostrado.current = Math.round(desde + (valor - desde) * suave);
      el.textContent = String(mostrado.current);
      if (k < 1) raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(raf);
  }, [valor, duracion, reducida]);

  return <span ref={ref} className="num">{valor}</span>;
}
