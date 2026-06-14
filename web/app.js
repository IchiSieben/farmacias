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
  soloN: false,          // solo productos con precio en TODAS las cadenas activas
  brechaMin: 0,          // % mínimo de brecha
  posCadena: "",         // #3: cadena objetivo
  posRol: "",            // #3: "cara" | "barata" | ""
  activas: null,         // Set de ids de cadenas a comparar (#4)
  sortKey: "brecha",     // "nombre" | "brecha" | <id de cadena>
  sortDir: "desc",       // "asc" | "desc"
};

// Columnas visibles (cadenas activas), en el orden agrupado.
function colsVis() {
  return state.cols.filter((c) => state.activas.has(c.id));
}

// Métricas en vivo sobre las cadenas ACTIVAS: barata/cara/brecha consistentes con
// la selección (#4). Con todas activas reproduce los valores del backend.
function metricas(p) {
  const precios = {};
  for (const c of state.cols) {
    if (state.activas.has(c.id) && p.precios[c.id] != null) precios[c.id] = p.precios[c.id];
  }
  const ids = Object.keys(precios);
  if (ids.length < 2) {
    return { precios, n: ids.length, mas_barato: null, mas_caro: null, brecha: null };
  }
  const vals = ids.map((i) => precios[i]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const baratos = ids.filter((i) => precios[i] === lo);
  const caros = ids.filter((i) => precios[i] === hi);
  return {
    precios, n: ids.length,
    mas_barato: baratos.length === 1 ? baratos[0] : "empate",
    mas_caro: caros.length === 1 ? caros[0] : "empate",
    brecha: lo ? Math.round(1000 * (hi - lo) / lo) / 10 : null,
  };
}

// --- carga ----------------------------------------------------------------
// ?demo=1 carga web/data.demo.json (cambios simulados para mostrar ▲▼/badges).
const params = new URLSearchParams(location.search);
const DATA_FILE = params.has("demo") ? "data.demo.json" : "data.json";

fetch(DATA_FILE)
  .then((r) => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  })
  .then(init)
  .catch((err) => {
    document.getElementById("meta").textContent =
      "No se pudo cargar " + DATA_FILE + " (" + err.message +
      "). Si abriste el archivo localmente, sírvelo con un servidor: py -m http.server";
  });

function init(data) {
  state.data = data;
  state.cadenas = data.cadenas; // [{id, nombre, grupo}]

  // Conglomerados (cadena -> grupo). El ORDEN de columnas se deriva de los grupos
  // para que las cadenas del mismo grupo queden adyacentes. Color por índice de
  // grupo (automático: un grupo nuevo recibe color solo).
  const byId = Object.fromEntries(state.cadenas.map((c) => [c.id, c]));
  state.grupos = (data.grupos && data.grupos.length)
    ? data.grupos
    : [{ id: "_", nombre: "", cadenas: state.cadenas.map((c) => c.id) }];
  state.grupoColor = {};
  state.grupos.forEach((g, i) => { state.grupoColor[g.id] = i; });

  // Orden de columnas + metadatos por columna (grupo, color, si abre grupo).
  state.cols = [];
  for (const g of state.grupos) {
    const ids = g.cadenas.filter((id) => byId[id]);
    ids.forEach((id, j) => {
      state.cols.push({ ...byId[id], gi: state.grupoColor[g.id], inicio: j === 0 });
    });
  }
  // Cadenas sin grupo declarado (defensivo): se añaden al final.
  for (const c of state.cadenas) {
    if (!state.cols.some((x) => x.id === c.id)) {
      state.cols.push({ ...c, gi: 0, inicio: true });
    }
  }

  // Todas las cadenas activas por defecto (#4).
  state.activas = new Set(state.cols.map((c) => c.id));

  // Banner de demo (cuando el JSON está marcado como tal).
  const banner = document.getElementById("demo-banner");
  if (banner && data.demo) banner.hidden = false;

  // meta
  const fecha = (data.generado || "").slice(0, 10);
  document.getElementById("meta").textContent =
    `${data.total} productos · ${data.con_boticas} con las 3 cadenas · snapshot ${fecha}`;

  renderCabecera();
  renderLeyendaGrupos(byId);

  // opciones de categoría
  const sel = document.getElementById("categoria");
  (data.categorias || []).forEach((c) => {
    const o = document.createElement("option");
    o.value = c; o.textContent = titulo(c);
    sel.appendChild(o);
  });

  // #3: opciones de cadena para "quién es más barato/caro"
  const posSel = document.getElementById("posCadena");
  for (const c of state.cols) {
    const o = document.createElement("option");
    o.value = c.id; o.textContent = c.nombre;
    posSel.appendChild(o);
  }

  // #4: checkboxes de cadenas a comparar (data-driven)
  const cadCont = document.getElementById("cadenasSel");
  cadCont.innerHTML = state.cols.map((c) =>
    `<label class="cad-chk"><input type="checkbox" data-cad="${c.id}" checked> ${esc(c.nombre)}</label>`
  ).join("");

  // listeners
  const q = document.getElementById("q");
  q.addEventListener("input", () => { state.q = q.value.trim().toLowerCase(); render(); });
  sel.addEventListener("change", () => { state.categoria = sel.value; render(); });
  document.getElementById("soloN").addEventListener("change", (e) => {
    state.soloN = e.target.checked; render();
  });

  // #1 brecha: slider + número sincronizados
  const rng = document.getElementById("brechaRange");
  const num = document.getElementById("brechaNum");
  const setBrecha = (v) => {
    v = Math.max(0, Math.min(100, Number(v) || 0));
    state.brechaMin = v; rng.value = v; num.value = v; render();
  };
  rng.addEventListener("input", () => setBrecha(rng.value));
  num.addEventListener("input", () => setBrecha(num.value));

  // #3 posición de precio
  posSel.addEventListener("change", () => { state.posCadena = posSel.value; render(); });
  document.getElementById("posRol").addEventListener("change", (e) => {
    state.posRol = e.target.value; render();
  });

  // #4 cadenas activas
  cadCont.addEventListener("change", (e) => {
    const id = e.target.getAttribute("data-cad");
    if (!id) return;
    if (e.target.checked) state.activas.add(id); else state.activas.delete(id);
    if (state.activas.size === 0) { state.activas.add(id); e.target.checked = true; return; }
    renderCabecera(); render();
  });

  // #2 ordenar por click en encabezados
  document.getElementById("cabecera").addEventListener("click", (e) => {
    const th = e.target.closest("th[data-sort]");
    if (!th) return;
    const key = th.getAttribute("data-sort");
    if (state.sortKey === key) { state.sortDir = state.sortDir === "asc" ? "desc" : "asc"; }
    else { state.sortKey = key; state.sortDir = key === "nombre" ? "asc" : "desc"; }
    renderCabecera(); render();
  });

  document.getElementById("descargar").addEventListener("click", descargar);
  document.getElementById("limpiar").addEventListener("click", limpiarFiltros);

  q.focus();
  render();
}

function limpiarFiltros() {
  state.q = ""; state.categoria = ""; state.soloN = false;
  state.brechaMin = 0; state.posCadena = ""; state.posRol = "";
  state.activas = new Set(state.cols.map((c) => c.id));
  document.getElementById("q").value = "";
  document.getElementById("categoria").value = "";
  document.getElementById("soloN").checked = false;
  document.getElementById("brechaRange").value = 0;
  document.getElementById("brechaNum").value = 0;
  document.getElementById("posCadena").value = "";
  document.getElementById("posRol").value = "";
  document.querySelectorAll("#cadenasSel input[data-cad]").forEach((c) => { c.checked = true; });
  renderCabecera(); render();
}

function hayFiltros() {
  return !!(state.q || state.categoria || state.soloN || state.brechaMin > 0 ||
            (state.posCadena && state.posRol) || state.activas.size !== state.cols.length);
}

// --- filtro ---------------------------------------------------------------
// Devuelve [{p, m}] aplicando todos los filtros sobre las métricas en vivo.
function filtrados() {
  const { q, categoria, soloN, brechaMin, posCadena, posRol } = state;
  const nActivas = state.activas.size;
  const out = [];
  for (const p of state.data.productos) {
    if (categoria && p.categoria !== categoria) continue;
    if (q) {
      const txt = (p.nombre + " " + (p.marca || "") + " " + p.categoria).toLowerCase();
      if (!txt.includes(q)) continue;
    }
    const m = metricas(p);
    if (soloN && m.n < nActivas) continue;
    if (brechaMin > 0 && !(m.brecha != null && m.brecha >= brechaMin)) continue;
    if (posCadena && posRol && state.activas.has(posCadena)) {
      const objetivo = posRol === "cara" ? m.mas_caro : m.mas_barato;
      if (objetivo !== posCadena) continue;   // "empate" o null no cuentan
    }
    out.push({ p, m });
  }
  return out;
}

// --- orden ----------------------------------------------------------------
function ordenar(items) {
  const dir = state.sortDir === "asc" ? 1 : -1;
  const key = state.sortKey;
  const val = ({ p, m }) => {
    if (key === "nombre") return p.nombre.toLowerCase();
    if (key === "brecha") return m.brecha;
    return m.precios[key];   // precio de una cadena
  };
  items.sort((a, b) => {
    const va = val(a), vb = val(b);
    const na = va == null || va === "", nb = vb == null || vb === "";
    if (na && nb) return 0;
    if (na) return 1;        // nulos siempre al final
    if (nb) return -1;
    if (typeof va === "string") return va.localeCompare(vb) * dir;
    return (va - vb) * dir;
  });
  return items;
}

// --- render ---------------------------------------------------------------
function render() {
  const items = ordenar(filtrados());
  const tbody = document.getElementById("filas");
  const vacio = document.getElementById("vacio");

  document.getElementById("count").textContent =
    `${items.length} resultado${items.length === 1 ? "" : "s"}`;
  document.getElementById("limpiar").hidden = !hayFiltros();

  if (!items.length) {
    tbody.innerHTML = "";
    vacio.hidden = false;
    return;
  }
  vacio.hidden = true;

  const frag = document.createDocumentFragment();
  for (const { p, m } of items) frag.appendChild(filaProducto(p, m));
  tbody.innerHTML = "";
  tbody.appendChild(frag);
}

// Indicador de orden (▲▼) para una columna ordenable.
function flechaOrden(key) {
  if (state.sortKey !== key) return '<span class="ord">↕</span>';
  return `<span class="ord act">${state.sortDir === "asc" ? "▲" : "▼"}</span>`;
}

// Cabecera de 2 filas: grupos (colspan + banda) sobre las cadenas. Encabezados
// clicables (data-sort) para ordenar por Producto, precio de cada cadena, o Brecha.
function renderCabecera() {
  let top = `<tr><th rowspan="2" class="sortable" data-sort="nombre">Producto ${flechaOrden("nombre")}</th>` +
            '<th rowspan="2">Categoría</th>';
  let bot = "<tr>";
  for (const g of state.grupos) {
    const ids = g.cadenas.filter((id) => state.activas.has(id));
    if (!ids.length) continue;
    const gi = state.grupoColor[g.id];
    top += `<th class="grupo g-${gi}" colspan="${ids.length}">${esc(g.nombre)}</th>`;
    ids.forEach((id, j) => {
      const c = state.cols.find((x) => x.id === id);
      bot += `<th class="precio sortable g-${gi}${j === 0 ? " grupo-inicio" : ""}" data-sort="${id}">` +
             `${esc(c.nombre)} ${flechaOrden(id)}</th>`;
    });
  }
  top += `<th rowspan="2" class="precio sortable" data-sort="brecha">Brecha ${flechaOrden("brecha")}</th></tr>`;
  bot += "</tr>";
  document.getElementById("cabecera").innerHTML = top + bot;
}

// Leyenda de conglomerados (chips de color arriba de la tabla).
function renderLeyendaGrupos(byId) {
  const cont = document.getElementById("grupos-leyenda");
  if (!cont || state.grupos.length < 2) return;
  cont.innerHTML = state.grupos.map((g, i) => {
    const nombres = g.cadenas.map((id) => byId[id] && byId[id].nombre).filter(Boolean);
    const txt = g.independiente
      ? `${esc(g.nombre)} (independiente)`
      : `${esc(g.nombre)} — ${nombres.map(esc).join(", ")}`;
    return `<span class="grupo-chip g-${i}"><span class="pt"></span>${txt}</span>`;
  }).join("");
  cont.hidden = false;
}

function filaProducto(p, m) {
  const tr = document.createElement("tr");

  const marca = p.marca ? `<span class="marca">${esc(p.marca)}</span>` : "";
  // Badge "nuevo": SKU presente hoy y ausente en el snapshot previo.
  const nuevo = p.nuevo ? ` <span class="nuevo-badge" title="Nuevo en esta captura">nuevo</span>` : "";
  // Presentación de ESTA fila (cada presentación es su propia fila).
  const pres = p.presentacion ? `<span class="pres">${esc(p.presentacion)}</span>` : "";

  let html = `<td class="prod">${esc(p.nombre)}${nuevo}${marca}${pres}</td>` +
             `<td><span class="cat">${titulo(p.categoria)}</span></td>`;

  // Solo columnas de cadenas ACTIVAS. Resaltado "más barato"/"más caro" según las
  // métricas en vivo (consistente con la selección de cadenas).
  for (const c of colsVis()) {
    const v = p.precios[c.id];
    const url = p.urls && p.urls[c.id];
    let clases = "precio g-" + c.gi + (c.inicio ? " grupo-inicio" : "");
    if (v == null) clases += " na";
    else if (m.mas_barato === c.id) clases += " barato";
    else if (m.mas_caro === c.id) clases += " caro";
    const precioTxt = (v != null && url)
      ? `<a class="precio-lnk" href="${esc(url)}" target="_blank" rel="noopener" title="Ver en ${esc(c.nombre)}">${SOLES(v)}</a>`
      : SOLES(v);
    html += `<td class="${clases}">${precioTxt}${tendencia(p, c.id)}${promoMarca(p, c.id)}${ppu(p, c.id)}</td>`;
  }

  const b = m.brecha;
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

// Precio por unidad de esa cadena (S//un o S//ml según la presentación), debajo del precio.
function ppu(p, cadena) {
  const v = p.precio_unidad && p.precio_unidad[cadena];
  if (v == null) return "";
  const u = p.unidad === "ml" ? "/ml" : (p.unidad === "g" ? "/g" : "/un");
  const dec = Number(v) < 1 ? 3 : 2;
  return `<span class="ppu" title="Precio por unidad">S/ ${Number(v).toFixed(dec)}${u}</span>`;
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
  const items = ordenar(filtrados());
  const payload = {
    generado: state.data.generado,
    descargado: new Date().toISOString(),
    filtros: {
      q: state.q || null, categoria: state.categoria || null,
      solo_con_activas: state.soloN, brecha_min_pct: state.brechaMin || null,
      posicion: state.posCadena && state.posRol ? { cadena: state.posCadena, rol: state.posRol } : null,
      cadenas_activas: [...state.activas],
      orden: { por: state.sortKey, dir: state.sortDir },
    },
    cadenas: state.cadenas.filter((c) => state.activas.has(c.id)),
    total: items.length,
    productos: items.map((x) => x.p),
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
