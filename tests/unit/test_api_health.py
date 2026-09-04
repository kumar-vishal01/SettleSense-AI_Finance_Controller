"""API contract test for GET /health (phase 1 service surface)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import SERVICE_NAME, SERVICE_VERSION, app


def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_returns_200_and_contract_fields(self):
        response = client().get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == SERVICE_NAME
        assert body["version"] == SERVICE_VERSION
        assert body["environment"] in {"local", "docker", "production"}
        assert "timezone" in body

    def test_response_parses_into_typed_schema(self):
        from backend.schemas import HealthResponse
        body = client().get("/health").json()
        parsed = HealthResponse(**body)  # raises if the payload violates contract
        assert parsed.status == "ok"
        assert parsed.service == SERVICE_NAME

    def test_openapi_documents_the_endpoint(self):
        body = client().get("/openapi.json").json()
        assert "/health" in body["paths"]
        assert body["info"]["version"] == SERVICE_VERSION

    def test_documented_surface_only(self):
        """Surface gate: health + batches + cash + constrained AI Q&A exist;
        no reconcile/metrics/export/trace routes yet (later phases)."""
        body = client().get("/openapi.json").json()
        assert set(body["paths"]) == {
            "/health",
            "/api/v1/batches",
            "/api/v1/batches/{batch_id}",
            "/api/v1/batches/{batch_id}/results",
            "/api/v1/batches/{batch_id}/exceptions",
            "/api/v1/batches/{batch_id}/cash-position",
            "/api/v1/batches/{batch_id}/reconcile",
            "/api/v1/batches/{batch_id}/metrics",
            "/api/v1/batches/{batch_id}/export",
            "/api/v1/ai/query",
            "/api/v1/transactions/{payment_id}/trace",
        }

    def test_health_contains_no_secrets_or_paths(self):
        body = client().get("/health").json()
        dumped = str(body).lower()
        for forbidden in ("key", "secret", "password", "token", "db", "/home", "c:\\"):
            assert forbidden not in dumped
