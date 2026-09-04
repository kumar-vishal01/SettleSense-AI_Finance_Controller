"""Phase 2 dataset tests: schema, determinism, scenario coverage, and the
engine-vs-ground-truth agreement gate.

Ground truth is used HERE (evaluation context) only — never by backend/
runtime code, which these tests also prove by construction: the engine runs
on the three source CSVs alone.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from generate_data import (
    BANK_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    LEDGER_COLUMNS,
    SETTLEMENT_COLUMNS,
    DatasetSpec,
    generate_dataset,
    write_dataset,
)

SEED = 42
BATCH_DATE = datetime(2026, 8, 20, tzinfo=timezone.utc)

EXPECTED_SCENARIOS = {
    "clean": 57,
    "same_amount_clean": 3,
    "delayed_bank_credit": 10,
    "missing_utr": 8,
    "amount_mismatch": 6,
    "missing_settlement": 5,
    "missing_bank_credit": 4,
    "duplicate_ledger": 1,
    "duplicate_bank": 1,
    "duplicate_settlement": 1,
    "refund": 2,
    "adjustment": 1,
    "ambiguous_review": 1,
}
EXPECTED_TOTAL = sum(EXPECTED_SCENARIOS.values())  # 100


def _files(path: Path) -> dict[str, list[dict[str, str]]]:
    out = {}
    for name in ("internal_ledger.csv", "settlements.csv",
                 "bank_statement.csv", "ground_truth.csv"):
        with open(path / name, newline="", encoding="utf-8") as fh:
            out[name] = list(csv.DictReader(fh))
    return out


@pytest.fixture(scope="module")
def dataset(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("synthetic-v2")
    ds = generate_dataset(DatasetSpec(), SEED, BATCH_DATE)
    write_dataset(ds, DatasetSpec(), SEED, out)
    return out


@pytest.fixture(scope="module")
def rows(dataset) -> dict[str, list[dict[str, str]]]:
    return _files(dataset)


class TestShapeAndSchema:
    def test_expected_number_of_logical_records(self, rows):
        gt = rows["ground_truth.csv"]
        ledger = rows["internal_ledger.csv"]
        assert len(gt) == EXPECTED_TOTAL == 100
        unique_payments = {r["payment_id"] for r in ledger}
        assert len(unique_payments) == EXPECTED_TOTAL

    def test_required_columns_per_file(self, dataset):
        with open(dataset / "internal_ledger.csv", newline="") as fh:
            assert next(csv.reader(fh)) == LEDGER_COLUMNS
        for name, columns in (
            ("settlements.csv", SETTLEMENT_COLUMNS),
            ("bank_statement.csv", BANK_COLUMNS),
            ("ground_truth.csv", GROUND_TRUTH_COLUMNS),
        ):
            with open(dataset / name, newline="") as fh:
                assert next(csv.reader(fh)) == columns

    def test_every_paise_value_is_a_nonnegative_integer(self, rows):
        # monetary amounts in the three source files are unsigned integers
        paise_columns = {
            "internal_ledger.csv": ["amount_paise"],
            "settlements.csv": ["amount_paise", "fee_paise", "tax_paise",
                                "debit_paise", "credit_paise"],
            "bank_statement.csv": ["credit_paise", "debit_paise"],
        }
        for name, columns in paise_columns.items():
            for i, row in enumerate(rows[name]):
                for column in columns:
                    assert row[column].isdigit(), f"{name} row {i} {column}={row[column]!r}"

    def test_ground_truth_variance_is_a_signed_integer(self, rows):
        # variance is signed: negative = bank credit lower than expected net
        for i, row in enumerate(rows["ground_truth.csv"]):
            value = row["expected_variance_paise"]
            assert value.lstrip("-").isdigit() and value not in {"-", ""}, \
                f"ground_truth row {i}: {value!r}"

    def test_realistic_id_formats(self, rows):
        for row in rows["ground_truth.csv"]:
            assert row["payment_id"].startswith("pay_")
        for row in rows["settlements.csv"]:
            assert row["settlement_id"].startswith("setl_")
            assert row["settlement_utr"] == "" or row["settlement_utr"].startswith("UTR")
        for row in rows["bank_statement.csv"]:
            assert row["bank_txn_id"].startswith("bank_")

    def test_currency_is_inr(self, rows):
        assert all(r["currency"] == "INR" for r in rows["internal_ledger.csv"])


class TestGroundTruthCoverage:
    def test_every_payment_has_exactly_one_label(self, rows):
        gt = rows["ground_truth.csv"]
        ledger_ids = [r["payment_id"] for r in rows["internal_ledger.csv"]]
        gt_ids = [r["payment_id"] for r in gt]
        assert len(gt_ids) == len(set(gt_ids)), "duplicate ground-truth rows"
        assert set(gt_ids) == set(ledger_ids), "ledger payment missing a label"

    def test_review_flag_consistent_with_status(self, rows):
        for row in rows["ground_truth.csv"]:
            expected = "true" if row["expected_status"] != "FULLY_RECONCILED" else "false"
            assert row["expected_review_flag"] == expected

    def test_all_required_scenarios_present(self, rows):
        counts: dict[str, int] = {}
        for row in rows["ground_truth.csv"]:
            counts[row["scenario"]] = counts.get(row["scenario"], 0) + 1
        assert counts == EXPECTED_SCENARIOS


class TestPlantedErrorRepresentations:
    def test_amount_mismatch_bank_credit_differs_by_expected_variance(self, rows):
        gt_by_id = {r["payment_id"]: r for r in rows["ground_truth.csv"]}
        settlement_by_payment: dict[str, list[dict[str, str]]] = {}
        for row in rows["settlements.csv"]:
            settlement_by_payment.setdefault(row["payment_id"], []).append(row)
        bank_by_id = {r["bank_txn_id"]: r for r in rows["bank_statement.csv"]}

        mismatches = [r for r in rows["ground_truth.csv"]
                      if r["scenario"] == "amount_mismatch"]
        assert len(mismatches) == 6
        for gt in mismatches:
            waterfall = sum(
                int(r["amount_paise"]) - int(r["fee_paise"]) - int(r["tax_paise"])
                - int(r["debit_paise"]) + int(r["credit_paise"])
                for r in settlement_by_payment[gt["payment_id"]]
            )
            credit = int(bank_by_id[gt["expected_bank_txn_id"]]["credit_paise"])
            assert credit - waterfall == int(gt["expected_variance_paise"])

    def test_settlement_exists_but_no_bank_credit(self, rows):
        gt_ids = {r["payment_id"] for r in rows["ground_truth.csv"]
                  if r["scenario"] == "missing_bank_credit"}
        assert len(gt_ids) == 4
        bank_pid_refs = {r["utr"] for r in rows["bank_statement.csv"]}
        settlement_utrs = {r["payment_id"]: r["settlement_utr"]
                           for r in rows["settlements.csv"]}
        for pid in gt_ids:
            assert settlement_utrs[pid], f"{pid} should still have a settlement"
            assert settlement_utrs[pid] not in bank_pid_refs, \
                f"{pid} should have no bank credit"

    def test_ambiguous_case_is_two_same_amount_unreferenced_credits(self, rows):
        gt = next(r for r in rows["ground_truth.csv"]
                  if r["scenario"] == "ambiguous_review")
        payment_settlements = [r for r in rows["settlements.csv"]
                               if r["payment_id"] == gt["payment_id"]]
        assert all(r["settlement_utr"] == "" for r in payment_settlements)
        expected_net = sum(
            int(r["amount_paise"]) - int(r["fee_paise"]) - int(r["tax_paise"])
            - int(r["debit_paise"]) + int(r["credit_paise"])
            for r in payment_settlements
        )
        # exactly two bank credits of that amount with no UTR and no reference
        # (the missing_utr rows also have empty UTRs, so match on the amount)
        pair = [r for r in rows["bank_statement.csv"]
                if r["utr"] == "" and r["credit_paise"] == str(expected_net)]
        assert len(pair) == 2
        assert pair[0]["bank_txn_id"] != pair[1]["bank_txn_id"]
        assert all("SETTL" not in r["description"] and "UTR" not in r["description"]
                   for r in pair)
        assert gt["expected_review_flag"] == "true"
        assert gt["expected_bank_txn_id"] == ""  # unknowable by design

    def test_duplicate_variants_are_planted(self, rows):
        # duplicated ledger row (same payment_id, two internal rows)
        ledger_ids = [r["payment_id"] for r in rows["internal_ledger.csv"]]
        assert len(ledger_ids) - len(set(ledger_ids)) == 1
        # duplicated bank row (same bank_txn_id twice)
        bank_ids = [r["bank_txn_id"] for r in rows["bank_statement.csv"]]
        assert len(bank_ids) - len(set(bank_ids)) == 1
        # duplicated settlement entity row (same entity_id twice)
        entity_ids = [r["entity_id"] for r in rows["settlements.csv"]]
        assert len(entity_ids) - len(set(entity_ids)) == 1

    def test_refund_and_adjustment_rows_exist(self, rows):
        types = [r["type"] for r in rows["settlements.csv"]]
        assert types.count("refund") == 2
        assert types.count("adjustment") == 1
        refunds = [r for r in rows["settlements.csv"] if r["type"] == "refund"]
        assert all(int(r["debit_paise"]) > 0 for r in refunds)
        adjustment = next(r for r in rows["settlements.csv"] if r["type"] == "adjustment")
        assert int(adjustment["credit_paise"]) > 0

    def test_missing_utr_still_referenceable_in_bank_description(self, rows):
        gt_ids = {r["payment_id"] for r in rows["ground_truth.csv"]
                  if r["scenario"] == "missing_utr"}
        assert len(gt_ids) == 8
        for row in rows["settlements.csv"]:
            if row["payment_id"] in gt_ids:
                assert row["settlement_utr"] == ""
        for row in rows["bank_statement.csv"]:
            if row["utr"] == "" and row["credit_paise"] != "0" and \
                    "SETTL" in row["description"]:
                assert row["bank_txn_id"] in {
                    r["expected_bank_txn_id"] for r in rows["ground_truth.csv"]
                    if r["scenario"] == "missing_utr"
                }

    def test_same_amount_group_shares_one_amount(self, rows):
        group = [r for r in rows["ground_truth.csv"]
                 if r["scenario"] == "same_amount_clean"]
        assert len(group) == 3
        amounts = {
            int(r["amount_paise"]) for r in rows["internal_ledger.csv"]
            if r["payment_id"] in {g["payment_id"] for g in group}
        }
        assert len(amounts) == 1, "the same-amount group must share one amount"


class TestDeterminism:
    def test_same_seed_same_seed_produces_identical_files(self, tmp_path):
        dirs = []
        for i in range(2):
            out = tmp_path / f"run{i}"
            ds = generate_dataset(DatasetSpec(), SEED, BATCH_DATE)
            write_dataset(ds, DatasetSpec(), SEED, out)
            dirs.append(out)
        for name in ("internal_ledger.csv", "settlements.csv",
                     "bank_statement.csv", "ground_truth.csv", "manifest.json"):
            first = hashlib.sha256((dirs[0] / name).read_bytes()).hexdigest()
            second = hashlib.sha256((dirs[1] / name).read_bytes()).hexdigest()
            assert first == second, f"{name} differs between runs"

    def test_different_seed_changes_data(self, tmp_path):
        hashes = []
        for seed in (42, 43):
            out = tmp_path / f"seed{seed}"
            ds = generate_dataset(DatasetSpec(), seed, BATCH_DATE)
            write_dataset(ds, DatasetSpec(), seed, out)
            hashes.append(hashlib.sha256((out / "settlements.csv").read_bytes()).hexdigest())
        assert hashes[0] != hashes[1]


class TestEngineAgreement:
    """The gate: run the production engine on the three source files only
    and require every logical payment to land on its labeled outcome."""

    def test_engine_statuses_match_ground_truth(self, dataset):
        from backend.config import ReconciliationConfig
        from backend.ingestion import read_csv_source
        from backend.metrics import evaluate_against_ground_truth
        from backend.models import Source
        from backend.normalization import (
            normalize_bank_statement,
            normalize_internal_ledger,
            normalize_settlement_report,
        )
        from backend.reconciliation import reconcile_batch

        read = lambda name, source: read_csv_source(
            (dataset / name).read_text(), source
        )
        outcome = reconcile_batch(
            normalize_internal_ledger(read("internal_ledger.csv", Source.INTERNAL_LEDGER)),
            normalize_settlement_report(read("settlements.csv", Source.SETTLEMENT_REPORT)),
            normalize_bank_statement(read("bank_statement.csv", Source.BANK_STATEMENT)),
            ReconciliationConfig(),
        )
        with open(dataset / "ground_truth.csv", newline="", encoding="utf-8") as fh:
            gt = list(csv.DictReader(fh))

        report = evaluate_against_ground_truth(outcome.results, gt, "synthetic-v2")
        assert report.status_mismatches == []
        assert report.false_auto_matches == 0
        assert report.precision == 1.0
        assert report.recall == 1.0
        assert report.exception_capture_rate == 1.0
        # variance reported by the engine equals the labeled variance
        by_payment = {r.payment_id: r for r in outcome.results}
        for row in gt:
            if row["scenario"] == "amount_mismatch":
                assert by_payment[row["payment_id"]].variance_paise == int(
                    row["expected_variance_paise"]
                )
            if row["scenario"] == "missing_utr":
                # resolved through reference evidence, still reconciled
                assert by_payment[row["payment_id"]].requires_review is False
