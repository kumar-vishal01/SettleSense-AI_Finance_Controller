"""Normalization rules: identifiers, UTRs, dates, types, raw preservation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.ingestion import RawTable
from backend.models import Source, TransactionType
from backend.normalization import (
    normalize_bank_statement,
    normalize_id,
    normalize_internal_ledger,
    normalize_transaction_type,
    normalize_utr,
    parse_datetime_utc,
    rupees_to_paise,
)


def _table(source: Source, csv_text: str) -> "RawTable":
    """Build a RawTable through the real ingestion path (typed rows)."""
    from backend.ingestion import read_csv_source
    return read_csv_source(csv_text, source)


def _ledger_csv(**overrides) -> str:
    row = {
        "internal_id": "int_001", "order_id": "order_001",
        "payment_id": " pay_001 ", "created_at": "2026-08-10 09:30:00",
        "amount_paise": "97640", "currency": "inr", "payment_status": "captured",
    }
    row.update(overrides)
    header = ",".join(row)
    return header + "\n" + ",".join(row.values()) + "\n"


def _bank_csv(**overrides) -> str:
    row = {
        "bank_txn_id": "bank_001", "value_date": "2026-08-12 10:00:00",
        "description": "NEFT CR-UTR: utr100001 ", "utr": "utr100001",
        "credit_paise": "97640", "debit_paise": "0",
    }
    row.update(overrides)
    header = ",".join(row)
    return header + "\n" + ",".join(row.values()) + "\n"


class TestScalars:
    def test_normalize_id_trims_and_blanks_to_none(self):
        assert normalize_id("  pay_1 ") == "pay_1"
        assert normalize_id("   ") is None
        assert normalize_id(None) is None

    def test_normalize_utr_trims_uppercases_removes_spaces(self):
        assert normalize_utr("  axb123456789  ") == "AXB123456789"
        assert normalize_utr("UTR 123 456") == "UTR123456"
        assert normalize_utr("") is None

    def test_parse_datetime_formats(self):
        expected = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
        assert parse_datetime_utc("2026-08-10 12:00:00") == expected
        assert parse_datetime_utc("2026-08-10T12:00:00") == expected
        assert parse_datetime_utc("2026-08-10") == datetime(
            2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc
        )

    def test_parse_datetime_invalid_returns_none(self):
        assert parse_datetime_utc("10/08/2026") is None
        assert parse_datetime_utc("") is None

    def test_transaction_type_mapping(self):
        assert normalize_transaction_type(" Payment ") is TransactionType.PAYMENT
        assert normalize_transaction_type("REFUND") is TransactionType.REFUND

    def test_unknown_transaction_type_rejected(self):
        with pytest.raises(ValueError):
            normalize_transaction_type("capture")


class TestInternalLedger:
    def test_row_mapping_and_raw_preserved(self):
        raw = {
            "internal_id": "int_001", "order_id": "order_001",
            "payment_id": " pay_001 ", "created_at": "2026-08-10 09:30:00",
            "amount_paise": "97640", "currency": "inr", "payment_status": "captured",
        }
        rows = normalize_internal_ledger(_table(Source.INTERNAL_LEDGER, _ledger_csv()))
        assert len(rows) == 1
        txn = rows[0]
        assert txn.payment_id == "pay_001"           # trimmed
        assert txn.currency == "INR"                 # uppercased
        assert txn.gross_amount_paise == 97_640      # int paise
        assert txn.transaction_at.tzinfo is not None
        # verbatim audit copy: whitespace and casing exactly as uploaded
        assert txn.raw_payload == raw

    def test_wrong_source_rejected(self):
        with pytest.raises(ValueError):
            normalize_internal_ledger(_table(Source.BANK_STATEMENT, _bank_csv()))


class TestNoFabricatedDates:
    """H2: normalizers must never substitute the wall clock for bad dates —
    same input has to mean same output (idempotent batches).

    Ingestion already quarantines unparseable dates, so these tests build
    tables programmatically (typed rows) to reach the normalizer guarantee
    for non-CSV adapter callers too.
    """

    def _ledger_table_with_date(self, created_at: str):
        from backend.ingestion import RawTable
        from backend.schemas import InternalLedgerRow
        row = InternalLedgerRow(
            internal_id="int_001", order_id="order_001", payment_id="pay_001",
            created_at=created_at, amount_paise="1000", currency="INR",
            payment_status="captured")
        return RawTable(source=Source.INTERNAL_LEDGER, rows=[row])

    def test_internal_ledger_bad_date_raises(self):
        with pytest.raises(ValueError, match="created_at"):
            normalize_internal_ledger(self._ledger_table_with_date("not-a-date"))

    def test_valid_rows_are_deterministic_across_calls(self):
        first = normalize_internal_ledger(self._ledger_table_with_date("2026-08-10 09:30:00"))
        second = normalize_internal_ledger(self._ledger_table_with_date("2026-08-10 09:30:00"))
        assert first[0].transaction_at == second[0].transaction_at


class TestBankStatement:
    def test_row_mapping(self):
        table = _table(Source.BANK_STATEMENT, _bank_csv())
        rows = normalize_bank_statement(table)
        entry = rows[0]
        assert entry.bank_txn_id == "bank_001"
        assert entry.utr == "UTR100001"              # normalized UTR
        assert entry.description == "NEFT CR-UTR: utr100001"  # trimmed for display
        assert entry.net_amount_paise() == 97_640
        assert entry.raw_payload["utr"] == "utr100001"  # raw preserved verbatim
