# SettleSense — AI Finance Controller

### Close the finance-ops loop from payment → settlement → bank → cash position → exception

> **Every payment accounted for. Every exception explained. Nothing guessed.**

[![Razorpay AI Buildathon 2026](https://img.shields.io/badge/Razorpay%20AI%20Buildathon-2026-blue)](#)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](#)
[![React](https://img.shields.io/badge/React-TypeScript-blue)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)](#)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](#)

## Razorpay AI Buildathon — Track 04: AI Finance Controller

SettleSense is an AI-assisted finance operations platform designed around one complete finance-ops loop:

```text
Internal Payment Ledger
        +
Settlement Report
        +
Bank Statement
        ↓
Validation & Normalization
        ↓
Deterministic Reconciliation
        ↓
Financial Calculation
        ↓
Match / Exception Decision
        ↓
Cash Position & Forecast
        ↓
Evidence-backed AI Assistant
        ↓
Human Review where required
```

The system processes a complete batch of synthetic payment records, reconciles them across multiple financial sources, calculates expected versus actual settlement amounts, measures its own performance, identifies unresolved exceptions, and exposes the evidence behind every decision.

---

# Table of Contents

* [The Problem](#the-problem)
* [The Buildathon Requirement](#the-buildathon-requirement)
* [Our Solution](#our-solution)
* [Why SettleSense](#why-settlesense)
* [Key Results](#key-results)
* [How It Works](#how-it-works)
* [Reconciliation Pipeline](#reconciliation-pipeline)
* [Matching Strategy](#matching-strategy)
* [Financial Calculation](#financial-calculation)
* [Exception Handling](#exception-handling)
* [Cash Position](#cash-position)
* [AI Finance Assistant](#ai-finance-assistant)
* [Evaluation & Benchmark](#evaluation--benchmark)
* [Synthetic Dataset](#synthetic-dataset)
* [Architecture](#architecture)
* [Tech Stack](#tech-stack)
* [Project Structure](#project-structure)
* [Running Locally](#running-locally)
* [Docker](#docker)
* [API](#api)
* [Testing](#testing)
* [Security & Reliability](#security--reliability)
* [Design Principles](#design-principles)
* [Limitations](#limitations)
* [Future Work](#future-work)
* [Documentation](#documentation)
* [License](#license)

---

# The Problem

Finance operations teams often need to reconcile information that lives in different systems:

* Internal payment/order records
* Payment-provider settlement reports
* Bank statements

A typical reconciliation process involves manually comparing identifiers, amounts, dates, settlement deductions, bank references, refunds, adjustments and missing records.

This creates four major problems:

### 1. Manual reconciliation is slow

Large batches require finance teams to compare hundreds or thousands of records across multiple sources.

### 2. Incorrect matches are dangerous

A finance system should never confidently match the wrong transaction simply because two amounts happen to be equal.

### 3. Exceptions are not enough — they need explanations

A useful finance-ops system must explain:

* What did not match?
* Which records were compared?
* What amount was expected?
* What amount actually arrived?
* Why was the record classified as an exception?
* What should happen next?

### 4. Finance teams need cash visibility

Knowing that a payment exists is not the same as knowing whether the money has actually reached the bank.

SettleSense therefore separates:

```text
Confirmed Cash
      +
Expected Cash
      +
Pending Settlements
      +
Variance
      ↓
Cash Position
```

---

# The Buildathon Requirement

The challenge asks builders to:

> **Run the books and the cash position.**

The system should close one finance-operations loop across a batch of synthetic records while reporting:

* Throughput
* Measured accuracy
* Exceptions that could not be resolved

SettleSense addresses this directly through a three-source reconciliation workflow.

| Buildathon Requirement      | SettleSense                                |
| --------------------------- | ------------------------------------------ |
| 50+ record batch            | 100 logical payment records                |
| Multi-source reconciliation | Internal ledger + settlement + bank        |
| Throughput                  | Records/second benchmark                   |
| Measured accuracy           | Precision, recall, match rate              |
| Honest exceptions           | Explicit exception statuses + human review |
| Financial visibility        | Actual/expected cash + variance            |
| AI                          | Evidence-backed finance Q&A                |
| Auditability                | Source IDs, evidence and audit events      |

---

# Our Solution

SettleSense closes the following finance-ops loop:

```text
             ┌─────────────────────┐
             │ Internal Ledger     │
             └──────────┬──────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ Settlement Report   │
             └──────────┬──────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ Bank Statement      │
             └──────────┬──────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ Validation          │
             │ Normalization       │
             └──────────┬──────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ Reconciliation      │
             │ Engine              │
             └──────────┬──────────┘
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
     ┌───────────────┐      ┌───────────────┐
     │ Reconciled    │      │ Exceptions    │
     │ Transactions   │      │ & Review      │
     └───────┬───────┘      └───────┬───────┘
             │                      │
             └──────────┬───────────┘
                        ▼
             ┌─────────────────────┐
             │ Cash Position       │
             │ + Forecast          │
             └──────────┬──────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ AI Finance Assistant│
             └─────────────────────┘
```

---

# Why SettleSense

## Deterministic first. AI second.

Financial decisions are too important to delegate blindly to an LLM.

SettleSense deliberately separates:

```text
Financial Truth
      ↓
Deterministic Reconciliation Engine
      ↓
Structured Results
      ↓
AI Interpretation
```

The reconciliation engine decides:

* Which records match
* Expected amounts
* Actual amounts
* Variance
* Reconciliation status
* Exception severity
* Whether human review is required

The AI layer operates on those structured results to:

* Explain discrepancies
* Answer finance questions
* Extract UTR/reference information
* Summarize exceptions
* Provide evidence-backed answers

**The LLM is not the source of financial truth.**

---

# Key Results

The current `synthetic-v2` benchmark contains **100 logical payment records** and deliberately planted reconciliation scenarios.

### Benchmark

| Metric                  |                Result |
| ----------------------- | --------------------: |
| Logical records         |               **100** |
| Match rate              |             **71.0%** |
| Automatic matches       |                **71** |
| False automatic matches |                 **0** |
| Precision               |            **100.0%** |
| Recall                  |            **100.0%** |
| Exception capture       |    **29 / 29 = 100%** |
| Status mismatches       |                 **0** |
| Validation skipped rows |                 **0** |
| Test suite              | **110 tests passing** |

The 71% match rate should not be interpreted as "71% accuracy".

The dataset intentionally contains unresolved and anomalous cases. The important result is that the engine automatically reconciles safe records while correctly refusing unsafe matches and identifying planted exceptions.

### The important number

> **0 false automatic matches.**

For financial reconciliation, avoiding an incorrect automatic match is more important than forcing every transaction into a match.

---

# How It Works

SettleSense processes the data in multiple stages.

## 1. Ingestion

The system accepts:

* Internal payment ledger
* Settlement report
* Bank statement

Each source is validated before entering the reconciliation pipeline.

---

## 2. Validation

The ingestion layer checks:

* Required columns
* File type
* File size
* Row structure
* Dates
* Currency
* Amount formats
* Duplicate source rows
* Invalid identifiers
* CSV formula-injection characters

Invalid rows are reported instead of silently disappearing.

---

## 3. Canonical Normalization

Different source formats are converted into a common internal model.

Normalization includes:

* Identifier normalization
* UTR/reference normalization
* Date normalization
* Transaction-type normalization
* Rupees → integer paise conversion
* Preservation of original source values

This allows the reconciliation engine to remain independent of provider-specific CSV formats.

---

## 4. Matching

The reconciliation engine performs multiple matching passes.

### Internal → Settlement

Priority:

1. Exact payment ID
2. Exact order ID
3. Provider entity ID
4. Settlement ID

### Settlement → Bank

Priority:

1. Exact settlement UTR
2. Bank reference
3. Settlement ID in description
4. Unique amount + currency + date-window candidate

---

## 5. Candidate Scoring

When identifiers are incomplete, candidate records can be scored using multiple pieces of evidence.

```text
Payment ID match       0.40
UTR/reference match    0.25
Amount match           0.20
Date proximity         0.10
Currency match         0.05
                       -----
                       1.00
```

The system does not automatically match based only on amount when multiple candidates exist.

---

# Confidence Policy

SettleSense uses confidence thresholds to determine how a candidate should be handled.

|     Score | Decision                                       |
| --------: | ---------------------------------------------- |
|    ≥ 0.95 | Automatic match                                |
| 0.80–0.94 | Automatic only when unique and non-conflicting |
| 0.60–0.79 | Human review                                   |
|    < 0.60 | Unresolved                                     |

This creates a critical safety property:

> **Uncertainty is a valid output.**

The system would rather create an exception than create a false financial match.

---

# Financial Calculation

For each settlement, SettleSense calculates expected net settlement using integer paise arithmetic.

```text
Expected Net
=
Gross Amount
− Fees
− Taxes
− Refund Debits
+ Adjustment Credits
```

Formally:

```text
expected_net_paise =
    gross_amount_paise
    - fee_paise
    - tax_paise
    - refund_debit_paise
    + adjustment_credit_paise
```

The system then compares:

```text
Expected Settlement
        vs
Actual Bank Credit
```

The resulting variance becomes part of the reconciliation evidence.

### Why paise?

Financial calculations are performed using integer paise rather than floating-point values.

This avoids common floating-point precision problems in monetary calculations.

---

# Exception Handling

SettleSense does not hide difficult records.

Each logical payment receives a final reconciliation status.

```text
FULLY_RECONCILED
MISSING_IN_SETTLEMENT
MISSING_BANK_CREDIT
AMOUNT_MISMATCH
DUPLICATE
TIMING_DELAY
NEEDS_HUMAN_REVIEW
```

Each exception can include:

* Payment ID
* Settlement ID
* Bank transaction ID
* UTR
* Expected amount
* Actual amount
* Variance
* Match method
* Reason
* Evidence
* Severity
* Recommended action
* Human-review requirement

---

# Example Exception

```text
Payment: pay_010

Status:
AMOUNT_MISMATCH

Expected:
₹1,000

Actual:
₹700

Variance:
-₹300

Reason:
Bank credit does not equal expected settlement amount.

Evidence:
- Internal payment record
- Settlement record
- Settlement UTR
- Bank transaction

Action:
Review settlement/bank discrepancy.
```

This makes the system useful to an actual finance operator rather than simply producing a percentage.

---

# Cash Position

Reconciliation is only half of the problem.

SettleSense also calculates the cash position.

The dashboard separates:

### Confirmed cash

Money supported by confirmed bank transactions.

### Expected cash

Money expected from settlements but not yet confirmed in the bank.

### Pending cash

Settlement amounts still waiting for bank realization.

### Variance

```text
Expected Cash − Actual Cash
```

The system also provides a short-horizon cash forecast with explicit assumptions and confidence.

Forecasted cash is clearly labelled as forecasted rather than booked cash.

---

# AI Finance Assistant

SettleSense includes a constrained AI finance assistant.

The assistant can answer questions such as:

```text
Which unresolved exception has the highest monetary impact?

Why is payment pay_010 unresolved?

What is the current cash variance?

Show me the transaction trail for pay_087.

Which payments are waiting for bank credit?

Explain this settlement discrepancy.
```

## Evidence-backed answers

AI responses are grounded in structured backend tools.

The assistant can use tools for:

* Batch summary
* Exception listing
* Cash position
* Transaction trace
* Exception explanation
* Bank-description parsing

Responses can include:

* Record IDs
* Monetary amounts
* Evidence
* Tools used
* Human-review requirement

---

# AI Safety

The AI assistant is intentionally constrained.

It does **not**:

* Modify financial records
* Execute settlements
* Make financial writes
* Override reconciliation decisions
* Invent missing transaction information
* Treat bank-description text as trusted instructions

If the system cannot establish an answer from available evidence, it can return a human-review result instead of hallucinating.

Optional model failure also has a deterministic fallback path for supported queries.

---

# Evaluation & Benchmark

The benchmark is designed around the actual Buildathon requirement:

```text
Throughput
+
Accuracy
+
Honest Exceptions
```

## Metrics

| Metric            | Meaning                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------- |
| Match Rate        | Percentage of logical records automatically/fully reconciled according to the benchmark definition |
| Precision         | Correct automatic matches / automatic matches                                                      |
| Recall            | Correctly identified true matches / true matches                                                   |
| Exception Capture | Correctly identified exceptions / actual exceptions                                                |
| Monetary Variance | Aggregate expected-vs-actual monetary difference                                                   |
| Throughput        | Records processed per second                                                                       |

---

# Current Benchmark

Run:

```bash
python scripts/run_benchmark.py --data-dir data
```

Expected benchmark characteristics:

```text
validation       : clean
match rate       : 71.0%
auto matches     : 71
precision        : 100.0%
recall           : 100.0%
exception capture: 29/29 = 100.0%
status mismatches: none
```

The benchmark also verifies planted anomaly scenarios individually.

---

# Synthetic Dataset

SettleSense intentionally uses synthetic financial data.

The dataset contains **100 logical payment records**.

The benchmark includes scenarios such as:

| Scenario              | Count |
| --------------------- | ----: |
| Clean transactions    |    60 |
| Delayed bank credits  |    10 |
| Missing UTR           |     8 |
| Amount mismatches     |     6 |
| Missing settlements   |     5 |
| Missing bank credits  |     4 |
| Duplicates            |     3 |
| Refunds               |     2 |
| Adjustments           |     1 |
| Ambiguous review case |     1 |

The current benchmark represents these through 13 scenario classes, including duplicate-source cases and same-amount clean transactions.

---

# Ground Truth Isolation

Ground truth exists only for evaluation.

It is **not used by the runtime reconciliation engine** to make financial decisions.

The production flow is:

```text
Ledger
Settlement
Bank
   ↓
Reconciliation Engine
```

Evaluation adds:

```text
Ground Truth
   ↓
Benchmark / Metrics
```

This prevents the benchmark from becoming a hidden oracle.

---

# Deterministic Dataset Generation

The dataset can be regenerated using a fixed seed.

```bash
python scripts/generate_data.py --out-dir data --seed 42
```

Running the generator with the same seed produces reproducible data.

This makes benchmark results repeatable and auditable.

---

# Architecture

```text
┌──────────────────────────────────────────────────────┐
│                    DATA SOURCES                      │
│                                                      │
│  Internal Ledger │ Settlement Report │ Bank Statement│
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│              INGESTION & VALIDATION                  │
│                                                      │
│ File checks │ Schema checks │ Row validation         │
│ Duplicate detection │ Formula-injection checks      │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│             CANONICAL NORMALIZATION                  │
│                                                      │
│ IDs │ UTR │ Dates │ Currency │ Paise │ Raw evidence │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│              RECONCILIATION ENGINE                   │
│                                                      │
│ Exact matching │ Candidate scoring │ Net settlement │
│ Variance calculation │ Status classification        │
└──────────────────────────┬───────────────────────────┘
                           │
             ┌─────────────┴──────────────┐
             ▼                            ▼
┌──────────────────────┐       ┌──────────────────────┐
│ Reconciled Records   │       │ Exception Engine    │
│                      │       │                      │
│ Matches              │       │ Missing records     │
│ Amounts              │       │ Mismatches          │
│ Evidence             │       │ Duplicates          │
└──────────┬───────────┘       │ Human review        │
           │                   └──────────┬───────────┘
           └──────────────┬───────────────┘
                          ▼
              ┌──────────────────────┐
              │   CASH ENGINE        │
              │                      │
              │ Actual cash          │
              │ Expected cash        │
              │ Pending settlements  │
              │ Forecast             │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ REST API + Dashboard │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ AI FINANCE ASSISTANT │
              │                      │
              │ Explain              │
              │ Query                │
              │ Trace                │
              │ Summarize            │
              └──────────────────────┘
```

---

# Key Architectural Principle

The most important architectural boundary is:

```text
                ┌───────────────────────┐
                │ Reconciliation Engine │
                │     SOURCE OF TRUTH   │
                └───────────┬───────────┘
                            │
                    Structured results
                            │
                            ▼
                ┌───────────────────────┐
                │     AI Assistant      │
                │ Interpretation/Q&A    │
                └───────────────────────┘
```

This prevents an LLM from becoming the authority over financial amounts or transaction matching.

---

# Tech Stack

## Backend

* Python 3.12+
* FastAPI
* Pydantic
* SQLAlchemy
* SQLite
* Pandas
* Pytest

## Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* Recharts
* TanStack Query
* React Router
* Framer Motion
* Lucide Icons

## AI

* LLM with structured JSON output
* Tool/function calling
* Server-side integration
* Deterministic fallback for supported queries

## Infrastructure

* Docker
* Docker Compose
* GitHub Actions
* Ruff
* ESLint
* Prettier

---

# Project Structure

```text
SettleSense-AI_Finance_Controller/
│
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
│
├── frontend/
│   └── src/
│       ├── api/
│       ├── components/
│       ├── pages/
│       └── types/
│
├── data/
│   ├── internal_ledger.csv
│   ├── settlements.csv
│   ├── bank_statement.csv
│   ├── ground_truth.csv
│   └── manifest.json
│
├── evaluation/
│   └── benchmark reports
│
├── scripts/
│   ├── generate_data.py
│   └── run_benchmark.py
│
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
│
├── ARCHITECTURE.md
├── PRD.md
├── TECHNICAL_DESIGN.md
├── TESTING.md
├── VERIFICATION.md
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

# Running Locally

## Prerequisites

* Python 3.12+
* Node.js 18+
* Node.js 20 recommended
* Docker optional

---

## 1. Clone the repository

Clone this repository from GitHub and enter the project directory:

```bash
git clone <REPOSITORY_URL>
cd SettleSense-AI_Finance_Controller
```

---

## 2. Backend setup

Create a virtual environment:

```bash
python -m venv venv
```

### Windows

```powershell
venv\Scripts\activate
```

### macOS / Linux

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy the environment template:

```bash
cp .env.example .env
```

Start the backend:

```bash
uvicorn backend.main:app --reload --port 8000
```

The backend should be available at:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

---

# 3. Frontend setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server runs on:

```text
http://localhost:5173
```

The frontend communicates with the backend through the configured development proxy.

---

# 4. Verify the backend

```bash
curl http://localhost:8000/health
```

The health endpoint should return a successful service response.

---

# Docker

The complete stack can also be started with Docker Compose.

```bash
docker compose up --build
```

Stop the stack:

```bash
docker compose down
```

Docker is recommended when you want to reproduce the complete application environment.

---

# Generate Synthetic Data

From the repository root:

```bash
python scripts/generate_data.py --out-dir data --seed 42
```

This creates the benchmark dataset used by the reconciliation engine.

---

# Run the Benchmark

```bash
python scripts/run_benchmark.py --data-dir data
```

The benchmark evaluates:

* Validation
* Match rate
* Automatic matches
* False automatic matches
* Precision
* Recall
* Exception capture
* Scenario coverage
* Monetary variance
* Throughput

---

# Testing

Run the complete test suite:

```bash
python -m pytest tests/ -q
```

Run unit tests:

```bash
python -m pytest tests/unit -q
```

Run integration tests:

```bash
python -m pytest tests/integration -q
```

Run the dataset tests:

```bash
python -m pytest tests/test_data_generation.py
```

The repository's verification suite currently reports:

```text
110 passed
```

The tests cover:

* Monetary calculations
* Integer-paise safety
* Normalization
* Ingestion
* CSV formula injection
* Matching rules
* Reconciliation statuses
* Exception classification
* Duplicate handling
* Ambiguous matches
* Metrics
* API contracts
* Dataset determinism
* Ground-truth isolation
* Idempotency
* End-to-end reconciliation

---

# API

The backend exposes REST endpoints for the complete finance-ops workflow.

## Health

```http
GET /health
```

---

## Create Batch

```http
POST /api/v1/batches
```

Accepts:

```text
internal_ledger
settlements
bank_statement
```

---

## Get Batch

```http
GET /api/v1/batches/{batch_id}
```

---

## Run Reconciliation

```http
POST /api/v1/batches/{batch_id}/reconcile
```

---

## Get Results

```http
GET /api/v1/batches/{batch_id}/results
```

---

## Get Exceptions

```http
GET /api/v1/batches/{batch_id}/exceptions
```

---

## Get Metrics

```http
GET /api/v1/batches/{batch_id}/metrics
```

---

## Get Cash Position

```http
GET /api/v1/batches/{batch_id}/cash-position
```

---

## Export Results

```http
GET /api/v1/batches/{batch_id}/export?format=csv
```

---

## Transaction Trace

```http
GET /api/v1/transactions/{payment_id}/trace
```

---

## AI Finance Query

```http
POST /api/v1/ai/query
```

Example:

```json
{
  "batch_id": "batch_001",
  "question": "Which exception has the highest monetary impact?"
}
```

The response can include:

```json
{
  "answer": "...",
  "record_ids": ["pay_087"],
  "tools_used": ["list_exceptions", "get_cash_position"]
}
```

---

# Security & Reliability

SettleSense is designed around financial-data safety.

## Secrets

* API keys are stored in server-side environment variables.
* Secrets are never exposed to the browser.
* Production credentials are not committed to the repository.

## Financial safety

* Integer paise for monetary calculations
* No floating-point financial comparisons
* Deterministic matching
* Confidence thresholds
* Human-review escalation
* No AI-initiated financial writes
* Append-only audit events

## Input safety

* File-size validation
* File-type validation
* Row-count limits
* CSV formula-injection checks
* Structured validation errors
* Parameterized database queries
* PII-conscious logging

## AI safety

* AI only accesses controlled read-only tools
* Bank descriptions are treated as untrusted data
* Prompt injection is not allowed to change financial decisions
* Unknown questions can be escalated to human review

---

# Idempotency

Re-running the same batch should not create duplicate reconciliation results or audit events.

```text
Same Input
    ↓
Same Normalization
    ↓
Same Matching
    ↓
Same Results
```

This is important for finance operations because retries are normal in real systems.

---

# Design Principles

## 1. Deterministic before generative

Financial decisions should be reproducible.

## 2. Evidence before confidence

Every important decision should have supporting source records.

## 3. Human review is a valid result

An unresolved transaction is better than an incorrect automatic match.

## 4. Paise, not floating-point money

All financial calculations use integer paise.

## 5. Ground truth is isolated

Ground truth evaluates the engine but does not drive runtime decisions.

## 6. Idempotent processing

The same batch can safely be processed again.

## 7. Synthetic-data first

The public project does not require real customer or bank information.

---

# What Makes This Different

Many AI finance systems focus on asking an LLM questions about financial data.

SettleSense takes a different approach.

```text
Traditional AI-first approach:

Financial Data
     ↓
     LLM
     ↓
Financial Answer
```

SettleSense:

```text
Financial Data
     ↓
Validation
     ↓
Normalization
     ↓
Deterministic Reconciliation
     ↓
Financial Truth
     ↓
AI Explanation
```

This means the AI is useful without allowing it to invent the financial state of the system.

---

# Limitations

SettleSense is a buildathon/MVP implementation and intentionally has limitations.

### Synthetic data

The benchmark uses generated data rather than production financial records.

### Limited provider integrations

The core engine works with normalized CSV/API-style inputs. Provider-specific integrations can be added through adapters.

### Forecasting

The cash forecast is intended as an operational projection, not a production treasury forecasting system.

### Human review

Ambiguous cases are intentionally escalated rather than automatically resolved.

### Production infrastructure

A production deployment would require additional infrastructure for:

* PostgreSQL
* Authentication/authorization
* Secrets management
* Observability
* Distributed processing
* Queue-based ingestion
* Stronger compliance controls
* Production-grade provider integrations

---

# Future Work

## Multi-provider reconciliation

Support multiple payment providers and banking formats through pluggable adapters.

## Real-time reconciliation

Move from batch processing to event-driven reconciliation.

## ERP integration

Integrate with accounting and ERP systems.

## Advanced forecasting

Use historical settlement behavior to improve cash forecasting.

## Human-in-the-loop workflow

Allow finance operators to approve, reject and annotate exceptions.

## Production observability

Add:

* Structured logs
* Metrics
* Distributed traces
* Alerting
* SLA monitoring

## Larger-scale processing

Extend the architecture from hundreds of records to millions of records using:

* PostgreSQL
* Background workers
* Queues
* Partitioned processing
* Incremental reconciliation

---

# Documentation

The repository contains additional engineering documentation:

* [`ARCHITECTURE.md`](./ARCHITECTURE.md) — System architecture and design principles
* [`PRD.md`](./PRD.md) — Product requirements
* [`TECHNICAL_DESIGN.md`](./TECHNICAL_DESIGN.md) — Technical implementation design
* [`TESTING.md`](./TESTING.md) — Testing strategy and coverage
* [`VERIFICATION.md`](./VERIFICATION.md) — Step-by-step verification guide

---

# Demo Checklist

For a Buildathon demo, the recommended flow is:

### Step 1 — Show the problem

Explain that the same payment exists across:

```text
Internal Ledger
Settlement Report
Bank Statement
```

### Step 2 — Upload/process the batch

Run the 100-record synthetic dataset.

### Step 3 — Show the headline metrics

Show:

```text
100 records processed
71% match rate
100% precision
100% recall
100% exception capture
0 false auto-matches
```

### Step 4 — Show an exception

Open an amount mismatch and demonstrate:

```text
Expected
Actual
Variance
Source IDs
Reason
Evidence
Recommended action
```

### Step 5 — Show cash position

Demonstrate:

```text
Actual Cash
Expected Cash
Pending Settlements
Variance
Forecast
```

### Step 6 — Ask the AI

Ask:

```text
Which unresolved exception has the highest monetary impact?
```

Then show that the answer references actual transaction evidence.

### Step 7 — Show the honest failure case

Demonstrate an ambiguous transaction.

The system should say:

```text
NEEDS_HUMAN_REVIEW
```

rather than forcing a match.

---

# The Core Demo Message

> **SettleSense does not try to make every transaction look reconciled.**
>
> It automatically resolves transactions when the evidence is strong, measures how well it performed, exposes the financial impact of exceptions, and sends ambiguous cases to humans instead of guessing.

---

# Buildathon Alignment

| Razorpay Buildathon Goal   | SettleSense Implementation                 |
| -------------------------- | ------------------------------------------ |
| Close one finance-ops loop | Payment → settlement → bank reconciliation |
| 50+ record batch           | 100 logical payment records                |
| Multi-source data          | 3 financial sources                        |
| Throughput                 | Records/second benchmark                   |
| Measured accuracy          | Precision + recall + match rate            |
| Honest exception list      | 29 planted exceptions captured             |
| Financial visibility       | Cash position + variance                   |
| AI assistance              | Evidence-backed finance Q&A                |
| Safety                     | Deterministic financial engine             |
| Auditability               | Evidence + audit events                    |
| Reproducibility            | Seeded synthetic dataset                   |
| Reliability                | Idempotent processing                      |
| Verification               | Automated test + benchmark suite           |

---

# License

This project is provided for educational, experimental and Buildathon purposes.

See the repository license for the applicable terms.

---

# Built for the Razorpay AI Buildathon 2026

**SettleSense — AI Finance Controller**

```text
Reconcile accurately.
Explain every decision.
Expose every exception.
Never guess with money.
```
