"""Groq LLM provider (OpenAI-compatible endpoint, api.groq.com).

Role: REPHRASING ONLY. The provider receives an already-grounded deterministic
answer and may reword it — it must never add or drop facts, IDs, or amounts.
The agent enforces this (`ai_agent` rejects rephrases that lose record IDs or
introduce unknown ones), and any timeout/error/cap-hit falls back to the
deterministic answer, so the assistant degrades gracefully to exactly the
behaviour it had without a model.

Key handling: the API key lives only in the process environment (loaded from
the git-ignored .env by backend.settings). It is never logged, never echoed
in errors, never sent anywhere except Groq's auth header.
"""

from __future__ import annotations

import os

import httpx

import backend.settings  # noqa: F401 — loads .env once (key stays in env)
from backend.ai_agent import AIProvider, DEFAULT_TIMEOUT_SECONDS

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

_SYSTEM_PROMPT = (
    "You are the wording layer of a finance reconciliation assistant. "
    "Rephrase the given grounded answer for the user's question. STRICT RULES: "
    "keep every fact, record ID (pay_*/setl_*/bank_*/UTR*), amount, date, and "
    "status EXACTLY as given; never add new information, IDs, numbers, or "
    "advice; never claim anything is reconciled unless the answer says so; "
    "keep it short and factual. Output only the rephrased answer."
)


class _HttpxTransport:
    """Default transport: real HTTP call to Groq."""

    def post(self, url: str, *, headers: dict, json: dict, timeout: float) -> dict:
        response = httpx.post(url, headers=headers, json=json, timeout=timeout)
        if response.status_code != 200:
            # message body may contain request ids etc. — keep it generic
            raise RuntimeError(f"groq request failed with status {response.status_code}")
        return response.json()


class GroqProvider(AIProvider):
    name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_GROQ_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        daily_call_cap: int = 200,
        transport=None,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.daily_call_cap = daily_call_cap
        self._transport = transport or _HttpxTransport()
        self._calls_today = 0

    def rephrase(self, grounded_answer: str, question: str,
                 timeout_seconds: float | None = None) -> str:
        self._calls_today += 1
        if self._calls_today > self.daily_call_cap:
            raise RuntimeError(
                f"groq daily call cap reached ({self.daily_call_cap}); "
                "serving deterministic answers")
        try:
            payload = self._transport.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content":
                            f"Question: {question}\nGrounded answer: {grounded_answer}"},
                    ],
                    "temperature": 0.1,
                },
                timeout=timeout_seconds or self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError("groq model timed out") from exc
        return payload["choices"][0]["message"]["content"]


def build_groq_provider_from_env() -> AIProvider | None:
    """Return a Groq provider when env selects it AND a key exists; otherwise
    None (caller serves deterministic answers). Never raises on missing
    config — absence of a model is a normal, supported state."""
    if os.environ.get("SETTLESENSE_AI_PROVIDER", "none").lower() != "groq":
        return None
    api_key = os.environ.get("SETTLESENSE_AI_API_KEY", "").strip()
    if not api_key:
        return None
    return GroqProvider(
        api_key=api_key,
        model=os.environ.get("SETTLESENSE_AI_MODEL", DEFAULT_GROQ_MODEL),
        timeout_seconds=float(os.environ.get("SETTLESENSE_AI_TIMEOUT_SECONDS",
                                             str(DEFAULT_TIMEOUT_SECONDS))),
        daily_call_cap=int(os.environ.get("SETTLESENSE_AI_DAILY_CALL_CAP", "200")),
    )
