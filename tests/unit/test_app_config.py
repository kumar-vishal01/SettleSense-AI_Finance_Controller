"""Service configuration guards (review finding L6)."""

from __future__ import annotations

import pytest

from backend.main import create_app


def test_wildcard_cors_rejected_in_production(monkeypatch):
    monkeypatch.setenv("SETTLESENSE_ENV", "production")
    monkeypatch.setenv("SETTLESENSE_CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="CORS"):
        create_app()


def test_explicit_origins_accepted_in_production(monkeypatch):
    monkeypatch.setenv("SETTLESENSE_ENV", "production")
    monkeypatch.setenv("SETTLESENSE_CORS_ORIGINS", "https://demo.example.com")
    assert create_app() is not None


def test_batch_status_fields_are_enum_typed():
    """L5: API status fields use the BatchStatus contract, not bare str."""
    import pytest as _pytest
    from backend.schemas import BatchCreateResponse
    with _pytest.raises(ValueError):
        BatchCreateResponse(
            batch_id="b", source_hash="h", status="bogus", record_count=0,
            counts={"ledger_rows": 0, "settlement_rows": 0, "bank_rows": 0},
            validation={"valid": True, "total_rows": 0, "valid_rows": 0,
                        "skipped_rows": 0, "duplicate_rows": 0,
                        "conflicting_rows": 0, "errors": []},
            started_at="2026-01-01T00:00:00+00:00",
        )
