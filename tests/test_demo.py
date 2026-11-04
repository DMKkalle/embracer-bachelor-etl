from pathlib import Path

from embracer_etl.demo import run_demo


def test_end_to_end_demo_writes_auditable_outputs(tmp_path: Path):
    summary = run_demo(
        Path("examples/sample_catalog.csv"),
        platform_config=Path("configs/platform_map.yaml"),
        source_config=Path("configs/source_weights.yaml"),
        output_dir=tmp_path,
    )

    assert summary["records"] == 4
    assert summary["review_queue_size"] >= 1
    assert (tmp_path / "normalized_catalog.csv").exists()
    assert (tmp_path / "consensus.csv").exists()
    assert (tmp_path / "provenance.csv").exists()
    assert (tmp_path / "review_queue.csv").exists()
    assert (tmp_path / "summary.json").exists()
