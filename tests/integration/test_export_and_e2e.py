"""Phase 10: export correctness, malformed-CSV handling, and the complete
upload-to-dashboard end-to-end flow."""

from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from backend.main import app

LEDGER = ("internal_id,order_id,payment_id,created_at,amount_paise,currency,payment_status\n"
          "int_001,order_001,pay_001,2026-08-10 09:00:00,100000,INR,captured\n")
SETTLEMENTS = ("entity_id,type,payment_id,order_id,settlement_id,settlement_utr,"
               "amount_paise,fee_paise,tax_paise,debit_paise,credit_paise,settled_at\n"
               "ent_001,payment,pay_001,order_001,setl_001,UTR001,100000,2000,360,0,0,2026-08-11 09:00:00\n")
MISMATCH_BANK = ("bank_txn_id,value_date,description,utr,credit_paise,debit_paise\n"
                 "bank_001,2026-08-12 10:00:00,NEFT CR UTR001,UTR001,94640,0\n")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SETTLESENSE_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def _upload(client, ledger=LEDGER, settlements=SETTLEMENTS, bank=MISMATCH_BANK):
    return client.post("/api/v1/batches", files={
        "internal_ledger": ("a.csv", ledger.encode()),
        "settlements": ("b.csv", settlements.encode()),
        "bank_statement": ("c.csv", bank.encode())})


class TestMalformedCsv:
    def test_garbage_bytes_rejected_as_structured_422(self, client):
        response = client.post("/api/v1/batches", files={
            "internal_ledger": ("a.csv", b"\x89PNG\r\n\x1a\n garbage not csv"),
            "settlements": ("b.csv", SETTLEMENTS.encode()),
            "bank_statement": ("c.csv", MISMATCH_BANK.encode())})
        assert response.status_code == 422
        assert response.json()["error"]["code"] in {"ingestion_error", "invalid_request"}

    def test_semicolon_delimited_rejected_not_misparsed(self, client):
        wrong = LEDGER.replace(",", ";")
        response = _upload(client, ledger=wrong)
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "ingestion_error"

    def test_nothing_persisted_after_malformed_reject(self, client, tmp_path):
        from backend.database import Database
        _upload(client, ledger="this is not; a csv at all\x00")
        conn = Database(tmp_path / "test.db").connect(init=False)
        try:
            n = conn.execute("SELECT COUNT(*) n FROM batches").fetchone()["n"]
        finally:
            conn.close()
        assert n == 0


class TestExport:
    def test_csv_export_matches_results_row_for_row(self, client):
        batch_id = _upload(client).json()["batch_id"]
        client.post(f"/api/v1/batches/{batch_id}/reconcile")
        response = client.get(f"/api/v1/batches/{batch_id}/export",
                              params={"format": "csv", "scope": "results"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers.get("content-disposition", "")
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert len(rows) == 1
        row = rows[0]
        assert row["payment_id"] == "pay_001"
        assert row["status"] == "AMOUNT_MISMATCH"
        assert row["variance_paise"] == "-3000"   # bank 94640 vs expected net 97640
        # evidence flattened, money stays integer paise
        assert "pay_001" in row["evidence"]
        assert row["expected_amount_paise"] == "97640"

    def test_exceptions_scope_and_json_format(self, client):
        batch_id = _upload(client).json()["batch_id"]
        client.post(f"/api/v1/batches/{batch_id}/reconcile")
        j = client.get(f"/api/v1/batches/{batch_id}/export",
                       params={"format": "json", "scope": "exceptions"})
        assert j.status_code == 200
        payload = j.json()
        assert payload["batch_id"] == batch_id
        assert len(payload["items"]) == 1
        assert payload["items"][0]["requires_review"] is True

    def test_export_before_reconcile_is_headers_only(self, client):
        batch_id = _upload(client).json()["batch_id"]
        r = client.get(f"/api/v1/batches/{batch_id}/export",
                       params={"format": "csv", "scope": "results"})
        assert r.status_code == 200
        rows = list(csv.DictReader(io.StringIO(r.text)))
        assert rows == []

    def test_invalid_params_422_and_unknown_batch_404(self, client):
        batch_id = _upload(client).json()["batch_id"]
        assert client.get(f"/api/v1/batches/{batch_id}/export",
                          params={"format": "xls"}).status_code == 422
        assert client.get("/api/v1/batches/batch_nope/export").status_code == 404

    def test_idempotent_export_bytes(self, client):
        batch_id = _upload(client).json()["batch_id"]
        client.post(f"/api/v1/batches/{batch_id}/reconcile")
        a = client.get(f"/api/v1/batches/{batch_id}/export").text
        b = client.get(f"/api/v1/batches/{batch_id}/export").text
        assert a == b


class TestFullDemoEndToEnd:
    def test_upload_to_dashboard_totals(self, client):
        """The exact call sequence the dashboard makes, totals asserted."""
        created = _upload(client).json()
        assert created["status"] == "validated"
        batch_id = created["batch_id"]

        reconciled = client.post(f"/api/v1/batches/{batch_id}/reconcile").json()
        assert reconciled["result_count"] == 1

        metrics = client.get(f"/api/v1/batches/{batch_id}/metrics").json()
        results = client.get(f"/api/v1/batches/{batch_id}/results").json()
        exceptions = client.get(f"/api/v1/batches/{batch_id}/exceptions").json()
        cash = client.get(f"/api/v1/batches/{batch_id}/cash-position",
                          params={"opening_balance_paise": 500000}).json()
        ai = client.post("/api/v1/ai/query",
                         json={"batch_id": batch_id,
                               "question": "Which unresolved exception has the highest monetary impact?"}).json()
        export_rows = list(csv.DictReader(io.StringIO(
            client.get(f"/api/v1/batches/{batch_id}/export").text)))

        assert metrics["total_records"] == results["total"] == len(export_rows) == 1
        assert metrics["exceptions"] == exceptions["total"] == 1
        assert metrics["fully_reconciled"] == 0
        assert results["items"][0]["status"] == "AMOUNT_MISMATCH"
        assert ai["record_ids"] == ["pay_001"]
        assert ai["requires_review"] is True
        assert cash["actual_cash_paise"] == (
            500000 + cash["confirmed_credits_paise"] - cash["confirmed_debits_paise"])


class TestTraceRoute:
    def test_trace_returns_structured_chain(self, client):
        batch_id = _upload(client).json()["batch_id"]
        client.post(f"/api/v1/batches/{batch_id}/reconcile")
        r = client.get("/api/v1/transactions/pay_001/trace",
                       params={"batch_id": batch_id})
        assert r.status_code == 200
        body = r.json()
        assert body["payment_id"] == "pay_001"
        assert body["ledger"]["internal_id"] == "int_001"
        assert body["settlements"] and body["settlements"][0]["settlement_id"] == "setl_001"
        assert body["bank"]["bank_txn_id"] == "bank_001"
        assert body["decision"]["status"] == "AMOUNT_MISMATCH"
        assert body["decision"]["expected_breakdown_paise"]["fee_paise"] > 0

    def test_unknown_payment_404(self, client):
        batch_id = _upload(client).json()["batch_id"]
        r = client.get("/api/v1/transactions/pay_999/trace",
                       params={"batch_id": batch_id})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "payment_not_found"

    def test_missing_batch_param_422(self, client):
        assert client.get("/api/v1/transactions/pay_001/trace").status_code == 422
