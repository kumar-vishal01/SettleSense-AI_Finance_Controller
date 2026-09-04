"""Groq provider: transport-injected (no network in tests), timeout-aware,
ID-preserving, capped."""

from __future__ import annotations

import pytest

from backend.ai_provider_groq import GroqProvider, build_groq_provider_from_env


class StubTransport:
    def __init__(self, *, status=200, text="sure thing", delay=None):
        self.status, self.text, self.delay = status, text, delay
        self.calls: list[dict] = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append({"url": url, "model": json["model"],
                           "system": json["messages"][0]["content"],
                           "timeout": timeout})
        if self.delay:
            raise TimeoutError("simulated slow model")
        if self.status != 200:
            raise RuntimeError(f"groq error {self.status}")
        return {"choices": [{"message": {"content": self.text}}]}


def _grounded():
    return ("The highest-impact unresolved exception is pay_069 "
            "(MISSING_BANK_CREDIT) with exposure 464175.68 INR.")


class TestGroqProvider:
    def test_rephrase_calls_groq_compatible_endpoint(self):
        transport = StubTransport(text="Reworded: pay_069 tops the list.")
        provider = GroqProvider(api_key="k", model="llama-3.3-70b-versatile",
                                transport=transport)
        out = provider.rephrase(_grounded(), "which is worst?")
        assert out == "Reworded: pay_069 tops the list."
        call = transport.calls[0]
        assert call["url"].endswith("/chat/completions")
        assert "api.groq.com" in call["url"]
        assert call["model"] == "llama-3.3-70b-versatile"
        assert "never" in call["system"].lower()  # constraint prompt
        assert transport.calls[0]["timeout"] == provider.timeout_seconds

    def test_timeout_raises_timeouterror(self):
        provider = GroqProvider(api_key="k", transport=StubTransport(delay=True))
        with pytest.raises(TimeoutError):
            provider.rephrase(_grounded(), "q")

    def test_http_failure_raises_runtimeerror(self):
        provider = GroqProvider(api_key="k", transport=StubTransport(status=429))
        with pytest.raises(RuntimeError):
            provider.rephrase(_grounded(), "q")

    def test_daily_cap_falls_back_loudly(self):
        provider = GroqProvider(api_key="k", transport=StubTransport(),
                                daily_call_cap=2)
        provider.rephrase(_grounded(), "q1")
        provider.rephrase(_grounded(), "q2")
        with pytest.raises(RuntimeError, match="cap"):
            provider.rephrase(_grounded(), "q3")

    def test_api_key_never_appears_in_errors_or_prompts(self):
        transport = StubTransport(status=500)
        provider = GroqProvider(api_key="SECRET_KEY_123", transport=transport)
        with pytest.raises(RuntimeError) as exc:
            provider.rephrase(_grounded(), "q")
        assert "SECRET_KEY_123" not in str(exc.value)
        assert "SECRET_KEY_123" not in str(transport.calls)


class TestFactory:
    def test_no_key_or_provider_means_deterministic(self, monkeypatch):
        monkeypatch.delenv("SETTLESENSE_AI_PROVIDER", raising=False)
        monkeypatch.delenv("SETTLESENSE_AI_API_KEY", raising=False)
        provider = build_groq_provider_from_env()
        assert provider is None or provider.name == "none"

    def test_groq_selected_only_with_key(self, monkeypatch):
        monkeypatch.setenv("SETTLESENSE_AI_PROVIDER", "groq")
        monkeypatch.delenv("SETTLESENSE_AI_API_KEY", raising=False)
        assert build_groq_provider_from_env() is None  # no key -> no provider
        monkeypatch.setenv("SETTLESENSE_AI_API_KEY", "gsk_test")
        provider = build_groq_provider_from_env()
        assert provider is not None and provider.name == "groq"
        assert provider.model == "llama-3.3-70b-versatile"


class TestAgentRephraseSafety:
    def test_model_that_drops_record_ids_is_rejected(self):
        from backend.ai_agent import AgentAnswer, answer_question
        from backend.database import Database
        import os, tempfile
        os.environ["SETTLESENSE_DB_PATH"] = tempfile.mktemp()
        from fastapi.testclient import TestClient
        from backend.main import app
        with TestClient(app) as c:
            batch_id = c.post("/api/v1/batches?fixture=synthetic-v2").json()["batch_id"]

        class Dropping(GroqProvider):
            def __init__(self):
                super().__init__(api_key="k", transport=StubTransport())
            def rephrase(self, grounded_answer, question, timeout_seconds=5.0):
                return "Everything looks fine, nothing to see here."  # IDs gone

        result = answer_question(
            batch_id, "Which unresolved exception has the highest monetary impact?",
            Database(os.environ["SETTLESENSE_DB_PATH"]), provider=Dropping())
        assert result.fallback is True
        assert "pay_069" in result.answer  # deterministic answer served instead

    def test_model_that_invents_new_ids_is_rejected(self):
        from backend.ai_agent import answer_question
        from backend.database import Database
        import os, tempfile
        os.environ["SETTLESENSE_DB_PATH"] = tempfile.mktemp()
        from fastapi.testclient import TestClient
        from backend.main import app
        with TestClient(app) as c:
            batch_id = c.post("/api/v1/batches?fixture=synthetic-v2").json()["batch_id"]

        class Inventing(GroqProvider):
            def __init__(self):
                super().__init__(api_key="k", transport=StubTransport())
            def rephrase(self, grounded_answer, question, timeout_seconds=5.0):
                return grounded_answer + " Also check pay_99999 immediately."

        result = answer_question(
            batch_id, "Which unresolved exception has the highest monetary impact?",
            Database(os.environ["SETTLESENSE_DB_PATH"]), provider=Inventing())
        assert result.fallback is True
        assert "pay_99999" not in result.answer


class TestEvidenceGuardAmountsAndStatuses:
    """F1 (senior review): the rephrase guard must protect amounts and
    statuses, not only record IDs (AGENTS section 6)."""

    GROUNDED = ("The highest-impact unresolved exception is pay_069 "
                "(MISSING_BANK_CREDIT) with exposure 464175.68 INR "
                "(46417568 paise). This record requires human review.")

    def test_tampered_amount_is_rejected(self):
        from backend.ai_agent import _rephrase_is_safe
        assert _rephrase_is_safe(
            "pay_069 exposure 999999.99 INR", self.GROUNDED, ["pay_069"]) is False

    def test_status_flip_is_rejected(self):
        from backend.ai_agent import _rephrase_is_safe
        assert _rephrase_is_safe(
            "pay_069 is now FULLY_RECONCILED with exposure 464175.68 INR",
            self.GROUNDED, ["pay_069"]) is False

    def test_comma_formatting_is_accepted(self):
        from backend.ai_agent import _rephrase_is_safe
        assert _rephrase_is_safe(
            "Top unresolved case: pay_069, MISSING_BANK_CREDIT, exposure "
            "464,175.68 INR (46,417,568 paise) — needs human review.",
            self.GROUNDED, ["pay_069"]) is True

    def test_substring_amount_is_rejected(self):
        from backend.ai_agent import _rephrase_is_safe
        assert _rephrase_is_safe(
            "pay_069 exposure 500 INR (46417568 paise)",
            self.GROUNDED, ["pay_069"]) is False

    def test_sign_flip_is_rejected(self):
        from backend.ai_agent import _rephrase_is_safe
        grounded = "pay_069 variance -1500 INR"
        assert _rephrase_is_safe("pay_069 variance 1500 INR", grounded, ["pay_069"]) is False

    def test_faithful_rephrase_is_accepted(self):
        from backend.ai_agent import _rephrase_is_safe
        assert _rephrase_is_safe(
            "Top unresolved case: pay_069, MISSING_BANK_CREDIT, exposure "
            "464175.68 INR (46417568 paise) — needs human review.",
            self.GROUNDED, ["pay_069"]) is True

    def test_end_to_end_tampering_serves_deterministic_answer(self):
        import os, tempfile
        from backend.ai_agent import answer_question
        from backend.database import Database
        from fastapi.testclient import TestClient
        from backend.main import app
        os.environ["SETTLESENSE_DB_PATH"] = tempfile.mktemp()
        with TestClient(app) as c:
            batch_id = c.post("/api/v1/batches?fixture=synthetic-v2").json()["batch_id"]

        class Tampering(GroqProvider):
            def __init__(self):
                super().__init__(api_key="k", transport=StubTransport())
            def rephrase(self, grounded_answer, question, timeout_seconds=5.0):
                return ("Great news: pay_069 is FULLY_RECONCILED for 5 INR. "
                        "Nothing needs attention.")

        result = answer_question(
            batch_id, "Which unresolved exception has the highest monetary impact?",
            Database(os.environ["SETTLESENSE_DB_PATH"]), provider=Tampering())
        assert result.fallback is True
        assert "MISSING_BANK_CREDIT" in result.answer
        assert "FULLY_RECONCILED for 5 INR" not in result.answer
