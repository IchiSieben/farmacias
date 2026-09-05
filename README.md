# Peru Pharmacy Price Comparator

Compare medicine prices across Peru's three largest pharmacy chains — think of
it as a price checker for the same box of paracetamol in three stores at once.

## Why it exists

The same product, from the same lab, routinely differs 20-70% in price between
chains — and two of the three chains belong to the same holding. This project
makes that spread visible: it collects prices on a schedule, matches products
across chains, and renders a static comparison page anyone can read.

## How it works

```
adapters (one per chain)  →  snapshots (JSONL)  →  matcher  →  static HTML
```

- **One adapter per chain**, each speaking the chain's own storefront protocol:
  - Inkafarma and Mifarma run on their holding's Algolia search (same document
    schema, separate instances). The adapters use the public client-side search
    keys each storefront ships in its own JS bundle.
  - Boticas Perú runs on Salesforce Commerce Cloud; its adapter combines the
    HTML product grid with the storefront's clean QuickView JSON.
- **A three-layer matcher** decides when two listings are the same product:
  1. Exact ID — Inkafarma and Mifarma share an internal product ID, so those
     match 1:1 for free.
  2. Fuzzy — name plus active ingredient and pack size, for chains that share
     nothing (with hard guards against bundles, variants and near-miss
     vitamins).
  3. Image verification — perceptual hashing of product photos to confirm
     doubtful fuzzy matches.
- **Snapshots are kept per run**, so the site can show price history and
  detect promotions by diffing runs, not by trusting promo labels.

## Running it

```
pip install -r requirements.txt
cp .env.example .env   # then fill in the Algolia search credentials
py -m core.adapters.inkafarma buscar paracetamol
py -m pipeline.build_comparativa
```

The credentials in `.env` are the public search-only keys each chain embeds in
its own website (visible in DevTools → Network → requests to `*.algolia.net`).
They are not private secrets, but they rotate occasionally and don't belong in
a repo; when search starts returning 403, re-capture and update your `.env`.

## The static demo

`web/` is the published artifact: plain HTML, CSS and JS with no build step. It loads
`data.json` (or `data.demo.json` with `?demo`) at runtime and renders the comparison table
client-side, so it costs nothing to host.

It opens with a five-step tutorial (`web/tutorial/`, vendored from `shared/tutorial/` in the
portfolio workspace) that a returning visitor never sees again — dismissal persists in
localStorage.

Every path in `web/` is relative, so the folder drops into any subdirectory unchanged.
Verified served from `/radar-precios/`: page renders, data loads, zero console errors.

## Scope and conduct

Read-only collection from the same public search endpoints the chains' own
storefronts call, throttled (2-6 s random delay, 2 concurrent requests max),
with raw responses cached per run to avoid re-fetching. Prices belong to their
respective chains; this project is an independent comparison exercise and is
not affiliated with any of them.

## Tests

`tests/test_matcher_regresion.py` pins the matcher against a curated basket of
known-good and known-bad pairs — the guard that keeps "Vitamina C 500mg x100"
from matching "Vitamina C gomitas x60".

---

*Internal working notes (SPEC, matching annex, roadmap) are in Spanish in the
repo root and `docs/`.*
