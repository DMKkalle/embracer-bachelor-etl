# Embracer Game Metadata ETL

**Bachelor thesis · Computer Science, Karlstad University · In collaboration with Embracer Games Archive**

A portfolio-safe reconstruction of the final proof-of-concept implementation for normalizing, enriching, matching, and quality-assuring video-game metadata from multiple heterogeneous sources.

The project was designed as a **modular ETL pipeline**, not as a one-off script for a single dataset. Normalization, edition/release construction, source-specific enrichment, merge/export, and QA are separate stages so the system can be extended with additional platforms, sources, and metadata fields.

> This public repository contains no proprietary Embracer archive exports, API tokens, cached private responses, or historical secrets. The offline demo uses synthetic catalog data and synthetic recorded enrichment fixtures with the same CSV contracts as the final thesis pipeline.

## What the pipeline does

```text
Raw catalog CSV
      |
      v
normalize_one.py
  - platform normalization
  - title / alias handling
  - accessory classification
      |
      v
build_releases.py
  - deterministic edition_id / release_id
  - editions + releases
  - object -> edition links
  - bundle children
      |
      +----------------+----------------+----------------+----------------+
      |                |                |                |
      v                v                v                v
     IGDB          GiantBomb         Wikidata        Wikipedia
      |                |                |                |
      +----------------+----------------+----------------+
                               |
                               v
                      merge_enriched.py
                               |
                               v
                 editions_enriched_master.csv
                               |
                               v
                export_enriched_catalog.py
                               |
                               v
                catalog_enriched_embracer.csv
                               |
                               v
                         qa_report.py
```

## Why it is modular

The core catalog transformation does not depend on one external source. Each enrichment source reads the normalized `editions.csv` contract and writes source-specific results keyed by `edition_id`.

Platform normalization is configuration-driven through YAML. Both the IGDB and GiantBomb matchers build platform aliases from the shared platform map, while Wikidata has a source-specific alias configuration.

Adding another source therefore does not require rewriting raw-data normalization or edition/release construction. A new source needs its own enrichment adapter and an explicit merge policy for whichever fields it contributes.

See [docs/EXTENDING.md](docs/EXTENDING.md).

## Run the offline demo

The fastest way to review the project does **not** require API accounts:

```bash
git clone https://github.com/DMKkalle/embracer-bachelor-etl.git
cd embracer-bachelor-etl
python -m venv .venv
python -m pip install -r requirements-dev.txt
python src/run_demo.py
```

The demo runs the real final implementations of:

1. `normalize_one.py`
2. `build_releases.py`
3. `merge_enriched.py`
4. `export_enriched_catalog.py`
5. `qa_report.py`

The only substituted stage is live network enrichment. Instead of calling third-party APIs, the demo installs small synthetic recorded results that obey the same source CSV schemas used by the final pipeline.

After a successful run, inspect:

```text
data/outputs/editions.csv
data/outputs/releases.csv
data/outputs/items_to_editions.csv
data/outputs/objects_expanded.csv
data/outputs/editions_enriched_master.csv
data/outputs/catalog_enriched_embracer.csv
data/outputs/qa/
```

The final demo catalog contains the same 24-column output contract used by the final thesis implementation, including developer, publisher, release year, platform, genres, origin/language metadata, creative roles, and confidence fields.

## Run the live pipeline

The original source adapters are also included:

- `igdb_enrich_editions.py`
- `gb_enrich_editions.py`
- `enrich_wikidata.py`
- `enrich_wikipedia.py`

Copy `.env.example` to `.env`, add your own credentials/user agents, and then run:

```bash
python src/run_pipeline.py
```

Live execution depends on current third-party API availability and API contracts. The offline demo is the reproducible review path used by CI.

## Source-specific matching

The final PoC did **not** use one generic 50/30/20 matching score for every provider. Each source has its own matching behavior.

For example:

- **IGDB** prioritizes platform match, title match, and then rating when choosing among candidates.
- **GiantBomb** normalizes titles, handles Roman/Arabic numerals, uses token overlap and platform aliases, and rejects incompatible numbered sequels.
- **Wikidata** evaluates title/platform evidence and entity type, while preserving candidate rows for later QA.

This is intentionally kept source-specific because the APIs expose different metadata and have different failure modes.

## Data model and traceability

The final implementation creates deterministic identifiers and explicit link tables:

- `edition_id` identifies a normalized title + platform combination in the final code.
- `release_id` adds country, language, and release date to an edition.
- `items_to_editions.csv` links archive objects to editions.
- `release_sources.csv` preserves which object produced a release.
- source-specific enrichment columns are retained in the master dataset rather than discarded.

An earlier design description also included region in the edition identity. The final implementation simplified the key to title + platform and retains region separately. This repository follows the **implemented final code**, not the earlier design draft. See [docs/IMPLEMENTATION_NOTES.md](docs/IMPLEMENTATION_NOTES.md).

## Repository structure

```text
configs/
  accessory_map.yaml
  platform_map.yaml
  wikidata_platform_aliases.yaml

src/
  normalize_one.py
  build_releases.py
  igdb_auth.py
  igdb_client.py
  igdb_enrich_editions.py
  gb_client.py
  gb_enrich_editions.py
  enrich_wikidata.py
  enrich_wikipedia.py
  merge_enriched.py
  export_enriched_catalog.py
  qa_report.py
  run_pipeline.py
  run_demo.py

data/raw/
  sample_catalog.csv              # synthetic only

demo/fixtures/enrichment/        # synthetic recorded source results

tests/
  test_offline_demo.py

docs/
  ARCHITECTURE.md
  EXTENDING.md
  IMPLEMENTATION_NOTES.md
  THESIS_CONTEXT.md
```

## Thesis scope

The thesis focused on a limited proof-of-concept subset rather than claiming full automation of Embracer Games Archive. The goal was to demonstrate a scalable, traceable method for integrating heterogeneous game metadata, while documenting uncertainty and leaving difficult cases for human review.

## Related project

See [AI Job Assistant](https://github.com/DMKkalle/ai-job-assistant) for my more recent AI/backend work with FastAPI, SQLAlchemy, Pydantic, structured LLM extraction, tests, and CI.
