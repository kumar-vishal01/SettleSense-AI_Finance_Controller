"""Canonical normalization (ARCHITECTURE.md section 3.3).

Converts validated raw rows into CanonicalTransaction / CanonicalBankEntry
models: trims whitespace, standardizes identifiers and UTRs, parses dates as
UTC, maps transaction types, and keeps the original row verbatim in
``raw_payload`` for audit and display.

Money: rupee amounts are converted to integer paise with Decimal-based
string arithmetic only. No float ever touches a monetary value.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from backend.models import CanonicalBankEntry, CanonicalTransaction, Source, TransactionType

#: Datetime formats accepted in inputs. All are interpreted as UTC.
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d",
)

#: Settlement ``type`` vocabulary; unknown types are rejected loudly.
_TRANSACTION_TYPES = {t.value for t in TransactionType}


# ---------------------------------------------------------------------------
# Scalar normalizers (pure, unit-tested)
# ---------------------------------------------------------------------------


def normalize_id(raw: str | None) -> str | None:
    """Trim an identifier. Empty becomes None (distinguish missing vs zero)."""
    if raw is None:
        return None
    cleaned = raw.strip()
    return cleaned or None


def normalize_utr(raw: str | None) -> str | None:
    """Standardize a UTR/reference: trim, uppercase, drop inner spaces."""
    if raw is None:
        return None
    cleaned = raw.strip().upper().replace(" ", "")
    return cleaned or None


def paise_from_int_string(raw: str) -> int:
    """Parse a paise column value. Ingestion already validated it, but this
    never silently coerces: failures raise ValueError."""
    cleaned = raw.strip()
    if not cleaned.isdigit():
        raise ValueError(f"not a non-negative integer paise value: {raw!r}")
    return int(cleaned)


def rupees_to_paise(raw: str) -> int:
    """Convert a decimal rupee string to integer paise via Decimal.

    For adapters that deliver rupees. Banker's rounding is avoided:
    half-up rounding on the exact decimal value, no float involved.
    """
    try:
        return int(
            (Decimal(raw.strip()) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
    except InvalidOperation as exc:
        raise ValueError(f"not a decimal rupee amount: {raw!r}") from exc


def parse_datetime_utc(raw: str) -> datetime | None:
    """Parse a timestamp into timezone-aware UTC, or None if unparseable."""
    cleaned = raw.strip()
    for fmt in _DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def normalize_transaction_type(raw: str) -> TransactionType:
    cleaned = raw.strip().lower()
    if cleaned not in _TRANSACTION_TYPES:
        raise ValueError(f"unknown transaction type: {raw!r}")
    return TransactionType(cleaned)


def required_datetime(raw: str, column: str) -> datetime:
    """Parse a datetime or raise — normalization never fabricates dates.

    A wall-clock fallback would make identical inputs produce different
    results across runs (breaking batch idempotency) and would invent a
    financial date the source never contained. Ingestion quarantines bad
    dates for CSV uploads; this guards programmatic callers too.
    """
    parsed = parse_datetime_utc(raw)
    if parsed is None:
        raise ValueError(f"unparseable date {raw!r} in {column}")
    return parsed


# ---------------------------------------------------------------------------
# Row normalizers
# ---------------------------------------------------------------------------


def normalize_internal_ledger(table) -> list[CanonicalTransaction]:
    """Typed InternalLedgerRow list -> canonical domain transactions."""
    if table.source is not Source.INTERNAL_LEDGER:
        raise ValueError(f"expected internal ledger table, got {table.source}")
    out: list[CanonicalTransaction] = []
    for row in table.rows:
        raw = row.raw()
        out.append(
            CanonicalTransaction(
                source=Source.INTERNAL_LEDGER,
                source_row_id=normalize_id(row.internal_id) or "",
                transaction_type=TransactionType.PAYMENT,
                payment_id=normalize_id(row.payment_id),
                order_id=normalize_id(row.order_id),
                currency=(row.currency or "INR").strip().upper(),
                gross_amount_paise=paise_from_int_string(row.amount_paise),
                transaction_at=required_datetime(row.created_at, "created_at"),
                raw_payload=raw,
            )
        )
    return out


def normalize_settlement_report(table) -> list[CanonicalTransaction]:
    """Typed SettlementRow list -> canonical domain transactions."""
    if table.source is not Source.SETTLEMENT_REPORT:
        raise ValueError(f"expected settlement table, got {table.source}")
    out: list[CanonicalTransaction] = []
    for row in table.rows:
        out.append(
            CanonicalTransaction(
                source=Source.SETTLEMENT_REPORT,
                source_row_id=normalize_id(row.entity_id) or "",
                entity_id=normalize_id(row.entity_id),
                transaction_type=normalize_transaction_type(row.type),
                payment_id=normalize_id(row.payment_id),
                order_id=normalize_id(row.order_id),
                settlement_id=normalize_id(row.settlement_id),
                settlement_utr=normalize_utr(row.settlement_utr),
                currency="INR",
                gross_amount_paise=paise_from_int_string(row.amount_paise),
                fee_paise=paise_from_int_string(row.fee_paise),
                tax_paise=paise_from_int_string(row.tax_paise),
                debit_paise=paise_from_int_string(row.debit_paise),
                credit_paise=paise_from_int_string(row.credit_paise),
                transaction_at=required_datetime(row.settled_at, "settled_at"),
                raw_payload=row.raw(),
            )
        )
    return out


def normalize_bank_statement(table) -> list[CanonicalBankEntry]:
    """Typed BankStatementRow list -> canonical domain entries."""
    if table.source is not Source.BANK_STATEMENT:
        raise ValueError(f"expected bank statement table, got {table.source}")
    out: list[CanonicalBankEntry] = []
    for row in table.rows:
        out.append(
            CanonicalBankEntry(
                source_row_id=normalize_id(row.bank_txn_id) or "",
                bank_txn_id=normalize_id(row.bank_txn_id) or "",
                value_date=required_datetime(row.value_date, "value_date"),
                description=row.description.strip(),
                utr=normalize_utr(row.utr),
                credit_paise=paise_from_int_string(row.credit_paise),
                debit_paise=paise_from_int_string(row.debit_paise),
                raw_payload=row.raw(),
            )
        )
    return out
