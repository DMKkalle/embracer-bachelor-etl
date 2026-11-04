from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from embracer_etl.normalization import (
    choose_canonical_title,
    infer_region,
    load_platform_rules,
    normalize_language,
    normalize_platform,
    normalize_punctuation,
    split_alternative_titles,
)
from embracer_etl.quality import quality_summary


def normalize_catalog(frame: pd.DataFrame, platform_rules: dict) -> pd.DataFrame:
    output = frame.copy()

    normalized_titles: list[str] = []
    title_sources: list[str] = []
    aliases: list[str] = []

    for _, row in output.iterrows():
        primary = normalize_punctuation(row.get("title_primary"))
        alternatives = split_alternative_titles(row.get("alt_titles"))
        canonical, source = choose_canonical_title(primary, alternatives)

        normalized_titles.append(canonical)
        title_sources.append(source)
        aliases.append(
            "|".join(
                title
                for title in [primary, *alternatives]
                if title and title != canonical
            )
        )

    output["title_norm"] = normalized_titles
    output["title_norm_source"] = title_sources
    output["title_aliases"] = aliases

    platform_values = output.get(
        "platform_raw",
        pd.Series([""] * len(output), index=output.index),
    )
    output["platform_norm"] = [
        normalize_platform(value, platform_rules) for value in platform_values
    ]

    broadcast_values = output.get(
        "broadcast_standard",
        pd.Series([""] * len(output), index=output.index),
    )
    place_values = output.get(
        "place_of_publication",
        pd.Series([""] * len(output), index=output.index),
    )
    output["region_norm"] = [
        infer_region(broadcast, place, title)
        for broadcast, place, title in zip(
            broadcast_values,
            place_values,
            output["title_norm"],
            strict=True,
        )
    ]

    language_values = output.get(
        "title_language",
        pd.Series([""] * len(output), index=output.index),
    )
    output["language_norm"] = [
        normalize_language(value) for value in language_values
    ]

    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize a game metadata catalog using thesis-derived rules."
    )
    parser.add_argument("input_csv", type=Path)
    parser.add_argument(
        "--platform-config",
        type=Path,
        default=Path("configs/platform_map.yaml"),
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    frame = pd.read_csv(args.input_csv)
    rules = load_platform_rules(args.platform_config)

    normalized = normalize_catalog(frame, rules)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(args.output, index=False)

    print(json.dumps(quality_summary(normalized), indent=2))


if __name__ == "__main__":
    main()
