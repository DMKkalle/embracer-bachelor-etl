# Embracer Game Metadata ETL

**Bachelor thesis · Computer Science, Karlstad University · Collaboration with Embracer Games Archive**

A portfolio-safe refactoring of a data-engineering pipeline built to normalize, match, enrich, and quality-check inconsistent video-game metadata across multiple external sources.

The thesis pipeline processed **10,000+ game editions** and addressed a practical entity-resolution problem: the same game can appear under different titles, regions, platform names, release years, and source-specific identifiers.

> This public repository intentionally excludes proprietary/raw archive exports, cached API payloads, credentials, and private project history. It contains only synthetic sample data and reusable engineering components.

## What this demonstrates

- ETL pipeline design with **Python + pandas**
- Config-driven normalization rather than hard-coded one-off fixes
- Entity resolution across inconsistent metadata sources
- Weighted title / platform / release-year matching
- Unicode, punctuation, alias, and Roman-numeral normalization
- Data-quality reporting and review prioritization
- Source provenance and confidence-oriented design
- Automated tests, Ruff, and GitHub Actions CI
- Safe handling of external-service credentials

## Pipeline

```text
Archive export
    -> Normalization
    -> Canonical editions / releases
    -> Wikidata / IGDB / GiantBomb enrichment
    -> Entity resolution
    -> Confidence + QA
    -> Traceable enriched output
```

## Core design decisions

**Config-driven normalization.** Platform aliases and patterns live in YAML, so mapping rules can evolve without changing transformation code.

**Canonical titles with preserved aliases.** A stable canonical title is selected while alternative names remain available for matching and provenance.

**Multi-signal entity resolution.** External records are linked using title, platform and release-year evidence rather than title alone.

**Review instead of silent guessing.** Weak or conflicting matches are intended to be surfaced for review rather than silently accepted.

**Public-safe data boundary.** The original project used archive exports and API caches that are not appropriate for a public portfolio. This repository uses only synthetic sample data.

## Repository structure

```text
src/embracer_etl/
  normalization.py   # titles, languages, regions, platform rules
  matching.py        # entity-resolution helpers and weighted scoring
  pipeline.py        # dataframe transformation pipeline
  quality.py         # QA metrics and review signals

configs/
  platform_map.yaml
  source_weights.yaml

examples/
  sample_catalog.csv # synthetic input only

tests/
  test_normalization.py
  test_matching.py
  test_pipeline.py
```

## Quick start

```bash
git clone https://github.com/DMKkalle/embracer-bachelor-etl.git
cd embracer-bachelor-etl
python -m venv .venv
python -m pip install -r requirements-dev.txt
python -m pytest
```

Run the synthetic example:

```bash
python -m embracer_etl.pipeline examples/sample_catalog.csv
```

## Matching model

| Signal | Weight |
|---|---:|
| Title similarity | 50% |
| Platform similarity | 30% |
| Release-year proximity | 20% |

The score is an auditable signal intended to be combined with provenance and manual review.

## Results from the thesis project

| Area | Result |
|---|---|
| Scale | 10,000+ game editions processed |
| Normalization | Titles, platforms, regions and languages standardized |
| Entity resolution | Rule-based multi-signal matching |
| External enrichment | Wikidata, IGDB and GiantBomb workflows |
| Quality control | Confidence/review-oriented output and QA reporting |
| Traceability | Source-aware design for auditing enriched metadata |

## Academic context

Developed as a **15 ECTS Bachelor thesis in Computer Science at Karlstad University**, in collaboration with Embracer Games Archive. The full thesis and original project materials are kept separately from this public portfolio snapshot.

## Related project

For a more recent AI/backend project, see **[AI Job Assistant](https://github.com/DMKkalle/ai-job-assistant)** — FastAPI, SQLAlchemy, Pydantic, LLM structured outputs, tests, and CI.
