# ESTADO DEL PROYECTO — FarmaComparador (para retomar)

> Dónde quedó todo y qué sigue. Abre esto al empezar la próxima sesión y
> retomas en 5 minutos sin perder el hilo.

---

## ✅ HECHO (todo commiteado y pusheado en main)

- **3 cadenas funcionando:** Inkafarma + Mifarma (API Algolia InRetail),
  Boticas Perú (Salesforce Commerce Cloud).
- **Matcher de 3 capas robusto:**
  - Capa 1: id/objectID (Inka↔Mifarma exacto).
  - Capa 2: fuzzy por principio activo + concentración semántica + reglas
    duras (forma, tamaño de envase).
  - Capa 3: verificación por imagen (pHash) en zona gris 70-85.
  - Endurecido: exige principio activo compartido (no confunde fármacos).
  - Cobertura Boticas: 86/196 filas, todos los matches verificados legítimos.
- **Presentaciones separadas** (blíster vs caja como filas distintas) +
  **precio por unidad** por cadena.
- **Histórico + detección de cambios** (▲▼ subidas/bajadas, promos, productos
  nuevos). Snapshots locales en data/snapshots/.
- **Buscador web estático** (HTML+CSS+JS vanilla) en web/:
  - Links por celda a la ficha de cada cadena.
  - Agrupación visual por conglomerado (InRetail vs independientes).
  - Filtros: brecha mínima, orden por columna, quién es más caro/barato,
    selector de cadenas, descarga JSON.
- **Demo** (?demo=1) con cambios simulados para mostrar las flechas.

---

## ⏳ PENDIENTE — Fase A (consolidar, ~1 semana)

Orden sugerido para las próximas sesiones. UNA pieza por sesión.

### 1. Subir al hosting (PRIORITARIO — tener el link demostrable)
- La carpeta `web/` es estática, lista para subir tal cual.
- Considerar GitHub Pages (gratis) sobre `web/` o el hosting propio.
- **Antes de hacer público:** revisar que las API keys de Algolia no queden
  expuestas (hoy el repo es público — evaluar privado o mover keys).
- Resultado: un link que puedas mandar a clientes / poner en portafolio.

### 2. Escalar productos (por CATEGORÍA, no volcado total)
- Crecer de ~150 a ~300-500 productos de alta rotación.
- Hacerlo categoría por categoría, validando el matching de cada una.
- NO volcar los 46k de una vez (falsos positivos sin auditar, corridas de horas).

### 3. Fotos interactivas (lo visual)
- Miniatura del producto al pasar el mouse / click sobre el precio.
- Las URLs de imagen ya vienen en los JSON de Algolia.
- Frontend puro, sin tocar scraping.

### 4. Campañas / ofertas
- Detectar campañas (Día del Padre, etc.) y alertas de descuento.
- Ya hay base: el histórico detecta inicio/fin de promo.

### 5. KPI "InRetail como un solo competidor" (follow-up)
- Hoy el "más barato" compara las 3 cadenas por separado.
- Como Inka+Mifarma son el mismo grupo, opción de tratarlos como uno solo
  en el cálculo de brecha.

---

## ⏳ PENDIENTE — Fase B y C (expansión, después de consolidar)

Ver `ROADMAP_expansion_farmacias.md` para el detalle. Resumen:

- **Fase B — Farmacia Universal** (1ª cadena nueva, independiente, valida
  que el motor escala a una 4ª).
- **Fase C — Grupo Quicorp: Fasa → Arcángel → BTL** (mismo grupo, probable
  backend compartido → 3 cadenas por el esfuerzo de ~1, como Inka/Mifarma).

Cada cadena nueva: reconocimiento DevTools → adapter → afinar matcher →
controles → commit. Una a la vez.

---

## 🔧 Notas técnicas / deuda conocida

- **Corridas pesadas:** al duplicar búsquedas a Boticas (query combinada), una
  corrida se cortó (exit transitorio). Si se vuelve recurrente al escalar,
  implementar fallback (query amplia solo si la precisa no encontró) o backoff.
- **Histórico se resetea** cuando cambian los ids de producto (pasó al separar
  presentaciones). Normal; las flechas vuelven desde la corrida siguiente.
- **Repo público con API keys:** pendiente decidir privado o mover keys a
  variable de entorno antes de difundir.
- **Stock:** no se captura hoy (vive en el detalle de producto). Útil a futuro
  para señal de quiebre de inventario del competidor.

---

## 🚀 Cómo correr / verificar

```
# Regenerar snapshot (consulta las 3 cadenas en vivo):
py -m pipeline.build_snapshot

# Ver el buscador localmente:
py -m http.server -d web 8000
# → http://localhost:8000        (real)
# → http://localhost:8000/index.html?demo=1   (demo con flechas)

# Regenerar la demo tras cambiar data.json:
py -m pipeline.make_demo
```

---

## Cómo retomar la próxima sesión

1. Abre este archivo y el ROADMAP.
2. Elige UNA pieza de la Fase A (recomendado: subir al hosting primero).
3. Pídele a Claude Code el diagnóstico/plan antes de codear (el método que
   funcionó: diagnóstico → controles → commit).
4. Una pieza por sesión. Commitea al terminar. No encadenar sin cerrar.
