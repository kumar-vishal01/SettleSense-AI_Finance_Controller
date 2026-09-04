"""Docs must not contradict the shipped service (review finding M1)."""

from __future__ import annotations

from pathlib import Path

from backend.main import SERVICE_VERSION

ROOT = Path(__file__).resolve().parents[2]


def test_verification_guide_references_current_version():
    text = (ROOT / "VERIFICATION.md").read_text(encoding="utf-8")
    assert SERVICE_VERSION in text, "VERIFICATION.md version drifted from backend.main"


def test_verification_guide_documents_the_batch_api():
    text = (ROOT / "VERIFICATION.md").read_text(encoding="utf-8")
    assert "/api/v1/batches" in text, "the batch API must be in the verification guide"


def test_readme_status_table_marks_phase4_done():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Phase 4" in text and "Phase 5" in text
    # the stale claim 'persistence + batch API is next' must be gone
    assert "SQLite persistence + batch/reconcile REST API | ⏭ next" not in text


class TestStructuralDocGuards:
    """M2 (third recurrence): docs must not be able to drift structurally."""

    def test_no_hard_test_counts_in_docs(self):
        import re
        for name in ("VERIFICATION.md", "README.md", "TESTING.md", "PROGRESS.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            hits = re.findall(r"\d+ tests\b", text)
            assert not hits, f"{name} hard-codes test counts: {hits} — counts drift; cite the command instead"

    def test_documented_endpoint_set_matches_openapi(self):
        import re
        from fastapi.testclient import TestClient
        from backend.main import app
        live = set(TestClient(app).get("/openapi.json").json()["paths"].keys())
        text = (ROOT / "VERIFICATION.md").read_text(encoding="utf-8")
        documented = set(re.findall(r"`(/health|/api/v1/[a-zA-Z0-9/{}_.-]+)`", text))
        assert documented == live, (
            f"VERIFICATION.md documents {documented ^ live} inconsistently with the app"
        )

    def test_readme_documents_cash_endpoint_and_current_phases(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "cash-position" in readme, "shipped cash endpoint missing from quickstart"
        assert "cash position" in readme.lower()
        # shipped phases must not be marked pending
        for phase in ("Phase 5", "Phase 6", "Phase 7"):
            for line in readme.splitlines():
                if line.startswith(f"| {phase} ") or line.startswith(f"| **{phase}"):
                    assert "⏭" not in line, f"{phase} shipped but README marks it pending"
