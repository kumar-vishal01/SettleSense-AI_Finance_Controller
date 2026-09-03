# Technical Design Document
## SettleSense AI Finance Controller

## 1. Architecture
```text
CSV/API adapters
      ↓
File validation and ingestion
      ↓
Canonical normalization layer
      ↓
Deterministic reconciliation engine
      ↓
Confidence, exception, and cash engine
      ↓
Database and audit log
      ↓
REST API → Web dashboard
      ↓
AI tool/Q&A layer
```

The AI layer is downstream of the reconciliation engine. It explains and queries structured results; it is not the authority for monetary matching.

## 2. Chosen tech stack
| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Fast implementation and clear API contracts |
| Validation | Pydantic | Typed request and response schemas |
| Batch processing | Pandas initially; Polars optional | Simple CSV processing for 50–1,000 records |
| Database | SQLite for MVP; PostgreSQL-ready schema | Zero setup locally and easy deployment path |
| Frontend | React + Vite + Tailwind CSS | Fast dashboard development |
| Charts | Recharts | Summary metrics and cash visualization |
| AI | LLM with JSON schema and tool calling | Controlled explanations and Q&A |
| Testing | Pytest | Unit, integration, and benchmark tests |
| Packaging | Docker + Docker Compose | Reproducible local setup |
| CI | GitHub Actions | Automated tests and linting |

## 3. Repository layout
```text
settlesense/
├── README.md
├── AGENTS.md
├── PRD.md
├── TECHNICAL_DESIGN.md
├── TESTING.md
├── .env.example
├── docker-compose.yml
├── requirements.txt
├── data/
│   ├── internal_ledger.csv
│   ├── settlements.csv
│   ├── bank_statement.csv
│   └── ground_truth.csv
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── ingestion.py
│   ├── normalization.py
│   ├── matching.py
│   ├── reconciliation.py
│   ├── exceptions.py
│   ├── cash_forecast.py
│   ├── metrics.py
│   ├── tools.py
│   └── ai_agent.py
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   └── types/
│   └── package.json
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
└── scripts/
    ├── generate_data.py
    └── run_benchmark.py
```

## 4. Database layout
### `batches`
- `id` primary key
- `source_hash`
- `status`
- `record_count`
- `started_at`
- `completed_at`

### `transactions`
- `id` primary key
- `batch_id` foreign key
- `source`
- `source_row_id`
- `entity_id`
- `transaction_type`
- `payment_id`
- `order_id`
- `settlement_id`
- `settlement_utr`
- `currency`
- `gross_amount_paise`
- `fee_paise`
- `tax_paise`
- `debit_paise`
- `credit_paise`
- `transaction_at`
- `raw_payload_json`

### `bank_entries`
- `id` primary key
- `batch_id` foreign key
- `bank_txn_id`
- `value_date`
- `description`
- `utr`
- `credit_paise`
- `debit_paise`
- `raw_payload_json`

### `reconciliation_results`
- `id` primary key
- `batch_id` foreign key
- `payment_id`
- `settlement_transaction_id`
- `bank_entry_id`
- `status`
- `confidence`
- `match_method`
- `expected_amount_paise`
- `actual_amount_paise`
- `variance_paise`
- `severity`
- `reason`
- `requires_review`
- `created_at`

### `audit_events`
- `id` primary key
- `batch_id`
- `record_id`
- `action`
- `actor`
- `details_json`
- `created_at`

## 5. API endpoints
### Health and configuration
`GET /health` — service health and version.

`GET /api/v1/config` — non-secret runtime configuration such as tolerances and supported file types.

### Batch ingestion
`POST /api/v1/batches` — create a batch from three uploaded files.

Request: multipart form with `internal_ledger`, `settlements`, `bank_statement`.

Response: `batch_id`, validation status, row counts, and errors.

`GET /api/v1/batches/{batch_id}` — batch status, counts, timestamps, and validation summary.

`POST /api/v1/batches/{batch_id}/reconcile` — run the reconciliation engine idempotently.

`GET /api/v1/batches/{batch_id}/results` — paginated reconciliation results with filters.

`GET /api/v1/batches/{batch_id}/exceptions` — paginated exception queue.

`GET /api/v1/batches/{batch_id}/metrics` — match rate, precision where ground truth is enabled, recall, variance, and throughput.

`GET /api/v1/batches/{batch_id}/cash-position` — actual cash, expected cash, pending settlements, variance, and forecast.

`GET /api/v1/transactions/{payment_id}/trace` — internal record, linked settlement, bank entry, decision, and audit evidence.

`GET /api/v1/batches/{batch_id}/export?format=csv` — export results or exceptions.

### AI endpoints
`POST /api/v1/ai/query` — natural-language question over a selected batch.

Request:
```json
{"batch_id":"batch_001","question":"Which exception has the highest monetary impact?"}
```

Response:
```json
{"answer":"...","record_ids":["pay_087"],"tools_used":["list_exceptions","get_cash_position"]}
```

`POST /api/v1/ai/parse-description` — extract provider and UTR from a bank description.

## 6. Matching algorithm
1. Normalize all sources into canonical models.
2. Match exact `payment_id`.
3. Match exact `order_id` where payment ID is unavailable.
4. Match settlement to bank using exact UTR.
5. Use settlement ID, amount, currency, and date window as secondary evidence.
6. Produce candidate scores.
7. Auto-match only when the candidate is unique and above threshold.
8. Calculate expected net in paise.
9. Compare bank credit with expected net and classify status.
10. Write result and audit event.

Suggested thresholds:
- `>= 0.95`: automatic match.
- `0.80–0.94`: automatic only if unique and no conflicting evidence.
- `0.60–0.79`: human review.
- `< 0.60`: unresolved.

## 7. Security design
- API keys only in server environment variables.
- No production credentials in the repository or browser.
- Synthetic data in all public demos.
- File-size, file-type, row-count, and CSV formula-injection checks.
- Parameterized database queries.
- Rate limits on AI endpoints.
- PII redaction in logs.
- No AI-initiated financial writes.
- Audit records are append-only.
