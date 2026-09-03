"""File ingestion: read, parse, validate, and type raw source rows.

Responsibility split (phase 3):
- ingestion.py — reading/parsing files and file-level rejection (columns,
  size, row caps, binary content), then orchestrating row validation and
  duplicate detection from validation.py, producing typed raw rows;
- validation.py — the row-level rules themselves;
- normalization.py — converting typed raw rows into canonical domain models.

The engine and API never see CSV column names — only typed rows and
canonical models.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

from backend.exceptions import IngestionError  # re-exported for callers
from backend.models import Source
from backend.schemas import (
    BankStatementRow,
    BatchInputSummary,
    FileInputSummary,
    InternalLedgerRow,
    SettlementRow,
    ValidationErrorItem,
)
from backend.validation import (
    REQUIRED_COLUMNS,
    RowError,  # noqa: F401  (re-export: callers historically import it here)
    detect_duplicates,
    validate_row,
)

#: source -> typed raw-row model used to carry validated rows forward
RAW_ROW_MODELS: dict = {
    Source.INTERNAL_LEDGER: InternalLedgerRow,
    Source.SETTLEMENT_REPORT: SettlementRow,
    Source.BANK_STATEMENT: BankStatementRow,
}


@dataclass
class RawTable:
    """One file's validated content: typed raw rows plus every error.

    ``rows`` are typed Pydantic row models (boundary contracts). Invalid
    rows are quarantined individually and reported in ``errors``; exact
    duplicate rows are KEPT (financial evidence) and only counted in
    ``duplicate_rows`` / listed in ``duplicate_row_numbers``.
    """

    source: Source
    file_name: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list = field(default_factory=list)  # typed rows per source
    errors: list[RowError] = field(default_factory=list)
    duplicate_row_numbers: list[int] = field(default_factory=list)
    # rows reusing a primary key with different values: KEPT for the engine
    # (which adjudicates DUPLICATE status) and reported here for visibility
    conflicting_row_numbers: list[int] = field(default_factory=list)

    @property
    def skipped_rows(self) -> int:
        return len(self.errors)

    @property
    def duplicate_rows(self) -> int:
        return len(self.duplicate_row_numbers)

    @property
    def conflicting_rows(self) -> int:
        return len(self.conflicting_row_numbers)

    @property
    def is_empty(self) -> bool:
        return not self.rows

    def summary(self) -> FileInputSummary:
        return FileInputSummary(
            file=self.file_name or self.source.value,
            source=self.source.value,
            total_rows=len(self.rows) + self.skipped_rows,
            valid_rows=len(self.rows),
            skipped_rows=self.skipped_rows,
            duplicate_rows=self.duplicate_rows,
            conflicting_rows=self.conflicting_rows,
        )


def read_csv_source(
    content: bytes | str,
    source: Source,
    config=None,
    file_name: str = "",
) -> RawTable:
    """Parse and validate one uploaded CSV into typed raw rows.

    File-level problems raise IngestionError; row-level problems quarantine
    the row into ``errors``; exact duplicates are kept and counted.
    """
    from backend.config import ReconciliationConfig

    cfg = config or ReconciliationConfig()
    size_bytes = len(content) if isinstance(content, bytes) else len(content.encode("utf-8"))
    if size_bytes > cfg.max_file_bytes:
        raise IngestionError(source, f"file exceeds {cfg.max_file_bytes} bytes")
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise IngestionError(
                source, f"file is not valid UTF-8 text: {exc}") from exc
    else:
        text = content.lstrip("\ufeff")
    if "\x00" in text:
        raise IngestionError(source, "unsupported content: binary/null bytes in CSV")

    try:
        frame = pd.read_csv(
            io.StringIO(text),
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=True,
        )
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise IngestionError(source, f"unreadable CSV: {exc}") from exc

    table = RawTable(source=source, file_name=file_name, columns=list(frame.columns))
    missing = [c for c in REQUIRED_COLUMNS[source] if c not in frame.columns]
    if missing:
        raise IngestionError(source, f"missing required columns: {', '.join(missing)}")

    records = frame.to_dict(orient="records")
    if len(records) > cfg.max_rows_per_file:
        raise IngestionError(
            source, f"row count {len(records)} exceeds limit {cfg.max_rows_per_file}"
        )

    valid_dicts: list[dict[str, str]] = []
    valid_row_numbers: list[int] = []
    for idx, row in enumerate(records, start=2):  # +2: header + 1-based rows
        error = validate_row(row, source, idx)
        if error is not None:
            error.file_name = file_name
            table.errors.append(error)
            continue
        valid_dicts.append(row)
        valid_row_numbers.append(idx)

    duplicate_report = detect_duplicates(valid_dicts, source, valid_row_numbers)
    table.duplicate_row_numbers = duplicate_report.duplicate_row_numbers
    table.conflicting_row_numbers = [c.row_number for c in duplicate_report.conflicting]

    # Senior-review rule: conflicting rows are NEVER dropped here. Hiding a
    # key conflict from the engine would let a payment reconcile cleanly over
    # a corrupted statement. The engine returns DUPLICATE for such payments;
    # ingestion only counts and reports.
    row_model = RAW_ROW_MODELS[source]
    for row in valid_dicts:
        table.rows.append(row_model(**row))

    return table


def summarize_input(*tables: RawTable) -> BatchInputSummary:
    """Aggregate one batch's file validation outcome (three tables)."""
    files = [t.summary() for t in tables]
    errors = [
        ValidationErrorItem(
            file=e.file_name or e.source.value,
            row_number=e.row_number,
            field=e.column,
            message=e.message,
            code=e.code,
            source=e.source.value,
        )
        for t in tables
        for e in t.errors
    ]
    return BatchInputSummary(
        files=files,
        total_rows=sum(f.total_rows for f in files),
        valid_rows=sum(f.valid_rows for f in files),
        skipped_rows=sum(f.skipped_rows for f in files),
        duplicate_rows=sum(f.duplicate_rows for f in files),
        conflicting_rows=sum(f.conflicting_rows for f in files),
        errors=errors,
        valid=all(f.skipped_rows == 0 for f in files),
    )
