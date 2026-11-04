from embracer_etl.matching import (
    clean_title_for_match,
    name_variants,
    score_candidate,
)


def test_name_variants_bridge_roman_and_arabic_numbers():
    variants = name_variants("Example Quest II")

    assert "example quest ii" in variants
    assert "example quest 2" in variants


def test_clean_title_removes_edition_noise():
    assert clean_title_for_match("Speed Racer - Limited Edition") == "speed racer"


def test_exact_multi_signal_match_scores_highly():
    signals = score_candidate(
        edition_title="Example Quest II",
        edition_platform="SNES",
        edition_year=1993,
        candidate_title="Example Quest 2",
        candidate_platform="Super Nintendo Entertainment System",
        candidate_year=1993,
    )

    assert signals.title == 1.0
    assert signals.platform == 1.0
    assert signals.year == 1.0
    assert signals.weighted_score == 1.0


def test_year_distance_reduces_score():
    close = score_candidate(
        "Example Quest",
        "SNES",
        1993,
        "Example Quest",
        "SNES",
        1994,
    )
    far = score_candidate(
        "Example Quest",
        "SNES",
        1993,
        "Example Quest",
        "SNES",
        2001,
    )

    assert close.weighted_score > far.weighted_score
