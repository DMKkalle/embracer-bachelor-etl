# Design decisions

## Why use several matching signals?

Title-only matching is unsafe for historical game metadata. Regional releases, translated titles, reissues and similarly named games create false positives.

The thesis workflow therefore used multiple pieces of evidence. The public demo illustrates the same idea with:

- title similarity: 50%
- platform similarity: 30%
- release-year proximity: 20%

These numbers are not presented as universally optimal. They are explicit, inspectable heuristics that can be calibrated against reviewed matches.

## Why preserve aliases?

A canonical title is useful for storage and reporting, but discarding aliases destroys useful evidence. The pipeline keeps alternative titles available for later matching.

## Why config-driven platform normalization?

Platform naming varies substantially across catalogues: SNES, Super NES, Super Nintendo Entertainment System, SFC and Super Famicom may describe closely related platform concepts.

Moving mappings to YAML makes rules reviewable and changeable without editing transformation code.

## Why provenance?

An enriched value is more useful when a reviewer can see where it came from. The public demo writes one provenance row per source observation.

## Why a review queue?

Low-confidence data should not silently become catalogue truth. If sources disagree, confidence is too low, or quorum is missing, the pipeline defers the field for human review.

## Why is the demo offline by default?

A recruiter should be able to clone and run the project without creating API accounts or receiving proprietary data. Live adapters are included as optional boundaries, while the default demo uses synthetic source observations.
