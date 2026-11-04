from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gb_enrich_editions import numbers_compatible
from gb_enrich_editions import pick_best_hit as gb_pick_best_hit
from igdb_enrich_editions import pick_best_hit as igdb_pick_best_hit


def test_igdb_prefers_platform_match_before_rating() -> None:
    hits = [
        {
            "name": "Chronicles III",
            "aggregated_rating": 99,
            "platforms": [{"name": "PC (Microsoft Windows)"}],
        },
        {
            "name": "Chronicles III",
            "aggregated_rating": 70,
            "platforms": [{"name": "Super Nintendo Entertainment System"}],
        },
    ]

    best, confidence = igdb_pick_best_hit("Chronicles III", "SNES", hits)

    assert best is hits[1]
    assert confidence == "1/2"


def test_giantbomb_rejects_a_different_numbered_sequel() -> None:
    aliases = {"MD": ["Sega Mega Drive", "Genesis"]}
    hits = [
        {
            "name": "Example Quest III",
            "platforms": [{"name": "Sega Mega Drive"}],
        },
        {
            "name": "Example Quest II",
            "platforms": [{"name": "Sega Mega Drive"}],
        },
    ]

    best, signals = gb_pick_best_hit("Example Quest II", "MD", hits, aliases)

    assert best is hits[1]
    assert signals == (1, 4)
    assert numbers_compatible("Example Quest II", "Example Quest 2") is True
    assert numbers_compatible("Example Quest II", "Example Quest III") is False
