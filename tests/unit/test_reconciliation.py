"""Status decisions and financial rules (AGENTS.md sections 4-5)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from backend.config import ReconciliationConfig
from backend.models import ReconciliationStatus, Severity
from backend.reconciliation import reconcile_batch
from tests.factories import (
    DEFAULT_NET,
    AS_OF,
    T1,
    T2,
    bank_entry,
    ledger_txn,
    settlement_txn,
)

CFG = ReconciliationConfig()


def _single(payment_row, settlements, bank, config=CFG, as_of=AS_OF):
    outcome = reconcile_batch([payment_row], settlements, bank, config, as_of)
    assert len(outcome.results) == 1
    return outcome.results[0]


class TestFullyReconciled:
    def test_happy_path(self):
        result = _single(
            ledger_txn(),
            [settlement_txn()],
            [bank_entry(credit=DEFAULT_NET)],
        )
        assert result.status is ReconciliationStatus.FULLY_RECONCILED
        assert result.confidence == 0.99
        assert result.expected_amount_paise == DEFAULT_NET
        assert result.actual_amount_paise == DEFAULT_NET
        assert result.variance_paise == 0
        assert result.severity is Severity.NONE
        assert result.requires_review is False
        assert "pay_001" in result.evidence
        assert "setl_001" in result.evidence
        assert "bank_001" in result.evidence
        assert result.match_method.startswith("payment_id + ")

    def test_variance_exactly_at_tolerance_still_reconciles(self):
        result = _single(
            ledger_txn(),
            [settlement_txn()],
            [bank_entry(credit=DEFAULT_NET - CFG.amount_tolerance_paise)],
        )
        assert result.status is ReconciliationStatus.FULLY_RECONCILED

    def test_waterfall_with_refund_and_adjustment(self):
        result = _single(
            ledger_txn(),
            [
                settlement_txn(gross=100_000, fee=2_000, tax=360),
                settlement_txn(entity_id="ent_001_r", gross=0, fee=0, tax=0, debit=30_000),
                settlement_txn(entity_id="ent_001_a", gross=0, fee=0, tax=0, credit=400),
            ],
            [bank_entry(credit=68_040)],
        )
        assert result.status is ReconciliationStatus.FULLY_RECONCILED
        assert result.expected_amount_paise == 68_040

    def test_result_records_the_waterfall_inputs(self):
        """H3: formula inputs must survive into the result for audit
        (ARCHITECTURE.md 3.5: record the formula inputs in the evidence)."""
        result = _single(
            ledger_txn(),
            [
                settlement_txn(gross=100_000, fee=2_000, tax=360),
                settlement_txn(entity_id="ent_001_r", gross=0, fee=0, tax=0, debit=30_000),
                settlement_txn(entity_id="ent_001_a", gross=0, fee=0, tax=0, credit=400),
            ],
            [bank_entry(credit=68_040)],
        )
        breakdown = result.expected_breakdown_paise
        assert breakdown == {
            "gross_amount_paise": 100_000,
            "fee_paise": 2_000,
            "tax_paise": 360,
            "debit_paise": 30_000,
            "credit_paise": 400,
        }
        recomputed = (
            breakdown["gross_amount_paise"] - breakdown["fee_paise"]
            - breakdown["tax_paise"] - breakdown["debit_paise"]
            + breakdown["credit_paise"]
        )
        assert recomputed == result.expected_amount_paise == 68_040
        assert result.to_contract_dict()["expected_breakdown_paise"] == breakdown

    def test_order_id_link_path(self):
        result = _single(
            ledger_txn(payment_id="pay_001", order_id="order_001"),
            [settlement_txn(payment_id=None, entity_id="ent_001", order_id="order_001")],
            [bank_entry(utr=None, credit=DEFAULT_NET, description="NEFT CR SETTL setl_001")],
        )
        assert result.status is ReconciliationStatus.FULLY_RECONCILED
        assert result.match_method.startswith("order_id + ")
        assert result.confidence <= 0.92  # description reference capped


class TestMissingStatuses:
    def test_missing_in_settlement(self):
        result = _single(ledger_txn(), [], [])
        assert result.status is ReconciliationStatus.MISSING_IN_SETTLEMENT
        assert result.severity is Severity.HIGH
        assert result.expected_amount_paise == 100_000  # ledger amount as expectation

    def test_missing_bank_credit_when_old(self):
        old = AS_OF - timedelta(days=6)
        result = _single(
            ledger_txn(at=old - timedelta(days=2)),
            [settlement_txn(at=old)],
            [],
        )
        assert result.status is ReconciliationStatus.MISSING_BANK_CREDIT

    def test_timing_delay_when_recent(self):
        recent = AS_OF - timedelta(days=1)
        result = _single(
            ledger_txn(at=recent - timedelta(days=2)),
            [settlement_txn(at=recent)],
            [],
        )
        assert result.status is ReconciliationStatus.TIMING_DELAY
        assert result.severity is Severity.MEDIUM


class TestAmountMismatch:
    def test_short_credit_is_mismatch_with_negative_variance(self):
        result = _single(
            ledger_txn(),
            [settlement_txn()],
            [bank_entry(credit=DEFAULT_NET - 30_000)],
        )
        assert result.status is ReconciliationStatus.AMOUNT_MISMATCH
        assert result.variance_paise == -30_000
        assert result.actual_amount_paise == DEFAULT_NET - 30_000
        assert result.severity is Severity.MEDIUM
        assert "INR 300.00 lower" in result.reason

    def test_large_variance_is_high_severity(self):
        result = _single(
            ledger_txn(),
            [settlement_txn()],
            [bank_entry(credit=DEFAULT_NET - 150_000)],
        )
        assert result.status is ReconciliationStatus.AMOUNT_MISMATCH
        assert result.severity is Severity.HIGH

    def test_small_variance_is_low_severity(self):
        result = _single(
            ledger_txn(),
            [settlement_txn()],
            [bank_entry(credit=DEFAULT_NET - 150)],
        )
        assert result.status is ReconciliationStatus.AMOUNT_MISMATCH
        assert result.severity is Severity.LOW


class TestDuplicates:
    def test_duplicate_ledger_rows(self):
        outcome = reconcile_batch(
            [ledger_txn(row_id="int_001"), ledger_txn(row_id="int_002")],
            [settlement_txn()],
            [bank_entry()],
            CFG, AS_OF,
        )
        result = outcome.results[0]
        assert result.status is ReconciliationStatus.DUPLICATE
        assert "int_001" in result.evidence and "int_002" in result.evidence
        # one result per logical payment despite two rows
        assert len(outcome.results) == 1

    def test_duplicate_bank_utr(self):
        result = _single(
            ledger_txn(),
            [settlement_txn()],
            [bank_entry(txn_id="bank_001"), bank_entry(txn_id="bank_002")],
        )
        assert result.status is ReconciliationStatus.DUPLICATE

    def test_duplicate_settlement_entity(self):
        result = _single(
            ledger_txn(),
            [
                settlement_txn(entity_id="ent_001", settlement_id="setl_001"),
                settlement_txn(entity_id="ent_001", settlement_id="setl_001"),
            ],
            [bank_entry()],
        )
        assert result.status is ReconciliationStatus.DUPLICATE


class TestNeedsHumanReview:
    def test_ambiguous_amount_date_candidates(self):
        result = _single(
            ledger_txn(),
            [settlement_txn(utr=None)],
            [
                bank_entry(txn_id="bank_a", utr=None, at=T2, description="NEFT CR-EXTERNAL"),
                bank_entry(txn_id="bank_b", utr=None, at=T2, description="NEFT CR-EXTERNAL"),
            ],
        )
        assert result.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert result.requires_review is True
        assert "bank_a" in result.evidence and "bank_b" in result.evidence

    def test_unique_weak_candidate_still_requires_review(self):
        result = _single(
            ledger_txn(),
            [settlement_txn(utr=None)],
            [bank_entry(txn_id="bank_a", utr=None, at=T2, description="NEFT CR-EXTERNAL")],
        )
        assert result.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert "bank_a" in result.evidence


class TestContestedEvidence:

    def test_ledger_row_without_payment_id_is_visible_not_silent(self):
        """M1: rows lacking a payment_id must surface for review instead of
        disappearing from the batch."""
        from datetime import datetime, timezone

        from backend.models import CanonicalTransaction, Source, TransactionType
        orphan = CanonicalTransaction(
            source=Source.INTERNAL_LEDGER, source_row_id="int_orphan",
            transaction_type=TransactionType.PAYMENT, payment_id=None,
            order_id="order_orphan", gross_amount_paise=100_000,
            transaction_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            raw_payload={"internal_id": "int_orphan"},
        )
        outcome = reconcile_batch(
            [orphan], [settlement_txn()], [bank_entry()], CFG, AS_OF
        )
        assert len(outcome.results) == 1
        result = outcome.results[0]
        assert result.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert result.requires_review is True
        assert "no payment_id" in result.reason
        assert "int_orphan" in result.evidence

    def test_shared_utr_cannot_double_match_one_bank_entry(self):
        ledger = [
            ledger_txn(payment_id="pay_a", order_id="order_a", row_id="int_a"),
            ledger_txn(payment_id="pay_b", order_id="order_b", row_id="int_b"),
        ]
        settlements = [
            settlement_txn(payment_id="pay_a", entity_id="ent_a",
                           settlement_id="setl_a", utr="UTRSHARED", order_id="order_a"),
            settlement_txn(payment_id="pay_b", entity_id="ent_b",
                           settlement_id="setl_b", utr="UTRSHARED", order_id="order_b"),
        ]
        bank = [bank_entry(txn_id="bank_x", utr="UTRSHARED", credit=DEFAULT_NET,
                           description="NEFT CR-EXTERNAL")]
        results = reconcile_batch(ledger, settlements, bank, CFG, AS_OF).results
        assert {r.status for r in results} == {ReconciliationStatus.NEEDS_HUMAN_REVIEW}
        assert all(r.requires_review for r in results)
        assert all(r.severity is Severity.HIGH for r in results)

    def test_shared_order_id_settlement_row_cannot_be_claimed_twice(self):
        ledger = [
            ledger_txn(payment_id="pay_a", order_id="order_shared", row_id="int_a"),
            ledger_txn(payment_id="pay_b", order_id="order_shared", row_id="int_b"),
        ]
        settlements = [
            settlement_txn(payment_id=None, entity_id="ent_s", settlement_id="setl_s",
                           order_id="order_shared", utr="UTRS"),
        ]
        bank = [bank_entry(txn_id="bank_x", utr="UTRS", credit=DEFAULT_NET,
                           description="NEFT CR-EXTERNAL")]
        results = reconcile_batch(ledger, settlements, bank, CFG, AS_OF).results
        assert {r.status for r in results} == {ReconciliationStatus.NEEDS_HUMAN_REVIEW}
        assert all(r.requires_review for r in results)


class TestDeterminismAndSafety:
    def test_same_inputs_same_outputs(self):
        ledger = [ledger_txn()]
        settlements = [settlement_txn()]
        bank = [bank_entry()]
        first = reconcile_batch(ledger, settlements, bank, CFG, AS_OF)
        second = reconcile_batch(ledger, settlements, bank, CFG, AS_OF)
        assert first.results == second.results  # idempotent by construction

    def test_as_of_drives_timing_classification(self):
        settled = AS_OF - timedelta(days=4)
        payment = ledger_txn(at=settled - timedelta(days=2))
        settlements = [settlement_txn(at=settled)]
        next_day = _single(payment, settlements, [], as_of=settled + timedelta(days=1))
        much_later = _single(payment, settlements, [], as_of=AS_OF)
        assert next_day.status is ReconciliationStatus.TIMING_DELAY
        assert much_later.status is ReconciliationStatus.MISSING_BANK_CREDIT

    def test_evidence_never_contains_empty_strings(self):
        result = _single(ledger_txn(), [settlement_txn(utr=None)], [])
        assert all(e for e in result.evidence)

    def test_wrong_source_rows_rejected_loudly(self):
        # settlement rows must never be passed as the ledger input
        with pytest.raises(ValueError, match="ledger input"):
            reconcile_batch([settlement_txn()], [], [], CFG, AS_OF)


class TestDisplayFormatting:
    def test_paise_to_rupees_string_is_exact(self):
        from backend.calculations import format_paise_as_rupees
        assert format_paise_as_rupees(30_000) == "300.00"
        assert format_paise_as_rupees(1) == "0.01"
        assert format_paise_as_rupees(0) == "0.00"
        assert format_paise_as_rupees(-105) == "-1.05"
        assert format_paise_as_rupees(123_456_789_012) == "1234567890.12"


class TestFutureDatedRows:
    def test_future_dated_settlement_explains_itself(self):
        future = AS_OF + timedelta(days=2)
        result = _single(
            ledger_txn(at=future - timedelta(days=1)),
            [settlement_txn(at=future)],
            [],
        )
        assert result.status is ReconciliationStatus.TIMING_DELAY
        assert "future-dated" in result.reason
        assert "settled -" not in result.reason


class TestNoWallClock:
    def test_empty_batch_raises_instead_of_fabricating_as_of(self):
        """L5: no code path may substitute the wall clock for data."""
        with pytest.raises(ValueError, match="as_of"):
            reconcile_batch([], [], [], CFG)
