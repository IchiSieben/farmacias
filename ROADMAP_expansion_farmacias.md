# ROADMAP — Expansión de Farmacias (FarmaComparador)

> Orden sugerido para agregar farmacias, por dificultad técnica y valor.
> Principio guía: farmacias del MISMO grupo comparten plataforma → una vez
> resuelta una, las hermanas son casi gratis (como pasó con Inkafarma→Mifarma).

---

## Mapa de grupos (quién es dueño de quién) — junio 2026

| Grupo | Cadenas | Cuota mercado aprox | Estado |
|-------|---------|--------------------|--------|
| **InRetail / Intercorp** | Inkafarma, Mifarma | ~52-57% (líder) | ✅ HECHO |
| **Quicorp / Química Suiza** | Fasa, BTL (Torres de Limatambo), Boticas Arcángel | ~36% (2º) | Pendiente |
| **Corporación Boticas Perú** | Boticas Perú (+ Tec. del Oriente, Tec. San Martín en selva) | ~8% (3º) | ✅ HECHO (target) |
| **Independientes** | Farmacia Universal, Hogar y Salud / Boticas y Salud, otras | — | Pendiente |

> Nota: la propiedad de Mifarma ha cambiado por adquisiciones a lo largo de los
> años (aparece tanto bajo InRetail como bajo Quicorp en distintas fuentes).
> Para el scraping da igual el dueño legal — lo que importa es que técnicamente
> Inkafarma y Mifarma comparten backend Algolia, ya verificado.

---

## El insight clave para priorizar

La dificultad de agregar una farmacia NO depende de su tamaño, sino de **qué
plataforma e-commerce usa**:

| Plataforma | Dificultad | Por qué | Ejemplo conocido |
|-----------|-----------|---------|------------------|
| API JSON (Algolia, etc.) | Baja | Datos limpios, precio/presentación directo | Inkafarma, Mifarma |
| Salesforce Commerce Cloud | Media | HTML SSR + endpoint detalle, matcher fuzzy | Boticas Perú |
| VTEX | Media | Tiene API pública `/api/catalog`, predecible | (varias peruanas usan VTEX) |
| WooCommerce / custom | Media-Alta | Cada una distinta, scraping HTML a medida | Por verificar |

> Cada plataforma nueva = el trabajo de reconocimiento + adapter + afinar
> matcher que ya hiciste. NO es copiar-pegar. Por eso: una a la vez.

---

## Roadmap sugerido (orden de implementación)

### Fase A — Consolidar lo que tienes (antes de expandir)
**Prioridad: ALTA. Esfuerzo: bajo-medio.**
Antes de sumar farmacias, dejar las 3 actuales sólidas:
- [ ] Completar fotos interactivas (lo visual, ya planeado)
- [ ] Campañas/ofertas (Día del Padre, alertas de descuento)
- [ ] **Decidir escala de productos** (ver sección aparte abajo)
- [ ] Subir al hosting (tener el link demostrable)

> Razón: 3 cadenas bien hechas y visibles venden más que 6 a medias.

### Fase B — Primera farmacia nueva: **Farmacia Universal**
**Prioridad: ALTA. Esfuerzo: medio.**
- Independiente (no comparte plataforma con nadie) → adapter propio.
- Buen candidato para validar que el motor escala a una 4ª cadena.
- Primer paso: reconocimiento DevTools (¿API JSON? ¿VTEX? ¿HTML?).
- Por qué primera: es un jugador relevante y al ser independiente, su adapter
  es "limpio" (no arrastra dependencias de grupo).

### Fase C — Grupo Quicorp (3 de un golpe): **Fasa → Arcángel → BTL**
**Prioridad: MEDIA. Esfuerzo: medio (el primero), bajo (los otros 2).**
- Fasa, Arcángel y BTL son del MISMO grupo (Quicorp) → muy probable que
  compartan plataforma, como Inkafarma/Mifarma.
- Hacer Fasa primero (reconocimiento + adapter). Si comparten backend,
  Arcángel y BTL son wrappers cortos → 3 cadenas por el precio de ~1.
- Esto es lo que más cobertura agrega por unidad de esfuerzo.
- Primer paso: reconocer fasa.com.pe en DevTools y ver si Arcángel/BTL usan
  el mismo host de API.

### Fase D — Resto de independientes
**Prioridad: BAJA. Esfuerzo: variable.**
- Hogar y Salud / Boticas y Salud, y cualquier otra con e-commerce.
- Una por una, según valor. Algunas quizá ni tengan tienda online scrapeable.

---

## Decisión aparte: ¿cuántos PRODUCTOS por farmacia?

Tu idea de "todos los productos mapeados" (46k Inka + 12k Mifarma + ...) merece
pensarse, porque tiene un costo real:

**Contra el volcado total ahora:**
- El matcher se validó sobre ~150 productos. Sobre decenas de miles produciría
  miles de matches sin revisar → falsos positivos imposibles de auditar a mano.
- Las corridas se vuelven muy pesadas (recuerda: ya una se cortó al duplicar
  búsquedas de Boticas). 46k productos × detalle × varias cadenas = horas.
- Para el OBJETIVO (demo vendible, inteligencia competitiva), no necesitas
  todo el catálogo — necesitas las categorías que importan.

**Estrategia recomendada (por capas, no todo de una):**
1. **Canasta ampliada** (lo que tienes hoy + crecer a ~300-500 productos de
   alta rotación por categoría). Suficiente para una demo potente y auditable.
2. **Por categoría** (analgésicos, antigripales, dermo, bebé...): volcar
   categoría completa de a una, validar matching, luego la siguiente.
3. **Catálogo total**: solo si un cliente real lo pide y paga la
   infraestructura. Ahí sí browse completo + Google Sheets/BigQuery + matching
   automático con revisión por muestreo.

> Regla: la cobertura de productos crece por categorías validadas, no por un
> volcado masivo sin revisar. Calidad auditable > volumen sin auditar.

---

## Resumen ejecutivo (qué hacer en qué orden)

1. **Consolidar las 3 actuales** (fotos, campañas, subir a hosting).
2. **Farmacia Universal** (1ª cadena nueva, valida escala).
3. **Fasa + Arcángel + BTL** (grupo Quicorp, 3 por el esfuerzo de 1).
4. **Crecer productos por categoría**, no por volcado total.
5. **Independientes restantes** según valor.

Cada cadena nueva: reconocimiento DevTools → adapter → afinar matcher →
controles → commit. Una a la vez. Es el método que ya te funcionó.
