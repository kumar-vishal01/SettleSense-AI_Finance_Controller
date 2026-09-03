"""Reconciliation orchestrator: financial status decisions (AGENTS.md section 2).

Pure and deterministic: the same inputs and config always produce the same
results, which makes batch reconciliation idempotent by construction.

Decision order per logical payment:
1. Source-integrity failures (duplicates) short-circuit to DUPLICATE.
2. Missing settlement link -> MISSING_IN_SETTLEMENT.
3. Bank matching: exact UTR beats description reference beats scored
   candidates. Ambiguity is never resolved silently -> NEEDS_HUMAN_REVIEW.
4. Linked amounts compared in integer paise -> AMOUNT_MISMATCH or
   FULLY_RECONCILED.
5. No bank candidate: recent settlement -> TIMING_DELAY, older ->
   MISSING_BANK_CREDIT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.calculations import (
    aggregate_settlement_group,
    format_paise_as_rupees,
    variance_paise,
    waterfall_breakdown,
)
from backend.config import ReconciliationConfig
from backend.matching import (
    BankCandidate,
    SettlementLink,
    classify_score,
    find_bank_candidates,
    link_settlements_for_payment,
)
from backend.models import (
    CanonicalBankEntry,
    CanonicalTransaction,
    ReconciliationResult,
    ReconciliationStatus,
    Source,
)
from backend.statuses import RECOMMENDED_ACTIONS, Severity, severity_for

#: Confidence cap for a fully evidenced deterministic chain (PRD example: 0.99).
MAX_CONFIDENCE = 0.99
#: Cap when the bank link came from a description reference rather than a UTR.
REFERENCE_LINK_CONFIDENCE_CAP = 0.92


@dataclass
class BatchOutcome:
    """Everything one reconciliation run produces."""

    results: list[ReconciliationResult] = field(default_factory=list)
    as_of: datetime | None = None  # never defaults to wall clock
    config: ReconciliationConfig = field(default_factory=ReconciliationConfig)
    ledger_row_count: int = 0
    settlement_row_count: int = 0
    bank_row_count: int = 0


# ---------------------------------------------------------------------------
# Duplicate detection (source-uniquiness integrity)
# ---------------------------------------------------------------------------


def _find_duplicate_keys(pairs: list[tuple[str | None, str]]) -> dict[str, list[str]]:
    """Group row ids by key; return only keys with more than one row.

    ``pairs`` is (key, row_id). Keys must be non-None to count: an absent
    value is a missing-data problem, not a uniqueness violation.
    """
    grouped: dict[str, list[str]] = {}
    for key, row_id in pairs:
        if key is not None:
            grouped.setdefault(key, []).append(row_id)
    return {k: ids for k, ids in grouped.items() if len(ids) > 1}


@dataclass
class SourceDuplicates:
    ledger_payment_ids: dict[str, list[str]]     # payment_id -> internal_ids
    settlement_entity_ids: dict[str, list[str]]  # entity_id -> entity_ids
    bank_txn_ids: dict[str, list[str]]           # bank_txn_id -> bank_txn_ids


def detect_source_duplicates(
    ledger: list[CanonicalTransaction],
    settlements: list[CanonicalTransaction],
    bank: list[CanonicalBankEntry],
) -> SourceDuplicates:
    return SourceDuplicates(
        ledger_payment_ids=_find_duplicate_keys(
            [(r.payment_id, r.source_row_id) for r in ledger]
        ),
        settlement_entity_ids=_find_duplicate_keys(
            [(r.entity_id, r.source_row_id) for r in settlements]
        ),
        bank_txn_ids=_find_duplicate_keys([(e.bank_txn_id, e.source_row_id) for e in bank]),
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def reconcile_batch(
    ledger: list[CanonicalTransaction],
    settlements: list[CanonicalTransaction],
    bank: list[CanonicalBankEntry],
    config: ReconciliationConfig | None = None,
    as_of: datetime | None = None,
) -> BatchOutcome:
    """Run the full reconciliation over one batch of canonical records."""
    check_input_sources(ledger, settlements, bank)
    cfg = config or ReconciliationConfig()
    duplicates = detect_source_duplicates(ledger, settlements, bank)
    batch_as_of = as_of or compute_as_of(ledger, settlements, bank)

    outcome = BatchOutcome(
        config=cfg,
        as_of=batch_as_of,
        ledger_row_count=len(ledger),
        settlement_row_count=len(settlements),
        bank_row_count=len(bank),
    )

    decisions: list[tuple[ReconciliationResult, list[str]]] = []
    seen_payment_ids: set[str] = set()
    for payment_row in ledger:
        payment_id = payment_row.payment_id
        if payment_id is None:
            # M1: never silently drop an unidentifiable ledger row — surface
            # it for human review so every input row stays visible.
            decisions.append((_unidentifiable_row_result(payment_row), []))
            continue
        if payment_id in seen_payment_ids:
            continue
        seen_payment_ids.add(payment_id)
        decisions.append(
            _reconcile_payment(
                payment_row, settlements, bank, cfg, duplicates, batch_as_of
            )
        )
    outcome.results = _resolve_contested_claims(decisions)
    return outcome


# ---------------------------------------------------------------------------
# Contested-resource resolution
# ---------------------------------------------------------------------------


def _resolve_contested_claims(
    decisions: list[tuple[ReconciliationResult, list[str]]],
) -> list[ReconciliationResult]:
    """A bank entry or settlement row claimed by more than one payment is
    ambiguous evidence, however strong it looked per-payment. Every such
    claim is downgraded to NEEDS_HUMAN_REVIEW (AGENTS.md section 4: multiple
    plausible candidates never auto-match). Deterministic and order-free.
    """
    bank_claims: dict[str, list[str]] = {}
    row_claims: dict[str, list[str]] = {}
    for result, claimed_rows in decisions:
        for row_id in claimed_rows:
            row_claims.setdefault(row_id, []).append(result.payment_id)
        if result.bank_txn_id:
            bank_claims.setdefault(result.bank_txn_id, []).append(result.payment_id)

    contested_rows = {rid for rid, pids in row_claims.items() if len(pids) > 1}
    contested_banks = {bid for bid, pids in bank_claims.items() if len(pids) > 1}

    final: list[ReconciliationResult] = []
    for result, claimed_rows in decisions:
        if result.status is ReconciliationStatus.DUPLICATE:
            final.append(result)  # already a source-integrity failure
            continue
        bid = result.bank_txn_id
        if bid and bid in contested_banks:
            final.append(_downgrade_to_review(
                result,
                f"bank entry {bid} is claimed by payments "
                f"{', '.join(sorted(bank_claims[bid]))}; the link is ambiguous",
            ))
            continue
        rows_hit = sorted(set(claimed_rows) & contested_rows)
        if rows_hit:
            final.append(_downgrade_to_review(
                result,
                f"settlement row(s) {', '.join(rows_hit)} are claimed by multiple "
                "payments; the link is ambiguous",
            ))
            continue
        final.append(result)
    return final


def _downgrade_to_review(result: ReconciliationResult, reason: str) -> ReconciliationResult:
    return result.model_copy(
        update={
            "status": ReconciliationStatus.NEEDS_HUMAN_REVIEW,
            "confidence": min(result.confidence, 0.50),
            "match_method": f"{result.match_method} (contested)",
            "severity": Severity.HIGH,
            "reason": reason,
            "recommended_action": RECOMMENDED_ACTIONS[ReconciliationStatus.NEEDS_HUMAN_REVIEW],
            "requires_review": True,
        }
    )


def compute_as_of(
    ledger: list[CanonicalTransaction],
    settlements: list[CanonicalTransaction],
    bank: list[CanonicalBankEntry],
) -> datetime:
    stamps = [r.transaction_at for r in ledger] + [r.transaction_at for r in settlements]
    stamps += [e.value_date for e in bank]
    if not stamps:
        # Never substitute the wall clock for absent data (L5): an empty
        # batch has no as_of, and fabricating one breaks determinism.
        raise ValueError("cannot compute as_of from empty inputs")
    return max(stamps)


def _unidentifiable_row_result(payment_row: CanonicalTransaction) -> ReconciliationResult:
    """Review result for a ledger row with no payment_id (M1)."""
    return _result(
        f"unidentified#{payment_row.source_row_id}",
        ReconciliationStatus.NEEDS_HUMAN_REVIEW,
        confidence=0.95,
        match_method="no payment identifier",
        reason=f"ledger row {payment_row.source_row_id} has no payment_id; "
               "the row cannot be matched safely",
        evidence=[payment_row.source_row_id],
        expected=payment_row.gross_amount_paise,
        cfg=ReconciliationConfig(),
    )


def _reconcile_payment(
    payment_row: CanonicalTransaction,
    settlements: list[CanonicalTransaction],
    bank: list[CanonicalBankEntry],
    cfg: ReconciliationConfig,
    duplicates: SourceDuplicates,
    as_of: datetime,
) -> tuple[ReconciliationResult, list[str]]:
    """Decide one payment. Returns the result plus the settlement row ids it
    claims, so reconcile_batch can detect resources claimed twice."""
    payment_id = payment_row.payment_id or ""

    # 1. Source-uniqueness violations take precedence over any match.
    if payment_id in duplicates.ledger_payment_ids:
        row_ids = duplicates.ledger_payment_ids[payment_id]
        return _result(
            payment_id, ReconciliationStatus.DUPLICATE, confidence=0.99,
            match_method="duplicate ledger rows",
            reason=f"payment_id appears {len(row_ids)} times in the internal ledger "
                 f"(rows: {', '.join(row_ids)})",
            evidence=[payment_id, *row_ids],
            expected=payment_row.gross_amount_paise,
            cfg=cfg,
        ), []

    # 2. Settlement link (pass 1).
    link = link_settlements_for_payment(payment_row, settlements)
    if link is None:
        return _result(
            payment_id, ReconciliationStatus.MISSING_IN_SETTLEMENT, confidence=0.95,
            match_method="no settlement link",
            reason="no settlement row matches the payment by payment_id or order_id",
            evidence=[payment_id, payment_row.source_row_id],
            expected=payment_row.gross_amount_paise,
            cfg=cfg,
        ), []
    claimed_rows = [r.source_row_id for r in link.rows]

    duplicated_entities = [
        eid for eid in {r.entity_id for r in link.rows if r.entity_id}
        if eid in duplicates.settlement_entity_ids
    ]
    if duplicated_entities:
        row_ids = [r.source_row_id for r in link.rows]
        return _result(
            payment_id, ReconciliationStatus.DUPLICATE, confidence=0.99,
            match_method="duplicate settlement rows",
            reason=f"settlement entity_id(s) {', '.join(duplicated_entities)} appear "
                 "more than once in the settlement report",
            evidence=[payment_id, payment_row.source_row_id, *row_ids],
            expected=payment_row.gross_amount_paise,
            cfg=cfg,
        ), claimed_rows

    # 3. Gross-to-net waterfall in integer paise.
    totals = aggregate_settlement_group(link.rows)
    expected_net = totals["net_paise"]
    breakdown = {
        key: totals[key] for key in (
            "gross_amount_paise", "fee_paise", "tax_paise",
            "debit_paise", "credit_paise",
        )
    }
    settlement_ids = sorted({r.settlement_id for r in link.rows if r.settlement_id})
    entity_ids = sorted({r.source_row_id for r in link.rows})
    utrs = sorted({r.settlement_utr for r in link.rows if r.settlement_utr})
    base_evidence = [payment_id, payment_row.source_row_id, *entity_ids, *settlement_ids, *utrs]
    settled_at = max(r.transaction_at for r in link.rows)

    # 4. Bank matching (pass 2 + 3).
    candidates = find_bank_candidates(link.rows, expected_net, bank, cfg)
    chosen = _choose_bank_candidate(candidates, duplicates)

    if chosen.kind == "duplicate":
        entry_ids = sorted({c.entry.bank_txn_id for c in chosen.candidates})
        return _result(
            payment_id, ReconciliationStatus.DUPLICATE, confidence=0.99,
            match_method="duplicate bank rows",
            reason="bank statement contains repeated rows for this settlement's reference "
                 f"({', '.join(entry_ids)})",
            evidence=[*base_evidence, *entry_ids],
            expected=expected_net,
            cfg=cfg, breakdown=breakdown,
        ), claimed_rows

    if chosen.kind == "matched":
        candidate = chosen.candidates[0]
        entry = candidate.entry
        if candidate.currency_conflict:
            # A UTR/reference link with the wrong currency is conflicting
            # evidence, never an auto-match (possible FX or mis-tagged
            # account). Phase-5 spec: currency mismatch -> human review.
            return _result(
                payment_id, ReconciliationStatus.NEEDS_HUMAN_REVIEW,
                confidence=0.60,
                match_method=f"{link.method} + UTR/reference (currency conflict)",
                reason=f"bank entry {entry.bank_txn_id} carries currency "
                       f"{entry.currency.strip().upper()} while the settlement "
                       "is INR; the link is conflicting evidence",
                expected=expected_net, actual=entry.net_amount_paise(),
                variance=variance_paise(entry.net_amount_paise(), expected_net),
                evidence=[*base_evidence, entry.bank_txn_id], cfg=cfg,
                breakdown=breakdown,
            ), claimed_rows
        actual = entry.net_amount_paise()
        variance = actual - expected_net
        method = f"{link.method} + {' + '.join(candidate.components)}"
        evidence = [*base_evidence, entry.bank_txn_id]

        if abs(variance) > cfg.amount_tolerance_paise:
            return _result(
                payment_id, ReconciliationStatus.AMOUNT_MISMATCH, confidence=0.98,
                match_method=method,
                reason=_mismatch_reason(link, variance, entry),
                expected=expected_net, actual=actual, variance=variance,
                evidence=evidence, cfg=cfg, breakdown=breakdown,
                settlement_id=settlement_ids[0] if len(settlement_ids) == 1 else None,
                bank_txn_id=entry.bank_txn_id,
            ), claimed_rows

        confidence = min(
            MAX_CONFIDENCE,
            round(link.payment_id_weight + candidate.score, 2),
        )
        if chosen.via == "reference":
            confidence = min(confidence, REFERENCE_LINK_CONFIDENCE_CAP)

        # F1 enforcement: the score bands gate the reconciled claim. The
        # matched candidate is unique and uncontested by construction, so
        # "auto_if_unique" [0.80, 0.95) and "auto" (>= 0.95) may reconcile;
        # anything weaker can never claim FULLY_RECONCILED, whatever future
        # evidence paths are added.
        if classify_score(confidence, cfg) in {"review", "unresolved"}:
            return _result(
                payment_id, ReconciliationStatus.NEEDS_HUMAN_REVIEW,
                confidence=confidence,
                match_method=f"{method} (below auto-match band)",
                reason=f"evidence chain scores {confidence:.2f}, below the "
                       f"configured auto-match band "
                       f"({cfg.strong_band_lower:.2f}); not auto-matched",
                expected=expected_net, actual=actual, variance=variance,
                evidence=evidence, cfg=cfg, breakdown=breakdown,
                settlement_id=settlement_ids[0] if len(settlement_ids) == 1 else None,
                bank_txn_id=entry.bank_txn_id,
            ), claimed_rows

        return _result(
            payment_id, ReconciliationStatus.FULLY_RECONCILED,
            confidence=confidence, match_method=method,
            reason="all linked records agree within tolerance",
            expected=expected_net, actual=actual, variance=variance,
            evidence=evidence, cfg=cfg, breakdown=breakdown,
            settlement_id=settlement_ids[0] if len(settlement_ids) == 1 else None,
            bank_txn_id=entry.bank_txn_id,
        ), claimed_rows

    if chosen.kind == "review":
        entry_ids = [c.entry.bank_txn_id for c in chosen.candidates]
        reason = (
            f"{len(entry_ids)} bank entries are plausible on amount and date alone; "
            "no identifier evidence distinguishes them"
            if len(entry_ids) > 1
            else "single bank entry is plausible on amount and date alone, but no "
                 "identifier evidence confirms the link"
        )
        band = classify_score(
            round(link.payment_id_weight + candidates[0].score, 2), cfg
        ) if candidates else "unresolved"
        if band == "unresolved":
            reason += "; evidence is below the review threshold (unresolved band)"
        conflicts = [c for c in candidates if c.currency_conflict]
        if conflicts:
            reason += (f"; note: {len(conflicts)} candidate(s) carry a "
                       "non-INR currency")
        return _result(
            payment_id, ReconciliationStatus.NEEDS_HUMAN_REVIEW, confidence=0.35,
            match_method="amount + date-window candidates",
            reason=reason, expected=expected_net,
            evidence=[*base_evidence, *entry_ids], cfg=cfg, breakdown=breakdown,
        ), claimed_rows

    # 5. No bank candidate at all.
    age_days = (as_of - settled_at).days
    if age_days <= cfg.timing_delay_days:
        if age_days < 0:
            reason_text = (
                "settlement is dated after batch as_of (future-dated row); "
                "treated as still in transit"
            )
        else:
            reason_text = (
                f"settled {age_days} day(s) before batch as_of; credit plausibly "
                "still in transit"
            )
        return _result(
            payment_id, ReconciliationStatus.TIMING_DELAY, confidence=0.90,
            match_method="settlement within delay window",
            reason=reason_text,
            expected=expected_net, evidence=base_evidence, cfg=cfg, breakdown=breakdown,
        ), claimed_rows
    return _result(
        payment_id, ReconciliationStatus.MISSING_BANK_CREDIT, confidence=0.95,
        match_method="no bank credit found",
        reason=f"no bank credit found and settlement is {age_days} days old "
               "(beyond the delay window)",
        expected=expected_net, evidence=base_evidence, cfg=cfg, breakdown=breakdown,
    ), claimed_rows


def _mismatch_reason(
    link: SettlementLink, variance_paise: int, entry: CanonicalBankEntry
) -> str:
    rupees = format_paise_as_rupees(abs(variance_paise))
    direction = "lower" if variance_paise < 0 else "higher"
    via = "UTR" if link.rows[0].settlement_utr else "settlement reference"
    return (
        f"{via} matched, but bank credit is INR {rupees} {direction} than "
        f"the expected net (bank entry {entry.bank_txn_id})"
    )


# ---------------------------------------------------------------------------
# Bank candidate selection
# ---------------------------------------------------------------------------


@dataclass
class BankChoice:
    kind: str  # "matched" | "duplicate" | "review" | "none"
    candidates: list[BankCandidate]
    via: str = ""  # "utr" | "reference"


def _choose_bank_candidate(
    candidates: list[BankCandidate], duplicates: SourceDuplicates
) -> BankChoice:
    """Apply ARCHITECTURE.md pass-2 priority to the scored candidates.

    Exact identifier evidence is decisive when unique; duplicated references
    are DUPLICATE; scored amount/date evidence alone is never auto-matched.
    """
    if not candidates:
        return BankChoice(kind="none", candidates=[])

    utr_linked = [c for c in candidates if c.has_utr_link]
    if utr_linked:
        if len(utr_linked) > 1 or any(
            c.entry.bank_txn_id in duplicates.bank_txn_ids for c in utr_linked
        ):
            return BankChoice(kind="duplicate", candidates=utr_linked, via="utr")
        return BankChoice(kind="matched", candidates=utr_linked[:1], via="utr")

    ref_linked = [c for c in candidates if c.has_reference_link]
    if ref_linked:
        if len(ref_linked) > 1:
            # Description references are weaker than UTRs: several entries
            # naming the same settlement is ambiguity, not proof of duplication.
            return BankChoice(kind="review", candidates=ref_linked, via="reference")
        return BankChoice(kind="matched", candidates=ref_linked[:1], via="reference")

    # Only amount/date-window evidence: never auto-match.
    return BankChoice(kind="review", candidates=candidates)


# ---------------------------------------------------------------------------
# Result construction
# ---------------------------------------------------------------------------


def _result(
    payment_id: str,
    status: ReconciliationStatus,
    *,
    confidence: float,
    match_method: str,
    reason: str,
    evidence: list[str],
    cfg: ReconciliationConfig,
    expected: int | None = None,
    actual: int | None = None,
    variance: int | None = None,
    settlement_id: str | None = None,
    bank_txn_id: str | None = None,
    breakdown: dict[str, int] | None = None,
) -> ReconciliationResult:
    is_exception = status is not ReconciliationStatus.FULLY_RECONCILED
    return ReconciliationResult(
        payment_id=payment_id,
        status=status,
        confidence=confidence,
        match_method=match_method,
        expected_amount_paise=expected,
        actual_amount_paise=actual,
        variance_paise=variance,
        severity=severity_for(
            status, variance,
            mismatch_high_paise=cfg.mismatch_high_paise,
            mismatch_medium_paise=cfg.mismatch_medium_paise,
        ),
        reason=reason,
        evidence=[e for e in evidence if e],
        recommended_action=RECOMMENDED_ACTIONS[status],
        requires_review=is_exception,
        settlement_id=settlement_id,
        bank_txn_id=bank_txn_id,
        expected_breakdown_paise=breakdown,
    )


def check_input_sources(
    ledger: list[CanonicalTransaction],
    settlements: list[CanonicalTransaction],
    bank: list[CanonicalBankEntry],
) -> None:
    """Refuse mixed-up inputs loudly: ledger/settlement lists must contain
    rows from their own source, or the batch is a caller bug, not data noise."""
    if any(r.source is not Source.INTERNAL_LEDGER for r in ledger):
        raise ValueError("ledger input contains rows from a different source")
    if any(r.source is not Source.SETTLEMENT_REPORT for r in settlements):
        raise ValueError("settlement input contains rows from a different source")
    if any(e.source_row_id == "" for e in bank):
        raise ValueError("bank input contains rows without a bank_txn_id")
