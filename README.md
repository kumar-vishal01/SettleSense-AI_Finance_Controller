# SettleSense -- AI Finance Controller

## AI Finance Control Center for Payment Reconciliation

> Every payment accounted for.

SettleSense is an AI-powered finance-operations system that reconciles internal payment records, Razorpay-style settlement reports, and bank statement entries. It processes a complete batch of financial records, automatically resolves high-confidence matches, calculates cash position, measures reconciliation accuracy, and escalates uncertain cases with evidence-backed explanations.

**Built for the Razorpay AI Buildathon 2026 — Track 04: AI Finance Controller**

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)]()
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## Table of Contents

- [Problem](#problem)
- [Solution](#solution)
- [Live Demo](#live-demo)
- [Screenshots](#screenshots)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Data](#data)
- [API Reference](#api-reference)
- [Evaluation](#evaluation)
- [Project Structure](#project-structure)
- [Security](#security)
- [Limitations](#limitations)
- [Future Work](#future-work)
- [Team](#team)
- [License](#license)

---

## Problem

Finance teams reconcile payment data manually using spreadsheets, which creates several challenges:

- **Time-consuming**: Matching hundreds of transactions across multiple systems requires hours of manual work.
- **Error-prone**: Manual matching increases the risk of missed discrepancies and incorrect cash positions.
- **Unclear exceptions**: When payments don't match, understanding the root cause requires cross-referencing multiple sources.
- **Missing visibility**: Teams often don't know which cash has actually arrived versus what is still pending.
- **Scaling issues**: Manual processes break down as transaction volume increases.

---

## Solution

SettleSense automates the three-way reconciliation workflow:

```text
Internal Payment Ledger
         ↓
Settlement Report (Razorpay-style)
         ↓
Bank Statement
         ↓
Reconciliation + Cash Position + Exceptions
```

The system:

1. **Ingests** three data sources (internal ledger, settlement report, bank statement).
2. **Validates** and normalizes the data into a canonical format.
3. **Matches** records using deterministic rules (payment ID, order ID, UTR, amount, date).
4. **Calculates** expected net settlement (gross − fee − tax − refund + adjustment).
5. **Compares** expected settlement with actual bank credit.
6. **Measures** reconciliation accuracy (match rate, precision, recall, exception capture).
7. **Shows** cash position (actual, expected, pending, variance).
8. **Creates** an exception queue with evidence and recommended actions.
9. **Uses AI** to explain discrepancies and answer finance questions.
10. **Escalates** ambiguous records for human review instead of guessing.

---

## Live Demo

🔗 **[View Live Demo](https://your-demo-url.com)**

**Demo credentials** (if applicable):
- Username: `demo@clearledger.io`
- Password: `demo123`

> The demo uses synthetic financial data only. No real customer or bank information is processed.

---

## Screenshots

### Dashboard Overview

![Dashboard Overview](./docs/screenshots/overview.png)
*Executive view showing match rate, cash position, and priority exceptions*

### Exception Queue

![Exception Queue](./docs/screenshots/exceptions.png)
*Actionable exception list with severity, amount, and recommended actions*

### Transaction Trace

![Transaction Trace](./docs/screenshots/trace.png)
*Complete evidence trail across internal, settlement, and bank records*

### AI Assistant

![AI Assistant](./docs/screenshots/ai-assistant.png)
*Evidence-backed answers to finance questions*

---

## Features

### Core Reconciliation

- ✅ Three-way matching (internal → settlement → bank)
- ✅ Deterministic financial rules (no AI guessing)
- ✅ Expected net settlement calculation
- ✅ Amount tolerance configuration
- ✅ Duplicate detection
- ✅ Timing-delay handling
- ✅ Refund and adjustment support
- ✅ UTR extraction and matching

### Exception Management

- ✅ 7 reconciliation statuses
- ✅ Priority scoring (monetary impact, age, risk)
- ✅ Evidence-backed exception details
- ✅ Gross-to-net waterfall breakdown
- ✅ Recommended next actions
- ✅ Human review workflow
- ✅ Immutable audit trail

### Cash Position

- ✅ Actual cash (confirmed bank credits)
- ✅ Expected cash (pending settlements)
- ✅ Cash variance calculation
- ✅ 7-day forecast with assumptions
- ✅ Separate confirmed vs forecast visualization

### AI Assistant

- ✅ UTR extraction from bank descriptions
- ✅ Exception classification
- ✅ Discrepancy explanations
- ✅ Natural-language finance Q&A
- ✅ Evidence-backed answers with record IDs
- ✅ "Needs human review" warnings
- ✅ Prompt-injection resistance

### Dashboard

- ✅ Overview with match rate, exceptions, cash variance
- ✅ Reconciliation health chart
- ✅ Cash movement visualization
- ✅ Priority exception panel
- ✅ Searchable reconciliation table
- ✅ Filterable exception queue
- ✅ Transaction trace timeline
- ✅ Batch upload and validation
- ✅ Data source quality status

### Developer Experience

- ✅ RESTful API
- ✅ OpenAPI documentation
- ✅ Synthetic dataset generator
- ✅ Benchmark evaluation script
- ✅ Comprehensive test suite
- ✅ Docker support
- ✅ Type-safe Python backend
- ✅ Responsive React frontend

---

## Tech Stack

### Backend

- **Python 3.12** — Core language
- **FastAPI** — REST API framework
- **Pydantic** — Data validation and schemas
- **SQLAlchemy** — Database ORM
- **SQLite** — MVP database (PostgreSQL-ready schema)
- **Pandas** — Batch data processing
- **Pytest** — Testing framework

### Frontend

- **React 18** — UI framework
- **TypeScript** — Type safety
- **Vite** — Build tool
- **Tailwind CSS** — Styling
- **Recharts** — Charts and visualizations
- **TanStack Query** — API data fetching
- **React Router** — Navigation
- **Framer Motion** — Animations
- **Lucide Icons** — Icon library

### AI Layer

- **Claude API** (or compatible LLM)
- Structured JSON output
- Tool/function calling
- Server-side only (no client-side secrets)

### DevOps

- **Docker** — Containerization
- **Docker Compose** — Local development
- **GitHub Actions** — CI/CD
- **ESLint + Prettier** — Code quality
- **Ruff** — Python linting

---

## Architecture

┌─────────────────────────────────────────────────────────────┐
│ Frontend (React) │
│ Overview | Reconciliation | Exceptions | Cash | AI | Upload │
└─────────────────────────────────────────────────────────────┘
↓ HTTPS
┌─────────────────────────────────────────────────────────────┐
│ Backend (FastAPI + Python) │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐ │
│ │ Ingestion │ │Validation │ │Normalization│ │ Matching │ │
│ └────────────┘ └────────────┘ └────────────┘ └───────────┘ │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐ │
│ │Reconciliation│ │Exceptions │ │ Metrics │ │ Cash │ │
│ └────────────┘ └────────────┘ └────────────┘ └───────────┘ │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐ │
│ │ Database │ │ Audit │ │ Tools │ │ AI Agent │ │
│ └────────────┘ └────────────┘ └────────────┘ └───────────┘ │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ Data Sources (CSV/API) │
│ Internal Ledger | Settlement Report | Bank Statement │
└─────────────────────────────────────────────────────────────┘



### Key Design Decisions

1. **Deterministic first, AI second**: Financial matching uses rules, not LLMs.
2. **Integer paise**: All money calculations use paise to avoid floating-point errors.
3. **Evidence over confidence**: Every match includes source IDs and method.
4. **Human review is valid**: Ambiguous records are escalated, not forced.
5. **Idempotent processing**: Rerunning the same batch produces the same result.
6. **Synthetic data only**: Public demo uses generated data, not real financial records.

---

## Installation

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (optional)

### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/yourusername/clearledger.git
cd clearledger

# Start all services
docker-compose up --build

# Access the application
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Manual Installation

#### Backend

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Run database migrations
python -m scripts.migrate

# Start the server
uvicorn main:app --reload
```

#### Frontend

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env.local

# Start development server
npm run dev
```

---

## Usage

### 1. Generate Synthetic Data

```bash
python scripts/generate_data.py
```

This creates:

- `data/internal_ledger.csv` — 100 payment records
- `data/settlements.csv` — 95 settlement records
- `data/bank_statement.csv` — 89 bank entries
- `data/ground_truth.csv` — Evaluation labels

### 2. Upload Data

Open the dashboard and navigate to **Batch Upload**.

Upload the three CSV files:

1. `internal_ledger.csv`
2. `settlements.csv`
3. `bank_statement.csv`

### 3. Run Reconciliation

Click **Run Reconciliation**.

The system will:

- Validate all files.
- Normalize records.
- Match payments to settlements.
- Match settlements to bank credits.
- Calculate expected net amounts.
- Assign reconciliation statuses.
- Generate exceptions.
- Calculate metrics and cash position.

### 4. Review Results

Navigate to:

- **Overview** — Summary metrics and priority exceptions.
- **Reconciliation** — Full table with search and filters.
- **Exceptions** — Actionable queue with evidence.
- **Cash Position** — Actual, expected, and forecast cash.
- **Transaction Trace** — Evidence trail for individual payments.
- **AI Assistant** — Ask questions about the batch.

### 5. Export Report

Click **Export Report** to download reconciliation results as CSV.

---

## Data

### Synthetic Dataset

SettleSense uses a deliberately imperfect synthetic dataset containing 100 logical payment records:

| Scenario | Count |
|----------|-------|
| Clean matches | 60 |
| Delayed bank credits | 10 |
| Missing UTR | 8 |
| Amount mismatches | 6 |
| Missing settlements | 5 |
| Missing bank credits | 4 |
| Duplicates | 3 |
| Refunds | 2 |
| Adjustments | 1 |
| Ambiguous match | 1 |

### Ground Truth

A separate `ground_truth.csv` file contains the expected outcome for each payment. This is used **only for evaluation** and never during runtime reconciliation.

### Data Privacy

- ✅ Uses synthetic data only.
- ✅ No real customer financial information.
- ✅ No real bank statements.
- ✅ No payment credentials.
- ✅ No secrets in code or repository.

---

## API Reference

### Health Check

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### Create Batch

```http
POST /api/v1/batches
```

Request: Multipart form with `internal_ledger`, `settlements`, `bank_statement`.

Response:

```json
{
  "batch_id": "batch_001",
  "status": "VALIDATED",
  "internal_rows": 100,
  "settlement_rows": 95,
  "bank_rows": 89,
  "validation_errors": []
}
```

### Run Reconciliation

```http
POST /api/v1/batches/{batch_id}/reconcile
```

Response:

```json
{
  "batch_id": "batch_001",
  "status": "COMPLETED",
  "records_processed": 100,
  "processing_time_ms": 842
}
```

### Get Results

```http
GET /api/v1/batches/{batch_id}/results
```

### Get Exceptions

```http
GET /api/v1/batches/{batch_id}/exceptions
```

### Get Metrics

```http
GET /api/v1/batches/{batch_id}/metrics
```

### Get Cash Position

```http
GET /api/v1/batches/{batch_id}/cash-position
```

### Get Transaction Trace

```http
GET /api/v1/transactions/{payment_id}/trace
```

### Ask AI

```http
POST /api/v1/ai/query
```

Request:

```json
{
  "batch_id": "batch_001",
  "question": "Which unresolved exception has the highest monetary impact?"
}
```

Response:

```json
{
  "answer": "Payment pay_087 has the highest unresolved impact at ₹300...",
  "record_ids": ["pay_087", "setl_087", "bank_087"],
  "tools_used": ["list_exceptions", "get_transaction_trace"],
  "requires_review": true
}
```

**Full API documentation**: http://localhost:8000/docs

---

## Evaluation

### Metrics

SettleSense reports the following metrics:

| Metric | Formula | Purpose |
|--------|---------|---------|
| Match Rate | Correct matches / Total records | Overall accuracy |
| Precision | Correct auto-matches / All auto-matches | Auto-match reliability |
| Recall | Correct auto-matches / True matches | Match coverage |
| Exception Capture | Correct exceptions / Actual exceptions | Exception detection |
| Monetary Variance | Σ\|Expected − Actual\| | Financial impact |
| Throughput | Records / Seconds | Processing speed |

### Benchmark Results

```json
{
  "total_records": 100,
  "records_processed": 100,
  "fully_reconciled": 61,
  "automatic_matches": 78,
  "correct_automatic_matches": 76,
  "match_rate": 0.82,
  "precision": 0.974,
  "recall": 0.89,
  "exception_capture_rate": 0.90,
  "total_monetary_variance_paise": 482000,
  "processing_time_ms": 842,
  "records_per_second": 118.76,
  "false_automatic_matches": [],
  "unresolved_high_value_cases": []
}
```

### Run Evaluation

```bash
python scripts/run_benchmark.py
```

Output:

- `evaluation/report.json` — Machine-readable metrics.
- `evaluation/report.md` — Human-readable summary.

---

## Project Structure

