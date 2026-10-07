# Seguridad · Security

**ES.** Si encuentras un problema de seguridad (una credencial expuesta, una forma de que el
demo cargue contenido ajeno, un abuso posible de los endpoints que lee el pipeline), no abras un
issue público: abre un *private security advisory* en GitHub (pestaña **Security → Report a vulnerability**).
Respondo en un plazo de 7 días.

**EN.** If you find a security issue (an exposed credential, a way to make the demo load
third-party content, a possible abuse of the endpoints the pipeline reads), please don't open a
public issue: open a private security advisory on GitHub (**Security → Report a vulnerability**). I reply within 7 days.

## Alcance · Scope

- Las llaves Algolia que usa el pipeline son las **públicas de solo búsqueda** que cada cadena
  publica en su propio frontend; se leen de `.env` y no están en el árbol (commits de junio de 2026 sí las tuvieron; ver
  `docs/PUBLICAR.md` §Auditoría). Que aparezcan en el
  JavaScript de una tienda no es una vulnerabilidad de este proyecto.
  · The Algolia keys are each chain's **public search-only** keys, shipped in its own storefront;
  they are read from `.env` and are not in the tree (June 2026 commits did contain them).
- El demo (`web/`) es estático, sin backend ni formularios, con una CSP que solo permite
  recursos propios (más imágenes https). · The demo is static, with no backend or forms, under a
  CSP that only allows same-origin resources (plus https images).
