from embracer_etl.normalization import (
    choose_canonical_title,
    infer_region,
    normalize_language,
    normalize_platform,
    normalize_punctuation,
    split_alternative_titles,
)


def test_normalizes_typographic_punctuation():
    assert normalize_punctuation("Game —  Special   Edition") == "Game - Special Edition"


def test_chooses_ascii_alternative_for_non_ascii_primary():
    alternatives = split_alternative_titles("Star Adventure|Hoshi no Bouken")
    title, source = choose_canonical_title("星の冒険", alternatives)

    assert title == "Star Adventure"
    assert source == "alternative_ascii"


def test_normalizes_language_to_short_code():
    assert normalize_language("Japanese;Japanese") == "ja"
    assert normalize_language(None) == "unknown"


def test_region_prefers_explicit_broadcast_standard():
    assert infer_region("NTSC-J", "Sweden") == "NTSC-J"


def test_region_can_be_inferred_from_country():
    assert infer_region("", "Sweden") == "PAL"


def test_platform_rules_support_aliases_and_regex():
    rules = {
        "exact_map": {"Nintendo Super Famicom": "SFC"},
        "alias_map": {"SNES": ["Super Nintendo Entertainment System"]},
        "regex_map": [{"pattern": "(?i)game\\s*boy", "code": "GB"}],
    }

    assert normalize_platform("Nintendo Super Famicom", rules) == "SFC"
    assert normalize_platform("Super Nintendo Entertainment System", rules) == "SNES"
    assert normalize_platform("Nintendo Game Boy", rules) == "GB"
