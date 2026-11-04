# Architecture

The public repository is a portfolio-safe reconstruction of the engineering boundaries used in the thesis project.

## Data flow

```text
Archive export / synthetic catalog
        |
        v
Normalization
- title canonicalization
- platform mapping
- region inference
- language normalization
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

## Public vs original thesis

### Included here

- reusable normalization logic
- weighted title/platform/year matching helpers
- separate source adapters for Wikidata, IGDB and GiantBomb
- source confidence and provenance structures
- review-queue behavior for ambiguous results
- synthetic end-to-end demo
- automated tests and CI

### Kept private

- proprietary/raw archive exports
- cached third-party API payloads from the original research work
- historical generated datasets and debug exports
- credentials
- original repository history

The public repository is therefore runnable and auditable without redistributing data that should not be public.
