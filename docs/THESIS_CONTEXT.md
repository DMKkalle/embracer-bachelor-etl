# Thesis context

## Problem

Game-preservation catalogues aggregate metadata created across decades, regions and databases. The same underlying game may have different titles, platform names, release dates, regions, languages and source-specific identifiers.

## Thesis project

The Bachelor thesis in Computer Science at Karlstad University was developed in collaboration with Embracer Games Archive.

The engineering work focused on:

1. normalizing archive metadata,
2. creating consistent edition/release representations,
3. enriching records from external sources,
4. linking external records to archive records,
5. retaining source provenance,
6. surfacing uncertain matches for review.

The working thesis pipeline processed more than 10,000 game editions.

## External sources

The original workflow experimented with and used metadata from sources including Wikidata, IGDB and GiantBomb. Exact source coverage varied by field and availability.

## What this public repository proves

This repository is a sanitized reconstruction rather than a dump of the thesis working directory.

A reviewer can run normalization on synthetic data, inspect entity-resolution logic, see external-source boundaries, run weighted consensus, inspect provenance, see ambiguous records routed to a review queue, and run the full test suite in CI.

## Data confidentiality

No raw Embracer archive export is included in the public repository. The original working repository remains private.
