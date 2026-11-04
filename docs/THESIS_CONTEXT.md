# Thesis context

The Bachelor thesis investigated how video-game metadata can be collected, normalized and quality-assured in a scalable and traceable way for digital game preservation.

The practical problem was that metadata across an archive and third-party databases can be incomplete or inconsistent: titles differ by language and region, platform names vary, identifiers are not standardized, and sources disagree.

The proof-of-concept therefore combined:

- modular ETL stages,
- a normalized data model,
- alias and title normalization,
- source-specific record matching,
- IGDB, GiantBomb, Wikidata and Wikipedia enrichment,
- deterministic IDs and link tables,
- source traceability,
- confidence-oriented QA and manual review for difficult cases.

The original working repository and archive-derived datasets remain private. This repository is a sanitized reconstruction of the final implementation plus a deterministic synthetic demo.
