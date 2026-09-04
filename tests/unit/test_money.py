"""Money-handling rules: integer paise only, no float coercion (AGENTS.md 3)."""

from __future__ import annotations

import pytest

from backend.normalization import paise_from_int_string, rupees_to_paise


class TestPaiseFromIntString:
    def test_plain_integer(self):
        assert paise_from_int_string("123456") == 123_456

    def test_surrounding_whitespace(self):
        assert paise_from_int_string("  42 ") == 42

    def test_rejects_decimal(self):
        with pytest.raises(ValueError):
            paise_from_int_string("12.5")

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            paise_from_int_string("-3")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            paise_from_int_string("")

    def test_rejects_comma_thousands(self):
        with pytest.raises(ValueError):
            paise_from_int_string("1,000")


class TestRupeesToPaise:
    def test_simple(self):
        assert rupees_to_paise("12.50") == 1250

    def test_whole_number(self):
        assert rupees_to_paise("100") == 10_000

    def test_zero(self):
        assert rupees_to_paise("0") == 0

    def test_half_up_rounding(self):
        # exact half: 0.005 rupees = 0.5 paise -> rounds UP under half-up
        assert rupees_to_paise("0.005") == 1

    def test_rejects_non_numeric(self):
        with pytest.raises(ValueError):
            rupees_to_paise("abc")

    def test_result_is_int_never_float(self):
        result = rupees_to_paise("19.99")
        assert isinstance(result, int)
