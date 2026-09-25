# CLAUDE.md — contexto del proyecto para Claude Code

Radar de Precios (repo `IchiSieben/farmacias`): comparador de precios de medicamentos
entre cadenas de farmacias peruanas. Demo viva en https://ichisieben.dev/radar-precios/.
Pieza de portafolio — la calidad visible (UI, README, datos correctos) importa tanto
como el código.

## Qué hay hoy (v1, junio 2026 — NO romper)

- 4 cadenas: Inkafarma + Mifarma (Algolia, grupo InRetail, mismo `objectID`),
  Boticas Perú (Salesforce Commerce Cloud), Farmacia Universal (VTEX, expone EAN).
- `core/` motor genérico: `adapter_base.py` (httpx, UA, delays, backoff),
  `adapters/*`, `modelo.py` (`Producto`), `normalizer.py` (specs desde el nombre),
  `matcher.py` (3 capas: id/EAN → fuzzy + reglas duras → pHash en zona gris 70–85),
  `imagen.py` (pHash).
- `pipeline/build_snapshot.py` orquesta todo y escribe `web/data.json`
  (296 productos, 64 con las 4 cadenas). Snapshots por corrida en `data/snapshots/`.
  `pipeline/cambios.py` deriva ▲▼/promos entre corridas.
- `web/` estático sin build (HTML/CSS/JS vanilla) — se sube tal cual al hosting.
- `tests/test_matcher_regresion.py`: 32 pares curados; se corre como script, no pytest.

## Hacia dónde va (v2) — leer `V2_PLAN.md` antes de tocar nada

Cuatro frentes, en este orden: (1) data lake — crudo a Google Drive, procesado a
Parquet + JSON, (2) cobertura real por categoría (browse/facetas, no búsquedas
sueltas), (3) matcher v2 multi-señal (atributos estructurados + registro sanitario +
imagen para todo candidato, no solo zona gris), (4) UI v2 bilingüe ES/EN. Cada frente
es una rama/PR. No mezclar frentes en un mismo commit.

## Comandos (Windows, Python 3.12, usar `py`)

```
py -m pip install -r requirements.txt
PYTHONIOENCODING=utf-8 py -m tests.test_matcher_regresion     # debe dar N/N OK
py -m pipeline.build_snapshot --objetivo 150 --salida web/data.json
py -m http.server -d web 8000
```

`PYTHONIOENCODING=utf-8` es obligatorio en consola Windows (cp1252 revienta con tildes).

## Reglas duras

- **Solo datos públicos de catálogo.** Delays 2–6 s por dominio, máx. 2 concurrentes,
  backoff en 429/503, respetar robots.txt. Nunca login, nunca carrito, nunca checkout.
- **Cachear el crudo siempre** (`RAW_DIR`, ver `.env.example`) antes de parsear: depurar
  contra el caché, no contra el sitio.
- **Credenciales fuera del repo.** Las llaves Algolia van en `.env` (son públicas
  search-only del frontend de cada cadena, pero rotan). Nunca hardcodear.
- **El matcher se cambia con regresión.** Todo cambio en `core/matcher.py` o
  `core/normalizer.py` agrega casos a la regresión y la deja en verde. Un falso
  positivo (dos productos distintos como iguales) es peor que un "—".
- **`web/data.json` es un artefacto generado** — no editarlo a mano. Si hay que
  cambiar el esquema, se cambia el generador y se regenera.
- **Bilingüe.** Todo texto visible al usuario (UI, README, mensajes) existe en ES y EN.
  Código, comentarios y docs internas: español (como está) — no traducir lo existente.
- Python 3.9+ compatible en `core/` (sin `X | Y` en runtime, sin `slots=`); el resto
  puede usar 3.12.
- Commits en español, imperativo, pequeños: "agrega browse por subcategoría a Inkafarma".

## Estilo de trabajo que ha funcionado

Diagnóstico → plan corto → controles (regresión, muestra revisada a mano) → commit.
Una pieza por sesión. Si una corrida en vivo se corta, no reintentar en bucle: revisar
`data/raw/` y seguir desde el caché.
