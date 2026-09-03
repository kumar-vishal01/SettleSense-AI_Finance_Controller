"""Candidate generation and scoring only (AGENTS.md section 2).

This module proposes and scores links between canonical records. It never
assigns financial statuses — that is reconciliation.py's job.

Pass structure mirrors ARCHITECTURE.md section 3.4:

Pass 1  ledger row -> settlement rows     exact payment_id, else order_id
Pass 2  settlement group -> bank entries  exact UTR, else reference in the
        bank description, else amount + currency + date-window scoring
Pass 3  scored candidates                 weighted components; amount alone
        never admits a candidate that shares no identifier evidence
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.config import ReconciliationConfig, SCORE_WEIGHTS
from backend.models import CanonicalBankEntry, CanonicalTransaction

DAY_SECONDS = 86_400


# ---------------------------------------------------------------------------
# Pass 1: internal payment -> settlement rows
# ---------------------------------------------------------------------------


@dataclass
class SettlementLink:
    """All settlement rows that belong to one internal payment."""

    rows: list[CanonicalTransaction]
    method: str  # "payment_id" | "order_id"
    payment_id_weight: float  # confidence weight earned by this link


def link_settlements_for_payment(
    payment: CanonicalTransaction,
    settlement_rows: list[CanonicalTransaction],
) -> SettlementLink | None:
    """Link one ledger payment to its settlement rows.

    Exact payment ID is stronger than any other evidence and is tried first
    (AGENTS.md section 4). Order ID is used only as a fallback and only for
    settlement rows that carry no payment ID, so a row already claimed by a
    stronger link is never stolen.
    """
    by_payment = [
        r for r in settlement_rows
        if payment.payment_id and r.payment_id == payment.payment_id
    ]
    if by_payment:
        return SettlementLink(
            rows=by_payment, method="payment_id",
            payment_id_weight=SCORE_WEIGHTS["payment_id"],
        )

    def unclaimed(rows):
        # rows not already claimable by a stronger key
        return [r for r in rows if r.payment_id is None and r.order_id is None]

    by_order = [
        r for r in settlement_rows
        if payment.order_id and r.order_id == payment.order_id and r.payment_id is None
    ]
    if by_order:
        return SettlementLink(
            rows=by_order, method="order_id",
            payment_id_weight=SCORE_WEIGHTS["payment_id"],
        )

    by_entity = [
        r for r in unclaimed(settlement_rows)
        if payment.entity_id and r.entity_id == payment.entity_id
    ]
    if by_entity:
        return SettlementLink(
            rows=by_entity, method="entity_id",
            payment_id_weight=SCORE_WEIGHTS["payment_id"],
        )

    by_settlement = [
        r for r in unclaimed(settlement_rows)
        if payment.settlement_id and r.settlement_id == payment.settlement_id
        and r.entity_id is None
    ]
    if by_settlement:
        return SettlementLink(
            rows=by_settlement, method="settlement_id",
            payment_id_weight=SCORE_WEIGHTS["payment_id"],
        )
    return None


# Pass 2 + 3: settlement group -> bank entry candidates
# ---------------------------------------------------------------------------


@dataclass
class BankCandidate:
    """One bank entry proposed for a settlement group, with its evidence."""

    entry: CanonicalBankEntry
    score: float
    has_utr_link: bool = False
    has_reference_link: bool = False
    amount_agrees: bool = False
    date_within_window: bool = False
    currency_conflict: bool = False
    components: list[str] = field(default_factory=list)


def find_bank_candidates(
    settlement_rows: list[CanonicalTransaction],
    expected_net_paise: int,
    bank_entries: list[CanonicalBankEntry],
    config: ReconciliationConfig,
) -> list[BankCandidate]:
    """Generate scored bank-entry candidates for one settlement group.

    A bank entry becomes a candidate only when it shares real evidence with
    the settlement: an exact UTR, a settlement reference inside the
    description, or BOTH amount and date-window agreement. Amount alone is
    never sufficient (AGENTS.md section 4).
    """
    utr = next((r.settlement_utr for r in settlement_rows if r.settlement_utr), None)
    settlement_ids = {r.settlement_id for r in settlement_rows if r.settlement_id}
    settled_at = min(r.transaction_at for r in settlement_rows)
    w = SCORE_WEIGHTS

    expected_currency = next(
        (r.currency for r in settlement_rows if r.currency), "INR"
    ).upper()

    candidates: list[BankCandidate] = []
    for entry in bank_entries:
        has_utr_column = bool(utr) and entry.utr == utr
        # UTR named inside the description counts as UTR evidence (spec step
        # 6) — token-boundary match so UTR777 never matches UTR7778.
        has_utr_in_description = bool(utr) and _references_token(
            entry.description, utr
        )
        has_utr = has_utr_column or has_utr_in_description
        has_ref = _description_references(entry.description, settlement_ids)
        amount_ok = abs(entry.net_amount_paise() - expected_net_paise) <= config.amount_tolerance_paise
        date_ok = _within_window(settled_at, entry.value_date, config.date_window_days)
        currency_conflict = entry.currency.strip().upper() != expected_currency
        currency_ok = not currency_conflict

        identifier_evidence = has_utr or has_ref
        weak_evidence = amount_ok and date_ok
        if not (identifier_evidence or weak_evidence):
            continue

        score = 0.0
        components: list[str] = []
        if has_utr_column:
            score += w["utr"]
            components.append("utr")
        elif has_utr_in_description:
            score += w["utr"]  # same weight tier as a UTR column match
            components.append("utr_in_description")
        elif has_ref:
            score += w["utr"]  # reference in description: same weight tier as UTR
            components.append("reference")
        if amount_ok:
            score += w["amount"]
            components.append("amount")
        if date_ok:
            score += w["date"]
            components.append("date")
        if currency_ok:
            score += w["currency"]
            components.append("currency")

        candidates.append(
            BankCandidate(
                entry=entry,
                score=round(score, 2),
                has_utr_link=has_utr,
                has_reference_link=has_ref,
                amount_agrees=amount_ok,
                date_within_window=date_ok,
                currency_conflict=currency_conflict,
                components=components,
            )
        )

    candidates.sort(key=lambda c: (-c.score, c.entry.bank_txn_id))
    return candidates


def classify_score(score: float, config: ReconciliationConfig) -> str:
    """Phase-5 decision bands for SCORED candidates.

    >= auto_match_threshold (0.95):            auto
    [strong_band_lower, 0.95) = [0.80, 0.95):  auto only if unique + non-conflicting
    [review_band_lower, 0.80) = [0.60, 0.80):  human review
    below 0.60:                                unresolved (still surfaced for
                                               review; never silently matched)

    Identifier-exact matches are deterministic links, not scored guesses —
    their composed evidence lands >= 0.95 anyway. Amount+date-only evidence
    tops out at 0.35, deep in the unresolved band, so two equally plausible
    amount twins can never auto-match.
    """
    if score >= config.auto_match_threshold:
        return "auto"
    if score >= config.strong_band_lower:
        return "auto_if_unique"
    if score >= config.review_band_lower:
        return "review"
    return "unresolved"


def _references_token(text: str, token: str) -> bool:
    """Case-insensitive token-boundary containment."""
    pattern = rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _description_references(description: str, settlement_ids: set[str]) -> bool:
    """True when the bank description names one of the settlement IDs.

    Token-boundary match, case-insensitive: ``setl_20`` must NOT match a
    description referencing ``setl_202`` — substring collisions would create
    false links. This is evidence only — never used to mutate or invent an ID.
    """
    for sid in settlement_ids:
        pattern = rf"(?<![A-Za-z0-9]){re.escape(sid)}(?![A-Za-z0-9])"
        if re.search(pattern, description, re.IGNORECASE):
            return True
    return False


def _within_window(settled_at, value_date, window_days: int) -> bool:
    """Credit date from settlement date up to window_days after it."""
    delta = (value_date - settled_at).total_seconds()
    return 0 <= delta <= window_days * DAY_SECONDS
