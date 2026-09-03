# Product Requirements Document
## SettleSense AI Finance Controller

## 1. Product summary
SettleSense is an AI-assisted finance-operations system that reconciles an internal payment ledger, Razorpay-style settlement records, and bank statement entries. It processes a batch of 50+ synthetic records, matches high-confidence records, calculates expected versus actual cash, and reports unresolved exceptions with evidence.

## 2. Main goals
- Close one complete finance-operations loop: payment → settlement → bank credit → reconciliation result.
- Process at least 50 records in a single batch; target 100 records for the benchmark.
- Maximize correct automatic matches without creating unsafe false positives.
- Report match rate, precision, recall, exception-capture rate, monetary variance, and throughput.
- Give every unresolved record a status, reason, severity, evidence, and recommended next action.
- Provide a cash-position view covering actual cash, expected cash, pending settlements, and variance.
- Enable natural-language finance questions using structured reconciliation tools.
- Keep the system auditable, deterministic for money decisions, and safe for human review.

## 3. Target users
### Finance operations analyst
Uploads files, runs reconciliation, investigates exceptions, and verifies settlement details.

### Finance controller or manager
Monitors cash position, monetary exposure, reconciliation quality, and unresolved cases.

### Merchant operations user
Checks whether customer payments, refunds, and adjustments have reached the expected financial state.

### Developer or data operator
Maintains adapters, validates schemas, runs benchmark tests, and reviews system logs.

## 4. Core user journeys
1. User uploads internal ledger, settlement report, and bank statement.
2. System validates the files and displays invalid rows before processing.
3. User runs a reconciliation batch.
4. System normalizes data and applies deterministic matching rules.
5. System calculates expected net settlement and compares it with bank cash.
6. User reviews summary metrics and filters the exception queue.
7. User opens an exception to see linked records, variance, confidence, evidence, and recommended action.
8. User asks a question such as “Which unresolved case has the highest monetary impact?”
9. User exports reconciliation results and exceptions.

## 5. Core features
### 5.1 Data ingestion
- Upload three CSV files: internal ledger, settlement report, and bank statement.
- Optional Razorpay test-mode/API adapter behind a server-side credential boundary.
- Support batch IDs and idempotent reruns.

### 5.2 Schema validation
- Check required columns, data types, date formats, currency, sign conventions, and duplicate source rows.
- Return row-level validation errors.
- Reject unsafe or oversized files.

### 5.3 Data normalization
- Normalize whitespace, casing, identifiers, dates, descriptions, and UTR formats.
- Convert all monetary amounts to integer paise.
- Preserve original values for audit display.

### 5.4 Reconciliation engine
- Match by payment ID, order ID, settlement ID, and UTR.
- Use amount and date-window matching only when identifiers are incomplete.
- Prevent auto-matching when candidates are ambiguous.
- Support payment, refund, transfer, and adjustment transaction types.

### 5.5 Gross-to-net calculation
`Expected net = gross − fee − tax − refund debit + adjustment credit`.

### 5.6 Status and exception management
Statuses:
- `FULLY_RECONCILED`
- `MISSING_IN_SETTLEMENT`
- `MISSING_BANK_CREDIT`
- `AMOUNT_MISMATCH`
- `DUPLICATE`
- `TIMING_DELAY`
- `NEEDS_HUMAN_REVIEW`

Every exception includes severity, confidence, variance, evidence, reason, and next action.

### 5.7 Metrics and evaluation
- Total records and processing time.
- Correct match rate.
- Automatic-match precision and recall.
- Exception-capture rate.
- Total and maximum monetary variance.
- Unresolved exception count.
- Records processed per second.

### 5.8 Cash position
- Opening balance.
- Confirmed bank credits and debits.
- Expected settlement inflows.
- Pending settlements.
- Actual versus expected cash.
- Unexplained variance.
- Seven-day forecast with assumptions and confidence.

### 5.9 AI finance assistant
- Parse UTR and provider references from bank descriptions.
- Classify exception types.
- Explain discrepancies using only structured records.
- Answer finance questions through backend tools.
- Refuse to guess when evidence is missing or conflicting.

### 5.10 Export and audit
- Export results and exceptions as CSV or JSON.
- Preserve input source references and matching method.
- Store immutable audit events for every decision.

## 6. Inputs and outputs
### Inputs
#### Internal ledger
`internal_id`, `order_id`, `payment_id`, `created_at`, `amount_paise`, `currency`, `payment_status`.

#### Settlement report
`entity_id`, `type`, `payment_id`, `order_id`, `settlement_id`, `settlement_utr`, `amount_paise`, `fee_paise`, `tax_paise`, `debit_paise`, `credit_paise`, `settled_at`.

#### Bank statement
`bank_txn_id`, `value_date`, `description`, `utr`, `credit_paise`, `debit_paise`.

#### Configuration
`date_window_days`, `amount_tolerance_paise`, `auto_match_threshold`, `currency`, and `forecast_horizon_days`.

### Final output
```json
{
  "batch_id": "batch_2026_08_22_001",
  "summary": {
    "total_records": 100,
    "fully_reconciled": 82,
    "exceptions": 18,
    "match_rate": 0.82,
    "precision": 0.975,
    "recall": 0.89,
    "monetary_variance_paise": 482000,
    "processing_time_ms": 842
  },
  "results": [
    {
      "payment_id": "pay_001",
      "status": "FULLY_RECONCILED",
      "confidence": 0.99,
      "settlement_id": "setl_001",
      "bank_txn_id": "bank_001",
      "expected_amount_paise": 97876,
      "actual_amount_paise": 97876,
      "variance_paise": 0,
      "match_method": "payment_id + UTR + amount",
      "evidence": ["pay_001", "setl_001", "UTR001", "bank_001"],
      "requires_review": false
    }
  ],
  "exceptions": []
}
```

## 7. Data sources and quality status
| Source | Use | Quality status |
|---|---|---|
| Synthetic internal ledger | Merchant payment truth for the benchmark | Controlled; generated with ground truth |
| Synthetic settlement report | Provider-side payments, refunds, fees, taxes, and adjustments | Controlled; deliberately noisy |
| Synthetic bank statement | Actual-cash simulation | Controlled; includes missing UTRs, delays, duplicates, and mismatches |
| Ground-truth labels | Evaluation only; never runtime input | High quality and maintained separately |
| Razorpay public API documentation | Field and endpoint context | Official reference; version/date should be recorded |
| Optional Razorpay test-mode API | Integration demonstration | Environment-dependent; never required for core demo |

## 8. Constraints and security
- Buildathon MVP timeline: prioritize one complete reconciliation loop over broad accounting features.
- Budget: use local SQLite and synthetic CSVs by default; keep paid API usage optional and capped.
- Scale: optimize initially for 50–1,000 records per batch.
- Privacy: do not use real customer, bank, card, or production payment data.
- Secrets: keep API keys server-side in environment variables; never commit `.env` files.
- Financial safety: no automatic ledger mutation, refunds, payouts, or journal posting.
- AI safety: the model cannot invent values, silently resolve ambiguity, or write financial records.
- Upload security: limit file size, validate MIME/type, sanitize filenames, and reject malformed content.
- Auditability: store source IDs, match methods, confidence, timestamps, and reasons.
- Reliability: rerunning the same batch must not duplicate results.

## 9. Success criteria
A successful MVP processes 100 synthetic records, displays reproducible metrics, correctly identifies known exceptions, produces no false auto-match on the ambiguous fixture, and demonstrates an evidence-backed Q&A flow.
