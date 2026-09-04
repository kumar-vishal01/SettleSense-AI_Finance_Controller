"""Phase 6 benchmark evaluation: metrics contract, denominators, artifacts,
false-positive identification, and ground-truth isolation."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from generate_data import DatasetSpec, generate_dataset, write_dataset
from run_benchmark import run_benchmark

SEED = 42
BATCH_DATE = datetime(2026, 8, 20, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    ds = generate_dataset(DatasetSpec(), SEED, BATCH_DATE)
    write_dataset(ds, DatasetSpec(), SEED, data)
    out = tmp_path_factory.mktemp("evaluation")
    return run_benchmark(data, out_dir=out)


class TestMetricContract:
    def test_every_required_metric_present_with_expected_values(self, report):
        assert report["total_records"] == 100
        assert report["records_processed"] == 100
        assert report["correctly_matched"] == 71
        assert report["automatic_matches"] == 71
        assert report["match_rate"] == 0.71
        assert report["precision"] == 1.0
        assert report["recall"] == 1.0
        assert report["exception_capture_rate"] == 1.0
        assert report["monetary_variance_paise"] == -150_000
        assert report["max_monetary_variance_paise"] == 120_000
        assert report["processing_time_ms"] > 0
        assert report["records_per_second"] > 0
        assert report["false_automatic_matches"] == []
        assert report["seed"] == SEED
        assert report["dataset_version"] == "synthetic-v2"

    def test_denominators_are_documented_in_code(self):
        import inspect
        from backend import metrics
        doc = inspect.getdoc(metrics.evaluate_against_ground_truth) + inspect.getdoc(metrics.summarize)
        for term in ("precision", "recall", "match rate", "exception capture"):
            assert term.lower() in doc.lower()

    def test_unresolved_high_value_queue(self, report):
        queue = report["unresolved_high_value_cases"]
        assert queue, "dataset has high-value exceptions; queue must not be empty"
        exposures = [case["exposure_paise"] for case in queue]
        assert exposures == sorted(exposures, reverse=True)
        assert all(c["requires_review"] for c in queue)
        assert all(c["exposure_paise"] >= 1_000_000 for c in queue)  # threshold


class TestFalsePositiveIdentification:
    def test_false_positives_are_detailed_not_just_counted(self):
        from backend.metrics import evaluate_against_ground_truth
        from backend.models import ReconciliationResult, ReconciliationStatus
        results = [
            ReconciliationResult(payment_id="p1", status=ReconciliationStatus.FULLY_RECONCILED,
                                 confidence=0.99, match_method="payment_id + utr",
                                 reason="ok", evidence=["p1"], settlement_id="WRONG_S",
                                 bank_txn_id="WRONG_B"),
            ReconciliationResult(payment_id="p2", status=ReconciliationStatus.FULLY_RECONCILED,
                                 confidence=0.99, match_method="payment_id + utr",
                                 reason="ok", evidence=["p2"], settlement_id="s2",
                                 bank_txn_id="b2"),
        ]
        gt = [
            {"payment_id": "p1", "expected_status": "FULLY_RECONCILED",
             "expected_settlement_id": "s1", "expected_bank_txn_id": "b1",
             "scenario": "clean"},
            {"payment_id": "p2", "expected_status": "FULLY_RECONCILED",
             "expected_settlement_id": "s2", "expected_bank_txn_id": "b2",
             "scenario": "clean"},
        ]
        report = evaluate_against_ground_truth(results, gt, "test")
        assert report.false_auto_matches == 1
        details = report.false_positive_details
        assert len(details) == 1
        assert details[0]["payment_id"] == "p1"
        assert details[0]["expected_status"] == "FULLY_RECONCILED"
        assert details[0]["expected_settlement_id"] == "s1"
        assert details[0]["linked_settlement_id"] == "WRONG_S"
        assert details[0]["expected_bank_txn_id"] == "b1"
        assert details[0]["linked_bank_txn_id"] == "WRONG_B"
        # a mismatched-status anomaly that got auto-matched is also a FP
        assert report.precision == 0.5  # 1 correct of 2 runtime auto-matches

    def test_false_positives_separate_from_unresolved(self, report):
        # unresolved = review-flagged runtime results; FPs = wrong auto-matches
        assert report["false_automatic_matches"] == []
        assert report["exception_count"] == 29


class TestArtifacts:
    def test_json_and_markdown_written(self, tmp_path_factory):
        data = tmp_path_factory.mktemp("data2")
        ds = generate_dataset(DatasetSpec(), SEED, BATCH_DATE)
        write_dataset(ds, DatasetSpec(), SEED, data)
        out = tmp_path_factory.mktemp("eval2")
        run_benchmark(data, out_dir=out)
        json_path = out / "report.json"
        md_path = out / "report.md"
        assert json_path.exists() and md_path.exists()
        parsed = json.loads(json_path.read_text())
        assert parsed["total_records"] == 100
        md = md_path.read_text()
        for section in ("# SettleSense Benchmark Report", "## Metrics",
                        "## Denominators", "## Scenario capture",
                        "## False automatic matches", "## Exception queue",
                        "## High-value unresolved cases"):
            assert section in md, section

    def test_markdown_contains_full_exception_list(self, tmp_path_factory):
        data = tmp_path_factory.mktemp("data3")
        ds = generate_dataset(DatasetSpec(), SEED, BATCH_DATE)
        write_dataset(ds, DatasetSpec(), SEED, data)
        out = tmp_path_factory.mktemp("eval3")
        run_benchmark(data, out_dir=out)
        md = (out / "report.md").read_text()
        # all 29 exceptions appear as table rows
        data_dir = data
        with open(data_dir / "ground_truth.csv", newline="") as fh:
            exception_ids = {r["payment_id"] for r in csv.DictReader(fh)
                             if r["expected_status"] != "FULLY_RECONCILED"}
        for pid in exception_ids:
            assert pid in md

    def test_reproducible_from_fixed_seed(self, tmp_path_factory):
        runs = []
        for i in range(2):
            data = tmp_path_factory.mktemp(f"repro{i}")
            ds = generate_dataset(DatasetSpec(), SEED, BATCH_DATE)
            write_dataset(ds, DatasetSpec(), SEED, data)
            out = tmp_path_factory.mktemp(f"out{i}")
            r = run_benchmark(data, out_dir=out)
            runs.append({k: v for k, v in r.items()
                         if k not in ("processing_time_ms", "records_per_second")})
        assert runs[0] == runs[1]


class TestGroundTruthIsolation:
    def test_ground_truth_never_enters_runtime_tables(self, report):
        # structural: the runtime pipeline receives only the three source
        # files; ground truth is loaded by the benchmark itself
        import inspect
        import run_benchmark
        source = inspect.getsource(run_benchmark.run_benchmark)
        assert "ground_truth" in source  # loaded here, in evaluation only
        import backend.reconciliation
        engine_source = inspect.getsource(backend.reconciliation)
        assert "ground_truth" not in engine_source
