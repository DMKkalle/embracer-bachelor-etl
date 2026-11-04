# Extending the pipeline

The thesis was intentionally structured so the proof-of-concept could grow beyond one console generation or one set of data providers.

## Add a platform

1. Add raw-name mappings, aliases and/or regex rules in `configs/platform_map.yaml`.
2. If Wikidata uses additional platform labels, add them to `configs/wikidata_platform_aliases.yaml`.
3. Add a small regression input covering the new platform.
4. Run the offline test suite.

IGDB and GiantBomb build their alias lists from the shared platform map, so their matching behavior automatically benefits from most platform additions.

## Add an external source

A new enrichment source should:

1. read `data/outputs/editions.csv`,
2. keep `edition_id` unchanged,
3. perform its own source-appropriate candidate matching,
4. write one auditable source result per edition,
5. preserve confidence / source-specific evidence where possible,
6. be added to the orchestration and merge policy.

The raw catalog normalization and edition/release stages do not need to be rewritten.

## Why the merge policy is explicit

Different sources are strong at different fields. The final PoC therefore does not pretend every provider is interchangeable. Adding a source may require extending `merge_enriched.py` so the project states explicitly when that source is preferred for developer, publisher, date, region, credits, or another field.

That is deliberate: modular extraction does not mean hiding source semantics behind a lowest-common-denominator interface.
