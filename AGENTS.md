# AGENTS.md
## AI Context File

## 1. Project identity
SettleSense AI Finance Controller is a finance-operations application that reconciles internal payment records, Razorpay-style settlement records, and bank statement entries. The project is evaluated on batch throughput, measured accuracy, and honest exceptions.

## 2. Folder patterns
```text
backend/     API, services, data models, reconciliation logic, and AI tools
frontend/    React dashboard and API client
data/       synthetic inputs and evaluation fixtures
tests/       unit, integration, contract, and benchmark tests
scripts/     dataset generation and benchmark commands
docs/        optional diagrams and decisions
```

Keep responsibilities separated:
- `ingestion.py`: read and validate external files.
- `normalization.py`: convert source-specific rows into canonical models.
- `matching.py`: candidate generation and scoring only.
- `reconciliation.py`: financial status decisions and formulas.
- `metrics.py`: benchmark calculations only.
- `tools.py`: safe structured functions exposed to the AI.
- `ai_agent.py`: explanations and question routing; no financial authority.

## 3. Coding rules
- Use Python type hints and Pydantic models at API boundaries.
- Use integer paise for all money calculations.
- Never compare money using floating-point values.
- Keep functions small and deterministic.
- Prefer explicit names over clever abstractions.
- Add tests before changing matching behavior.
- Preserve raw input values alongside normalized values.
- Make all batch operations idempotent.
- Use UTC internally and display the configured local timezone in the UI.
- Return structured errors; do not swallow exceptions.
- Do not put secrets, credentials, or real financial data in code, logs, fixtures, or screenshots.

## 4. Matching rules
- Exact payment ID is stronger than amount similarity.
- Exact UTR is strong evidence for settlement-to-bank matching.
- Amount alone is never sufficient when duplicate amounts exist.
- Date differences must be evaluated against a configured window.
- If multiple candidates are plausible, return `NEEDS_HUMAN_REVIEW`.
- Never lower thresholds merely to improve the displayed match rate.

## 5. Status rules
- `FULLY_RECONCILED`: all required records and amounts agree.
- `MISSING_IN_SETTLEMENT`: internal payment lacks an eligible settlement.
- `MISSING_BANK_CREDIT`: settlement exists but bank credit is absent.
- `AMOUNT_MISMATCH`: linked amount differs beyond tolerance.
- `DUPLICATE`: source uniqueness is violated.
- `TIMING_DELAY`: credit is plausibly delayed.
- `NEEDS_HUMAN_REVIEW`: ambiguity or conflicting evidence.

## 6. AI rules
- The LLM may parse text, classify exceptions, explain results, and answer queries.
- The LLM must use backend tools for facts.
- The LLM must never invent IDs, amounts, dates, or causes.
- The LLM must state when information is unavailable.
- The LLM must not mutate ledger, settlement, bank, or accounting data.
- Always return evidence IDs with finance answers.

## 7. Required result contract
```json
{
  "payment_id":"pay_001",
  "status":"FULLY_RECONCILED",
  "confidence":0.99,
  "match_method":"payment_id + UTR + amount",
  "expected_amount_paise":97876,
  "actual_amount_paise":97876,
  "variance_paise":0,
  "reason":"All linked records agree",
  "evidence":["pay_001","setl_001","bank_001"],
  "requires_review":false
}
```

## 8. Definition of done
Every feature includes tests, documentation, structured errors, audit behavior, and no hidden mutation. Benchmark claims must be reproducible from a versioned synthetic dataset.
