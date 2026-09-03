# ARCHITECTURE.md
## SettleSense AI Finance Controller

## 1. Architecture objective
SettleSense is designed to close one finance-operations loop safely:

```text
Internal payment ledger
          +
Razorpay-style settlement report
          +
Bank statement
          ↓
  Ingestion and validation
          ↓
  Canonical normalization
          ↓
Deterministic reconciliation
          ↓
Confidence and exception engine
          ↓
 Database and audit log
          ↓
 REST API and dashboard
          ↓
 Constrained AI finance assistant
```

The architecture separates financial decisions from language-model behavior. The reconciliation engine is the source of truth for matching, amounts, statuses, and cash. The AI layer explains and queries those results.

## 2. Design principles
- Deterministic before generative: exact rules make financial decisions; AI handles interpretation.
- Evidence before confidence: every match has linked source IDs and a method.
- Human review is a valid result: ambiguous records are not forcibly matched.
- Paise, not floats: all monetary calculations use integer paise.
- Append-only auditability: decisions and changes are traceable.
- Idempotency: rerunning the same batch produces the same result without duplicates.
- Adapter-based ingestion: CSV and API sources map into the same canonical model.
- Synthetic-data first: public demos never require real customer or bank data.

## 3. High-level component architecture

### 3.1 Source adapters
Adapters convert external data into internal input records.

Sources:
- Internal ledger CSV.
- Settlement report CSV.
- Bank statement CSV.
- Optional Razorpay test-mode API adapter.

Responsibilities:
- Read files or API responses.
- Preserve raw source rows.
- Attach source name and source-row identifier.
- Return structured validation errors.

The core engine must not depend directly on CSV column names or provider-specific response formats.

### 3.2 Ingestion and validation layer
This layer creates a batch and validates:

- Required columns.
- File type and size.
- Date and timestamp formats.
- Currency values.
- Positive and negative amount conventions.
- Duplicate source rows.
- Invalid identifiers.
- Formula-injection characters in exported CSV content.

Invalid rows should be reported individually. The system may support partial processing, but it must clearly show skipped rows and their reasons.

### 3.3 Canonical normalization layer
Every source is converted into a canonical model.

```python
CanonicalTransaction(
    source,
    source_row_id,
    entity_id,
    transaction_type,
    payment_id,
    order_id,
    settlement_id,
    settlement_utr,
    currency,
    gross_amount_paise,
    fee_paise,
    tax_paise,
    debit_paise,
    credit_paise,
    transaction_at,
    raw_payload
)
```

Normalization includes:
- Trimming and case normalization.
- Standardizing UTR and reference strings.
- Converting rupee values to paise.
- Converting dates to UTC internally.
- Standardizing transaction types.
- Preserving original values for audit and display.

### 3.4 Reconciliation engine
The engine links records in multiple passes.

#### Pass 1: Exact internal-to-settlement matching
Priority order:
1. Exact payment ID.
2. Exact order ID.
3. Exact provider entity ID.
4. Exact settlement ID where applicable.

#### Pass 2: Settlement-to-bank matching
Priority order:
1. Exact settlement UTR.
2. Exact bank reference extracted from the description.
3. Settlement ID in description.
4. Unique amount, currency, and date-window candidate.

#### Pass 3: Candidate scoring
When identifiers are incomplete, score candidates using:

```text
payment ID match       0.40
UTR/reference match    0.25
amount match            0.20
date proximity          0.10
currency match          0.05
```

Suggested policy:
- Score ≥ 0.95: auto-match.
- Score 0.80–0.94: auto-match only if unique and non-conflicting.
- Score 0.60–0.79: human review.
- Score < 0.60: unresolved.

Amount alone is never sufficient where multiple candidates exist.

### 3.5 Financial calculation engine
For each settlement:

```text
expected_net_paise =
    gross_amount_paise
    - fee_paise
    - tax_paise
    - refund_debit_paise
    + adjustment_credit_paise
```

The calculation engine must:
- Use integer arithmetic.
- Apply a configurable rounding tolerance.
- Preserve each component of the gross-to-net waterfall.
- Distinguish missing data from zero values.
- Record the formula inputs in the audit evidence.

### 3.6 Status and exception engine
The result classifier assigns exactly one final status per logical payment.

```text
FULLY_RECONCILED
MISSING_IN_SETTLEMENT
MISSING_BANK_CREDIT
AMOUNT_MISMATCH
DUPLICATE
TIMING_DELAY
NEEDS_HUMAN_REVIEW
```

Exception records contain:

```json
{
  "payment_id": "pay_087",
  "status": "AMOUNT_MISMATCH",
  "severity": "high",
  "confidence": 0.98,
  "expected_amount_paise": 4821200,
  "actual_amount_paise": 4791200,
  "variance_paise": -30000,
  "reason": "UTR matched, but bank credit is ₹300 lower",
  "recommended_action": "Check adjustment, reserve, or bank charge",
  "evidence": ["pay_087", "setl_087", "UTR087", "bank_087"],
  "requires_review": true
}
```

### 3.7 Metrics engine
The metrics engine operates independently from the runtime matching logic.

It calculates:
- Total logical records.
- Records processed.
- Fully reconciled records.
- Automatic matches.
- Match rate.
- Precision.
- Recall.
- Exception-capture rate.
- Total monetary variance.
- Maximum individual variance.
- Processing time.
- Records per second.

Ground-truth data is used only by evaluation commands and must never be passed into the production reconciliation endpoint.

### 3.8 Cash-position engine
The cash engine calculates:

```text
actual_cash = opening_balance + confirmed_credits - confirmed_debits

expected_cash = actual_cash + eligible_pending_settlements

cash_variance = actual_confirmed_cash - expected_confirmed_cash
```

The seven-day forecast must include:
- Forecast horizon.
- Settlement-delay assumption.
- Included transaction types.
- Excluded or uncertain records.
- Forecast confidence.

Forecast cash must never be presented as booked or confirmed cash.

### 3.9 AI context and tool layer
The AI layer is a controlled interface over backend tools.

Available tools:
- `parse_bank_description(description)`.
- `get_reconciliation_summary(batch_id, filters)`.
- `list_exceptions(batch_id, filters)`.
- `get_transaction_trace(payment_id)`.
- `get_cash_position(batch_id, date_range)`.
- `explain_exception(exception_id)`.

The model may:
- Extract UTRs from unstructured descriptions.
- Classify exceptions.
- Summarize results.
- Explain discrepancies.
- Answer questions using tool output.

The model may not:
- Invent IDs, amounts, dates, or evidence.
- Override matching thresholds.
- Change ledger, settlement, bank, or accounting records.
- Hide unresolved records.
- Treat a suggestion as a confirmed financial fact.

### 3.10 API layer
The FastAPI service exposes the backend to the dashboard and AI agent.

```text
POST /api/v1/batches
GET  /api/v1/batches/{batch_id}
POST /api/v1/batches/{batch_id}/reconcile
GET  /api/v1/batches/{batch_id}/results
GET  /api/v1/batches/{batch_id}/exceptions
GET  /api/v1/batches/{batch_id}/metrics
GET  /api/v1/batches/{batch_id}/cash-position
GET  /api/v1/transactions/{payment_id}/trace
GET  /api/v1/batches/{batch_id}/export
POST /api/v1/ai/query
POST /api/v1/ai/parse-description
```

All response models should be versioned and validated with Pydantic.

## 4. Deployment architecture

### Local development
```text
React/Vite frontend
        ↓
FastAPI backend
        ↓
SQLite database
        ↓
Local synthetic CSV fixtures
```

### Demo deployment
```text
Browser
  ↓ HTTPS
Hosted frontend
  ↓ HTTPS/API token
Hosted FastAPI service
  ↓
Managed PostgreSQL or SQLite volume
  ↓
Synthetic dataset storage
```

The AI provider key remains only in the backend environment. The browser never receives provider credentials.

## 5. Database relationships

```text
batches 1 ──── many transactions
batches 1 ──── many bank_entries
batches 1 ──── many reconciliation_results
reconciliation_results many ─── 1 transactions
reconciliation_results many ─── 0..1 bank_entries
batches 1 ──── many audit_events
```

The settlement report may contain several transaction types for the same settlement. Store them as separate transactions and aggregate them only in the financial calculation layer.

## 6. Processing sequence

```text
1. Create batch ID.
2. Calculate source hashes.
3. Validate input files.
4. Store raw source references.
5. Normalize rows into canonical records.
6. Detect duplicates.
7. Match internal records to settlement records.
8. Match settlement records to bank entries.
9. Calculate expected net and variance.
10. Assign status and confidence.
11. Persist reconciliation results.
12. Persist audit events.
13. Calculate metrics and cash position.
14. Return results to dashboard and AI tools.
```

## 7. Failure handling
- Invalid file: reject batch creation with row-level errors.
- Invalid row: quarantine the row and continue only if partial processing is enabled.
- Missing source: return an incomplete-batch status rather than claiming reconciliation.
- Database failure: do not expose partial success without a batch status.
- AI timeout: show deterministic reconciliation results and a clear assistant-unavailable message.
- Ambiguous match: persist `NEEDS_HUMAN_REVIEW`.
- Duplicate batch: return the existing batch result when the source hash is unchanged.

## 8. Observability
Log:
- Batch ID.
- Source name and row count.
- Processing duration.
- Number of matches and exceptions.
- Error class and safe error message.
- AI tool name and latency.

Do not log:
- API keys.
- Full bank descriptions where they contain sensitive data.
- Customer personal data.
- Full payment credentials.

Useful dashboards:
- Batch success rate.
- Average processing latency.
- Match-rate trend.
- False-match count from benchmark runs.
- Exception monetary exposure.
- AI tool error rate.

## 9. Architecture decisions
### Why deterministic matching first?
Financial matching must be explainable and repeatable. Rules allow exact evidence, predictable thresholds, and reliable testing.

### Why use AI?
Bank descriptions and exception explanations contain unstructured language. AI improves extraction and usability without becoming the source of financial truth.

### Why use synthetic data?
The buildathon can demonstrate throughput and accuracy without exposing real merchant or banking information.

### Why preserve exceptions?
A system that reports uncertainty is safer and more useful than one that claims a high match rate by making unsupported guesses.

## 10. Future extensions
- Live Razorpay test-mode synchronization.
- Multiple payment providers through adapters.
- Accounting-system export after human approval.
- Scheduled daily reconciliation.
- Role-based access control.
- Merchant-specific fee rules.
- Multi-currency support with explicit FX rates.
- Approval workflows for material exceptions.
