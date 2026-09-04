"""Matching rules: candidate generation and scoring only (AGENTS.md section 4)."""

from __future__ import annotations

from datetime import timedelta

from backend.config import ReconciliationConfig
from backend.calculations import aggregate_settlement_group
from backend.matching import find_bank_candidates, link_settlements_for_payment
from tests.factories import (
    AS_OF,
    DEFAULT_NET,
    T1,
    T2,
    bank_entry,
    ledger_txn,
    settlement_txn,
)


class TestPass1SettlementLink:
    def test_exact_payment_id_wins(self):
        payment = ledger_txn(payment_id="pay_001", order_id="order_001")
        rows = [
            settlement_txn(payment_id="pay_001", entity_id="ent_001"),
            settlement_txn(payment_id="pay_999", entity_id="ent_999", order_id="order_001"),
        ]
        link = link_settlements_for_payment(payment, rows)
        assert link is not None
        assert link.method == "payment_id"
        assert [r.source_row_id for r in link.rows] == ["ent_001"]

    def test_order_id_fallback_only_without_payment_id_on_settlement(self):
        payment = ledger_txn(payment_id="pay_001", order_id="order_001")
        rows = [settlement_txn(payment_id=None, entity_id="ent_001", order_id="order_001")]
        link = link_settlements_for_payment(payment, rows)
        assert link is not None
        assert link.method == "order_id"

    def test_no_link_returns_none(self):
        assert link_settlements_for_payment(ledger_txn(), []) is None


class TestWaterfallAggregation:
    def test_net_waterfall_sums_across_rows(self):
        rows = [
            settlement_txn(gross=100_000, fee=2_000, tax=360),
            settlement_txn(entity_id="ent_001_r", gross=0, fee=0, tax=0, debit=30_000),
            settlement_txn(entity_id="ent_001_a", gross=0, fee=0, tax=0, credit=400),
        ]
        totals = aggregate_settlement_group(rows)
        assert totals["gross_amount_paise"] == 100_000
        assert totals["fee_paise"] == 2_000
        assert totals["tax_paise"] == 360
        assert totals["debit_paise"] == 30_000
        assert totals["credit_paise"] == 400
        # 100000 - 2000 - 360 - 30000 + 400
        assert totals["net_paise"] == 68_040


class TestBankCandidates:
    def test_exact_utr_candidate(self):
        rows = [settlement_txn(utr="UTR100001")]
        entry = bank_entry(txn_id="bank_001", utr="UTR100001", credit=DEFAULT_NET)
        candidates = find_bank_candidates(rows, DEFAULT_NET, [entry], ReconciliationConfig())
        assert len(candidates) == 1
        assert candidates[0].has_utr_link
        assert candidates[0].score == 0.60  # utr+amount+date+currency

    def test_amount_and_date_alone_form_weak_candidate(self):
        rows = [settlement_txn(utr="UTR100001")]
        entry = bank_entry(txn_id="bank_x", utr=None, credit=DEFAULT_NET, at=T2,
                           description="NEFT CR-EXTERNAL")
        candidates = find_bank_candidates(rows, DEFAULT_NET, [entry], ReconciliationConfig())
        assert len(candidates) == 1
        assert not candidates[0].has_utr_link
        assert candidates[0].score == 0.35  # amount+date+currency

    def test_amount_without_date_is_not_a_candidate(self):
        rows = [settlement_txn(utr="UTR100001", at=T1)]
        entry = bank_entry(txn_id="bank_x", utr=None, credit=DEFAULT_NET,
                           at=T1 + timedelta(days=10), description="NEFT CR-EXTERNAL")
        candidates = find_bank_candidates(rows, DEFAULT_NET, [entry], ReconciliationConfig())
        assert candidates == []

    def test_duplicate_amounts_yield_multiple_candidates(self):
        rows = [settlement_txn(utr=None)]
        entries = [
            bank_entry(txn_id="bank_a", utr=None, credit=DEFAULT_NET, at=T2,
                       description="NEFT CR-EXTERNAL"),
            bank_entry(txn_id="bank_b", utr=None, credit=DEFAULT_NET, at=T2,
                       description="NEFT CR-EXTERNAL"),
        ]
        candidates = find_bank_candidates(rows, DEFAULT_NET, entries, ReconciliationConfig())
        assert len(candidates) == 2  # ambiguous: caller must send to review

    def test_settlement_id_in_description_is_reference_evidence(self):
        rows = [settlement_txn(utr=None, settlement_id="setl_042")]
        entry = bank_entry(txn_id="bank_r", utr=None, credit=DEFAULT_NET,
                           description="NEFT CR SETTL setl_042 RZP")
        candidates = find_bank_candidates(rows, DEFAULT_NET, [entry], ReconciliationConfig())
        assert len(candidates) == 1
        assert candidates[0].has_reference_link

    def test_prefix_settlement_id_is_not_a_reference(self):
        # setl_20 must NOT reference-match a description naming setl_202:
        # substring collisions create false links (senior-review H1)
        rows = [settlement_txn(utr=None, settlement_id="setl_20")]
        entry = bank_entry(txn_id="bank_202", utr=None, credit=DEFAULT_NET,
                           description="NEFT CR SETTL setl_202 RZPGROUP")
        candidates = find_bank_candidates(rows, DEFAULT_NET, [entry], ReconciliationConfig())
        assert not any(c.has_reference_link for c in candidates)
        # amount+date alone still yields only weak evidence, never a reference
        assert all(c.score <= 0.35 for c in candidates)

    def test_reference_match_honors_delimiters(self):
        rows = [settlement_txn(utr=None, settlement_id="setl_020")]
        for description in ("SETTL setl_020 RZPGROUP", "(setl_020)", "setl_020."):
            entry = bank_entry(txn_id="bank_r", utr=None, credit=DEFAULT_NET,
                               description=description)
            candidates = find_bank_candidates(rows, DEFAULT_NET, [entry], ReconciliationConfig())
            assert candidates[0].has_reference_link, description

    def test_candidates_sorted_by_score_then_id(self):
        rows = [settlement_txn(utr="UTR100001")]
        weak = bank_entry(txn_id="bank_a", utr=None, credit=DEFAULT_NET, at=T2,
                          description="NEFT CR-EXTERNAL")
        strong = bank_entry(txn_id="bank_b", utr="UTR100001", credit=DEFAULT_NET, at=T2)
        candidates = find_bank_candidates(
            rows, DEFAULT_NET, [weak, strong], ReconciliationConfig()
        )
        assert candidates[0].entry.bank_txn_id == "bank_b"


class TestPhase5LinkPriority:
    """Matching order per phase-5 spec: payment_id > order_id > entity_id >
    settlement_id; weaker keys never steal rows claimed by stronger ones."""

    def test_entity_id_fallback_links(self):
        payment = ledger_txn(payment_id=None, order_id=None, entity_id="ent_9")
        rows = [settlement_txn(payment_id=None, order_id=None, entity_id="ent_9")]
        link = link_settlements_for_payment(payment, rows)
        assert link is not None and link.method == "entity_id"

    def test_settlement_id_fallback_links(self):
        payment = ledger_txn(payment_id=None, order_id=None, settlement_id="setl_9")
        # settlement-id is the WEAKEST link: only rows carrying no entity
        # key at all may be claimed through it
        rows = [settlement_txn(payment_id=None, order_id=None, entity_id=None,
                               settlement_id="setl_9")]
        link = link_settlements_for_payment(payment, rows)
        assert link is not None and link.method == "settlement_id"

    def test_entity_fallback_never_steals_payment_id_rows(self):
        payment = ledger_txn(payment_id=None, order_id=None, entity_id="ent_9")
        rows = [settlement_txn(payment_id="pay_other", order_id=None,
                               entity_id="ent_9")]
        assert link_settlements_for_payment(payment, rows) is None


class TestUtrFromDescription:
    def test_utr_named_in_description_is_utr_evidence(self):
        # bank UTR column blank, but the description names the UTR exactly
        rows = [settlement_txn(utr="UTR777")]
        entry = bank_entry(txn_id="bank_x", utr=None, credit=DEFAULT_NET,
                           description="NEFT CR REF UTR777 RZPGROUP")
        candidates = find_bank_candidates(rows, DEFAULT_NET, [entry], ReconciliationConfig())
        assert candidates[0].has_utr_link
        assert "utr_in_description" in candidates[0].components
        assert candidates[0].score == 0.60  # utr + amount + date + currency

    def test_partial_utr_token_is_not_evidence(self):
        rows = [settlement_txn(utr="UTR777")]
        entry = bank_entry(txn_id="bank_x", utr=None, credit=DEFAULT_NET,
                           description="NEFT CR REF UTR7778 RZPGROUP")
        candidates = find_bank_candidates(rows, DEFAULT_NET, [entry], ReconciliationConfig())
        assert not candidates[0].has_utr_link


class TestCurrencyConflict:
    def test_wrong_currency_flags_candidate(self):
        rows = [settlement_txn(utr="UTR1")]
        entry = bank_entry(txn_id="bank_x", utr="UTR1", credit=DEFAULT_NET,
                           currency="USD")
        candidates = find_bank_candidates(rows, DEFAULT_NET, [entry], ReconciliationConfig())
        assert candidates[0].currency_conflict is True
        assert "currency" not in candidates[0].components  # no currency credit

    def test_currency_conflict_never_auto_matches(self):
        from backend.reconciliation import reconcile_batch
        from backend.models import ReconciliationStatus
        ledger = [ledger_txn()]
        settlements = [settlement_txn(utr="UTR1")]
        entry = bank_entry(txn_id="bank_x", utr="UTR1", credit=DEFAULT_NET,
                           currency="USD")
        result = reconcile_batch(
            ledger, settlements, [entry], ReconciliationConfig(), AS_OF
        ).results[0]
        assert result.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert "currency" in result.reason.lower()
        assert result.requires_review is True


class TestScoreBands:
    def test_band_classification(self):
        from backend.matching import classify_score
        cfg = ReconciliationConfig()
        assert classify_score(0.95, cfg) == "auto"
        assert classify_score(0.99, cfg) == "auto"
        assert classify_score(0.85, cfg) == "auto_if_unique"
        assert classify_score(0.94, cfg) == "auto_if_unique"
        assert classify_score(0.60, cfg) == "review"
        assert classify_score(0.79, cfg) == "review"
        assert classify_score(0.59, cfg) == "unresolved"
        assert classify_score(0.35, cfg) == "unresolved"

    def test_amount_alone_lands_unresolved(self):
        from backend.matching import classify_score
        # amount + date + currency without identifiers = 0.35: even a UNIQUE
        # such candidate is below the review floor and can never auto-match
        assert classify_score(0.35, ReconciliationConfig()) == "unresolved"


class TestBandsAreEnforced:
    """F1: the score bands must be enforced by the pipeline, not decorative."""

    def test_strict_thresholds_demote_reference_match_to_review(self):
        """With thresholds raised above the evidence chain's score, the same
        inputs that reconcile by default MUST fall back to review — proving
        the guard actually gates the FULLY_RECONCILED claim."""
        from backend.config import ReconciliationConfig
        from backend.models import ReconciliationStatus
        from backend.reconciliation import reconcile_batch

        strict = ReconciliationConfig(
            auto_match_threshold=1.01, strong_band_lower=1.00,
            review_band_lower=0.99,
        )
        ledger = [ledger_txn()]
        settlements = [settlement_txn(utr=None)]          # reference path
        bank = [bank_entry(
            txn_id="bank_r", utr=None, credit=DEFAULT_NET,
            description="NEFT CR SETTL setl_001 RZPGROUP")]
        result = reconcile_batch(
            ledger, settlements, bank, strict, AS_OF).results[0]
        assert result.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert "below the configured auto-match band" in result.reason
        assert result.requires_review is True

    def test_default_thresholds_keep_reference_match_auto(self):
        from backend.config import ReconciliationConfig
        from backend.models import ReconciliationStatus
        from backend.reconciliation import reconcile_batch
        ledger = [ledger_txn()]
        settlements = [settlement_txn(utr=None)]
        bank = [bank_entry(
            txn_id="bank_r", utr=None, credit=DEFAULT_NET,
            description="NEFT CR SETTL setl_001 RZPGROUP")]
        result = reconcile_batch(
            ledger, settlements, bank, ReconciliationConfig(), AS_OF).results[0]
        # 0.92 = unique-non-conflicting band -> auto is allowed and used
        assert result.status is ReconciliationStatus.FULLY_RECONCILED
        assert result.confidence == 0.92

    def test_unresolved_band_wording_when_score_below_review_floor(self):
        """With the review floor raised above the composed evidence (0.40
        link + 0.35 weak candidate = 0.75), the reason must say so."""
        from backend.config import ReconciliationConfig
        from backend.models import ReconciliationStatus
        from backend.reconciliation import reconcile_batch
        strict = ReconciliationConfig(review_band_lower=0.80,
                                      strong_band_lower=0.95,
                                      auto_match_threshold=1.0)
        ledger = [ledger_txn()]
        settlements = [settlement_txn(utr=None)]
        bank = [bank_entry(txn_id="bank_w", utr=None, credit=DEFAULT_NET, at=T2,
                           description="NEFT CR-EXTERNAL")]
        result = reconcile_batch(
            ledger, settlements, bank, strict, AS_OF).results[0]
        assert result.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert "below the review threshold" in result.reason

    def test_default_config_weak_candidate_is_review_band_not_unresolved(self):
        from backend.config import ReconciliationConfig
        from backend.models import ReconciliationStatus
        from backend.reconciliation import reconcile_batch
        ledger = [ledger_txn()]
        settlements = [settlement_txn(utr=None)]
        bank = [bank_entry(txn_id="bank_w", utr=None, credit=DEFAULT_NET, at=T2,
                           description="NEFT CR-EXTERNAL")]
        result = reconcile_batch(
            ledger, settlements, bank, ReconciliationConfig(), AS_OF).results[0]
        assert result.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert "below the review threshold" not in result.reason

    def test_weak_candidates_reason_mentions_currency_conflict(self):
        from backend.config import ReconciliationConfig
        from backend.models import ReconciliationStatus
        from backend.reconciliation import reconcile_batch
        ledger = [ledger_txn()]
        settlements = [settlement_txn(utr=None)]
        twins = [
            bank_entry(txn_id="bank_usd_a", utr=None, credit=DEFAULT_NET, at=T2,
                       description="NEFT CR-EXTERNAL", currency="USD"),
            bank_entry(txn_id="bank_usd_b", utr=None, credit=DEFAULT_NET, at=T2,
                       description="NEFT CR-EXTERNAL", currency="USD"),
        ]
        result = reconcile_batch(
            ledger, settlements, twins, ReconciliationConfig(), AS_OF).results[0]
        assert result.status is ReconciliationStatus.NEEDS_HUMAN_REVIEW
        assert "non-INR currency" in result.reason
