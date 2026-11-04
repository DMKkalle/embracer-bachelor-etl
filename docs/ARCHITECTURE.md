# Architecture

The project separates the pipeline into stable core stages and source-specific enrichment stages.

## Core flow

1. **Raw catalog ingestion** — one or more archive-style CSV exports.
2. **Normalization** — platform, title/aliases and accessory classification.
3. **Edition/release construction** — deterministic identifiers and link tables.
4. **External enrichment** — independent source-specific scripts keyed by `edition_id`.
5. **Merge** — source columns remain inspectable while harmonized fields are selected.
6. **Export** — enriched values are joined back to the archive object view.
7. **QA** — orphan checks, duplicate checks, unknown country/language checks and confidence breakdowns.

## Stable contracts between stages

The important architectural boundary is the CSV contract rather than a specific API.

`editions.csv` is the seed for every external source. Source scripts do not need to know how the original archive CSV was structured.

Each source result is then joined using `edition_id`. This isolates provider-specific API behavior from the catalog-normalization layer.

## Live vs offline demo

`run_pipeline.py` is the final live pipeline orchestration and invokes IGDB, GiantBomb, Wikidata and Wikipedia.

`run_demo.py` preserves the same downstream file contracts but replaces the network calls with synthetic recorded enrichment fixtures. This makes the review path deterministic and avoids requiring third-party API accounts.
