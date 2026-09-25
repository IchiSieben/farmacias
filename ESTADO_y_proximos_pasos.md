# ESTADO DEL PROYECTO — Radar de Precios (para retomar)

> Abre esto al empezar la sesión. Claude Code lo actualiza al cerrar cada fase.
> Última actualización: 2026-09-24 (arranque de v2).

---

## ✅ v1 — HECHO y en producción

- **4 cadenas:** Inkafarma + Mifarma (Algolia InRetail), Boticas Perú (SFCC),
  Farmacia Universal (VTEX, con EAN).
- **Matcher de 3 capas** con reglas duras (concentración, cantidad, forma, pediátrico,
  vitamina, gomita, efervescente, activo compartido) + pHash en zona gris.
  Regresión: 32/32 OK.
- **Snapshots por corrida** + `pipeline/cambios.py` (▲▼, promos, nuevos).
- **Web estática** (`web/`) desplegada en https://ichisieben.dev/radar-precios/ —
  296 productos, 64 con las 4 cadenas. Tutorial de apertura. Vista `?demo`.
- README bilingüe, CITATION.cff, Apache 2.0. Repo público
  `github.com/IchiSieben/farmacias`.

## 🚧 v2 — EN CURSO (plan completo en `V2_PLAN.md`)

| Fase | Qué | Estado |
|---|---|---|
| F1 | Data lake: crudo a Google Drive (`RAW_DIR`), Parquet, `pipeline/run.py`, tarea diaria Windows, `--desde-cache` | ⬜ siguiente |
| F2 | Cobertura por categoría (browse/facetas/cgid/fq), `config/categorias.yaml`, una categoría por sesión con muestra revisada | ⬜ |
| F3 | Matcher v2: `core/ficha.py` (atributos > nombre), registro sanitario como llave, imagen en todo candidato, evidencia por match, set curado | ⬜ |
| F4 | UI v2 bilingüe (Astro): buscador, ficha con historial, panorama por cadena, metodología | ⬜ |
| F5 | README final con capturas nuevas, `docs/` (esquema, matching, operación), CITATION 2.0.0 | ⬜ |

**Arranque:** pegar `PROMPT_claude_code.md` en Claude Code desde la raíz del repo.

## 🔧 Deuda conocida (sigue vigente)

- Llaves Algolia rotan → 403; recapturar desde DevTools y actualizar `.env`.
- Corridas pesadas contra Boticas se han cortado alguna vez; F1 resuelve con caché +
  reanudación. No reintentar en bucle.
- El histórico se resetea si cambian los ids de match (pasó al separar
  presentaciones). En F3 el `match_id` pasa a ser estable (derivado de llaves duras
  cuando existan).
- Stock no se captura en InRetail (vive en el detalle) — entra en F2 con el detalle
  REST por producto, solo para lo que ya está emparejado.

## 🚀 Cómo correr / verificar (v1, sigue igual hasta F4)

```
PYTHONIOENCODING=utf-8 py -m tests.test_matcher_regresion
py -m pipeline.build_snapshot --objetivo 150 --salida web/data.json
py -m http.server -d web 8000     # http://localhost:8000  ·  ?demo=1 para la demo
py -m pipeline.make_demo          # regenerar data.demo.json tras cambiar data.json
```

## Cómo retomar la próxima sesión

1. Leer esta tabla y `V2_PLAN.md` de la fase que toca.
2. Pedir a Claude Code diagnóstico → plan corto → implementar → controles → commit.
3. Una fase (o una categoría, en F2) por sesión. Actualizar esta tabla al cerrar.
