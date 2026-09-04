"""End-to-end over the committed synthetic-v2 dataset: seeded dataset ->
full pipeline -> ground-truth evaluation (PRD section 9 success gate)."""

from __future__ import annotations

from pathlib import Path

from run_benchmark import run_benchmark

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

EXPECTED_STATUS_COUNTS = {
    "FULLY_RECONCILED": 71,
    "TIMING_DELAY": 10,
    "AMOUNT_MISMATCH": 6,
    "MISSING_IN_SETTLEMENT": 5,
    "MISSING_BANK_CREDIT": 4,
    "DUPLICATE": 3,
    "NEEDS_HUMAN_REVIEW": 1,
}

EXPECTED_TOTAL_VARIANCE_PAISE = sum(
    [-30_000, -45_000, -120_000, 15_000, -60_000, 90_000]
)


def test_committed_dataset_meets_success_gate(tmp_path):
    report = run_benchmark(DATA_DIR, out_dir=tmp_path)

    assert report["dataset_version"] == "synthetic-v2"
    assert report["total_records"] == 100
    assert report["records_processed"] == 100
    assert report["status_counts"] == EXPECTED_STATUS_COUNTS
    assert report["match_rate"] == 0.71

    assert report["false_automatic_matches"] == []
    assert report["precision"] == 1.0
    assert report["recall"] == 1.0
    assert report["exception_capture_rate"] == 1.0
    assert report["status_mismatches"] == []
    assert report["automatic_matches"] == 71
    assert report["exception_count"] == 29

    assert report["validation"]["skipped_rows"] == 0
    assert report["processing_time_ms"] > 0
    assert report["records_per_second"] > 0


def test_total_variance_is_exactly_the_planted_deltas(tmp_path):
    report = run_benchmark(DATA_DIR, out_dir=tmp_path)
    assert report["monetary_variance_paise"] == EXPECTED_TOTAL_VARIANCE_PAISE
    assert report["max_monetary_variance_paise"] == 120_000


def test_rerun_is_idempotent(tmp_path):
    first = run_benchmark(DATA_DIR, out_dir=tmp_path / "a")
    second = run_benchmark(DATA_DIR, out_dir=tmp_path / "b")
    for key in ("status_counts", "exceptions", "false_automatic_matches",
                "scenario_capture"):
        assert first[key] == second[key]
