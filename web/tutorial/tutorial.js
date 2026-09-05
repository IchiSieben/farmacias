/**
 * Opening tutorial — shared across every iC7 demo.
 *
 * Vanilla ES module, zero dependencies, framework-agnostic. It only touches the
 * DOM, so the same file works in a static HTML page, a Vite/React app or an
 * Astro island. See README.md for the three wiring patterns.
 *
 * Design rules this encodes:
 *   - Dismissal is remembered per demo, so a returning visitor is never nagged.
 *   - A step whose target is missing is SKIPPED, not rendered pointing at
 *     nothing. Demos change; a stale selector must not break onboarding.
 *   - Escape always exits. Nothing traps the visitor inside the tour.
 *   - Honours prefers-reduced-motion.
 *   - If every step is unreachable, the tour never opens at all.
 */

const NS = 'ic7-tutorial';
const PREFIX = `${NS}:seen:`;

/** localStorage can throw (private mode, blocked cookies). Never let that break the demo. */
function safeGet(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
function safeSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* sin persistencia: el tutorial simplemente se repite */
  }
}
function safeRemove(key) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* idem */
  }
}

export function hasSeen(id) {
  return safeGet(PREFIX + id) === '1';
}
export function markSeen(id) {
  safeSet(PREFIX + id, '1');
}
export function resetSeen(id) {
  safeRemove(PREFIX + id);
}

/**
 * @param {object}   opts
 * @param {string}   opts.id            Clave de persistencia. Única por demo.
 * @param {Array}    opts.steps         [{ target?, title, body, placement? }]
 * @param {boolean} [opts.auto=true]    Abrir solo en la primera visita.
 * @param {string}  [opts.labels]       Textos de los botones (i18n).
 * @returns {{open:Function, close:Function, destroy:Function, seen:Function}}
 */
export function createTutorial(opts) {
  const {
    id,
    steps = [],
    auto = true,
    labels = {
      next: 'Siguiente',
      prev: 'Atrás',
      done: 'Entendido',
      skip: 'Saltar',
      of: 'de',
    },
  } = opts || {};

  if (!id) throw new Error('createTutorial: falta `id`');

  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  let index = 0;
  let root = null;
  let active = false;
  let lastFocus = null;

  const resolve = (s) => (s.target ? document.querySelector(s.target) : null);
  // Un paso con selector que no existe hoy se descarta: mejor un tour corto que
  // un tooltip apuntando al vacio.
  const usable = () => steps.filter((s) => !s.target || resolve(s));

  function build() {
    root = document.createElement('div');
    root.className = `${NS}-root`;
    root.setAttribute('role', 'dialog');
    root.setAttribute('aria-modal', 'true');
    root.setAttribute('aria-label', 'Tutorial de introducción');
    root.innerHTML = `
      <div class="${NS}-backdrop" data-close></div>
      <div class="${NS}-spot" hidden></div>
      <div class="${NS}-card" role="document">
        <p class="${NS}-count"></p>
        <h2 class="${NS}-title"></h2>
        <div class="${NS}-body"></div>
        <div class="${NS}-actions">
          <button type="button" class="${NS}-skip" data-close></button>
          <span class="${NS}-spacer"></span>
          <button type="button" class="${NS}-prev"></button>
          <button type="button" class="${NS}-next"></button>
        </div>
      </div>`;
    if (reduced) root.classList.add(`${NS}-reduced`);
    document.body.appendChild(root);

    root.querySelector(`.${NS}-skip`).textContent = labels.skip;
    root.addEventListener('click', (e) => {
      if (e.target.closest('[data-close]')) close();
    });
    root.querySelector(`.${NS}-prev`).addEventListener('click', () => go(index - 1));
    root.querySelector(`.${NS}-next`).addEventListener('click', () => {
      const list = usable();
      if (index >= list.length - 1) close();
      else go(index + 1);
    });
    document.addEventListener('keydown', onKey, true);
  }

  function onKey(e) {
    if (!active) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'ArrowRight') {
      go(index + 1);
    } else if (e.key === 'ArrowLeft') {
      go(index - 1);
    } else if (e.key === 'Tab') {
      // Foco atrapado dentro de la tarjeta mientras el tour esta abierto.
      const f = root.querySelectorAll('button');
      const first = f[0];
      const last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  /** Coloca la tarjeta junto al objetivo sin salirse del viewport. */
  function place(card, rect, placement) {
    const pad = 14;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const cw = card.offsetWidth;
    const ch = card.offsetHeight;

    if (!rect) {
      card.style.left = `${Math.max(pad, (vw - cw) / 2)}px`;
      card.style.top = `${Math.max(pad, (vh - ch) / 2)}px`;
      return;
    }
    // Elige el lado con más aire si el pedido no entra.
    const room = {
      bottom: vh - rect.bottom,
      top: rect.top,
      right: vw - rect.right,
      left: rect.left,
    };
    let side = placement || 'bottom';
    const needs = side === 'top' || side === 'bottom' ? ch + pad : cw + pad;
    if (room[side] < needs) {
      side = Object.entries(room).sort((a, b) => b[1] - a[1])[0][0];
    }

    let left;
    let top;
    if (side === 'bottom' || side === 'top') {
      left = rect.left + rect.width / 2 - cw / 2;
      top = side === 'bottom' ? rect.bottom + pad : rect.top - ch - pad;
    } else {
      top = rect.top + rect.height / 2 - ch / 2;
      left = side === 'right' ? rect.right + pad : rect.left - cw - pad;
    }
    card.style.left = `${Math.min(Math.max(pad, left), vw - cw - pad)}px`;
    card.style.top = `${Math.min(Math.max(pad, top), vh - ch - pad)}px`;
  }

  function go(i) {
    const list = usable();
    if (!list.length) return close();
    index = Math.max(0, Math.min(i, list.length - 1));
    const step = list[index];
    const el = resolve(step);
    const card = root.querySelector(`.${NS}-card`);
    const spot = root.querySelector(`.${NS}-spot`);

    root.querySelector(`.${NS}-count`).textContent = `${index + 1} ${labels.of} ${list.length}`;
    root.querySelector(`.${NS}-title`).textContent = step.title ?? '';
    // Los pasos son contenido propio del demo, no entrada del visitante.
    root.querySelector(`.${NS}-body`).innerHTML = step.body ?? '';

    const prev = root.querySelector(`.${NS}-prev`);
    const next = root.querySelector(`.${NS}-next`);
    prev.textContent = labels.prev;
    prev.hidden = index === 0;
    next.textContent = index === list.length - 1 ? labels.done : labels.next;

    if (el) {
      el.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
      const r = el.getBoundingClientRect();
      spot.hidden = false;
      spot.style.left = `${r.left - 6}px`;
      spot.style.top = `${r.top - 6}px`;
      spot.style.width = `${r.width + 12}px`;
      spot.style.height = `${r.height + 12}px`;
      place(card, r, step.placement);
    } else {
      spot.hidden = true;
      place(card, null);
    }
    next.focus();
  }

  function open() {
    if (active) return;
    const list = usable();
    // Ningun objetivo presente: no se abre un tour vacio.
    if (!list.length) return;
    lastFocus = document.activeElement;
    if (!root) build();
    active = true;
    root.classList.add(`${NS}-on`);
    document.documentElement.style.overflow = 'hidden';
    go(0);
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
  }

  function reposition() {
    if (active) go(index);
  }

  function close() {
    if (!active) return;
    active = false;
    markSeen(id);
    root.classList.remove(`${NS}-on`);
    document.documentElement.style.overflow = '';
    window.removeEventListener('resize', reposition);
    window.removeEventListener('scroll', reposition, true);
    lastFocus?.focus?.();
  }

  function destroy() {
    close();
    document.removeEventListener('keydown', onKey, true);
    root?.remove();
    root = null;
  }

  if (auto && !hasSeen(id)) {
    // Espera al primer frame: los demos montan sus targets en el load.
    requestAnimationFrame(() => requestAnimationFrame(open));
  }

  return { open, close, destroy, seen: () => hasSeen(id) };
}

export default createTutorial;
