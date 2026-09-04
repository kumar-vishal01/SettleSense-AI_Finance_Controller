"""Phase 3 validation rules: columns, amounts, currency, types, dates,
duplicates, blank-vs-zero, injection, and the BatchInputSummary contract."""

from __future__ import annotations

import pytest

from backend.exceptions import IngestionError
from backend.ingestion import read_csv_source, summarize_input
from backend.models import Source
from backend.schemas import (
    BankStatementRow,
    InternalLedgerRow,
    SettlementRow,
)
from backend.validation import validate_row

LEDGER_CSV = (
    "internal_id,order_id,payment_id,created_at,amount_paise,currency,payment_status\n"
    "int_001,order_001,pay_001,2026-08-10 09:00:00,100000,INR,captured\n"
)
SETTLEMENT_CSV = (
    "entity_id,type,payment_id,order_id,settlement_id,settlement_utr,amount_paise,"
    "fee_paise,tax_paise,debit_paise,credit_paise,settled_at\n"
    "ent_001,payment,pay_001,order_001,setl_001,UTR001,100000,2000,360,0,0,2026-08-11 09:00:00\n"
)
BANK_CSV = (
    "bank_txn_id,value_date,description,utr,credit_paise,debit_paise\n"
    "bank_001,2026-08-12 10:00:00,NEFT CR,UTR001,97640,0\n"
)


def _read(csv: str, source: Source):
    return read_csv_source(csv, source)


def _last_error(table):
    assert table.errors, "expected at least one row error"
    return table.errors[-1]


class TestValidRows:
    def test_all_three_sources_produce_typed_rows(self):
        ledger = _read(LEDGER_CSV, Source.INTERNAL_LEDGER)
        settlement = _read(SETTLEMENT_CSV, Source.SETTLEMENT_REPORT)
        bank = _read(BANK_CSV, Source.BANK_STATEMENT)
        assert isinstance(ledger.rows[0], InternalLedgerRow)
        assert isinstance(settlement.rows[0], SettlementRow)
        assert isinstance(bank.rows[0], BankStatementRow)
        assert not any(t.errors for t in (ledger, settlement, bank))

    def test_raw_strings_survive_untouched(self):
        table = _read(LEDGER_CSV.replace("int_001", " int_001 "), Source.INTERNAL_LEDGER)
        # raw keeps leading/trailing whitespace exactly as uploaded
        assert table.rows[0].raw()["internal_id"] == " int_001 "


class TestMissingColumns:
    def test_missing_required_column_is_file_level_error(self):
        csv = "internal_id,payment_id\nint_001,pay_001\n"
        with pytest.raises(IngestionError, match="missing required columns"):
            _read(csv, Source.INTERNAL_LEDGER)

    def test_blank_required_field_is_row_error(self):
        table = _read(LEDGER_CSV.replace("order_001", ""), Source.INTERNAL_LEDGER)
        assert table.skipped_rows == 1
        assert _last_error(table).code == "missing_required"
        assert _last_error(table).column == "order_id"


class TestInvalidDates:
    def test_unparseable_date_quarantined(self):
        table = _read(BANK_CSV.replace("2026-08-12 10:00:00", "12/08/2026"),
                      Source.BANK_STATEMENT)
        assert table.skipped_rows == 1
        assert _last_error(table).code == "invalid_date"
        assert _last_error(table).column == "value_date"


class TestInvalidAmounts:
    @pytest.mark.parametrize("bad", ["12.5", "-500", "abc", "12e3"])
    def test_bad_paise_quarantined(self, bad):
        table = _read(BANK_CSV.replace(",97640,0", f",{bad},0"), Source.BANK_STATEMENT)
        assert table.skipped_rows == 1
        assert _last_error(table).code == "invalid_amount"

    def test_blank_is_not_zero(self):
        # blank amount = missing data (error); zero is a legitimate value
        blank = _read(LEDGER_CSV.replace(",100000,", ",,"), Source.INTERNAL_LEDGER)
        assert blank.skipped_rows == 1
        assert _last_error(blank).code in {"missing_required", "invalid_amount"}

        zero = _read(LEDGER_CSV.replace(",100000,", ",0,"), Source.INTERNAL_LEDGER)
        assert zero.skipped_rows == 0
        assert zero.rows[0].amount_paise == "0"


class TestUnsupportedCurrency:
    def test_non_inr_ledger_row_rejected(self):
        table = _read(LEDGER_CSV.replace(",INR,", ",USD,"), Source.INTERNAL_LEDGER)
        assert table.skipped_rows == 1
        assert _last_error(table).code == "unsupported_currency"
        assert _last_error(table).column == "currency"

    def test_currency_check_is_case_insensitive(self):
        table = _read(LEDGER_CSV.replace(",INR,", ",inr,"), Source.INTERNAL_LEDGER)
        assert table.skipped_rows == 0


class TestUnknownTransactionType:
    def test_unknown_type_quarantined(self):
        table = _read(SETTLEMENT_CSV.replace(",payment,", ",capture,"),
                      Source.SETTLEMENT_REPORT)
        assert table.skipped_rows == 1
        assert _last_error(table).code == "unknown_transaction_type"

    def test_all_allowed_types_pass(self):
        csv = SETTLEMENT_CSV
        for i, row_type in enumerate(("refund", "adjustment", "transfer"), start=2):
            line = csv.splitlines()[1].replace(",payment,", f",{row_type},")
            line = line.replace("ent_001", f"ent_{i:03d}").replace("pay_001", f"pay_{i:03d}")
            csv += line + "\n"
        table = _read(csv, Source.SETTLEMENT_REPORT)
        assert table.skipped_rows == 0
        assert len(table.rows) == 4


class TestUtrNormalization:
    def test_blank_utr_is_valid_and_maps_to_none(self):
        csv = SETTLEMENT_CSV.replace("UTR001", "")
        table = _read(csv, Source.SETTLEMENT_REPORT)
        assert table.skipped_rows == 0          # blank UTR is legal missing data
        from backend.normalization import normalize_settlement_report
        canonical = normalize_settlement_report(table)
        assert canonical[0].settlement_utr is None   # distinguishable from ""


class TestDuplicateRows:
    def test_exact_duplicate_counted_not_dropped(self):
        doubled = LEDGER_CSV + LEDGER_CSV.splitlines()[1] + "\n"
        table = _read(doubled, Source.INTERNAL_LEDGER)
        assert len(table.rows) == 2             # kept: financial evidence
        assert table.duplicate_rows == 1
        assert table.duplicate_row_numbers == [3]
        assert table.skipped_rows == 0

    def test_same_key_different_values_kept_and_reported(self):
        """A row reusing a primary key with different content is financial
        evidence the ENGINE must adjudicate as DUPLICATE — ingestion keeps
        it and reports the conflict, never quarantines it (senior review)."""
        conflicting = LEDGER_CSV + LEDGER_CSV.splitlines()[1].replace(
            "100000", "250000") + "\n"
        table = _read(conflicting, Source.INTERNAL_LEDGER)
        assert len(table.rows) == 2             # both rows kept
        assert table.skipped_rows == 0          # not quarantined
        assert table.conflicting_rows == 1      # but loudly reported
        assert table.conflicting_row_numbers == [3]

    def test_conflicting_bank_rows_still_reach_engine_as_duplicate(self):
        """End-to-end guarantee: key conflicts in the bank statement must
        surface as DUPLICATE status, not a silent clean reconcile."""
        from backend.config import ReconciliationConfig
        from backend.models import ReconciliationStatus
        from backend.normalization import (
            normalize_bank_statement,
            normalize_internal_ledger,
            normalize_settlement_report,
        )
        from backend.reconciliation import reconcile_batch
        from tests.factories import AS_OF

        settlement_csv = (
            "entity_id,type,payment_id,order_id,settlement_id,settlement_utr,amount_paise,"
            "fee_paise,tax_paise,debit_paise,credit_paise,settled_at\n"
            "ent_001,payment,pay_001,order_001,setl_001,UTR001,100000,2000,360,0,0,"
            "2026-08-11 09:00:00\n"
        )
        bank_csv = (
            "bank_txn_id,value_date,description,utr,credit_paise,debit_paise\n"
            "bank_001,2026-08-12 10:00:00,NEFT CR,UTR001,97640,0\n"
            "bank_001,2026-08-12 10:00:00,NEFT CR,UTR001,50000,0\n"
        )
        ledger = _read(LEDGER_CSV, Source.INTERNAL_LEDGER)
        settlement = _read(settlement_csv, Source.SETTLEMENT_REPORT)
        bank = _read(bank_csv, Source.BANK_STATEMENT)
        assert bank.conflicting_rows == 1 and len(bank.rows) == 2

        outcome = reconcile_batch(
            normalize_internal_ledger(ledger),
            normalize_settlement_report(settlement),
            normalize_bank_statement(bank),
            ReconciliationConfig(), AS_OF,
        )
        result = outcome.results[0]
        assert result.status is ReconciliationStatus.DUPLICATE
        assert result.requires_review is True

    def test_summary_counts_conflicts(self):
        conflicting = LEDGER_CSV + LEDGER_CSV.splitlines()[1].replace(
            "100000", "250000") + "\n"
        summary = summarize_input(_read(conflicting, Source.INTERNAL_LEDGER))
        assert summary.conflicting_rows == 1
        assert summary.skipped_rows == 0
        assert summary.valid is True  # rows kept; the engine adjudicates


class TestUnsafeContent:
    def test_null_bytes_rejected_as_file(self):
        with pytest.raises(IngestionError, match="binary"):
            _read(LEDGER_CSV.replace("int_001", "\x00int_001"), Source.INTERNAL_LEDGER)

    def test_formula_injection_still_blocked(self):
        table = _read(BANK_CSV.replace("NEFT CR", "=HYPERLINK(1)"), Source.BANK_STATEMENT)
        assert _last_error(table).code == "formula_injection"


class TestBatchInputSummary:
    def test_summary_aggregates_three_files(self):
        tables = [
            _read(LEDGER_CSV, Source.INTERNAL_LEDGER),
            _read(SETTLEMENT_CSV, Source.SETTLEMENT_REPORT),
            _read(BANK_CSV, Source.BANK_STATEMENT),
        ]
        summary = summarize_input(*tables)
        assert summary.valid is True
        assert summary.total_rows == 3
        assert summary.valid_rows == 3
        assert [f.source for f in summary.files] == [
            "internal_ledger", "settlement_report", "bank_statement"]
        assert summary.errors == []

    def test_summary_carries_row_errors_with_file_row_field(self):
        tables = [_read(LEDGER_CSV.replace("order_001", ""), Source.INTERNAL_LEDGER)]
        summary = summarize_input(*tables)
        assert summary.valid is False
        error = summary.errors[0]
        assert error.file == "internal_ledger"
        assert error.row_number == 2
        assert error.field == "order_id"
        assert "missing or blank" in error.message

    def test_row_error_dict_contract(self):
        table = _read(LEDGER_CSV.replace("INR", "USD"), Source.INTERNAL_LEDGER)
        d = _last_error(table).to_dict()
        assert d["file"] == "internal_ledger"
        assert d["row_number"] == 2
        assert d["field"] == "currency"
        assert d["code"] == "unsupported_currency"


class TestValidationIsPure:
    def test_validate_row_returns_none_for_valid_row(self):
        row = {
            "internal_id": "int_001", "order_id": "order_001", "payment_id": "pay_001",
            "created_at": "2026-08-10 09:00:00", "amount_paise": "1000",
            "currency": "INR", "payment_status": "captured",
        }
        assert validate_row(row, Source.INTERNAL_LEDGER, 2) is None
