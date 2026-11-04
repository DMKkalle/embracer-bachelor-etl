from __future__ import annotations

import pandas as pd


def quality_summary(frame: pd.DataFrame) -> dict[str, int]:
    summary = {
        "rows": len(frame),
        "duplicate_object_numbers": 0,
        "unknown_platforms": 0,
        "unknown_regions": 0,
        "unknown_languages": 0,
    }

    if "object_number" in frame:
        summary["duplicate_object_numbers"] = int(
            frame["object_number"].astype(str).duplicated().sum()
        )
    if "platform_norm" in frame:
        summary["unknown_platforms"] = int((frame["platform_norm"] == "UNKNOWN").sum())
    if "region_norm" in frame:
        summary["unknown_regions"] = int((frame["region_norm"] == "UNKNOWN").sum())
    if "language_norm" in frame:
        summary["unknown_languages"] = int(
            (frame["language_norm"] == "unknown").sum()
        )

    return summary
