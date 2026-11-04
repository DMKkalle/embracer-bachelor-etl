import pandas as pd

from embracer_etl.pipeline import normalize_catalog
from embracer_etl.quality import quality_summary


def test_normalize_catalog_with_synthetic_data():
    frame = pd.DataFrame(
        [
            {
                "object_number": "1001",
                "title_primary": "星の冒険",
                "alt_titles": "Star Adventure",
                "platform_raw": "Super Nintendo",
                "broadcast_standard": "NTSC-J",
                "place_of_publication": "Japan",
                "title_language": "Japanese",
            }
        ]
    )
    rules = {
        "exact_map": {},
        "alias_map": {"SNES": ["Super Nintendo"]},
        "regex_map": [],
    }

    result = normalize_catalog(frame, rules)

    assert result.loc[0, "title_norm"] == "Star Adventure"
    assert result.loc[0, "platform_norm"] == "SNES"
    assert result.loc[0, "region_norm"] == "NTSC-J"
    assert result.loc[0, "language_norm"] == "ja"

    assert quality_summary(result) == {
        "rows": 1,
        "duplicate_object_numbers": 0,
        "unknown_platforms": 0,
        "unknown_regions": 0,
        "unknown_languages": 0,
    }
