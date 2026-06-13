/* Radar de Precios — buscador estático (vanilla JS, sin backend).
   Carga data.json, filtra en vivo y compara precios de las 3 cadenas. */
"use strict";

const SOLES = (v) =>
  v == null ? "—" : "S/ " + Number(v).toFixed(2);

const titulo = (s) =>
  (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const state = {
  data: null,
  cadenas: [],
  q: "",
  categoria: "",
  solo3: false,
};

// --- carga ----------------------------------------------------------------
fetch("data.json")
  .then((r) => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  })
  .then(init)
  .catch((err) => {
    document.getElementById("meta").textContent =
      "No se pudo cargar data.json (" + err.message +
      "). Si abriste el archivo localmente, sírvelo con un servidor: py -m http.server";
  });

function init(data) {
  state.data = data;
  state.cadenas = data.cadenas; // [{id, nombre}]

  // meta
  const fecha = (data.generado || "").slice(0, 10);
  document.getElementById("meta").textContent =
    `${data.total} productos · ${data.con_boticas} con las 3 cadenas · snapshot ${fecha}`;

  // cabecera de tabla
  const cab = document.getElementById("cabecera");
  cab.innerHTML =
    "<th>Producto</th><th>Categoría</th>" +
    state.cadenas.map((c) => `<th class="precio">${c.nombre}</th>`).join("") +
    '<th class="precio">Brecha</th>';

  // opciones de categoría
  const sel = document.getElementById("categoria");
  (data.categorias || []).forEach((c) => {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = titulo(c);
    sel.appendChild(o);
  });

  // listeners
  const q = document.getElementById("q");
  q.addEventListener("input", () => { state.q = q.value.trim().toLowerCase(); render(); });
  sel.addEventListener("change", () => { state.categoria = sel.value; render(); });
  document.getElementById("solo3").addEventListener("change", (e) => {
    state.solo3 = e.target.checked; render();
  });
  document.getElementById("descargar").addEventListener("click", descargar);

  q.focus();
  render();
}

// --- filtro ---------------------------------------------------------------
function filtrados() {
  const { q, categoria, solo3 } = state;
  return state.data.productos.filter((p) => {
    if (categoria && p.categoria !== categoria) return false;
    if (solo3 && Object.keys(p.precios).length < 3) return false;
    if (q) {
      const txt = (p.nombre + " " + (p.marca || "") + " " + p.categoria).toLowerCase();
      if (!txt.includes(q)) return false;
    }
    return true;
  });
}

// --- render ---------------------------------------------------------------
function render() {
  const items = filtrados();
  const tbody = document.getElementById("filas");
  const vacio = document.getElementById("vacio");

  document.getElementById("count").textContent =
    `${items.length} resultado${items.length === 1 ? "" : "s"}`;

  if (!items.length) {
    tbody.innerHTML = "";
    vacio.hidden = false;
    return;
  }
  vacio.hidden = true;

  const frag = document.createDocumentFragment();
  for (const p of items) frag.appendChild(filaProducto(p));
  tbody.innerHTML = "";
  tbody.appendChild(frag);
}

function filaProducto(p) {
  const tr = document.createElement("tr");

  const marca = p.marca ? `<span class="marca">${esc(p.marca)}</span>` : "";

  let html = `<td class="prod">${esc(p.nombre)}${marca}</td>` +
             `<td><span class="cat">${titulo(p.categoria)}</span></td>`;

  // Cada celda de precio enlaza a la ficha de ESA cadena (si hay precio y URL).
  // Sin equivalente ("—") o sin URL conocida -> no es clickeable.
  // Junto al precio: ▲▼ vs. el snapshot previo + marca de promo (inicia/fin).
  for (const c of state.cadenas) {
    const v = p.precios[c.id];
    const url = p.urls && p.urls[c.id];
    const clases = "precio" + (v == null ? " na" : (p.mas_barato === c.id ? " barato" : ""));
    const precioTxt = (v != null && url)
      ? `<a class="precio-lnk" href="${esc(url)}" target="_blank" rel="noopener" title="Ver en ${esc(c.nombre)}">${SOLES(v)}</a>`
      : SOLES(v);
    html += `<td class="${clases}">${precioTxt}${tendencia(p, c.id)}${promoMarca(p, c.id)}</td>`;
  }

  const b = p.brecha_pct;
  const bClase = !b ? "brecha cero" : "brecha";
  const bTxt = b == null ? "—" : (b === 0 ? "0%" : "+" + b.toFixed(1) + "%");
  html += `<td class="precio"><span class="${bClase}">${bTxt}</span></td>`;

  tr.innerHTML = html;
  return tr;
}

// Flecha ▲ (subió) / ▼ (bajó) vs. el snapshot previo, con el precio anterior y % en el tooltip.
function tendencia(p, cadena) {
  const t = p.tendencia && p.tendencia[cadena];
  if (!t || (t.dir !== "sube" && t.dir !== "baja")) return "";
  const flecha = t.dir === "sube" ? "▲" : "▼";
  const d = t.delta_pct;
  const pct = d == null ? "" : ` · ${d > 0 ? "+" : ""}${d.toFixed(1)}%`;
  const titulo = `Antes ${SOLES(t.antes)}${pct}`;
  return ` <span class="tend tend-${t.dir}" title="${esc(titulo)}">${flecha}</span>`;
}

// Marca de promo cuando inicia/termina una promoción en esa cadena vs. el snapshot previo.
function promoMarca(p, cadena) {
  const pc = p.promo_cambio && p.promo_cambio[cadena];
  if (pc === "inicia") return ` <span class="promo promo-inicia" title="Nueva promoción">promo</span>`;
  if (pc === "fin") return ` <span class="promo promo-fin" title="Terminó la promoción">fin promo</span>`;
  return "";
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// --- descarga del resultado filtrado --------------------------------------
function descargar() {
  const items = filtrados();
  const payload = {
    generado: state.data.generado,
    descargado: new Date().toISOString(),
    filtros: { q: state.q || null, categoria: state.categoria || null, solo_3_cadenas: state.solo3 },
    cadenas: state.cadenas,
    total: items.length,
    productos: items,
  };
  const blob = new Blob([JSON.stringify(payload, null, 1)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "radar-precios-farmacias.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
