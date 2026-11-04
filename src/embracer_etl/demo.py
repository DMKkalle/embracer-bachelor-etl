from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from embracer_etl.consensus import (
    SourceObservation,
    provenance_rows,
    weighted_consensus,
)
from embracer_etl.pipeline import normalize_catalog
from embracer_etl.quality import quality_summary


def load_source_weights(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    return {
        source: float(settings.get("base_weight", 0.0))
        for source, settings in config.get("sources", {}).items()
    }


def synthetic_observations(record_id: str) -> list[SourceObservation]:
    samples = {
        "1001": [
            SourceObservation("igdb", "release_year", "1993", 0.95),
            SourceObservation("wikidata", "release_year", "1993", 0.90),
            SourceObservation("giantbomb", "release_year", "1994", 0.70),
        ],
        "1002": [
            SourceObservation("igdb", "release_year", "1992", 0.90),
            SourceObservation("wikidata", "release_year", "1992", 0.95),
            SourceObservation("giantbomb", "release_year", "1992", 0.80),
        ],
        "1003": [
            SourceObservation("igdb", "release_year", "1995", 0.55),
            SourceObservation("wikidata", "release_year", "1996", 0.55),
        ],
        "1004": [
            SourceObservation("igdb", "release_year", "1994", 0.90),
            SourceObservation("wikidata", "release_year", "1994", 0.85),
        ],
    }
    return samples.get(record_id, [])


def run_demo(
    input_csv: Path,
    *,
    platform_config: Path,
    source_config: Path,
    output_dir: Path,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = pd.read_csv(input_csv, dtype=str).fillna("")
    with platform_config.open(encoding="utf-8") as handle:
        platform_rules = yaml.safe_load(handle) or {}

    normalized = normalize_catalog(frame, platform_rules)
    normalized_path = output_dir / "normalized_catalog.csv"
    normalized.to_csv(normalized_path, index=False)

    source_weights = load_source_weights(source_config)

    consensus_rows = []
    provenance = []
    review_rows = []

    for _, row in normalized.iterrows():
        record_id = str(row["object_number"])
        observations = synthetic_observations(record_id)

        provenance.extend(provenance_rows(record_id, observations))

        result = weighted_consensus(
            "release_year",
            observations,
            source_weights,
            accept_threshold=0.60,
            quorum_min_sources=2,
        )

        consensus_rows.append(
            {
                "object_number": record_id,
                "release_year": result.value or "",
                "confidence": result.confidence,
                "sources": "|".join(result.sources),
                "review_required": result.review_required,
                "review_reason": result.reason or "",
            }
        )

        if result.review_required:
            review_rows.append(consensus_rows[-1])

    pd.DataFrame(consensus_rows).to_csv(
        output_dir / "consensus.csv",
        index=False,
    )
    pd.DataFrame(provenance).to_csv(
        output_dir / "provenance.csv",
        index=False,
    )
    pd.DataFrame(review_rows).to_csv(
        output_dir / "review_queue.csv",
        index=False,
    )

    summary = {
        "quality": quality_summary(normalized),
        "records": len(normalized),
        "review_queue_size": len(review_rows),
        "outputs": {
            "normalized": str(normalized_path),
            "consensus": str(output_dir / "consensus.csv"),
            "provenance": str(output_dir / "provenance.csv"),
            "review_queue": str(output_dir / "review_queue.csv"),
        },
    }

    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the portfolio-safe end-to-end ETL demo."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("examples/sample_catalog.csv"),
    )
    parser.add_argument(
        "--platform-config",
        type=Path,
        default=Path("configs/platform_map.yaml"),
    )
    parser.add_argument(
        "--source-config",
        type=Path,
        default=Path("configs/source_weights.yaml"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("demo_output"),
    )
    args = parser.parse_args()

    print(
        json.dumps(
            run_demo(
                args.input,
                platform_config=args.platform_config,
                source_config=args.source_config,
                output_dir=args.output_dir,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
