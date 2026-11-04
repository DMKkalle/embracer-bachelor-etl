# Embracer Game Metadata ETL

**Bachelor thesis · Computer Science, Karlstad University · Collaboration with Embracer Games Archive**

A portfolio-safe reconstruction of a data-engineering pipeline built to normalize, match, enrich, and quality-check inconsistent video-game metadata across multiple external sources.

The thesis pipeline processed **10,000+ game editions** and addressed a practical entity-resolution problem: the same game can appear under different titles, regions, platform names, release years, and source-specific identifiers.

> This public repository intentionally excludes proprietary/raw archive exports, cached API payloads, credentials, and private project history. It contains synthetic examples plus reusable engineering components that mirror the original architecture.

## What this demonstrates

- ETL pipeline design with **Python + pandas**
- Config-driven metadata normalization
- Entity resolution across inconsistent sources
- Weighted title / platform / release-year matching
- Separate adapters for **Wikidata, IGDB, and GiantBomb**
- Source provenance and confidence-aware consensus
- Review queues for ambiguous or low-confidence results
- Automated tests, Ruff, and GitHub Actions CI
- Safe credential boundaries for optional live integrations

## Architecture

```text
Archive export / synthetic catalog
        |
        v
Normalization
        |
        v
Canonical records
        |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
     Wikidata              IGDB             GiantBomb
        |                   |                   |
        +-------------------+-------------------+
                            |
                            v
                    Source observations
                            |
                            v
                    Weighted consensus
                    + provenance trail
                            |
                            v
                  accepted values / review queue
                            |
                            v
                           QA
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full breakdown.

## Run the project

Clone and install:

```bash
git clone https://github.com/DMKkalle/embracer-bachelor-etl.git
cd embracer-bachelor-etl

python -m venv .venv
python -m pip install -r requirements-dev.txt
```

Run the tests:

```bash
python -m pytest
```

Run the complete **offline end-to-end demo**:

```bash
python -m embracer_etl.demo
```

That produces a local `demo_output/` directory containing:

- `normalized_catalog.csv`
- `consensus.csv`
- `provenance.csv`
- `review_queue.csv`
- `summary.json`

No API credentials are required for the demo.

## Optional live-source adapters

The repository also contains adapters for Wikidata, IGDB and GiantBomb under `src/embracer_etl/sources/`.

Wikidata can be used without an API key. IGDB and GiantBomb require your own credentials.

Copy the example environment file:

```bash
cp .env.example .env
```

The offline demo and tests do **not** depend on those credentials.

## Matching model

The public matching example combines multiple transparent signals:

| Signal | Weight |
|---|---:|
| Title similarity | 50% |
| Platform similarity | 30% |
| Release-year proximity | 20% |

These are inspectable heuristics, not claimed as universally optimal weights. In a production system, they should be calibrated against a reviewed validation set.

## Why provenance and a review queue?

The pipeline is designed not to silently turn uncertain metadata into catalogue truth.

Every source observation can retain:

- source
- field
- proposed value
- source confidence

Weighted consensus can accept a value when agreement is strong enough. If confidence or source quorum is insufficient, the field is deferred to a **review queue** instead.

## Repository structure

```text
src/embracer_etl/
  normalization.py
  matching.py
  consensus.py
  pipeline.py
  demo.py
  quality.py
  sources/
    wikidata.py
    igdb.py
    giantbomb.py

configs/
  platform_map.yaml
  source_weights.yaml

examples/
  sample_catalog.csv

tests/
  test_normalization.py
  test_matching.py
  test_pipeline.py
  test_consensus.py
  test_demo.py

docs/
  ARCHITECTURE.md
  DESIGN_DECISIONS.md
  THESIS_CONTEXT.md
  INTERVIEW_NOTES.md
```

## Results from the thesis project

| Area | Result |
|---|---|
| Scale | 10,000+ game editions processed |
| Normalization | Titles, platforms, regions and languages standardized |
| Entity resolution | Rule-based multi-signal matching |
| External enrichment | Wikidata, IGDB and GiantBomb workflows |
| Quality control | Confidence/review-oriented output and QA reporting |
| Traceability | Source-aware design for auditing enriched metadata |

## Public repository vs original thesis repository

This public repository is intentionally **not a raw copy** of the original working repository.

The original private project contains historical development files, generated datasets, API caches, and archive-derived data that should not be redistributed publicly.

This version preserves the important engineering ideas in a smaller, reviewable, reproducible form.

For more context, see:

- [Thesis context](docs/THESIS_CONTEXT.md)
- [Design decisions](docs/DESIGN_DECISIONS.md)
- [Technical discussion guide](docs/INTERVIEW_NOTES.md)

## Related project

See **[AI Job Assistant](https://github.com/DMKkalle/ai-job-assistant)** for my more recent AI/backend work with FastAPI, SQLAlchemy, Pydantic, LLM structured outputs, tests, and CI.
