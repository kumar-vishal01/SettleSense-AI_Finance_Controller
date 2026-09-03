"""Structured errors for ingestion and validation (never swallowed).

Phase 3 note on naming: TECHNICAL_DESIGN.md reserves an "exception engine"
concept for the *reconciliation status* engine (DUPLICATE, AMOUNT_MISMATCH,
...). That financial logic stays in reconciliation.py per AGENTS.md section 2
(`matching.py` = candidates only, `reconciliation.py` = status decisions).
This module holds structured *error types* raised/returned while reading and
validating input, so callers can distinguish file rejection from row
quarantine from programmatic misuse.
"""

from __future__ import annotations

from backend.models import Source


class SettleSenseError(Exception):
    """Base class for structured, machine-readable errors."""

    def to_dict(self) -> dict[str, str | int]:
        raise NotImplementedError


class IngestionError(SettleSenseError):
    """File-level rejection: the whole file is unusable.

    Raised for missing required columns, unreadable/unsupported content,
    oversized files, and row-count overruns. Row-level problems are NOT
    raised — they are returned as row errors so a batch can partially
    process with visible skips (ARCHITECTURE.md section 7).
    """

    def __init__(self, source: Source, message: str, errors: list | None = None):
        super().__init__(message)
        self.source = source
        self.errors = errors or []

    def to_dict(self) -> dict[str, str | int]:
        return {
            "error": "ingestion_error",
            "source": self.source.value,
            "message": str(self),
        }


class UnsupportedSourceError(SettleSenseError):
    """The input variation is recognized but not supported by the MVP.

    Examples: non-INR currency datasets (per-file), XLSX workbooks, API
    adapters — anything that is a source-shape decision, not bad data.
    """
