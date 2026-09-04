"""Phase 5 integration: every fixture scenario through the REAL pipeline
(CSV ingestion -> typed rows -> normalization -> engine), asserting the full
result contract per scenario. Ground truth is never used — expectations are
scenario definitions, not labels."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.config import ReconciliationConfig
from backend.ingestion import read_csv_source
from backend.models import ReconciliationStatus, Source
from backend.normalization import (
    normalize_bank_statement,
    normalize_internal_ledger,
    normalize_settlement_report,
)
from backend.reconciliation import reconcile_batch

AS_OF = datetime(2026, 8, 20, 23, 0, tzinfo=timezone.utc)
CFG = ReconciliationConfig()

LEDGER_HEADER = "internal_id,order_id,payment_id,created_at,amount_paise,currency,payment_status"
SETL_HEADER = ("entity_id,type,payment_id,order_id,settlement_id,settlement_utr,"
               "amount_paise,fee_paise,tax_paise,debit_paise,credit_paise,settled_at")
BANK_HEADER = "bank_txn_id,value_date,description,utr,credit_paise,debit_paise"

GROSS, FEE, TAX = 100_000, 2_000, 360
NET = GROSS - FEE - TAX  # 97_640


def _ledger(payment="pay_001", created="2026-08-10 09:00:00", amount=GROSS):
    return (
        f"{LEDGER_HEADER}\n"
        f"int_001,order_001,{payment},{created},{amount},INR,captured\n"
    )


def _settlement(*, utr="UTR001", fee=FEE, tax=TAX, debit=0, credit=0,
                settled="2026-08-11 09:00:00", extra_rows=(), amount=GROSS):
    rows = [
        f"ent_001,payment,pay_001,order_001,setl_001,{utr},{amount},{fee},{tax},"
        f"{debit},{credit},{settled}"
    ]
    rows.extend(extra_rows)
    return SETL_HEADER + "\n" + "\n".join(rows) + "\n"


def _bank(*, credit=NET, utr="UTR001", date="2026-08-12 10:00:00",
          description="NEFT CR-UTR:UTR001 SETTL setl_001", rows=None):
    if rows is None:
        rows = [f"bank_001,{date},{description},{utr},{credit},0"]
    return BANK_HEADER + "\n" + "\n".join(rows) + "\n"


def _run(ledger_csv, settlement_csv, bank_csv):
    ledger = normalize_internal_ledger(
        read_csv_source(ledger_csv, Source.INTERNAL_LEDGER))
    settlements = normalize_settlement_report(
        read_csv_source(settlement_csv, Source.SETTLEMENT_REPORT))
    bank = normalize_bank_statement(
        read_csv_source(bank_csv, Source.BANK_STATEMENT))
    outcome = reconcile_batch(ledger, settlements, bank, CFG, AS_OF)
    assert len(outcome.results) == 1
    return outcome.results[0]


CONTRACT_FIELDS = {
    "payment_id", "status", "confidence", "match_method",
    "expected_amount_paise", "actual_amount_paise", "variance_paise",
    "reason", "evidence", "requires_review",
}


def _assert_contract(result):
    missing = CONTRACT_FIELDS - set(result.to_contract_dict())
    assert not missing, f"result contract missing {missing}"
    assert result.evidence and all(result.evidence)


class TestScenarios:
    def test_clean_match(self):
        r = _run(_ledger(), _settlement(), _bank())
        _assert_contract(r)
        assert r.status is ReconciliationStatus.FULLY_RECONCILED
        assert r.confidence == 0.99
        assert r.variance_paise == 0
        assert r.requires_review is False
        assert "pay_001" in r.evidence and "setl_001" in r.evidence

    def test_missing_settlement(self):
        r = _run(_ledger(), SETL_HEADER + "\n", _bank())
        assert r.status is ReconciliationStatus.MISSING_IN_SETTLEMENT
        assert r.expected_amount_paise == GROSS
        assert r.requires_review is True

    def test_missing_bank_credit(self):
        r = _run(_ledger(), _settlement(settled="2026-08-14 09:00:00"),
                 BANK_HEADER + "\n")
        assert r.status is ReconciliationStatus.MISSING_BANK_CREDIT
        assert r.expected_amount_paise == NET
        assert r.actual_amount_paise is None

    def test_amount_mismatch(self):
        r = _run(_ledger(), _settlement(), _bank(credit=NET - 30_000))
        assert r.status is ReconciliationStatus.AMOUNT_MISMATCH
        assert r.variance_paise == -30_000
        assert "INR 300.00 lower" in r.reason

    def test_fee_mismatch_manifests_as_variance(self):
        # settlement claims double the fee; bank paid the original net
        r = _run(_ledger(), _settlement(fee=2 * FEE), _bank(credit=NET))
        assert r.status is ReconciliationStatus.AMOUNT_MISMATCH
        assert r.variance_paise == FEE  # fee delta = 2*FEE - FEE
        # the audit breakdown names the component that moved
        assert r.expected_breakdown_paise["fee_paise"] == 2 * FEE

    def test_tax_mismatch_manifests_as_variance(self):
        r = _run(_ledger(), _settlement(tax=5 * TAX), _bank(credit=NET))
        assert r.status is ReconciliationStatus.AMOUNT_MISMATCH
        assert r.variance_paise == 4 * TAX
        assert r.expected_breakdown_paise["tax_paise"] == 5 * TAX

    def test_refund(self):
        refund_row = ("ent_001_r,refund,pay_001,order_001,setl_001,,0,0,0,"
                      "25000,0,2026-08-11 09:00:00")
        r = _run(_ledger(), _settlement(extra_rows=[refund_row]),
                 _bank(credit=NET - 25_000))
        assert r.status is ReconciliationStatus.FULLY_RECONCILED
        assert r.expected_amount_paise == NET - 25_000
        assert r.expected_breakdown_paise["debit_paise"] == 25_000

    def test_adjustment(self):
        adjustment_row = ("ent_001_a,adjustment,pay_001,order_001,setl_001,,"
                          "0,0,0,0,400,2026-08-11 09:00:00")
        r = _run(_ledger(), _settlement(extra_rows=[adjustment_row]),
                 _bank(credit=NET + 400))
        assert r.status is ReconciliationStatus.FULLY_RECONCILED
        assert r.expected_amount_paise == NET + 400
        assert r.expected_breakdown_paise["credit_paise"] == 400

    def test_duplicate_bank_rows(self):
        row = "bank_001,2026-08-12 10:00:00,NEFT CR-UTR:UTR001 SETTL setl_001,UTR001,97640,0"
        r = _run(_ledger(), _settlement(), _bank(rows=[row, row]))
        assert r.status is ReconciliationStatus.DUPLICATE
        assert r.requires_review is True

    def test_timing_delay(self):
        # settlement is young relative to AS_OF; no bank credit yet
        r = _run(_ledger(created="2026-08-19 09:00:00"),
                 _settlement(settled="2026-08-19 20:00:00"),
                 BANK_HEADER + "\n")
        assert r.status is ReconciliationStatus.TIMING_DELAY
        assert r.requires_review is True

    def test_missing_utr_resolved_by_reference(self):
        r = _run(
            _ledger(),
            _settlement(utr=""),
            _bank(utr="", description="NEFT CR SETTL setl_001 RZPGROUP"),
        )
        assert r.status is ReconciliationStatus.FULLY_RECONCILED
        assert r.confidence <= 0.92  # reference link capped below UTR-grade

    def test_ambiguous_candidate_never_auto_matches(self):
        twin_a = "bank_001a,2026-08-12 10:00:00,NEFT CR-EXTERNAL,,97640,0"
        twin_b = "bank_001b,2026-08-12 10:00:00,NEFT CR-EXTERNAL,,97640,0"
        r = _run(_ledger(), _settlement(utr=""), _bank(rows=[twin_a, twin_b]))
        assert r.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert "bank_001a" in r.evidence and "bank_001b" in r.evidence

    def test_currency_mismatch_is_review_not_match(self):
        # engine-level: a USD bank entry carrying the right UTR must not
        # auto-match (ingestion-level non-INR ledger rows are rejected in
        # test_validation.py — this covers the bank-side conflict)
        from tests.factories import DEFAULT_NET, bank_entry, ledger_txn, settlement_txn
        ledger = [ledger_txn()]
        settlements = [settlement_txn(utr="UTR1")]
        bank = [bank_entry(txn_id="bank_usd", utr="UTR1", credit=DEFAULT_NET,
                           currency="USD")]
        outcome = reconcile_batch(ledger, settlements, bank, CFG, AS_OF)
        r = outcome.results[0]
        _assert_contract(r)
        assert r.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert r.requires_review is True
        assert "currency" in r.reason.lower()


class TestDatasetWide:
    def test_full_synthetic_dataset_statuses_stable(self):
        """The phase-5 refactor + new evidence paths must not change the
        committed dataset's outcomes (71/29 split, variance untouched)."""
        from pathlib import Path

        from backend.metrics import summarize
        d = Path(__file__).resolve().parents[2] / "data"
        outcome = reconcile_batch(
            normalize_internal_ledger(
                read_csv_source((d / "internal_ledger.csv").read_text(),
                                Source.INTERNAL_LEDGER)),
            normalize_settlement_report(
                read_csv_source((d / "settlements.csv").read_text(),
                                Source.SETTLEMENT_REPORT)),
            normalize_bank_statement(
                read_csv_source((d / "bank_statement.csv").read_text(),
                                Source.BANK_STATEMENT)),
            CFG, AS_OF,
        )
        summary = summarize(outcome.results)
        assert summary.total_records == 100
        assert summary.fully_reconciled == 71
        assert summary.status_counts["NEEDS_HUMAN_REVIEW"] == 1
        assert summary.status_counts["DUPLICATE"] == 3
        assert summary.total_variance_paise == -150_000
