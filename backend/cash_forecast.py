"""Cash position and forward forecast (ARCHITECTURE.md section 3.8).

Definitions (integer paise, documented denominators):

    actual_cash        = opening_balance + confirmed_credits - confirmed_debits
    expected_cash      = actual_cash + eligible_pending_settlements
    cash_variance      = actual_confirmed_cash - expected_confirmed_cash

What counts as CONFIRMED (money we can book):
- bank credits linked by the engine to FULLY_RECONCILED or AMOUNT_MISMATCH
  decisions (the bank row is real; a mismatch shows in variance, not in
  cash presence);
- every bank debit EXCEPT rows implicated in duplicates (charges are real).

What is EXCLUDED from confirmed cash (ambiguous / unresolved):
- credits claimed by DUPLICATE decisions (a duplicated statement row is a
  reporting artifact until a human resolves it — booking it risks
  double-counting);
- credits claimed by NEEDS_HUMAN_REVIEW (e.g. currency conflicts);
- unlinked credits (the ambiguous twins, orphan credits). They are reported
  in ``unattributed_or_excluded_paise`` — never silently dropped.

Expected CONFIRMED cash (what should have landed by as_of):
- opening + expected net of FULLY_RECONCILED / AMOUNT_MISMATCH /
  MISSING_BANK_CREDIT payments. MISSING_IN_SETTLEMENT has no settlement, so
  no landing expectation. DUPLICATE / NEEDS_HUMAN_REVIEW are excluded from
  BOTH sides (symmetric exclusion keeps variance meaningful).

Eligible PENDING settlements: TIMING_DELAY payments only — young
settlements plausibly still in transit. Old missing credits are NOT pending;
they are variance.

Forecast: projected_cash(day) = actual_cash + pending once
``settle_assumption_days`` has elapsed, flat afterwards. Forecast cash is
NEVER booked/confirmed cash — every payload repeats that in assumptions and
the per-day note.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.models import (
    CanonicalBankEntry,
    ReconciliationResult,
    ReconciliationStatus,
)

#: statuses whose linked bank credits are booked as confirmed cash
CONFIRMING_STATUSES = (
    ReconciliationStatus.FULLY_RECONCILED,
    ReconciliationStatus.AMOUNT_MISMATCH,
)
#: statuses whose expected net should have landed by as_of
EXPECTED_LANDED_STATUSES = (
    ReconciliationStatus.FULLY_RECONCILED,
    ReconciliationStatus.AMOUNT_MISMATCH,
    ReconciliationStatus.MISSING_BANK_CREDIT,
)


@dataclass(frozen=True)
class CashForecastConfig:
    horizon_days: int = 7
    settle_assumption_days: int = 1  # pending settles within one banking day


def compute_cash_position(
    results: list[ReconciliationResult],
    bank_entries: list[CanonicalBankEntry],
    *,
    opening_balance_paise: int,
    as_of: datetime | None,
    config: CashForecastConfig | None = None,
) -> dict:
    """Pure calculation of the cash-position payload (schema-shaped dict)."""
    cfg = config or CashForecastConfig()

    # -- classify bank rows by engine decision -----------------------------
    confirmed_bank_ids: set[str] = set()
    excluded_bank_ids: set[str] = set()
    for r in results:
        if not r.bank_txn_id:
            continue
        if r.status in CONFIRMING_STATUSES:
            confirmed_bank_ids.add(r.bank_txn_id)
        else:  # DUPLICATE, NEEDS_HUMAN_REVIEW, currency conflicts
            excluded_bank_ids.add(r.bank_txn_id)

    confirmed_credits = 0
    confirmed_debits = 0
    unattributed_or_excluded = 0
    bank_charges = 0  # debits with no settlement expectation (fees/charges)
    for entry in bank_entries:
        if entry.bank_txn_id in confirmed_bank_ids:
            confirmed_credits += entry.credit_paise
            confirmed_debits += entry.debit_paise
        elif entry.bank_txn_id in excluded_bank_ids:
            unattributed_or_excluded += entry.credit_paise
        else:
            # unlinked row: debits (charges) are real cash out; credits stay
            # unattributed until something claims them
            confirmed_debits += entry.debit_paise
            bank_charges += entry.debit_paise
            unattributed_or_excluded += entry.credit_paise

    # -- expectations -------------------------------------------------------
    expected_confirmed = opening_balance_paise
    pending = 0
    for r in results:
        if r.status in EXPECTED_LANDED_STATUSES and r.expected_amount_paise is not None:
            expected_confirmed += r.expected_amount_paise
        elif r.status is ReconciliationStatus.TIMING_DELAY:
            pending += r.expected_amount_paise or 0

    actual_cash = opening_balance_paise + confirmed_credits - confirmed_debits
    expected_cash = actual_cash + pending
    variance = actual_cash - expected_confirmed

    # -- forecast -----------------------------------------------------------
    forecast = []
    assumptions = [
        "Processed settlements settle within one banking day",
        "Unresolved and ambiguous amounts are excluded from confirmed cash",
        "Duplicate statement rows are excluded pending human resolution",
        "Eligible pending settlements are timing-delayed credits only",
        "Forecast cash is NOT booked or confirmed cash",
    ]
    if as_of is None:
        # an empty batch has no date anchor: nothing to forecast
        assumptions.append("Batch contains no records: no forecast is produced")
    for day in range(1, cfg.horizon_days + 1) if as_of is not None else ():
        projected = actual_cash + (
            pending if day >= max(1, cfg.settle_assumption_days) else 0
        )
        forecast.append({
            "day": day,
            "date": (as_of + timedelta(days=day)).date().isoformat(),
            "projected_cash_paise": projected,
            "note": "includes pending settlements; forecast is not booked cash",
        })

    return {
        "opening_balance_paise": opening_balance_paise,
        "confirmed_credits_paise": confirmed_credits,
        "confirmed_debits_paise": confirmed_debits,
        "actual_cash_paise": actual_cash,
        "pending_settlements_paise": pending,
        "expected_cash_paise": expected_cash,
        "expected_confirmed_cash_paise": expected_confirmed,
        "variance_paise": variance,
        "unattributed_or_excluded_paise": unattributed_or_excluded,
        "bank_charges_paise": bank_charges,
        "forecast_horizon_days": cfg.horizon_days,
        "forecast": forecast,
        "assumptions": assumptions,
        "confidence": _confidence(results, unattributed_or_excluded, pending),
    }


def _confidence(
    results: list[ReconciliationResult],
    unattributed_paise: int,
    pending_paise: int,
) -> str:
    """Reliability of the position: low when ambiguity exists, medium when
    money is in flight, high only for a fully clean batch."""
    statuses = {r.status for r in results}
    if (
        ReconciliationStatus.DUPLICATE in statuses
        or ReconciliationStatus.NEEDS_HUMAN_REVIEW in statuses
        or unattributed_paise > 0
    ):
        return "low"
    if pending_paise > 0 or any(
        s is not ReconciliationStatus.FULLY_RECONCILED for s in statuses
    ):
        return "medium"
    return "high"
