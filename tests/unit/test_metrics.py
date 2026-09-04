"""Metrics: runtime summary + ground-truth evaluation separation."""

from __future__ import annotations

from backend.metrics import evaluate_against_ground_truth, exception_queue, summarize
from backend.models import ReconciliationResult, ReconciliationStatus, Severity
from tests.factories import DEFAULT_NET


def _result(payment_id, status, settlement_id=None, bank_txn_id=None, variance=None):
    return ReconciliationResult(
        payment_id=payment_id,
        status=status,
        confidence=0.9,
        match_method="test",
        expected_amount_paise=DEFAULT_NET,
        actual_amount_paise=DEFAULT_NET + variance if variance is not None else None,
        variance_paise=variance,
        severity=Severity.MEDIUM if status is not ReconciliationStatus.FULLY_RECONCILED else Severity.NONE,
        reason="test",
        evidence=[payment_id],
        requires_review=status is not ReconciliationStatus.FULLY_RECONCILED,
        settlement_id=settlement_id,
        bank_txn_id=bank_txn_id,
    )


class TestSummarize:
    def test_counts_and_match_rate(self):
        results = [
            _result("p1", ReconciliationStatus.FULLY_RECONCILED, "s1", "b1"),
            _result("p2", ReconciliationStatus.FULLY_RECONCILED, "s2", "b2"),
            _result("p3", ReconciliationStatus.AMOUNT_MISMATCH, variance=-30_000),
            _result("p4", ReconciliationStatus.TIMING_DELAY),
        ]
        s = summarize(results)
        assert s.total_records == 4
        assert s.fully_reconciled == 2
        assert s.exceptions == 2
        assert s.match_rate == 0.5
        assert s.total_variance_paise == -30_000
        assert s.max_abs_variance_paise == 30_000
        assert s.status_counts["AMOUNT_MISMATCH"] == 1

    def test_exception_queue_orders_by_severity_then_exposure(self):
        results = [
            _result("p_low", ReconciliationStatus.TIMING_DELAY),          # medium
            _result("p_mid", ReconciliationStatus.AMOUNT_MISMATCH, variance=-5_000),
            _result("p_big", ReconciliationStatus.AMOUNT_MISMATCH, variance=-500_000),
        ]
        queue = exception_queue(results)
        assert [r.payment_id for r in queue] == ["p_big", "p_mid", "p_low"]


class TestEvaluation:
    GT = [
        {"payment_id": "p1", "expected_status": "FULLY_RECONCILED",
         "expected_settlement_id": "s1", "expected_bank_txn_id": "b1",
         "expected_variance_paise": "0", "scenario": "clean",
         "expected_review_flag": "false"},
        {"payment_id": "p2", "expected_status": "MISSING_BANK_CREDIT",
         "expected_settlement_id": "", "expected_bank_txn_id": "",
         "expected_variance_paise": "0", "scenario": "missing_bank_credit",
         "expected_review_flag": "true"},
    ]

    def test_perfect_run(self):
        results = [
            _result("p1", ReconciliationStatus.FULLY_RECONCILED, "s1", "b1"),
            _result("p2", ReconciliationStatus.MISSING_BANK_CREDIT),
        ]
        report = evaluate_against_ground_truth(results, self.GT, "test-v1")
        assert report.precision == 1.0
        assert report.recall == 1.0
        assert report.false_auto_matches == 0
        assert report.exception_capture_rate == 1.0
        assert report.status_mismatches == []
        assert report.scenario_totals == {"clean": 1, "missing_bank_credit": 1}
        assert report.scenario_captured == {"clean": 1, "missing_bank_credit": 1}

    def test_false_auto_match_detected(self):
        results = [
            _result("p1", ReconciliationStatus.FULLY_RECONCILED, "s1", "WRONG_BANK"),
            _result("p2", ReconciliationStatus.FULLY_RECONCILED),  # auto-matched an anomaly
        ]
        report = evaluate_against_ground_truth(results, self.GT, "test-v1")
        assert report.precision == 0.0
        assert report.false_auto_matches == 2
        assert report.recall == 0.0

    def test_status_mismatch_recorded(self):
        results = [
            _result("p1", ReconciliationStatus.FULLY_RECONCILED, "s1", "b1"),
            _result("p2", ReconciliationStatus.TIMING_DELAY),
        ]
        report = evaluate_against_ground_truth(results, self.GT, "test-v1")
        assert report.exception_capture_rate == 0.0
        assert report.status_mismatches == [
            {"payment_id": "p2", "expected": "MISSING_BANK_CREDIT", "actual": "TIMING_DELAY"}
        ]

    def test_missing_result_recorded(self):
        report = evaluate_against_ground_truth([], self.GT, "test-v1")
        assert len(report.status_mismatches) == 2
        assert all(m["actual"] == "MISSING_RESULT" for m in report.status_mismatches)
