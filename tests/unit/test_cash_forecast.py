"""Phase 7 cash position: pure paise math for confirmed/expected/pending
cash, variance, and the transparent forecast."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.cash_forecast import CashForecastConfig, compute_cash_position
from backend.config import ReconciliationConfig
from backend.reconciliation import reconcile_batch
from tests.factories import (
    DEFAULT_GROSS, DEFAULT_NET, T0, T1, T2, AS_OF, bank_entry,
    ledger_txn, settlement_txn,
)

CFG = ReconciliationConfig()


def _results(ledger, settlements, bank, as_of=AS_OF):
    return reconcile_batch(ledger, settlements, bank, CFG, as_of).results


class TestCleanCash:
    def test_fully_reconciled_batch_balances(self):
        results = _results([ledger_txn()], [settlement_txn()], [bank_entry()])
        pos = compute_cash_position(
            results, [bank_entry()], opening_balance_paise=1_000_000,
            as_of=AS_OF, config=CashForecastConfig())
        assert pos["opening_balance_paise"] == 1_000_000
        assert pos["confirmed_credits_paise"] == DEFAULT_NET
        assert pos["confirmed_debits_paise"] == 0
        assert pos["actual_cash_paise"] == 1_000_000 + DEFAULT_NET
        assert pos["pending_settlements_paise"] == 0
        assert pos["expected_cash_paise"] == 1_000_000 + DEFAULT_NET
        assert pos["variance_paise"] == 0
        assert pos["confidence"] == "high"

    def test_bank_debit_charge_reduces_actual_cash(self):
        entry = bank_entry(credit=0, debit=5_900, utr="UTRCHARGE")
        results = _results([ledger_txn()], [settlement_txn()], [bank_entry()])
        pos = compute_cash_position(results, [bank_entry(), entry],
                                    opening_balance_paise=0, as_of=AS_OF)
        assert pos["confirmed_debits_paise"] == 5_900
        assert pos["actual_cash_paise"] == DEFAULT_NET - 5_900


class TestMissingBankCreditDrivesNegativeVariance:
    def test_old_missing_credit_is_negative_variance_not_pending(self):
        old = AS_OF - timedelta(days=6)
        ledger = [ledger_txn(at=old - timedelta(days=2))]
        settlements = [settlement_txn(at=old)]
        results = _results(ledger, settlements, [])
        pos = compute_cash_position(results, [], opening_balance_paise=0, as_of=AS_OF)
        assert pos["pending_settlements_paise"] == 0        # too old to pend
        assert pos["variance_paise"] == -DEFAULT_NET        # expected, never landed
        assert pos["confidence"] == "medium"


class TestPendingSettlement:
    def test_timing_delay_is_eligible_pending(self):
        recent = AS_OF - timedelta(days=1)
        ledger = [ledger_txn(at=recent - timedelta(days=2))]
        settlements = [settlement_txn(at=recent)]
        results = _results(ledger, settlements, [])
        pos = compute_cash_position(results, [], opening_balance_paise=0, as_of=AS_OF)
        assert pos["pending_settlements_paise"] == DEFAULT_NET
        assert pos["expected_cash_paise"] == 0 + DEFAULT_NET
        assert pos["variance_paise"] == 0                  # not late yet: no variance
        assert pos["confidence"] == "medium"
        # forecast assumes it lands on day 1 (one banking day) and stays flat
        assert pos["forecast"][0]["projected_cash_paise"] == DEFAULT_NET
        assert pos["forecast"][6]["projected_cash_paise"] == DEFAULT_NET


class TestRefundAndAdjustment:
    def test_refund_reduces_expected_and_pending(self):
        recent = AS_OF - timedelta(days=1)
        ledger = [ledger_txn(at=recent - timedelta(days=2))]
        settlements = [
            settlement_txn(at=recent),
            settlement_txn(entity_id="e_r", gross=0, fee=0, tax=0, debit=30_000),
        ]
        results = _results(ledger, settlements, [])
        pos = compute_cash_position(results, [], opening_balance_paise=0, as_of=AS_OF)
        assert pos["pending_settlements_paise"] == DEFAULT_NET - 30_000

    def test_adjustment_increases_pending(self):
        recent = AS_OF - timedelta(days=1)
        ledger = [ledger_txn(at=recent - timedelta(days=2))]
        settlements = [
            settlement_txn(at=recent),
            settlement_txn(entity_id="e_a", gross=0, fee=0, tax=0, credit=400),
        ]
        results = _results(ledger, settlements, [])
        pos = compute_cash_position(results, [], opening_balance_paise=0, as_of=AS_OF)
        assert pos["pending_settlements_paise"] == DEFAULT_NET + 400


class TestAmbiguousMoneyExcluded:
    def test_duplicate_and_unattributed_credits_not_confirmed(self):
        # duplicate bank rows -> DUPLICATE; both excluded from confirmed cash
        results = _results([ledger_txn()], [settlement_txn()],
                           [bank_entry(), bank_entry(txn_id="bank_002")])
        pos = compute_cash_position(
            results, [bank_entry(), bank_entry(txn_id="bank_002")],
            opening_balance_paise=0, as_of=AS_OF)
        assert pos["confirmed_credits_paise"] == 0
        assert pos["unattributed_or_excluded_paise"] == 2 * DEFAULT_NET
        assert pos["confidence"] == "low"

    def test_mismatch_credit_confirmed_at_actual_with_variance(self):
        short = bank_entry(credit=DEFAULT_NET - 30_000)
        results = _results([ledger_txn()], [settlement_txn()], [short])
        pos = compute_cash_position(results, [short], opening_balance_paise=0,
                                    as_of=AS_OF)
        assert pos["confirmed_credits_paise"] == DEFAULT_NET - 30_000
        assert pos["variance_paise"] == -30_000


class TestEmptyBatch:
    def test_empty_inputs_yield_opening_balance_only(self):
        pos = compute_cash_position([], [], opening_balance_paise=500_000,
                                    as_of=AS_OF)
        assert pos["actual_cash_paise"] == 500_000
        assert pos["expected_cash_paise"] == 500_000
        assert pos["variance_paise"] == 0
        assert pos["pending_settlements_paise"] == 0
        assert pos["confidence"] == "high"
        assert pos["forecast"][0]["projected_cash_paise"] == 500_000


class TestForecastShape:
    def test_horizon_configurable_and_assumptions_shown(self):
        results = _results([ledger_txn()], [settlement_txn()], [bank_entry()])
        pos = compute_cash_position(results, [bank_entry()], opening_balance_paise=0,
                                    as_of=AS_OF,
                                    config=CashForecastConfig(horizon_days=3))
        assert pos["forecast_horizon_days"] == 3
        assert len(pos["forecast"]) == 3
        assert any("banking day" in a.lower() for a in pos["assumptions"])
        assert any("not booked" in a.lower() or "not confirmed" in a.lower()
                   for a in pos["assumptions"])
        # dates are calendar days after as_of
        assert pos["forecast"][0]["date"] == (AS_OF + timedelta(days=1)).date().isoformat()


class TestSeniorReviewPhase7:
    def test_bank_charges_breakout_inside_variance(self):
        """Known bank charges must be visible separately: variance still
        includes them (real cash out, no settlement expectation), but the
        payload names the amount so −7,100 is never mysterious."""
        from datetime import timedelta
        charge = bank_entry(txn_id="bank_chg", credit=0, debit=7_100,
                            utr="UTRCHG", description="BANK CHARGE",
                            at=AS_OF - timedelta(days=1))
        results = _results([ledger_txn()], [settlement_txn()], [bank_entry()])
        pos = compute_cash_position(results, [bank_entry(), charge],
                                    opening_balance_paise=0, as_of=AS_OF)
        assert pos["bank_charges_paise"] == 7_100
        assert pos["confirmed_debits_paise"] == 7_100
        # variance = mismatch(0) - missing(0) - charges(7100)
        assert pos["variance_paise"] == -7_100

    def test_contested_downgrades_exclude_credits_from_confirmed_cash(self):
        """Two payments claiming one bank entry -> both downgraded to review;
        neither the claiming result nor the credit may count as confirmed."""
        ledger = [ledger_txn(payment_id="pay_a", order_id="order_a", row_id="int_a"),
                  ledger_txn(payment_id="pay_b", order_id="order_b", row_id="int_b")]
        settlements = [
            settlement_txn(payment_id="pay_a", entity_id="ent_a",
                           settlement_id="setl_a", utr="UTRSHARED", order_id="order_a"),
            settlement_txn(payment_id="pay_b", entity_id="ent_b",
                           settlement_id="setl_b", utr="UTRSHARED", order_id="order_b"),
        ]
        shared = bank_entry(txn_id="bank_shared", utr="UTRSHARED",
                            description="NEFT CR-EXTERNAL")
        results = _results(ledger, settlements, [shared])
        assert all(r.requires_review for r in results)  # contested -> review
        pos = compute_cash_position(results, [shared], opening_balance_paise=0,
                                    as_of=AS_OF)
        assert pos["confirmed_credits_paise"] == 0
        assert pos["unattributed_or_excluded_paise"] == DEFAULT_NET
        assert pos["confidence"] == "low"
