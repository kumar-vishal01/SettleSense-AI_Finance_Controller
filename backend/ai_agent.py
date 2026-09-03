"""Constrained AI finance agent.

Deterministic-first: questions route to read-only backend tools and answers
are assembled STRICTLY from tool output — every amount, ID, date, and status
in an answer comes from a tool payload, so the agent cannot invent facts by
construction. An optional LLM provider may later REPHRASE the grounded
answer; it never adds facts, never overrides statuses, and is bypassed
entirely when unavailable or slow (timeout -> deterministic fallback).

Safety rules enforced here (AGENTS.md section 6):
- factual answers come only from tool output; record IDs are always cited;
- unknown questions get an honest "insufficient evidence / needs human
  review" answer with no fabricated content;
- untrusted text (bank descriptions) is sanitized and quoted as data, so
  prompt injection inside a description cannot steer the agent — routing
  decisions use only the user's question;
- there is no write path: the agent can call tools.py functions only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.calculations import format_paise_as_rupees
from backend.database import Database
from backend.tools import (
    explain_exception,
    get_cash_position,
    get_reconciliation_summary,
    get_transaction_trace,
    list_exceptions,
    parse_bank_description,
)

#: seconds before an optional LLM rephrase is abandoned for the fallback
DEFAULT_TIMEOUT_SECONDS = 5.0

_PAYMENT_ID_IN_QUESTION = re.compile(r"\b(pay_\d+)\b", re.I)

#: record-ID tokens a grounded answer may contain; a model rephrase must
#: neither drop the cited ones nor introduce any new ones
_RECORD_ID = re.compile(r"\b(?:pay_\w+|setl_\w+|bank_\w+|UTR\w+)\b")
#: Numeric facts must survive an LLM rephrase unchanged. Commas and decimal
#: presentation may differ (1,500 == 1500), but signs and values may not.
_NUMBER_TOKEN = re.compile(r"(?<![A-Za-z_])[-+]?\d[\d,]*(?:\.\d+)?%?")
#: deterministic statuses a rephrase may quote but never invent or upgrade
_STATUS_TOKEN = re.compile(
    r"\b(FULLY_RECONCILED|MISSING_IN_SETTLEMENT|MISSING_BANK_CREDIT|"
    r"AMOUNT_MISMATCH|DUPLICATE|TIMING_DELAY|NEEDS_HUMAN_REVIEW)\b")


@dataclass(frozen=True)
class AgentAnswer:
    answer: str
    record_ids: list[str]
    tools_used: list[str]
    requires_review: bool
    fallback: bool = False  # True when the optional model was unavailable

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "record_ids": self.record_ids,
            "tools_used": self.tools_used,
            "requires_review": self.requires_review,
            "fallback": self.fallback,
        }


class AIProvider:
    """Optional rephrasing layer. The default implementation is 'none':
    deterministic answers are used as-is. A real provider wraps a
    system-prompted, tool-grounded completion and MUST raise TimeoutError
    on overrun; the agent then falls back."""

    name = "none"

    def rephrase(self, grounded_answer: str, question: str,
                 timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> str:
        return grounded_answer


def answer_question(
    batch_id: str,
    question: str,
    db: Database,
    provider: AIProvider | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> AgentAnswer:
    """Route one finance question through tools and build a grounded answer."""
    q = " ".join((question or "").split())
    lowered = q.lower()

    # ---- intent routing (uses ONLY the user question, never descriptions) --
    if "parse" in lowered and ("description" in lowered or "utr" in lowered):
        result = _answer_parse(q)
    elif re.search(r"\bhighest|largest|biggest\b", lowered) and \
            re.search(r"exception|impact|unresolved|variance|value|exposure", lowered):
        result = _answer_highest_impact(batch_id, db)
    elif re.search(r"cash|balance|forecast|pending", lowered):
        result = _answer_cash(batch_id, db)
    elif re.search(r"explain|why|detail on|what happened", lowered) and \
            _PAYMENT_ID_IN_QUESTION.search(q):
        payment_id = _PAYMENT_ID_IN_QUESTION.search(q).group(1)
        result = _answer_explain(payment_id, batch_id, db)
    elif re.search(r"trace|history of|ledger", lowered) and \
            _PAYMENT_ID_IN_QUESTION.search(q):
        payment_id = _PAYMENT_ID_IN_QUESTION.search(q).group(1)
        result = _answer_trace(payment_id, batch_id, db)
    elif re.search(r"summar|overview|how many|match rate|status", lowered):
        result = _answer_summary(batch_id, db)
    elif _PAYMENT_ID_IN_QUESTION.search(q):
        payment_id = _PAYMENT_ID_IN_QUESTION.search(q).group(1)
        result = _answer_trace(payment_id, batch_id, db)
    else:
        result = AgentAnswer(
            answer=("I can only answer from reconciliation records via my tools, "
                    "and this question maps to none of them. Evidence is "
                    "insufficient — needs human review. Try asking about the "
                    "batch summary, cash position, exceptions by exposure, a "
                    "specific payment (pay_XXX), or parsing a bank description."),
            record_ids=[], tools_used=[], requires_review=True,
        )

    # ---- optional grounded rephrase with safety validation ----------------
    provider = provider or AIProvider()
    if provider.name != "none":
        try:
            rephrased = provider.rephrase(result.answer, q, timeout_seconds)
            if not _rephrase_is_safe(rephrased, result.answer, result.record_ids):
                # the model dropped cited IDs or invented new record tokens:
                # reject its wording entirely, serve the deterministic answer
                return AgentAnswer(
                    result.answer + " (assistant model wording rejected by the "
                    "evidence guard; deterministic answer served)",
                    result.record_ids, result.tools_used,
                    result.requires_review, fallback=True)
            return AgentAnswer(rephrased, result.record_ids, result.tools_used,
                               result.requires_review, fallback=False)
        except TimeoutError:
            return AgentAnswer(
                result.answer + " (assistant model timed out; deterministic "
                "answer served)",
                result.record_ids, result.tools_used,
                result.requires_review, fallback=True)
        except Exception:
            return AgentAnswer(
                result.answer + " (assistant model unavailable; deterministic "
                "answer served)",
                result.record_ids, result.tools_used,
                result.requires_review, fallback=True)
    return result


def _rephrase_is_safe(rephrased: str, grounded: str, record_ids: list[str]) -> bool:
    """Evidence guard (AGENTS section 6): a model rephrase is acceptable only
    when it keeps every cited record ID, introduces no new record tokens,
    contains no monetary figure absent from the grounded answer, and never
    names a status the grounded answer did not contain (no invented amounts,
    no status upgrades, no invented evidence)."""
    if any(rid not in rephrased for rid in record_ids):
        return False
    if set(_RECORD_ID.findall(rephrased)) - set(_RECORD_ID.findall(grounded)):
        return False
    # Compare the complete multiset of numeric facts after normalizing only
    # presentation separators. This catches subtle changes such as 1,500 ->
    # 500, -1500 -> 1500, or 12.50 -> 12.05. Numeric IDs remain protected by
    # the record-ID checks above.
    def numeric_facts(text: str) -> list[str]:
        facts: list[str] = []
        from decimal import Decimal, InvalidOperation
        for token in _NUMBER_TOKEN.findall(text):
            percent = token.endswith("%")
            raw = token[:-1] if percent else token
            try:
                value = Decimal(raw.replace(",", ""))
            except InvalidOperation:
                continue
            facts.append(("%" if percent else "") + str(value.normalize()))
        return facts

    from collections import Counter
    if Counter(numeric_facts(rephrased)) != Counter(numeric_facts(grounded)):
        return False
    if set(_STATUS_TOKEN.findall(rephrased)) - set(_STATUS_TOKEN.findall(grounded)):
        return False
    return True


# ---------------------------------------------------------------------------
# Grounded answer builders — template-only, no invented facts
# ---------------------------------------------------------------------------

def _answer_summary(batch_id: str, db: Database) -> AgentAnswer:
    out = get_reconciliation_summary(batch_id, db)
    if not out["ok"]:
        return _tool_error(out)
    return AgentAnswer(
        answer=(
            f"Batch {batch_id} contains {out['total_records']} logical records; "
            f"{out['fully_reconciled']} are fully reconciled and "
            f"{out['exceptions']} are exceptions "
            f"(match rate {out['match_rate']:.0%}). Status counts: "
            + ", ".join(f"{k} {v}" for k, v in sorted(out["status_counts"].items()))
            + f". Total monetary variance is "
              f"{format_paise_as_rupees(out['total_variance_paise'])} INR "
              f"({out['total_variance_paise']} paise). Batch status is "
              f"{out['batch_status']} — reconciliation results are computed "
              "deterministically from the stored records."
        ),
        record_ids=[], tools_used=["get_reconciliation_summary"],
        requires_review=out["exceptions"] > 0,
    )


def _answer_highest_impact(batch_id: str, db: Database) -> AgentAnswer:
    out = list_exceptions(batch_id, db)
    if not out["ok"]:
        return _tool_error(out)
    if not out["items"]:
        return AgentAnswer(
            answer=f"No unresolved exceptions exist in batch {batch_id}.",
            record_ids=[], tools_used=["list_exceptions"], requires_review=False)
    top = out["items"][0]
    exposure = format_paise_as_rupees(top["exposure_paise"])
    return AgentAnswer(
        answer=(
            f"The highest-impact unresolved exception in batch {batch_id} is "
            f"{top['payment_id']} ({top['status']}, severity {top['severity']}) "
            f"with monetary exposure {exposure} INR "
            f"({top['exposure_paise']} paise). Engine reason: "
            f"{top['reason']}. Evidence: {', '.join(top['evidence'])}. "
            f"Recommended action: {top['recommended_action']} This record "
            "requires human review."
        ),
        record_ids=[top["payment_id"]],
        tools_used=["list_exceptions"],
        requires_review=True,
    )


def _answer_cash(batch_id: str, db: Database) -> AgentAnswer:
    out = get_cash_position(batch_id, db)
    if not out["ok"]:
        return _tool_error(out)
    p = out["position"]
    return AgentAnswer(
        answer=(
            f"Confirmed cash for batch {batch_id} is "
            f"{format_paise_as_rupees(p['actual_cash_paise'])} INR "
            f"(opening {format_paise_as_rupees(p['opening_balance_paise'])}, "
            f"confirmed credits {format_paise_as_rupees(p['confirmed_credits_paise'])}, "
            f"confirmed debits {format_paise_as_rupees(p['confirmed_debits_paise'])}). "
            f"Pending settlements add "
            f"{format_paise_as_rupees(p['pending_settlements_paise'])} INR, so "
            f"expected cash is "
            f"{format_paise_as_rupees(p['expected_cash_paise'])} INR. Unexplained "
            f"variance is {format_paise_as_rupees(p['variance_paise'])} INR "
            f"(of which bank charges are "
            f"{format_paise_as_rupees(p['bank_charges_paise'])} INR). Confidence: "
            f"{p['confidence']}. Forecast values are projections, not booked "
            "cash."
        ),
        record_ids=[],
        tools_used=["get_cash_position"],
        requires_review=p["confidence"] != "high" or p["variance_paise"] != 0,
    )


def _answer_explain(payment_id: str, batch_id: str, db: Database) -> AgentAnswer:
    out = explain_exception(payment_id, batch_id, db)
    if not out["ok"]:
        # not an exception -> fall back to the full trace view
        trace = get_transaction_trace(payment_id, batch_id, db)
        if trace["ok"]:
            return _answer_trace(payment_id, batch_id, db)
        return _tool_error(trace)
    variance = (f" Variance is {out['variance_rupees']} INR "
                f"({out['variance_paise']} paise).") if out["variance_paise"] is not None else ""
    return AgentAnswer(
        answer=(
            f"{out['payment_id']} is {out['status']} (severity "
            f"{out['severity']}). Engine reason: {out['reason']}.{variance} "
            f"Evidence: {', '.join(out['evidence'])}. Recommended action: "
            f"{out['recommended_action']} This record requires human review."
        ),
        record_ids=[out["payment_id"]],
        tools_used=["explain_exception"],
        requires_review=True,
    )


def _answer_trace(payment_id: str, batch_id: str, db: Database) -> AgentAnswer:
    out = get_transaction_trace(payment_id, batch_id, db)
    if not out["ok"]:
        return _tool_error(out)
    d = out["decision"]
    return AgentAnswer(
        answer=(
            f"Trace for {payment_id} in batch {batch_id}: ledger row "
            f"{out['ledger']['internal_id']}; "
            f"{len(out['settlements'])} settlement row(s) "
            f"({', '.join(s['source_row_id'] for s in out['settlements'])}); "
            f"bank entry {out['bank']['bank_txn_id'] if out['bank'] else 'none linked'}. "
            f"Engine decision: {d['status']} via {d['match_method']} "
            f"(confidence {d['confidence']}). Expected net "
            f"{d['expected_amount_paise']} paise, actual "
            f"{d['actual_amount_paise'] if d['actual_amount_paise'] is not None else 'n/a'} "
            f"paise, variance {d['variance_paise'] if d['variance_paise'] is not None else 'n/a'} "
            f"paise. Reason: {d['reason']}. Evidence: {', '.join(d['evidence'])}."
        ),
        record_ids=[payment_id],
        tools_used=["get_transaction_trace"],
        requires_review=d["requires_review"],
    )


def _answer_parse(question: str) -> AgentAnswer:
    quoted = re.findall(r"['\"](.*?)['\"]", question)
    if not quoted:
        return AgentAnswer(
            answer=("To parse a bank description, include it in quotes, e.g. "
                    "parse \"NEFT CR-UTR:UTR042 SETTL setl_042\". No unquoted "
                    "text is interpreted."),
            record_ids=[], tools_used=[], requires_review=False,
        )
    out = parse_bank_description(quoted[0])
    parts = []
    for key, label in (("utr_refs", "UTR references"), ("settlement_refs", "settlement references"),
                       ("payment_refs", "payment references"), ("provider_refs", "provider tokens")):
        if out[key]:
            parts.append(f"{label}: {', '.join(out[key])}")
    body = "; ".join(parts) if parts else "no known reference tokens found"
    return AgentAnswer(
        answer=f"Parsed as untrusted data — {body}.",
        record_ids=[], tools_used=["parse_bank_description"], requires_review=False,
    )


def _tool_error(out: dict) -> AgentAnswer:
    error = out["error"]
    return AgentAnswer(
        answer=(f"The tool could not answer this ({error['code']}: "
                f"{error['message']}). No facts are available to answer from — "
                "needs human review."),
        record_ids=[], tools_used=[out.get("tool", "unknown")], requires_review=True,
    )
