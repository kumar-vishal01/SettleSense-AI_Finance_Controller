"""Status and exception policy (AGENTS.md sections 4-5).

Single source of truth for statuses, severity bands, review flags, and
recommended actions. Financial DECISIONS stay in reconciliation.py; this
module only classifies and describes.

Re-exported through backend.models for existing callers.
"""

from __future__ import annotations

from enum import Enum


class ReconciliationStatus(str, Enum):
    """Exactly one final status per logical payment."""

    FULLY_RECONCILED = "FULLY_RECONCILED"
    MISSING_IN_SETTLEMENT = "MISSING_IN_SETTLEMENT"
    MISSING_BANK_CREDIT = "MISSING_BANK_CREDIT"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DUPLICATE = "DUPLICATE"
    TIMING_DELAY = "TIMING_DELAY"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


#: Statuses that open an exception-queue entry.
EXCEPTION_STATUSES: frozenset[ReconciliationStatus] = frozenset(
    s for s in ReconciliationStatus if s is not ReconciliationStatus.FULLY_RECONCILED
)


class Severity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


#: Paise thresholds for AMOUNT_MISMATCH severity (default config values;
#: reconciliation passes its configured thresholds explicitly).
DEFAULT_MISMATCH_HIGH_PAISE = 100_000      # >= INR 1,000
DEFAULT_MISMATCH_MEDIUM_PAISE = 10_000     # >= INR 100


RECOMMENDED_ACTIONS: dict[ReconciliationStatus, str] = {
    ReconciliationStatus.FULLY_RECONCILED: "",
    ReconciliationStatus.MISSING_IN_SETTLEMENT: (
        "Verify the payment ID with the provider and request an updated settlement report."
    ),
    ReconciliationStatus.MISSING_BANK_CREDIT: (
        "Confirm with the bank whether the credit arrived; escalate if older than the delay window."
    ),
    ReconciliationStatus.AMOUNT_MISMATCH: (
        "Check adjustment, reserve, or bank charges against the gross-to-net waterfall."
    ),
    ReconciliationStatus.DUPLICATE: (
        "Remove the duplicated source row or confirm two genuine transactions share the reference."
    ),
    ReconciliationStatus.TIMING_DELAY: (
        "Re-run the batch after the configured settlement delay window."
    ),
    ReconciliationStatus.NEEDS_HUMAN_REVIEW: (
        "Compare the candidate records manually and confirm the correct link."
    ),
}

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}


def is_exception(status: ReconciliationStatus) -> bool:
    return status in EXCEPTION_STATUSES


def severity_for(
    status: ReconciliationStatus,
    variance_paise: int | None,
    *,
    mismatch_high_paise: int = DEFAULT_MISMATCH_HIGH_PAISE,
    mismatch_medium_paise: int = DEFAULT_MISMATCH_MEDIUM_PAISE,
) -> Severity:
    """Deterministic severity policy (moved from reconciliation.py)."""
    if status is ReconciliationStatus.FULLY_RECONCILED:
        return Severity.NONE
    if status is ReconciliationStatus.AMOUNT_MISMATCH:
        magnitude = abs(variance_paise or 0)
        if magnitude >= mismatch_high_paise:
            return Severity.HIGH
        if magnitude >= mismatch_medium_paise:
            return Severity.MEDIUM
        return Severity.LOW
    if status in (
        ReconciliationStatus.MISSING_IN_SETTLEMENT,
        ReconciliationStatus.MISSING_BANK_CREDIT,
        ReconciliationStatus.DUPLICATE,
    ):
        return Severity.HIGH
    return Severity.MEDIUM  # TIMING_DELAY, NEEDS_HUMAN_REVIEW
