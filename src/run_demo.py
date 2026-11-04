from __future__ import annotations

import shutil
import sys
from pathlib import Path

from run_pipeline import ROOT, clean_outputs, run_step

FIXTURES = ROOT / "demo" / "fixtures" / "enrichment"
ENRICHMENT_OUT = ROOT / "data" / "outputs" / "enrichment"


def install_recorded_fixtures() -> None:
    ENRICHMENT_OUT.mkdir(parents=True, exist_ok=True)
    for name in [
        "igdb_enrichment.csv",
        "giantbomb_enrichment.csv",
        "wikidata_enrichment.csv",
        "wikipedia_enrichment.csv",
    ]:
        source = FIXTURES / name
        if not source.exists():
            raise SystemExit(f"Missing demo fixture: {source}")
        shutil.copy2(source, ENRICHMENT_OUT / name)


def main() -> None:
    """Run the real final pipeline structure without requiring external API keys.

    Normalization, edition/release construction, merge, export and QA use the
    final thesis implementation. Only the four external enrichment calls are
    replaced by recorded synthetic fixtures with the same CSV contracts.
    """

    clean_outputs()

    run_step("normalize_one", [sys.executable, "src/normalize_one.py"])
    run_step("build_releases", [sys.executable, "src/build_releases.py"])

    print("\n" + "=" * 80)
    print("▶ install_recorded_enrichment_fixtures")
    print("   Offline demo: replacing live API calls with synthetic recorded results")
    print("=" * 80)
    install_recorded_fixtures()
    print("✅ Klart: recorded enrichment fixtures installed")

    run_step(
        "merge_enriched",
        [
            sys.executable,
            "src/merge_enriched.py",
            "--gb",
            "data/outputs/enrichment/giantbomb_enrichment.csv",
            "--igdb",
            "data/outputs/enrichment/igdb_enrichment.csv",
            "--wikidata",
            "data/outputs/enrichment/wikidata_enrichment.csv",
            "--wikipedia",
            "data/outputs/enrichment/wikipedia_enrichment.csv",
            "--out",
            "data/outputs/editions_enriched_master.csv",
        ],
    )

    run_step(
        "export_enriched_catalog",
        [
            sys.executable,
            "src/export_enriched_catalog.py",
            "--catalog",
            "data/raw/sample_catalog.csv",
            "--links",
            "data/outputs/items_to_editions.csv",
            "--master",
            "data/outputs/editions_enriched_master.csv",
            "--out",
            "data/outputs/catalog_enriched_embracer.csv",
        ],
    )

    run_step("qa_report", [sys.executable, "src/qa_report.py"])

    print("\n🎉 OFFLINE DEMO KLAR!")
    print("   Inspect: data/outputs/catalog_enriched_embracer.csv")
    print("   Inspect: data/outputs/editions_enriched_master.csv")
    print("   Inspect: data/outputs/qa/")


if __name__ == "__main__":
    main()
