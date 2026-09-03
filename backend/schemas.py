"""API-boundary schemas (Pydantic) — versioned input/output contracts.

Boundary models live here and only here:
- raw row models (InternalLedgerRow / SettlementRow / BankStatementRow)
  carry validated-but-uncoerced source strings into normalization;
- ValidationErrorItem / BatchInputSummary describe validation outcomes.

Internal processing uses the explicit domain models in backend/models.py
(dataclasses), which import nothing from this file. All monetary fields are
integer-paise strings at the boundary and integer paise in the domain.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.models import BatchStatus

# ---------------------------------------------------------------------------
# Raw source-row contracts (validated strings, never coerced)
# ---------------------------------------------------------------------------

LEDGER_REQUIRED_COLUMNS: list[str] = [
    "internal_id", "order_id", "payment_id", "created_at",
    "amount_paise", "currency", "payment_status",
]
SETTLEMENT_REQUIRED_COLUMNS: list[str] = [
    "entity_id", "type", "payment_id", "order_id", "settlement_id",
    "settlement_utr", "amount_paise", "fee_paise", "tax_paise",
    "debit_paise", "credit_paise", "settled_at",
]
BANK_REQUIRED_COLUMNS: list[str] = [
    "bank_txn_id", "value_date", "description", "utr",
    "credit_paise", "debit_paise",
]


class _RawRow(BaseModel):
    """Base for raw rows: every field stays a string exactly as uploaded
    (whitespace and all); extra columns are tolerated and preserved."""

    model_config = ConfigDict(extra="allow")

    def raw(self) -> dict[str, str]:
        return {k: str(v) for k, v in self.model_dump().items()}


class InternalLedgerRow(_RawRow):
    internal_id: str
    order_id: str
    payment_id: str
    created_at: str
    amount_paise: str
    currency: str
    payment_status: str


class SettlementRow(_RawRow):
    entity_id: str
    type: str
    payment_id: str
    order_id: str
    settlement_id: str
    settlement_utr: str
    amount_paise: str
    fee_paise: str
    tax_paise: str
    debit_paise: str
    credit_paise: str
    settled_at: str


class BankStatementRow(_RawRow):
    bank_txn_id: str
    value_date: str
    description: str
    utr: str
    credit_paise: str
    debit_paise: str


class ValidationErrorItem(BaseModel):
    """Row-level validation failure as returned by the API: file, row
    number, field, message (+ stable code)."""

    file: str
    row_number: int
    field: str
    message: str
    code: str
    source: str = ""


class FileInputSummary(BaseModel):
    """Validation outcome for one uploaded file.

    duplicate_rows: exact repeats of an earlier row (kept for the engine).
    conflicting_rows: rows reusing a primary key with different values
    (also kept — the engine adjudicates them as DUPLICATE; reported here
    so uploads are never silently confusing).
    """

    file: str
    source: str
    total_rows: int
    valid_rows: int
    skipped_rows: int
    duplicate_rows: int
    conflicting_rows: int = 0


class BatchInputSummary(BaseModel):
    """Aggregate validation outcome for a three-file batch input."""

    files: list[FileInputSummary]
    total_rows: int
    valid_rows: int
    skipped_rows: int
    duplicate_rows: int
    conflicting_rows: int = 0
    errors: list[ValidationErrorItem] = Field(default_factory=list)
    valid: bool  # every row passed; duplicate/conflicting rows are kept, not fatal


# ---------------------------------------------------------------------------
# API response contracts
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """GET /health — liveness plus service identity and version."""

    status: str = Field(description="\"ok\" when the service is up")
    service: str = Field(description="stable service name")
    version: str = Field(description="semantic service version")
    environment: str = Field(description="local | docker | production")
    timezone: str = Field(description="display timezone; internals are UTC")


# ---------------------------------------------------------------------------
# Batch API contracts (phase 4)
# ---------------------------------------------------------------------------

class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class FileCounts(BaseModel):
    ledger_rows: int
    settlement_rows: int
    bank_rows: int


class ValidationView(BaseModel):
    valid: bool
    total_rows: int
    valid_rows: int
    skipped_rows: int
    duplicate_rows: int
    conflicting_rows: int
    errors: list[ValidationErrorItem]
    errors_truncated: bool = False  # response caps errors; DB keeps them all


class BatchCreateResponse(BaseModel):
    """POST /api/v1/batches. Status is always 'validated' in phase 4 —
    creating a batch never claims reconciliation."""

    batch_id: str
    source_hash: str
    status: BatchStatus = BatchStatus.VALIDATED
    idempotent: bool = False
    record_count: int
    counts: FileCounts
    validation: ValidationView
    started_at: str


class AuditEventView(BaseModel):
    action: str
    actor: str
    record_id: str = ""
    created_at: str
    details: dict = {}  # structured audit payload (ints/objects allowed)


class BatchDetailResponse(BaseModel):
    batch_id: str
    source_hash: str
    status: BatchStatus
    record_count: int
    counts: FileCounts
    skipped_rows: int
    duplicate_rows: int
    conflicting_rows: int
    validation_errors: list[ValidationErrorItem]
    started_at: str
    completed_at: str | None
    result_count: int = 0
    audit_events: list[AuditEventView] = []


class ResultItem(BaseModel):
    payment_id: str
    order_id: str | None = None
    status: str
    confidence: float
    match_method: str
    expected_amount_paise: int | None
    actual_amount_paise: int | None
    variance_paise: int | None
    expected_breakdown_paise: dict[str, int] | None = None
    severity: str = "none"
    reason: str
    evidence: list[str] = []
    requires_review: bool
    recommended_action: str = ""
    settlement_id: str | None = None
    bank_txn_id: str | None = None


class PaginatedResults(BaseModel):
    items: list[ResultItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    batch_status: str
    note: str | None = None


# ---------------------------------------------------------------------------
# Cash position contracts (phase 7)
# ---------------------------------------------------------------------------

class ForecastDay(BaseModel):
    day: int
    date: str
    projected_cash_paise: int
    note: str


class CashPositionResponse(BaseModel):
    """GET /api/v1/batches/{id}/cash-position. Forecast entries are
    projections — never booked or confirmed cash."""

    opening_balance_paise: int
    confirmed_credits_paise: int
    confirmed_debits_paise: int
    actual_cash_paise: int
    pending_settlements_paise: int
    expected_cash_paise: int
    expected_confirmed_cash_paise: int
    variance_paise: int
    unattributed_or_excluded_paise: int
    bank_charges_paise: int
    forecast_horizon_days: int
    forecast: list[ForecastDay]
    assumptions: list[str]
    confidence: str  # high | medium | low (documented policy in cash_forecast)
    batch_id: str
    batch_status: str
    as_of: str
