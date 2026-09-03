"""Gross-to-net and money calculations — pure functions, integer paise only.

Moved out of matching.py/reconciliation.py (phase 5): AGENTS.md section 2
assigns candidate generation/scoring to matching.py and financial formulas
to a calculation concern. No floats ever touch a monetary value here.
"""

from __future__ import annotations

from decimal import Decimal

from backend.models import CanonicalTransaction

WATERFALL_KEYS = (
    "gross_amount_paise", "fee_paise", "tax_paise",
    "debit_paise", "credit_paise", "net_paise",
)


def aggregate_settlement_group(rows: list[CanonicalTransaction]) -> dict[str, int]:
    """Sum the gross-to-net waterfall components across a payment's rows.

    expected_net = gross - fee - tax - refund/other debit + adjustment credit

    Zero-valued components are legitimate; "absent" is the caller's concern
    (zero rows vs no rows) and is never conflated here.
    """
    totals = {key: 0 for key in WATERFALL_KEYS}
    for row in rows:
        totals["gross_amount_paise"] += row.gross_amount_paise
        totals["fee_paise"] += row.fee_paise
        totals["tax_paise"] += row.tax_paise
        totals["debit_paise"] += row.debit_paise
        totals["credit_paise"] += row.credit_paise
        totals["net_paise"] += row.net_contribution_paise()
    return totals


def waterfall_breakdown(totals: dict[str, int]) -> dict[str, int]:
    """The five formula inputs recorded with every result for audit."""
    return {
        key: totals[key] for key in WATERFALL_KEYS if key != "net_paise"
    }


def variance_paise(actual_paise: int, expected_paise: int) -> int:
    """Signed variance: positive = bank credit higher than expected net."""
    return actual_paise - expected_paise


def within_tolerance(variance: int, amount_tolerance_paise: int) -> bool:
    """|variance| at or below the configured tolerance still reconciles."""
    return abs(variance) <= amount_tolerance_paise


def expected_net_from_components(
    gross: int, fee: int = 0, tax: int = 0, debit: int = 0, credit: int = 0
) -> int:
    """The formula as one pure function (mirrors net_contribution_paise)."""
    return gross - fee - tax - debit + credit


def format_paise_as_rupees(paise: int) -> str:
    """Exact paise -> rupees string for display. Decimal arithmetic only:
    floats must never touch monetary values, even for formatting."""
    return str((Decimal(paise) / 100).quantize(Decimal("0.01")))
