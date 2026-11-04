# Implementation notes

## Design vs final implementation: edition identity

The thesis design chapter describes an edition identity based on title, platform and region. During implementation, the final `build_releases.py` was simplified to generate `edition_id` from **title + platform**.

Region is still inferred and retained on `editions.csv`, while country, language and date contribute to `release_id`.

The public repository intentionally follows the final executable implementation so the demo and saved output contracts stay reproducible.

## Matching is source-specific

There is no single universal `MatchSignals` object in the final implementation.

- IGDB uses title/platform matching and provider rating for candidate selection.
- GiantBomb uses stronger title canonicalization, token overlap, number compatibility and platform matching.
- Wikidata validates candidate entity type and exposes candidate-level QA information.

This reflects the reality that providers expose different structures and signals.

## Confidence is not a statistical probability

`info_confidence_score` is an interpretable heuristic indicator for review prioritization. It increases when multiple identifiers/sources are present and when Wikipedia/Wikidata evidence exists. It should not be interpreted as a calibrated probability of correctness.

## Public-data boundary

The original working project contained archive exports, generated datasets, API caches and local credentials. None of those are part of this public reconstruction.

## Known matching limitation retained from the final PoC

The GiantBomb matcher separately understands Roman/Arabic sequel numbers for compatibility checks (`II` vs `2`), but the title-overlap threshold can still reject that pair because the normalized token score does not convert the numeral before scoring. This public reconstruction keeps that behavior rather than silently rewriting the thesis implementation. A production follow-up should canonicalize numeric tokens before title scoring and cover the behavior with labeled regression cases.
