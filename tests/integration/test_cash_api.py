"""Phase 7 API: GET /api/v1/batches/{id}/cash-position."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.database import Database
from backend.main import app

LEDGER = ("internal_id,order_id,payment_id,created_at,amount_paise,currency,payment_status\n"
          "int_001,order_001,pay_001,2026-08-10 09:00:00,100000,INR,captured\n")
SETTLEMENTS = ("entity_id,type,payment_id,order_id,settlement_id,settlement_utr,"
               "amount_paise,fee_paise,tax_paise,debit_paise,credit_paise,settled_at\n"
               "ent_001,payment,pay_001,order_001,setl_001,UTR001,100000,2000,360,0,0,"
               "2026-08-11 09:00:00\n")
BANK = ("bank_txn_id,value_date,description,utr,credit_paise,debit_paise\n"
        "bank_001,2026-08-12 10:00:00,NEFT CR UTR001,UTR001,97640,0\n")
EMPTY_SETTLEMENTS = SETTLEMENTS.splitlines()[0] + "\n"
EMPTY_BANK = BANK.splitlines()[0] + "\n"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SETTLESENSE_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def _batch(client, ledger=LEDGER, settlements=SETTLEMENTS, bank=BANK):
    response = client.post(
        "/api/v1/batches",
        files={
            "internal_ledger": ("a.csv", ledger.encode(), "text/csv"),
            "settlements": ("b.csv", settlements.encode(), "text/csv"),
            "bank_statement": ("c.csv", bank.encode(), "text/csv"),
        })
    assert response.status_code == 201
    return response.json()["batch_id"]


class TestCashPositionEndpoint:
    def test_clean_batch_cash_math(self, client):
        batch_id = _batch(client)
        r = client.get(f"/api/v1/batches/{batch_id}/cash-position",
                       params={"opening_balance_paise": 1_000_000})
        assert r.status_code == 200
        body = r.json()
        assert body["opening_balance_paise"] == 1_000_000
        assert body["confirmed_credits_paise"] == 97_640
        assert body["confirmed_debits_paise"] == 0
        assert body["actual_cash_paise"] == 1_000_000 + 97_640
        assert body["pending_settlements_paise"] == 0
        assert body["expected_cash_paise"] == 1_000_000 + 97_640
        assert body["variance_paise"] == 0
        assert body["confidence"] == "high"
        assert body["forecast_horizon_days"] == 7
        assert len(body["forecast"]) == 7
        assert any("NOT booked" in a for a in body["assumptions"])

    def test_missing_bank_credit_negative_variance(self, client):
        # a later-dated anchor row keeps the batch as_of AFTER the settlement
        # date, so the absent credit is MISSING (old), not timing delay
        anchored_bank = (BANK.splitlines()[0] + "\n"
                        + "bank_anchor,2026-08-15 10:00:00,BANK CHARGE,,0,0\n")
        batch_id = _batch(client, bank=anchored_bank)
        body = client.get(f"/api/v1/batches/{batch_id}/cash-position").json()
        assert body["confirmed_credits_paise"] == 0
        assert body["variance_paise"] == -97_640
        assert body["pending_settlements_paise"] == 0
        assert body["confidence"] == "medium"

    def test_empty_batch_returns_opening_only(self, client):
        empty_ledger = LEDGER.splitlines()[0] + "\n"
        batch_id = _batch(client, ledger=empty_ledger,
                          settlements=EMPTY_SETTLEMENTS, bank=EMPTY_BANK)
        body = client.get(
            f"/api/v1/batches/{batch_id}/cash-position",
            params={"opening_balance_paise": 500_000}).json()
        assert body["actual_cash_paise"] == 500_000
        assert body["expected_cash_paise"] == 500_000
        assert body["variance_paise"] == 0
        assert body["confidence"] == "high"

    def test_horizon_is_configurable_and_validated(self, client):
        batch_id = _batch(client)
        r = client.get(f"/api/v1/batches/{batch_id}/cash-position",
                       params={"horizon": 3})
        assert r.status_code == 200 and r.json()["forecast_horizon_days"] == 3
        assert len(r.json()["forecast"]) == 3
        assert client.get(f"/api/v1/batches/{batch_id}/cash-position",
                          params={"horizon": 0}).status_code == 422
        assert client.get(f"/api/v1/batches/{batch_id}/cash-position",
                          params={"horizon": 31}).status_code == 422

    def test_unknown_batch_404(self, client):
        r = client.get("/api/v1/batches/batch_nope/cash-position")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "batch_not_found"

    def test_negative_opening_balance_rejected(self, client):
        batch_id = _batch(client)
        r = client.get(f"/api/v1/batches/{batch_id}/cash-position",
                       params={"opening_balance_paise": -5})
        assert r.status_code == 422

    def test_forecast_never_claimed_as_booked(self, client):
        batch_id = _batch(client, bank=EMPTY_BANK)  # pending-ish scenarios
        body = client.get(f"/api/v1/batches/{batch_id}/cash-position").json()
        for day in body["forecast"]:
            assert "not booked cash" in day["note"]


class TestDatasetLevel:
    def test_synthetic_fixture_cash_position_coherent(self, client):
        batch = client.post("/api/v1/batches?fixture=synthetic-v2")
        assert batch.status_code == 201
        batch_id = batch.json()["batch_id"]
        body = client.get(
            f"/api/v1/batches/{batch_id}/cash-position",
            params={"opening_balance_paise": 10_000_000}).json()
        # dataset: 71 reconciled credits confirmed; 10 timing-delay pending
        assert body["pending_settlements_paise"] > 0
        assert body["variance_paise"] < 0  # 4 missing credits + 6 mismatch deltas
        assert body["confidence"] == "low"  # duplicates + ambiguous exist
        assert body["unattributed_or_excluded_paise"] > 0
        # sanity: actual = opening + credits - debits, all paise ints
        assert (body["actual_cash_paise"]
                == 10_000_000 + body["confirmed_credits_paise"]
                - body["confirmed_debits_paise"])


class TestLowFindingFixes:
    def test_bank_charges_field_reaches_api_payload(self, client):
        batch = client.post("/api/v1/batches?fixture=synthetic-v2")
        batch_id = batch.json()["batch_id"]
        body = client.get(
            f"/api/v1/batches/{batch_id}/cash-position").json()
        assert body["bank_charges_paise"] == 7_100  # 5,900 + 1,200 noise rows

    def test_cash_route_documents_error_contract(self, client):
        spec = client.get("/openapi.json").json()
        cash = spec["paths"]["/api/v1/batches/{batch_id}/cash-position"]
        assert "ErrorResponse" in str(cash), "cash route must declare error responses"
