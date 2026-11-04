# Technical discussion guide

## How did you prevent false matches?

Matches were not based on raw title equality alone. The pipeline normalized titles and platform names and considered additional evidence such as platform and release year. Ambiguous results were designed to be reviewed rather than silently accepted.

## Why are the matching weights heuristic?

The weights make the decision process transparent and tunable. In a production system, they should be calibrated against a labeled validation set and evaluated with precision/recall or ranking metrics.

## What happens when sources disagree?

Observations retain their source. Consensus is weighted and can require both a confidence threshold and a minimum number of agreeing sources. If those conditions are not met, the value is deferred to the review queue.

## Why not publish the original dataset?

The original project used archive data that should not be redistributed as part of a public job portfolio. This repository therefore uses synthetic records while preserving the architecture and algorithms.

## What would you improve next?

- build a larger hand-reviewed evaluation set
- measure entity-resolution precision/recall
- add caching and rate limiting for live source adapters
- add retry/backoff and observability around HTTP clients
- model source-specific field reliability more rigorously
- persist provenance and review decisions in a database
