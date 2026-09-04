"""Ingestion: file-level rejection vs row-level quarantine (ARCHITECTURE.md 7)."""

from __future__ import annotations

import pytest

from backend.config import ReconciliationConfig
from backend.exceptions import IngestionError
from backend.ingestion import read_csv_source
from backend.models import Source

LEDGER_CSV = (
    "internal_id,order_id,payment_id,created_at,amount_paise,currency,payment_status\n"
    "int_001,order_001,pay_001,2026-08-10 09:00:00,100000,INR,captured\n"
    "int_002,order_002,pay_002,2026-08-11 09:00:00,250000,INR,captured\n"
)

BANK_CSV = (
    "bank_txn_id,value_date,description,utr,credit_paise,debit_paise\n"
    "bank_001,2026-08-12 10:00:00,NEFT CR,UTR1,97640,0\n"
)


class TestValidFiles:
    def test_rows_parsed_verbatim(self):
        table = read_csv_source(LEDGER_CSV, Source.INTERNAL_LEDGER)
        assert table.skipped_rows == 0
        assert len(table.rows) == 2
        assert table.rows[0].amount_paise == "100000"  # raw string preserved

    def test_leading_bom_stripped(self):
        table = read_csv_source("\ufeff" + LEDGER_CSV, Source.INTERNAL_LEDGER)
        assert len(table.rows) == 2


class TestFileLevelRejection:
    def test_missing_required_column(self):
        csv = "internal_id,payment_id\nint_001,pay_001\n"
        with pytest.raises(IngestionError, match="missing required columns"):
            read_csv_source(csv, Source.INTERNAL_LEDGER)

    def test_empty_file(self):
        with pytest.raises(IngestionError):
            read_csv_source("", Source.INTERNAL_LEDGER)

    def test_oversized_file(self):
        cfg = ReconciliationConfig(max_file_bytes=10)
        with pytest.raises(IngestionError, match="exceeds"):
            read_csv_source(LEDGER_CSV, Source.INTERNAL_LEDGER, cfg)


SETTLEMENT_CSV = (
    "entity_id,type,payment_id,order_id,settlement_id,settlement_utr,amount_paise,"
    "fee_paise,tax_paise,debit_paise,credit_paise,settled_at\n"
    "ent_001,payment,pay_001,order_001,setl_001,UTR1,100000,2000,360,0,0,2026-08-11 09:00:00\n"
    "ent_001_r,refund,pay_001,order_001,setl_001,,0,0,0,30000,0,2026-08-11 09:00:00\n"
)


class TestNullableReferences:
    def test_blank_settlement_utr_is_valid_data(self):
        # refund/adjustment rows carry no UTR; blank means absent, not invalid
        table = read_csv_source(SETTLEMENT_CSV, Source.SETTLEMENT_REPORT)
        assert table.skipped_rows == 0
        assert len(table.rows) == 2
        assert table.rows[1].settlement_utr == ""


class TestSettlementTypeValidation:
    def test_unknown_transaction_type_is_quarantined_not_crashed(self):
        csv = SETTLEMENT_CSV.replace("refund", "capture")
        table = read_csv_source(csv, Source.SETTLEMENT_REPORT)
        assert table.skipped_rows == 1
        assert "unknown transaction type" in table.errors[0].message
        assert table.errors[0].column == "type"

    def test_normalization_never_sees_invalid_types(self):
        from backend.normalization import normalize_settlement_report
        table = read_csv_source(SETTLEMENT_CSV, Source.SETTLEMENT_REPORT)
        rows = normalize_settlement_report(table)  # must not raise
        assert len(rows) == 2


class TestRowLevelQuarantine:
    def test_blank_required_field_skips_only_that_row(self):
        csv = LEDGER_CSV + "int_003,,pay_003,2026-08-12 09:00:00,1000,INR,captured\n"
        table = read_csv_source(csv, Source.INTERNAL_LEDGER)
        assert len(table.rows) == 2
        assert table.skipped_rows == 1
        assert table.errors[0].row_number == 4
        assert table.errors[0].column == "order_id"

    def test_non_integer_paise_rejected(self):
        csv = LEDGER_CSV.replace("250000", "2500.50")
        table = read_csv_source(csv, Source.INTERNAL_LEDGER)
        assert table.skipped_rows == 1
        assert "paise" in table.errors[0].message

    def test_formula_injection_rejected(self):
        csv = BANK_CSV.replace("NEFT CR", "=HYPERLINK(1)")
        table = read_csv_source(csv, Source.BANK_STATEMENT)
        assert table.skipped_rows == 1
        assert "formula-injection" in table.errors[0].message

    def test_leading_minus_also_flagged_as_injection_on_text_columns(self):
        # OWASP CSV-injection prefixes are = + - @ ; "-" must be caught on
        # text columns even though it cannot start a valid paise amount.
        csv = BANK_CSV.replace("NEFT CR", "-2+5*cmd|' /C")
        table = read_csv_source(csv, Source.BANK_STATEMENT)
        assert table.skipped_rows == 1
        assert "formula-injection" in table.errors[0].message

    def test_negative_paise_still_reports_as_amount_error_not_injection(self):
        csv = BANK_CSV.replace(",97640,0", ",-97640,0")
        table = read_csv_source(csv, Source.BANK_STATEMENT)
        assert table.skipped_rows == 1
        assert "non-negative integer paise" in table.errors[0].message

    def test_unparseable_date_rejected(self):
        csv = BANK_CSV.replace("2026-08-12 10:00:00", "12/08/2026")
        table = read_csv_source(csv, Source.BANK_STATEMENT)
        assert table.skipped_rows == 1
        assert table.errors[0].column == "value_date"

    def test_error_dict_shape(self):
        csv = LEDGER_CSV.replace("100000", "abc")
        table = read_csv_source(csv, Source.INTERNAL_LEDGER)
        d = table.errors[0].to_dict()
        assert {"source", "row_number", "column", "message", "file",
                "field", "code"} <= set(d)
        assert d["source"] == "internal_ledger"
        assert d["code"] == "invalid_amount"
