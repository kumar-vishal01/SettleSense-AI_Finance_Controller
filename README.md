# ClearLedger

## AI Finance Control Center for Payment Reconciliation

> Every payment accounted for.

ClearLedger is an AI-powered finance-operations system that reconciles internal payment records, Razorpay-style settlement reports, and bank statement entries. It processes a complete batch of financial records, automatically resolves high-confidence matches, calculates cash position, measures reconciliation accuracy, and escalates uncertain cases with evidence-backed explanations.

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

ClearLedger automates the three-way reconciliation workflow:

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
