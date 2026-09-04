"""Phase 5 calculation module: pure paise math for the gross-to-net
waterfall, tolerance, variance, and exact display formatting."""

from __future__ import annotations

import pytest

from backend.calculations import (
    aggregate_settlement_group,
    expected_net_from_components,
    format_paise_as_rupees,
    variance_paise,
    waterfall_breakdown,
    within_tolerance,
)
from tests.factories import settlement_txn


class TestWaterfall:
    def test_plain_payment_net(self):
        totals = aggregate_settlement_group(
            [settlement_txn(gross=100_000, fee=2_000, tax=360)]
        )
        assert totals["net_paise"] == 97_640

    def test_refund_and_adjustment_rows_flow_through(self):
        totals = aggregate_settlement_group([
            settlement_txn(gross=100_000, fee=2_000, tax=360),
            settlement_txn(entity_id="e_r", gross=0, fee=0, tax=0, debit=30_000),
            settlement_txn(entity_id="e_a", gross=0, fee=0, tax=0, credit=400),
        ])
        # 100000 - 2000 - 360 - 30000 + 400
        assert totals["net_paise"] == 68_040
        assert totals["debit_paise"] == 30_000
        assert totals["credit_paise"] == 400

    def test_breakdown_records_the_five_formula_inputs(self):
        totals = aggregate_settlement_group(
            [settlement_txn(gross=100_000, fee=2_000, tax=360)])
        breakdown = waterfall_breakdown(totals)
        assert set(breakdown) == {
            "gross_amount_paise", "fee_paise", "tax_paise",
            "debit_paise", "credit_paise"}
        assert sum(breakdown.values()) == 102_360  # components sum, not net

    def test_zero_components_are_legitimate_not_missing(self):
        totals = aggregate_settlement_group(
            [settlement_txn(gross=0, fee=0, tax=0, credit=500)])
        assert totals["net_paise"] == 500

    def test_formula_helper_mirrors_row_contribution(self):
        row = settlement_txn(gross=250_000, fee=5_000, tax=900, debit=1_000, credit=200)
        assert expected_net_from_components(
            250_000, fee=5_000, tax=900, debit=1_000, credit=200
        ) == row.net_contribution_paise()


class TestFeeTaxMismatchManifestation:
    """A fee or tax that disagrees with the merchant's expectation shows up
    as bank variance: the waterfall is computed FROM the settlement's fee,
    so any fee/tax inflation directly shifts expected net."""

    def test_inflated_fee_creates_exact_variance(self):
        base = aggregate_settlement_group(
            [settlement_txn(gross=100_000, fee=2_000, tax=360)])
        inflated = aggregate_settlement_group(
            [settlement_txn(gross=100_000, fee=4_000, tax=360)])
        bank_paid = base["net_paise"]  # bank paid the original expectation
        # the settlement's inflated fee lowers ITS net, so the bank credit is
        # HIGHER than the settlement-implied expectation by exactly the delta
        assert variance_paise(bank_paid, inflated["net_paise"]) == 2_000

    def test_inflated_tax_creates_exact_variance(self):
        base = aggregate_settlement_group(
            [settlement_txn(gross=100_000, fee=2_000, tax=360)])
        inflated = aggregate_settlement_group(
            [settlement_txn(gross=100_000, fee=2_000, tax=1_360)])
        assert variance_paise(base["net_paise"], inflated["net_paise"]) == 1_000


class TestToleranceAndVariance:
    def test_variance_sign_convention(self):
        assert variance_paise(97_000, 100_000) == -3_000  # bank short
        assert variance_paise(101_000, 100_000) == 1_000  # bank excess

    @pytest.mark.parametrize(
        "variance,tolerance,expected",
        [(0, 100, True), (100, 100, True), (101, 100, False), (-100, 100, True)],
    )
    def test_tolerance_boundary_is_inclusive(self, variance, tolerance, expected):
        assert within_tolerance(variance, tolerance) is expected


class TestDisplayFormatting:
    def test_exact_decimal_strings(self):
        assert format_paise_as_rupees(30_000) == "300.00"
        assert format_paise_as_rupees(1) == "0.01"
        assert format_paise_as_rupees(0) == "0.00"
        assert format_paise_as_rupees(-105) == "-1.05"
        assert format_paise_as_rupees(123_456_789_012) == "1234567890.12"
