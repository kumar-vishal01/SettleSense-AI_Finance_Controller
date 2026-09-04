"""Phase 9 backend: POST /reconcile (persist results + per-decision audit,
idempotent) and GET /metrics."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.database import Database
from backend.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SETTLESENSE_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def _batch(client) -> str:
    response = client.post("/api/v1/batches?fixture=synthetic-v2")
    assert response.status_code == 201
    return response.json()["batch_id"]


class TestReconcile:
    def test_reconcile_persists_results_and_audit(self, client, tmp_path):
        batch_id = _batch(client)
        r = client.post(f"/api/v1/batches/{batch_id}/reconcile")
        assert r.status_code == 200
        body = r.json()
        assert body["result_count"] == 100
        assert body["summary"]["fully_reconciled"] == 71
        assert body["summary"]["exceptions"] == 29

        conn = Database(tmp_path / "test.db").connect(init=False)
        try:
            results = conn.execute(
                "SELECT COUNT(*) n FROM reconciliation_results WHERE batch_id=?",
                (batch_id,)).fetchone()["n"]
            decisions = conn.execute(
                "SELECT COUNT(*) n FROM audit_events WHERE batch_id=? AND action='result_recorded'",
                (batch_id,)).fetchone()["n"]
            summary_events = conn.execute(
                "SELECT COUNT(*) n FROM audit_events WHERE batch_id=? AND action='batch_reconciled'",
                (batch_id,)).fetchone()["n"]
            batch_status = conn.execute(
                "SELECT status, completed_at FROM batches WHERE id=?",
                (batch_id,)).fetchone()
        finally:
            conn.close()
        assert results == 100
        assert decisions == 100, "one audit event per persisted decision"
        assert summary_events == 1
        assert batch_status["status"] == "reconciled"
        assert batch_status["completed_at"] is not None

    def test_reconcile_is_idempotent(self, client, tmp_path):
        batch_id = _batch(client)
        first = client.post(f"/api/v1/batches/{batch_id}/reconcile").json()
        second = client.post(f"/api/v1/batches/{batch_id}/reconcile")
        assert second.status_code == 200
        body = second.json()
        assert body["idempotent"] is True
        assert body["result_count"] == first["result_count"]
        conn = Database(tmp_path / "test.db").connect(init=False)
        try:
            n = conn.execute(
                "SELECT COUNT(*) n FROM reconciliation_results WHERE batch_id=?",
                (batch_id,)).fetchone()["n"]
            events = conn.execute(
                "SELECT COUNT(*) n FROM audit_events WHERE batch_id=?",
                (batch_id,)).fetchone()["n"]
        finally:
            conn.close()
        assert n == 100, "no duplicated results on rerun"
        assert events == 102, "no duplicated audit events (100 + create + reconcile)"

    def test_results_now_flow_through_existing_endpoints(self, client):
        batch_id = _batch(client)
        client.post(f"/api/v1/batches/{batch_id}/reconcile")
        results = client.get(f"/api/v1/batches/{batch_id}/results",
                             params={"page_size": 100}).json()
        assert results["total"] == 100
        assert results["batch_status"] == "reconciled"
        assert results["note"] is None
        first = results["items"][0]
        for field in ("payment_id", "order_id", "settlement_id", "bank_txn_id",
                      "expected_amount_paise", "actual_amount_paise",
                      "variance_paise", "status", "confidence", "match_method"):
            assert field in first
        exceptions = client.get(f"/api/v1/batches/{batch_id}/exceptions",
                                params={"page_size": 100}).json()
        assert exceptions["total"] == 29

    def test_unknown_batch_404(self, client):
        r = client.post("/api/v1/batches/batch_nope/reconcile")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "batch_not_found"

    def test_empty_batch_reconciles_to_zero_results(self, client):
        empty_ledger = ("internal_id,order_id,payment_id,created_at,amount_paise,"
                        "currency,payment_status\n")
        empty_settlements = ("entity_id,type,payment_id,order_id,settlement_id,"
                             "settlement_utr,amount_paise,fee_paise,tax_paise,"
                             "debit_paise,credit_paise,settled_at\n")
        empty_bank = "bank_txn_id,value_date,description,utr,credit_paise,debit_paise\n"
        response = client.post("/api/v1/batches", files={
            "internal_ledger": ("a.csv", empty_ledger.encode()),
            "settlements": ("b.csv", empty_settlements.encode()),
            "bank_statement": ("c.csv", empty_bank.encode())})
        assert response.status_code == 201
        batch_id = response.json()["batch_id"]
        r = client.post(f"/api/v1/batches/{batch_id}/reconcile")
        assert r.status_code == 200
        assert r.json()["result_count"] == 0


class TestMetrics:
    def test_metrics_totals_match_engine(self, client):
        batch_id = _batch(client)
        client.post(f"/api/v1/batches/{batch_id}/reconcile")
        r = client.get(f"/api/v1/batches/{batch_id}/metrics")
        assert r.status_code == 200
        m = r.json()
        assert m["total_records"] == 100
        assert m["fully_reconciled"] == 71
        assert m["exceptions"] == 29
        assert m["match_rate"] == 0.71
        assert m["total_variance_paise"] == -150_000
        assert m["max_abs_variance_paise"] == 120_000
        assert m["processing_time_ms"] > 0
        assert m["records_per_second"] > 0
        # ground-truth-derived fields are explicitly NOT here (isolation)
        assert "precision" not in m and "recall" not in m

    def test_metrics_before_reconcile_is_honest(self, client):
        batch_id = _batch(client)
        r = client.get(f"/api/v1/batches/{batch_id}/metrics")
        assert r.status_code == 200
        assert r.json()["available"] is False
        assert "not been reconciled" in r.json()["note"]

    def test_unknown_batch_404(self, client):
        assert client.get("/api/v1/batches/batch_nope/metrics").status_code == 404


class TestCrossEndpointConsistency:
    def test_totals_agree_across_metrics_results_exceptions(self, client):
        """The dashboard renders three endpoints; their totals must agree."""
        batch_id = _batch(client)
        client.post(f"/api/v1/batches/{batch_id}/reconcile")
        m = client.get(f"/api/v1/batches/{batch_id}/metrics").json()
        r = client.get(f"/api/v1/batches/{batch_id}/results",
                       params={"page_size": 100}).json()
        e = client.get(f"/api/v1/batches/{batch_id}/exceptions",
                       params={"page_size": 100}).json()
        detail = client.get(f"/api/v1/batches/{batch_id}").json()
        assert m["total_records"] == r["total"] == 100
        assert m["fully_reconciled"] + m["exceptions"] == m["total_records"]
        assert e["total"] == m["exceptions"] == 29
        assert detail["result_count"] == m["total_records"]
        assert detail["status"] == "reconciled"
        # cash identity against the same batch
        cash = client.get(f"/api/v1/batches/{batch_id}/cash-position",
                          params={"opening_balance_paise": 1_000_000}).json()
        assert cash["actual_cash_paise"] == (
            1_000_000 + cash["confirmed_credits_paise"]
            - cash["confirmed_debits_paise"])
