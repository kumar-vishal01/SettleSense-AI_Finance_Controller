"""Runtime configuration for SettleSense.

All monetary values are integer paise. Money is never stored or compared as
floating point; the only floats in the system are confidence scores, which are
not financial values.

Thresholds mirror ARCHITECTURE.md section 3.4 and TECHNICAL_DESIGN.md
section 6. Changing a threshold never changes the past: persisted results keep
the configuration they were produced with.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationConfig:
    """Deterministic knobs for one reconciliation run."""

    #: Bank credits may lag the settlement date by at most this many days
    #: to be considered date-compatible candidates.
    date_window_days: int = 3

    #: |bank_credit - expected_net| at or below this value (paise) still
    #: counts as reconciled. Bank rounding differences stay under ~1 INR.
    amount_tolerance_paise: int = 100

    #: Score at or above which a scored candidate may auto-match.
    auto_match_threshold: float = 0.95

    #: Score band [strong_band_lower, auto_match_threshold) auto-matches only
    #: when the candidate is unique and has no conflicting evidence.
    strong_band_lower: float = 0.80

    #: Score band [review_band_lower, strong_band_lower) always goes to a
    #: human. Below review_band_lower the record stays unresolved/review.
    review_band_lower: float = 0.60

    #: Settlements younger than this many days (relative to batch as_of)
    #: with no bank credit are TIMING_DELAY rather than MISSING_BANK_CREDIT.
    timing_delay_days: int = 2

    currency: str = "INR"
    forecast_horizon_days: int = 7

    #: Severity thresholds for AMOUNT_MISMATCH, in paise.
    mismatch_high_paise: int = 100_000      # >= INR 1,000
    mismatch_medium_paise: int = 10_000     # >= INR 100

    #: Hard ingestion limits (upload safety).
    max_file_bytes: int = 10 * 1024 * 1024
    max_rows_per_file: int = 10_000


#: Component weights for scored (non-exact) candidate matching, from
#: ARCHITECTURE.md section 3.4 pass 3. Payment-ID weight (0.40) applies only
#: to ledger-to-settlement matching; bank statements carry no payment IDs.
SCORE_WEIGHTS: dict[str, float] = {
    "payment_id": 0.40,
    "utr": 0.25,
    "amount": 0.20,
    "date": 0.10,
    "currency": 0.05,
}
