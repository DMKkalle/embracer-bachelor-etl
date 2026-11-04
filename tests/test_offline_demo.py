from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_offline_demo_reproduces_pipeline_contracts() -> None:
    result = subprocess.run(
        [sys.executable, "src/run_demo.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    editions = pd.read_csv(ROOT / "data/outputs/editions.csv", dtype=str).fillna("")
    releases = pd.read_csv(ROOT / "data/outputs/releases.csv", dtype=str).fillna("")
    master = pd.read_csv(
        ROOT / "data/outputs/editions_enriched_master.csv", dtype=str
    ).fillna("")
    catalog = pd.read_csv(
        ROOT / "data/outputs/catalog_enriched_embracer.csv", dtype=str
    ).fillna("")

    assert editions.shape == (3, 4)
    assert releases.shape == (3, 7)
    assert master.shape[0] == 3
    assert catalog.shape == (3, 24)

    assert set(editions["platform"]) == {"SNES", "SFC", "MD"}
    assert set(editions["region"]) == {"PAL", "NTSC-J"}
    assert set(catalog["info_confidence_flag"]) == {"high", "low"}


def test_edition_ids_are_deterministic_for_demo_input() -> None:
    editions = pd.read_csv(ROOT / "data/outputs/editions.csv", dtype=str).fillna("")
    expected = {
        "Chronicles III": "ED-AD3B4385D9",
        "Example Quest II": "ED-6723A1FECC",
        "星の冒険": "ED-2D26B0CE38",
    }
    assert dict(zip(editions["title_primary"], editions["edition_id"], strict=True)) == expected
