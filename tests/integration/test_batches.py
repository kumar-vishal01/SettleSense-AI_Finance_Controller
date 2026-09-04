"""Phase 4 batch API integration tests: creation, validation errors,
idempotency, retrieval, pagination, exception filtering, rollback."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.database import Database
from backend.main import app
from backend.models import BatchStatus
from backend.repositories import (
    AuditRepository,
    BankEntryRepository,
    BatchRepository,
    ReconciliationResultRepository,
    TransactionRepository,
)

LEDGER = (
    "internal_id,order_id,payment_id,created_at,amount_paise,currency,payment_status\n"
    "int_001,order_001,pay_001,2026-08-10 09:00:00,100000,INR,captured\n"
    "int_002,order_002,pay_002,2026-08-10 10:00:00,250000,INR,captured\n"
)
SETTLEMENTS = (
    "entity_id,type,payment_id,order_id,settlement_id,settlement_utr,amount_paise,"
    "fee_paise,tax_paise,debit_paise,credit_paise,settled_at\n"
    "ent_001,payment,pay_001,order_001,setl_001,UTR001,100000,2000,360,0,0,2026-08-11 09:00:00\n"
    "ent_002,payment,pay_002,order_002,setl_002,UTR002,250000,5000,900,0,0,2026-08-11 10:00:00\n"
)
BANK = (
    "bank_txn_id,value_date,description,utr,credit_paise,debit_paise\n"
    "bank_001,2026-08-12 10:00:00,NEFT CR UTR001,UTR001,97640,0\n"
    "bank_002,2026-08-12 10:30:00,NEFT CR UTR002,UTR002,244100,0\n"
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SETTLESENSE_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _upload(client, *, ledger=LEDGER, settlements=SETTLEMENTS, bank=BANK):
    return client.post(
        "/api/v1/batches",
        files={
            "internal_ledger": ("internal_ledger.csv", ledger.encode(), "text/csv"),
            "settlements": ("settlements.csv", settlements.encode(), "text/csv"),
            "bank_statement": ("bank_statement.csv", bank.encode(), "text/csv"),
        },
    )


class TestValidBatchCreation:
    def test_create_returns_201_validated_not_reconciled(self, client):
        response = _upload(client)
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "validated"
        assert body["idempotent"] is False
        assert body["record_count"] == 6  # 2+2+2 valid source rows
        assert body["counts"] == {
            "ledger_rows": 2, "settlement_rows": 2, "bank_rows": 2}
        assert body["validation"]["valid"] is True
        assert body["validation"]["errors"] == []
        assert len(body["source_hash"]) == 64

    def test_rows_and_audit_persisted(self, client, tmp_path):
        _upload(client)
        db = Database(tmp_path / "test.db")
        conn = db.connect(init=False)
        try:
            batches = conn.execute("SELECT * FROM batches").fetchall()
            assert len(batches) == 1
            assert batches[0]["status"] == BatchStatus.VALIDATED.value
            assert TransactionRepository(conn).count_for_batch(batches[0]["id"]) == 4
            assert BankEntryRepository(conn).count_for_batch(batches[0]["id"]) == 2
            audit = AuditRepository(conn).list_for_batch(batches[0]["id"])
            assert [a["action"] for a in audit] == ["batch_created"]
            assert audit[0]["details"]["note"].startswith("batch validated only")
            # raw payloads preserved for audit
            raw = conn.execute("SELECT raw_payload_json FROM bank_entries").fetchone()
            assert "NEFT CR UTR001" in raw[0]
        finally:
            conn.close()

    def test_results_empty_and_honest_before_reconciliation(self, client):
        batch_id = _upload(client).json()["batch_id"]
        response = client.get(f"/api/v1/batches/{batch_id}/results")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["batch_status"] == "validated"
        assert "has not been run" in body["note"]


class TestInvalidFiles:
    def test_missing_columns_is_structured_422(self, client):
        response = _upload(client, ledger="internal_id,payment_id\nint_001,pay_001\n")
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "ingestion_error"
        assert "missing required columns" in error["message"]

    def test_row_level_errors_reported_but_batch_created(self, client):
        bad_row = ("int_003,order_003,pay_003,2026-08-10 11:00:00,abc,INR,captured\n")
        response = _upload(client, ledger=LEDGER + bad_row)
        assert response.status_code == 201
        body = response.json()
        assert body["validation"]["skipped_rows"] == 1
        assert body["validation"]["errors"][0]["code"] == "invalid_amount"
        assert body["validation"]["errors"][0]["row_number"] == 4

    def test_missing_files_rejected(self, client):
        response = client.post("/api/v1/batches")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "missing_files"
        assert "three files are required" in response.json()["error"]["message"]

    def test_unknown_fixture_rejected(self, client):
        response = client.post("/api/v1/batches", params={"fixture": "../../etc"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_fixture"
        assert "unknown fixture" in response.json()["error"]["message"]

    def test_error_bodies_contain_no_filesystem_paths(self, client):
        response = _upload(client, ledger="internal_id,payment_id\nint_001,pay_001\n")
        text = response.text
        assert "/home/" not in text and "C:\\\\" not in text


class TestIdempotency:
    def test_duplicate_upload_returns_existing_batch(self, client):
        first = _upload(client)
        second = _upload(client)
        assert first.status_code == 201 and second.status_code == 200
        assert second.json()["idempotent"] is True
        assert second.json()["batch_id"] == first.json()["batch_id"]
        assert second.json()["record_count"] == first.json()["record_count"]

    def test_duplicate_upload_writes_no_new_rows(self, client, tmp_path):
        _upload(client)
        _upload(client)
        conn = Database(tmp_path / "test.db").connect(init=False)
        try:
            assert conn.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"] == 1
            assert conn.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"] == 4
            assert conn.execute("SELECT COUNT(*) c FROM bank_entries").fetchone()["c"] == 2
            assert conn.execute("SELECT COUNT(*) c FROM audit_events").fetchone()["c"] == 1
        finally:
            conn.close()

    def test_changed_content_creates_new_batch(self, client):
        _upload(client)
        changed = LEDGER.replace("100000", "100001")
        response = _upload(client, ledger=changed)
        assert response.status_code == 201
        assert response.json()["idempotent"] is False


class TestBatchRetrieval:
    def test_get_batch_detail(self, client):
        batch_id = _upload(client).json()["batch_id"]
        response = client.get(f"/api/v1/batches/{batch_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["batch_id"] == batch_id
        assert body["status"] == "validated"
        assert body["result_count"] == 0
        assert body["audit_events"][0]["action"] == "batch_created"
        assert body["completed_at"] is None

    def test_unknown_batch_is_structured_404(self, client):
        response = client.get("/api/v1/batches/batch_nope")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "batch_not_found"

    def test_results_for_unknown_batch_404(self, client):
        assert client.get("/api/v1/batches/batch_nope/results").status_code == 404


class TestPaginationAndFilters:
    @pytest.fixture()
    def batch_with_results(self, client, tmp_path):
        from tests.factories import (
            DEFAULT_NET, bank_entry, ledger_txn, settlement_txn,
        )
        from backend.config import ReconciliationConfig
        from backend.reconciliation import reconcile_batch
        from tests.factories import AS_OF

        batch_id = _upload(client).json()["batch_id"]
        # exercise the (existing, tested) engine to fill the results table
        outcome = reconcile_batch(
            [ledger_txn(payment_id=f"pay_{i:03d}", order_id=f"order_{i:03d}",
                        row_id=f"int_{i:03d}") for i in (1, 2)],
            [settlement_txn(payment_id=f"pay_{i:03d}", entity_id=f"ent_{i:03d}",
                            settlement_id=f"setl_{i:03d}", utr=f"UTR{i:03d}",
                            order_id=f"order_{i:03d}") for i in (1, 2)],
            [bank_entry(txn_id=f"bank_{i:03d}", utr=f"UTR{i:03d}", credit=DEFAULT_NET)
             for i in (1, 2)],
            ReconciliationConfig(), AS_OF,
        )
        # force one exception so filtering has something to filter on
        from backend.models import ReconciliationStatus
        results = list(outcome.results)
        results[1] = results[1].model_copy(
            update={"requires_review": True,
                    "status": ReconciliationStatus.NEEDS_HUMAN_REVIEW}
        )
        conn = Database(tmp_path / "test.db").connect(init=False)
        try:
            with conn:
                ReconciliationResultRepository(conn).insert_many(batch_id, results)
        finally:
            conn.close()
        return batch_id

    def test_pagination_pages(self, client, batch_with_results):
        page1 = client.get(
            f"/api/v1/batches/{batch_with_results}/results",
            params={"page": 1, "page_size": 1},
        ).json()
        page2 = client.get(
            f"/api/v1/batches/{batch_with_results}/results",
            params={"page": 2, "page_size": 1},
        ).json()
        assert page1["total"] == 2 and page1["total_pages"] == 2
        assert len(page1["items"]) == 1 and len(page2["items"]) == 1
        assert page1["items"][0]["payment_id"] != page2["items"][0]["payment_id"]

    def test_page_size_capped(self, client, batch_with_results):
        response = client.get(
            f"/api/v1/batches/{batch_with_results}/results",
            params={"page_size": 5000},
        )
        assert response.status_code == 422  # le=MAX_PAGE_SIZE enforced

    def test_status_filter(self, client, batch_with_results):
        body = client.get(
            f"/api/v1/batches/{batch_with_results}/results",
            params={"status": "FULLY_RECONCILED"},
        ).json()
        assert body["total"] == 1
        assert body["items"][0]["status"] == "FULLY_RECONCILED"

    def test_unknown_status_filter_is_422(self, client, batch_with_results):
        response = client.get(
            f"/api/v1/batches/{batch_with_results}/results",
            params={"status": "RECONCILED_PERFECTLY"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"

    def test_exceptions_endpoint_returns_only_review_items(self, client, batch_with_results):
        body = client.get(
            f"/api/v1/batches/{batch_with_results}/exceptions").json()
        assert body["total"] == 1
        assert body["items"][0]["requires_review"] is True


class TestDatabaseRollback:
    def test_failed_persist_leaves_no_partial_batch(self, client, tmp_path, monkeypatch):
        from backend.routes import batches as batches_route

        original = batches_route.create_batch_transactionally

        def exploding(*args, **kwargs):
            # simulate a mid-transaction failure after the batch row insert
            from backend.repositories import BatchRepository, BatchRow
            db = kwargs["db"] if "db" in kwargs else args[0]
            batch = BatchRow(
                id="batch_doomed", source_hash=kwargs["source_hash"],
                status=BatchStatus.VALIDATED, record_count=0,
                ledger_rows=0, settlement_rows=0, bank_rows=0,
                skipped_rows=0, duplicate_rows=0, conflicting_rows=0,
                validation_errors=[], started_at="2026-01-01T00:00:00+00:00",
            )
            conn = db.connect(init=False)
            try:
                with conn:
                    BatchRepository(conn).insert(batch)
                    raise RuntimeError("simulated disk failure mid-transaction")
            finally:
                conn.close()
            return original(*args, **kwargs)

        monkeypatch.setattr(batches_route, "create_batch_transactionally", exploding)
        response = _upload(client)
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_error"

        conn = Database(tmp_path / "test.db").connect(init=False)
        try:
            assert conn.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"] == 0
            assert conn.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"] == 0
            assert conn.execute("SELECT COUNT(*) c FROM audit_events").fetchone()["c"] == 0
        finally:
            conn.close()

        # and a retry after the failure succeeds cleanly (restore ONLY the
        # patched function — undo() would also revert the env fixture)
        monkeypatch.setattr(batches_route, "create_batch_transactionally", original)
        assert _upload(client).status_code == 201


class TestSeniorReviewPhase4:
    """Findings from the phase-4 senior review, pinned as regressions."""

    def test_every_error_uses_one_envelope(self, client):
        """All non-2xx JSON bodies must be {"error": {code, message}} — the
        envelope OpenAPI documents. No stray {"detail": ...} shapes."""
        cases = [
            client.post("/api/v1/batches"),  # missing files
            client.post("/api/v1/batches", params={"fixture": "nope"}),
            client.get("/api/v1/batches/batch_missing"),
            client.get("/api/v1/batches/batch_missing/results"),
            client.get("/api/v1/does-not-exist"),  # unrouted path -> 404
        ]
        bad = _upload(client, ledger="internal_id,payment_id\nint_001,pay_001\n")
        cases.append(bad)
        for response in cases:
            assert response.status_code >= 400
            body = response.json()
            assert "detail" not in body, response.request.url
            assert set(body["error"]) >= {"code", "message"}, body

    def test_oversized_upload_rejected_before_full_read(self, client, monkeypatch):
        from backend.config import ReconciliationConfig
        from backend.routes import batches as batches_route

        tiny = ReconciliationConfig(max_file_bytes=100)
        monkeypatch.setattr(
            batches_route, "ReconciliationConfig", lambda: tiny)
        big_ledger = LEDGER + ("int_003,order_003,pay_003,2026-08-10 12:00:00,"
                               "100000,INR,captured\n" * 20)
        response = _upload(client, ledger=big_ledger)
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "file_too_large"

    def test_concurrent_duplicate_upload_is_idempotent_not_500(
            self, client, tmp_path, monkeypatch):
        """UNIQUE(source_hash) is the hard backstop: when the pre-check loses
        a race, the request must still return the existing batch (200),
        never a 500 or a second batch."""
        from backend.routes import batches as batches_route

        first = _upload(client)
        batch_id = first.json()["batch_id"]

        real_find = batches_route.BatchRepository.find_by_source_hash
        calls = {"n": 0}

        def race_then_real(self, source_hash):
            calls["n"] += 1
            if calls["n"] == 1:
                return None  # the pre-check loses the race...
            return real_find(self, source_hash)  # ...recovery must see the winner

        monkeypatch.setattr(
            batches_route.BatchRepository, "find_by_source_hash", race_then_real,
        )
        second = _upload(client)

        assert second.status_code == 200
        body = second.json()
        assert body["idempotent"] is True
        assert body["batch_id"] == batch_id
        conn = Database(tmp_path / "test.db").connect(init=False)
        try:
            assert conn.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"] == 1
        finally:
            conn.close()

    def test_many_row_errors_are_capped_in_response(self, client):
        bad_rows = "".join(
            f"int_{i:03d},order_{i:03d},pay_{i:03d},2026-08-10 12:00:00,nope,INR,captured\n"
            for i in range(150)
        )
        response = _upload(client, ledger=LEDGER + bad_rows)
        assert response.status_code == 201
        body = response.json()
        assert body["validation"]["skipped_rows"] == 150  # full count visible
        assert len(body["validation"]["errors"]) <= 100
        assert body["validation"]["errors_truncated"] is True


class TestFullRepoReview:
    """Findings from the full-repository review round."""

    def test_fixture_plus_files_conflict_is_422(self, client):
        response = client.post(
            "/api/v1/batches",
            params={"fixture": "synthetic-v2"},
            files={"internal_ledger": ("a.csv", LEDGER.encode())},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"
        assert "not both" in response.json()["error"]["message"]

    def test_schema_ddl_runs_once_per_app_not_per_request(self, client, monkeypatch):
        """M2: request paths must never execute schema DDL."""
        from backend.database import Database
        calls = {"n": 0}
        original = Database.init_schema

        def counting(conn):
            calls["n"] += 1
            return original(conn)

        monkeypatch.setattr(Database, "init_schema", staticmethod(counting))
        with TestClient(app) as fresh:
            fresh.post("/api/v1/batches?fixture=synthetic-v2")
            fresh.get("/api/v1/batches")
            fresh.get("/api/v1/batches")
        assert calls["n"] == 1, "DDL must run once per app startup, not per request"


class TestLowFindingFixes:
    def test_exceptions_unknown_batch_404(self, client):
        response = client.get("/api/v1/batches/batch_missing/exceptions")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "batch_not_found"
