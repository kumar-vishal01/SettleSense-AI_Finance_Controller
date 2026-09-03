"""Constrained backend tools for the AI layer (ARCHITECTURE.md section 3.9).

Every tool is READ-ONLY, deterministic, and evidence-first:
- returns structured data (``ok`` flag + payload or ``error`` dict);
- never mutates payment, settlement, bank, or accounting records — there is
  no write path in this module, by design;
- treats descriptions as UNTRUSTED input: tokens are extracted as data,
  clamped in length, and echoed only as inert excerpts.

The engine runs on demand over the batch's persisted canonical rows — the
same deterministic path as the cash endpoint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.calculations import format_paise_as_rupees
from backend.cash_forecast import CashForecastConfig, compute_cash_position
from backend.config import ReconciliationConfig
from backend.database import Database
from backend.models import ReconciliationStatus, Source
from backend.reconciliation import compute_as_of, reconcile_batch
from backend.repositories import (
    BankEntryRepository,
    BatchRepository,
    TransactionRepository,
)
from backend.statuses import SEVERITY_ORDER

#: untrusted descriptions are clamped before storage in any payload
MAX_DESCRIPTION_CHARS = 120

_UTR_PATTERN = re.compile(r"(?<![A-Za-z0-9])(UTR[A-Za-z0-9]{2,})(?![A-Za-z0-9])")
_SETTLEMENT_PATTERN = re.compile(r"(?<![A-Za-z0-9])(setl_[A-Za-z0-9]+)(?![A-Za-z0-9])", re.I)
_PAYMENT_PATTERN = re.compile(r"(?<![A-Za-z0-9])(pay_[A-Za-z0-9]+)(?![A-Za-z0-9])", re.I)
_PROVIDER_WORDS = ("NEFT", "IMPS", "RTGS", "RZP", "RZPGROUP", "UPI")

#: characters that could smuggle control semantics into logs/payloads
_UNTRUSTED_STRIP = re.compile(r"[\x00-\x1f\x7f<>\"']")


def _sanitize_untrusted(text: str) -> str:
    """Make untrusted text inert: strip control chars/quotes/tags, clamp."""
    cleaned = _UNTRUSTED_STRIP.sub("", text or "")
    return cleaned[:MAX_DESCRIPTION_CHARS]


def _ok(tool: str, **payload) -> dict:
    return {"tool": tool, "ok": True, **payload}


def _err(tool: str, code: str, message: str) -> dict:
    return {"tool": tool, "ok": False, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Tool 1: parse_bank_description
# ---------------------------------------------------------------------------

def parse_bank_description(description: str) -> dict:
    """Extract UTR / settlement / payment / provider tokens from a bank
    description. The text is data, never instructions."""
    if not isinstance(description, str):
        return _err("parse_bank_description", "invalid_input",
                    "description must be a string")
    excerpt = _sanitize_untrusted(description)
    upper = description.upper()
    return _ok(
        "parse_bank_description",
        description_excerpt=excerpt,
        untrusted_input=True,
        utr_refs=sorted(set(_UTR_PATTERN.findall(description.upper()))),
        settlement_refs=sorted(set(m.lower() for m in _SETTLEMENT_PATTERN.findall(description))),
        payment_refs=sorted(set(m.lower() for m in _PAYMENT_PATTERN.findall(description))),
        provider_refs=[word for word in _PROVIDER_WORDS if word in upper],
    )


# ---------------------------------------------------------------------------
# Shared batch loader (read-only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _EngineView:
    batch: dict
    results: list
    bank: list
    ledger: list
    settlements: list


def _load_view(batch_id: str, db: Database) -> _EngineView | dict:
    conn = db.connect(init=False)
    try:
        batch = BatchRepository(conn).find_by_id(batch_id)
        if batch is None:
            return _err("get_batch", "batch_not_found",
                        f"no batch with id {batch_id!r}")
        transactions = TransactionRepository(conn).list_canonical(batch_id)
        bank = BankEntryRepository(conn).list_canonical(batch_id)
    finally:
        conn.close()
    ledger = [t for t in transactions if t.source is Source.INTERNAL_LEDGER]
    settlements = [t for t in transactions if t.source is Source.SETTLEMENT_REPORT]
    results = reconcile_batch(ledger, settlements, bank, ReconciliationConfig()).results
    return _EngineView(batch=batch, results=results, bank=bank,
                       ledger=ledger, settlements=settlements)


def _exposure_paise(result) -> int:
    if result.variance_paise is not None:
        return abs(result.variance_paise)
    return result.expected_amount_paise or 0


# ---------------------------------------------------------------------------
# Tools 2-6
# ---------------------------------------------------------------------------

def get_reconciliation_summary(batch_id: str, db: Database, filters: dict | None = None) -> dict:
    view = _load_view(batch_id, db)
    if isinstance(view, dict):
        return _err("get_reconciliation_summary", **view["error"])
    total = len(view.results)
    fully = sum(1 for r in view.results
                if r.status is ReconciliationStatus.FULLY_RECONCILED)
    counts: dict[str, int] = {}
    variance_total = 0
    for r in view.results:
        counts[r.status.value] = counts.get(r.status.value, 0) + 1
        variance_total += r.variance_paise or 0
    return _ok(
        "get_reconciliation_summary",
        batch_status=view.batch["status"],
        total_records=total,
        records_processed=total,
        fully_reconciled=fully,
        exceptions=total - fully,
        match_rate=round(fully / total, 4) if total else 0.0,
        status_counts=counts,
        total_variance_paise=variance_total,
    )


def list_exceptions(batch_id: str, db: Database, filters: dict | None = None) -> dict:
    view = _load_view(batch_id, db)
    if isinstance(view, dict):
        return _err("list_exceptions", **view["error"])
    filters = filters or {}
    wanted_status = filters.get("status")
    items = [
        {
            "payment_id": r.payment_id,
            "status": r.status.value,
            "severity": r.severity.value,
            "exposure_paise": _exposure_paise(r),
            "variance_paise": r.variance_paise,
            "expected_amount_paise": r.expected_amount_paise,
            "reason": r.reason,
            "evidence": r.evidence,
            "recommended_action": r.recommended_action,
        }
        for r in view.results
        if r.requires_review
        and (not wanted_status or r.status.value == wanted_status)
    ]
    items.sort(key=lambda i: (-i["exposure_paise"], i["payment_id"]))
    return _ok("list_exceptions", count=len(items), items=items)


def get_transaction_trace(payment_id: str, batch_id: str, db: Database) -> dict:
    conn = db.connect(init=False)
    try:
        batch = BatchRepository(conn).find_by_id(batch_id)
        if batch is None:
            return _err("get_transaction_trace", "batch_not_found",
                        f"no batch with id {batch_id!r}")
        transactions = TransactionRepository(conn).list_canonical(batch_id)
        bank = BankEntryRepository(conn).list_canonical(batch_id)
    finally:
        conn.close()

    ledger = [t for t in transactions
              if t.source is Source.INTERNAL_LEDGER and t.payment_id == payment_id]
    if not ledger:
        return _err("get_transaction_trace", "payment_not_found",
                    f"no ledger payment {payment_id!r} in batch {batch_id!r}")
    settlements = [t for t in transactions
                   if t.source is Source.SETTLEMENT_REPORT and t.payment_id == payment_id]
    results = reconcile_batch(
        [t for t in transactions if t.source is Source.INTERNAL_LEDGER],
        [t for t in transactions if t.source is Source.SETTLEMENT_REPORT],
        bank, ReconciliationConfig()).results
    decision = next((r for r in results if r.payment_id == payment_id), None)
    bank_entry = next((e for e in bank
                       if decision and e.bank_txn_id == decision.bank_txn_id), None)

    def _txn_view(t):
        return {
            "source_row_id": t.source_row_id, "transaction_type": t.transaction_type.value,
            "settlement_id": t.settlement_id, "settlement_utr": t.settlement_utr,
            "gross_amount_paise": t.gross_amount_paise, "fee_paise": t.fee_paise,
            "tax_paise": t.tax_paise, "debit_paise": t.debit_paise,
            "credit_paise": t.credit_paise,
            "net_contribution_paise": t.net_contribution_paise(),
            "transaction_at": t.transaction_at.isoformat(),
        }

    return _ok(
        "get_transaction_trace",
        payment_id=payment_id,
        ledger={**_txn_view(ledger[0]), "internal_id": ledger[0].source_row_id},
        settlements=[_txn_view(t) for t in settlements],
        bank={
            "bank_txn_id": bank_entry.bank_txn_id,
            "utr": bank_entry.utr,
            "credit_paise": bank_entry.credit_paise,
            "debit_paise": bank_entry.debit_paise,
            "value_date": bank_entry.value_date.isoformat(),
            "description_excerpt": _sanitize_untrusted(bank_entry.description),
        } if bank_entry else None,
        decision={
            "status": decision.status.value,
            "confidence": decision.confidence,
            "match_method": decision.match_method,
            "expected_amount_paise": decision.expected_amount_paise,
            "actual_amount_paise": decision.actual_amount_paise,
            "variance_paise": decision.variance_paise,
            "expected_breakdown_paise": decision.expected_breakdown_paise,
            "reason": decision.reason,
            "evidence": decision.evidence,
            "requires_review": decision.requires_review,
        } if decision else None,
    )


def get_cash_position(batch_id: str, db: Database, date_range_days: int = 7) -> dict:
    view = _load_view(batch_id, db)
    if isinstance(view, dict):
        return _err("get_cash_position", **view["error"])
    if not (view.ledger or view.settlements or view.bank):
        position = compute_cash_position(view.results, view.bank,
                                         opening_balance_paise=0, as_of=None,
                                         config=CashForecastConfig(
                                             horizon_days=date_range_days))
    else:
        as_of = compute_as_of(view.ledger, view.settlements, view.bank)
        position = compute_cash_position(
            view.results, view.bank, opening_balance_paise=0, as_of=as_of,
            config=CashForecastConfig(horizon_days=date_range_days))
    return _ok("get_cash_position", position=position)


def explain_exception(exception_id: str, batch_id: str, db: Database) -> dict:
    """exception_id is the payment_id of the review-flagged record."""
    view = _load_view(batch_id, db)
    if isinstance(view, dict):
        return _err("explain_exception", **view["error"])
    result = next((r for r in view.results if r.payment_id == exception_id), None)
    if result is None:
        return _err("explain_exception", "payment_not_found",
                    f"no record {exception_id!r} in batch {batch_id!r}")
    if not result.requires_review:
        return _err("explain_exception", "not_an_exception",
                    f"{exception_id} is {result.status.value}, not an exception")
    return _ok(
        "explain_exception",
        payment_id=result.payment_id,
        status=result.status.value,
        severity=result.severity.value,
        reason=result.reason,
        recommended_action=result.recommended_action,
        variance_paise=result.variance_paise,
        variance_rupees=format_paise_as_rupees(result.variance_paise)
        if result.variance_paise is not None else None,
        expected_amount_paise=result.expected_amount_paise,
        actual_amount_paise=result.actual_amount_paise,
        expected_breakdown_paise=result.expected_breakdown_paise,
        evidence=result.evidence,
    )
