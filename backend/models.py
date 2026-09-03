"""Canonical domain models for SettleSense.

These are the single source of truth for the shape of data inside the
reconciliation engine. Source adapters and normalization convert external
rows into these models; matching, reconciliation, and metrics depend only
on these models, never on CSV column names or framework types.

Explicit dataclasses (not Pydantic): the domain layer stays framework-free;
validation happens at the ingestion boundary (backend/schemas.py) and
conversion here is trusted, typed code.

Money rules (AGENTS.md section 3):
- every monetary field is integer paise
- raw source values are preserved verbatim in ``raw_payload`` for audit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field  # result/report contracts only


class Source(str, Enum):
    INTERNAL_LEDGER = "internal_ledger"
    SETTLEMENT_REPORT = "settlement_report"
    BANK_STATEMENT = "bank_statement"


class TransactionType(str, Enum):
    """Note on TRANSFER (review L4): accepted at ingestion, aggregated in the
    waterfall like any other row (its gross/fee/tax/debit/credit all count).
    No transfer-specific semantics exist yet; an explicit policy is decided
    when the synthetic dataset grows transfer scenarios."""

    PAYMENT = "payment"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    TRANSFER = "transfer"


# Statuses, severity, and exception policy live in backend/statuses.py
# (phase 5). Re-exported here because domain code historically imports them
# from models — one source of truth, two import paths.
from backend.statuses import (  # noqa: E402,F401
    EXCEPTION_STATUSES,
    RECOMMENDED_ACTIONS,
    ReconciliationStatus,
    Severity,
)


class BatchStatus(str, Enum):
    """Lifecycle of one batch. Phase 4 stops at VALIDATED: creating a batch
    never claims reconciliation (matching is wired in a later phase)."""

    VALIDATED = "validated"        # files ingested, normalized, persisted
    RECONCILING = "reconciling"    # reserved: engine running
    RECONCILED = "reconciled"      # reserved: results available
    FAILED = "failed"              # terminal processing failure


@dataclass(frozen=True)
class CanonicalTransaction:
    """One row of the internal ledger or the settlement report."""

    source: Source
    source_row_id: str
    transaction_type: TransactionType
    transaction_at: datetime
    entity_id: str | None = None
    payment_id: str | None = None
    order_id: str | None = None
    settlement_id: str | None = None
    settlement_utr: str | None = None
    currency: str = "INR"
    gross_amount_paise: int = 0
    fee_paise: int = 0
    tax_paise: int = 0
    debit_paise: int = 0
    credit_paise: int = 0
    raw_payload: dict[str, str] = field(default_factory=dict)

    def net_contribution_paise(self) -> int:
        """Gross-to-net contribution of this row inside the waterfall.

        gross - fee - tax - refund/other debit + adjustment credit
        """
        return (
            self.gross_amount_paise
            - self.fee_paise
            - self.tax_paise
            - self.debit_paise
            + self.credit_paise
        )


@dataclass(frozen=True)
class CanonicalBankEntry:
    """One row of the bank statement."""

    source_row_id: str
    bank_txn_id: str
    value_date: datetime
    description: str = ""
    utr: str | None = None
    currency: str = "INR"
    credit_paise: int = 0
    debit_paise: int = 0
    raw_payload: dict[str, str] = field(default_factory=dict)

    def net_amount_paise(self) -> int:
        """Signed net movement of this bank row (credit minus debit)."""
        return self.credit_paise - self.debit_paise


class ReconciliationResult(BaseModel):
    """Final decision for one logical payment. Required contract fields
    from AGENTS.md section 7 plus queue-management fields."""

    payment_id: str
    status: ReconciliationStatus
    confidence: float
    match_method: str
    expected_amount_paise: int | None = None
    actual_amount_paise: int | None = None
    variance_paise: int | None = None
    #: Gross-to-net formula inputs (integer paise) persisted with the result
    #: for audit — ARCHITECTURE.md 3.5. None when no settlement waterfall
    #: exists (e.g. MISSING_IN_SETTLEMENT, duplicate short-circuits).
    expected_breakdown_paise: dict[str, int] | None = None
    severity: Severity = Severity.NONE
    reason: str
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    requires_review: bool = False
    settlement_id: str | None = None
    bank_txn_id: str | None = None

    def to_contract_dict(self) -> dict[str, Any]:
        """The AGENTS.md section 7 result contract, JSON-ready."""
        return {
            "payment_id": self.payment_id,
            "status": self.status.value,
            "confidence": self.confidence,
            "match_method": self.match_method,
            "expected_amount_paise": self.expected_amount_paise,
            "actual_amount_paise": self.actual_amount_paise,
            "variance_paise": self.variance_paise,
            "expected_breakdown_paise": self.expected_breakdown_paise,
            "reason": self.reason,
            "evidence": self.evidence,
            "requires_review": self.requires_review,
        }


class BatchSummary(BaseModel):
    """Aggregate counts for one batch (no ground truth involved)."""

    total_records: int
    records_processed: int = 0
    fully_reconciled: int
    exceptions: int
    status_counts: dict[str, int]
    match_rate: float
    total_variance_paise: int
    max_abs_variance_paise: int


class EvaluationReport(BaseModel):
    """Ground-truth comparison. Evaluation only — never produced by or
    passed into the runtime reconciliation engine."""

    dataset_version: str
    total_ground_truth: int
    auto_matches: int
    correct_auto_matches: int
    false_auto_matches: int
    precision: float
    recall: float
    matchable_ground_truth: int
    planted_anomalies: int
    anomalies_correctly_stated: int
    exception_capture_rate: float
    status_mismatches: list[dict[str, str]]
    scenario_totals: dict[str, int] = {}
    scenario_captured: dict[str, int] = {}
    #: per-record wrong auto-matches with expected vs linked IDs
    false_positive_details: list[dict[str, str]] = []
