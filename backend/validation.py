"""Row-level validation rules and duplicate detection (AGENTS.md section 2:
"ingestion.py: read and validate external files" — validation logic lives
here, orchestrated by ingestion.py; matching/status logic never enters).

Every rule returns a structured RowError instead of raising, so one bad row
quarantines only itself. Error codes are stable strings for tests and the
future API layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.models import Source
from backend.normalization import parse_datetime_utc
from backend.schemas import (
    BANK_REQUIRED_COLUMNS,
    LEDGER_REQUIRED_COLUMNS,
    SETTLEMENT_REQUIRED_COLUMNS,
)

#: Columns that must exist in the file header.
REQUIRED_COLUMNS: dict[Source, list[str]] = {
    Source.INTERNAL_LEDGER: LEDGER_REQUIRED_COLUMNS,
    Source.SETTLEMENT_REPORT: SETTLEMENT_REQUIRED_COLUMNS,
    Source.BANK_STATEMENT: BANK_REQUIRED_COLUMNS,
}

#: Required columns that may legitimately be blank in a row (absent
#: reference data, e.g. a refund row has no UTR). Blank != zero.
NULLABLE_COLUMNS: dict[Source, set[str]] = {
    Source.INTERNAL_LEDGER: set(),
    Source.SETTLEMENT_REPORT: {"settlement_utr"},
    Source.BANK_STATEMENT: {"utr"},
}

#: Columns that must hold non-negative integer paise strings.
PAISE_COLUMNS: dict[Source, list[str]] = {
    Source.INTERNAL_LEDGER: ["amount_paise"],
    Source.SETTLEMENT_REPORT: [
        "amount_paise", "fee_paise", "tax_paise", "debit_paise", "credit_paise",
    ],
    Source.BANK_STATEMENT: ["credit_paise", "debit_paise"],
}

#: Columns parsed as datetimes (format validated here; conversion in
#: normalization so raw strings survive for audit).
DATE_COLUMNS: dict[Source, list[str]] = {
    Source.INTERNAL_LEDGER: ["created_at"],
    Source.SETTLEMENT_REPORT: ["settled_at"],
    Source.BANK_STATEMENT: ["value_date"],
}

#: Primary-key column per source, used for duplicate/conflict detection.
KEY_COLUMN: dict[Source, str] = {
    Source.INTERNAL_LEDGER: "internal_id",
    Source.SETTLEMENT_REPORT: "entity_id",
    Source.BANK_STATEMENT: "bank_txn_id",
}

#: MVP is single-currency (PRD: "currency: INR"). Case-insensitive.
SUPPORTED_CURRENCIES: frozenset[str] = frozenset({"INR"})

#: Settlement ``type`` vocabulary; anything else is rejected loudly.
ALLOWED_TRANSACTION_TYPES: frozenset[str] = frozenset(
    {"payment", "refund", "adjustment", "transfer"}
)

#: OWASP CSV-injection prefixes (= + - @ and tab). Paise columns are checked
#: separately with a clearer amount error, so "-" handling doesn't collide.
_INJECTION_PREFIXES = ("=", "@", "+", "-", "\t")


@dataclass
class RowError:
    """One validation failure tied to a specific source row."""

    source: Source
    row_number: int          # 1-based data row number as it appeared in the file
    column: str
    message: str
    code: str                # stable machine-readable error class
    file_name: str = ""      # upload name when provided; else the source slug

    def to_dict(self) -> dict[str, str | int]:
        return {
            "source": self.source.value,
            "file": self.file_name or self.source.value,
            "row_number": self.row_number,
            "column": self.column,
            "field": self.column,
            "message": self.message,
            "code": self.code,
        }


def validate_row(row: dict[str, str], source: Source, row_number: int) -> RowError | None:
    """Return the first problem found in a row, or None if the row is valid.

    Checks, in order: required/blank fields, formula injection, integer
    paise, currency, transaction type, date formats. First-error semantics
    keep messages precise (one cause per skipped row).
    """
    for column in REQUIRED_COLUMNS[source]:
        blank = column not in row or not row[column].strip()
        if blank and column not in NULLABLE_COLUMNS[source]:
            return RowError(
                source, row_number, column,
                "required value is missing or blank", code="missing_required",
            )

    for column, value in row.items():
        if column in PAISE_COLUMNS[source]:
            continue  # sign/format handled below with an amount-specific error
        if value.startswith(_INJECTION_PREFIXES):
            return RowError(
                source, row_number, column,
                "value starts with a formula-injection character (=, +, -, @, tab)",
                code="formula_injection",
            )

    for column in PAISE_COLUMNS[source]:
        raw = row.get(column, "")
        if not raw.strip().isdigit():
            return RowError(
                source, row_number, column,
                f"expected a non-negative integer paise value, got {raw!r}",
                code="invalid_amount",
            )

    if source is Source.INTERNAL_LEDGER:
        currency = row.get("currency", "").strip().upper()
        if currency not in SUPPORTED_CURRENCIES:
            return RowError(
                source, row_number, "currency",
                f"unsupported currency {currency!r}; MVP supports INR only",
                code="unsupported_currency",
            )

    if source is Source.SETTLEMENT_REPORT:
        row_type = row.get("type", "").strip().lower()
        if row_type not in ALLOWED_TRANSACTION_TYPES:
            return RowError(
                source, row_number, "type",
                f"unknown transaction type {row.get('type')!r} "
                "(expected payment, refund, adjustment, or transfer)",
                code="unknown_transaction_type",
            )

    for column in DATE_COLUMNS[source]:
        raw = row.get(column, "")
        if parse_datetime_utc(raw) is None:
            return RowError(
                source, row_number, column,
                f"unparseable date {raw!r}", code="invalid_date",
            )

    return None


@dataclass
class DuplicateReport:
    """Outcome of duplicate detection over one file's valid rows.

    exact_duplicates: rows whose every field repeats an earlier row —
    counted and REPORTED but never dropped here, because duplicate source
    rows are financial evidence the reconciliation engine must adjudicate
    as status DUPLICATE (dropping them would hide money).
    """

    duplicate_row_numbers: list[int]
    conflicting: list[RowError]


def detect_duplicates(
    valid_rows: list[dict[str, str]], source: Source, row_numbers: list[int]
) -> DuplicateReport:
    """Exact-duplicate counting + primary-key conflict quarantine.

    A row repeating an earlier row field-for-field is a duplicate (kept).
    A row reusing a primary key with DIFFERENT content is a conflict — also
    KEPT: the reconciliation engine must see the evidence to return DUPLICATE
    status. Ingestion reports both classes; it never drops financial rows.
    """
    seen_exact: set[tuple[tuple[str, str], ...]] = set()
    seen_keys: dict[str, tuple[tuple[str, str], ...]] = {}
    key_column = KEY_COLUMN[source]

    duplicates: list[int] = []
    conflicts: list[RowError] = []
    for row, row_number in zip(valid_rows, row_numbers):
        fingerprint = tuple(sorted(row.items()))
        key = row.get(key_column, "").strip()

        if fingerprint in seen_exact:
            duplicates.append(row_number)
            continue
        seen_exact.add(fingerprint)

        if key and key in seen_keys and seen_keys[key] != fingerprint:
            conflicts.append(
                RowError(
                    source, row_number, key_column,
                    f"row reuses {key_column} {key!r} with different values "
                    "than an earlier row",
                    code="conflicting_key",
                )
            )
            continue
        if key:
            seen_keys[key] = fingerprint

    return DuplicateReport(duplicate_row_numbers=duplicates, conflicting=conflicts)
