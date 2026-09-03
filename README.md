# SettleSense — AI Finance Controller

SettleSense reconciles three sources — an **internal payment ledger**, a
**Razorpay-style settlement report**, and a **bank statement** — into one
auditable finance-operations loop:

```
payment → settlement → bank credit → reconciliation result
```

The deterministic reconciliation engine is the **only** source of financial
truth. The (future) AI layer explains and queries results through
constrained backend tools; it never invents, mutates, or overrides financial
records.

Full specs: [PRD.md](PRD.md) · [TECHNICAL_DESIGN.md](TECHNICAL_DESIGN.md) ·
[ARCHITECTURE.md](ARCHITECTURE.md) · [AGENTS.md](AGENTS.md) ·
[TESTING.md](TESTING.md) · **[VERIFICATION.md](VERIFICATION.md)** — how to
confirm each part is working, with expected outputs

## Project status

| Phase | Scope | State |
|---|---|---|
| Core engine | ingestion → normalization → matching → reconciliation → metrics, synthetic dataset, benchmark | ✅ 157+ tests |
| Phase 1 | scaffold, FastAPI `/health`, React/Vite/Tailwind shell, pytest + Docker | ✅ |
| Phase 2 | synthetic-v2 dataset: 100 payments, 13 scenarios, ground truth | ✅ |
| Phase 3 | typed ingestion/validation/normalization layer | ✅ |
| Phase 4 | SQLite persistence (5 tables) + validated batch APIs | ✅ |
| Phase 5 | matching/reconciliation engine (statuses, calculations, bands) | ✅ |
| Phase 6 | benchmark evaluation + metrics (evaluation/report.*) | ✅ |
| Phase 7 | cash position + 7-day forecast API | ✅ |
| Phase 8 | constrained AI assistant (grounded tools, injection-safe, graceful fallback) | ✅ |
| Phase 9 | reconcile persistence + decision audit events + metrics API, TypeScript dashboard | ✅ |
| Phase 10 | hardening + `/export` (CSV/JSON) + final reports (test/security/demo) | ✅ |
| — | REST trace route, CI pipeline, packaging polish | ⏭ future |

## Repository layout

```
settlesense/
├── backend/            domain (no framework code) + FastAPI service layer
│   ├── main.py             app factory + GET /health
│   ├── settings.py         env-var service settings (non-secret)
│   ├── schemas.py          versioned API response contracts (Pydantic)
│   └── *.py                domain engine (config, models, ingestion, …)
├── frontend/           React + Vite + Tailwind dashboard (phase-1 shell)
├── scripts/            generate_data.py, run_benchmark.py
├── data/               versioned synthetic dataset (seed 42) + ground truth
├── tests/              unit + integration + (planned) evaluation — see tests/README.md
├── docker-compose.yml  backend + frontend local stack
├── pytest.ini          test discovery/strictness config
└── requirements.txt
```

## Setup — Linux / macOS

```bash
# 1. Python service (3.12+)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Verify: import check, tests, then run the API
python -c "import backend.main; print('backend imports OK')"
python -m pytest tests/ -q
uvicorn backend.main:app --reload          # http://localhost:8000/health

# 3. Dashboard (separate terminal)
cd frontend
npm install
npm run dev                                # http://localhost:5173

# 4. Or run the whole stack in Docker
docker compose up --build
```

## Setup — Windows (PowerShell)

```powershell
# 1. Python service (3.12+)
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Verify and run
python -c "import backend.main; print('backend imports OK')"
python -m pytest tests/ -q
uvicorn backend.main:app --reload          # http://localhost:8000/health

# 3. Dashboard (separate terminal)
cd frontend
npm install
npm run dev                                # http://localhost:5173

# 4. Or run the whole stack in Docker
docker compose up --build
```

## Configuration

All configuration is environment-driven (`.env.example` documents every
variable; copy to `.env`, never commit it). No secrets exist in the repo,
the browser bundle, logs, or fixtures.

| Variable | Purpose | Default |
|---|---|---|
| `SETTLESENSE_ENV` | `local` / `docker` / `production` | `local` |
| `SETTLESENSE_TIMEZONE` | display timezone (internals stay UTC) | `Asia/Kolkata` |
| `SETTLESENSE_DB_PATH` | SQLite database file | `settlesense.db` |
| `SETTLESENSE_LOG_LEVEL` | uvicorn/app log level | `info` |
| `SETTLESENSE_CORS_ORIGINS` | dev CORS allowlist | vite dev ports |

## Batch API quickstart (phase 4)

```bash
# from three uploaded files…
curl -X POST http://localhost:8000/api/v1/batches \
  -F internal_ledger=@data/internal_ledger.csv \
  -F settlements=@data/settlements.csv \
  -F bank_statement=@data/bank_statement.csv

# …or from the whitelisted server-side fixture
curl -X POST "http://localhost:8000/api/v1/batches?fixture=synthetic-v2"
curl http://localhost:8000/api/v1/batches/{batch_id}
curl "http://localhost:8000/api/v1/batches/{batch_id}/results?page=1&page_size=20"
curl -X POST "http://localhost:8000/api/v1/batches/{batch_id}/reconcile"
curl "http://localhost:8000/api/v1/batches/{batch_id}/metrics"
curl "http://localhost:8000/api/v1/batches/{batch_id}/exceptions"
curl "http://localhost:8000/api/v1/batches/{batch_id}/cash-position?opening_balance_paise=1000000&horizon=7"
curl -X POST http://localhost:8000/api/v1/ai/query \
  -H "Content-Type: application/json" \
  -d '{"batch_id": "<id>", "question": "Which unresolved exception has the highest monetary impact?"}'
```

Creating a batch validates and persists it (`status: "validated"`) — it never
claims reconciliation; re-uploading identical files returns the same batch
(`idempotent: true`). Errors use one envelope: `{"error": {code, message}}`.

## Cash position (phase 7)

`GET /api/v1/batches/{id}/cash-position` — confirmed cash (evidence-linked
credits + debits), pending settlements (timing-delayed only), expected cash,
variance with a `bank_charges_paise` breakout, unattributed/excluded money
reported separately, a day-by-day forecast explicitly labelled **not booked
cash**, assumptions, and a confidence level. All integer paise.

## Export (phase 10)

`GET /api/v1/batches/{id}/export?format=csv|json&scope=results|exceptions` —
audit-grade export: integer paise, evidence IDs included, byte-identical on
repeat calls, headers-only until reconciled.

## Health endpoint

`GET /health` → `200`

```json
{
  "status": "ok",
  "service": "settlesense-backend",
  "version": "0.1.0",
  "environment": "local",
  "timezone": "Asia/Kolkata"
}
```

Interactive docs: `http://localhost:8000/docs` (OpenAPI 3).

## Architecture boundaries

```
frontend/ (React)      HTTP only — no business rules, no money math
backend/main.py        service layer: routing, schemas, middleware
backend/settings.py    env config for the service layer (non-secret)
backend/schemas.py     versioned API contracts
backend/{models,matching,reconciliation,metrics,...}.py   pure domain
scripts/               dataset generation + benchmark evaluation (ground
                       truth lives here only — never in the service layer)
tests/                 mirrors the same split (unit vs integration)
```

Rules that keep it clean:

- Domain modules import nothing from FastAPI; the service layer imports
  domain but contains **no** financial decisions.
- The engine is a pure function of inputs + config (idempotent batches).
- Money is integer paise everywhere; the API never receives or returns
  floats for amounts.
- Ground truth is evaluation-only and never reaches runtime endpoints.
- The AI layer (phase 4) will sit behind backend tools and be read-only.

## Run the Demo

The complete 5-minute demo — exact commands, expected numbers, and the
timed presentation script — lives in **[DEMO.md](DEMO.md)**. Shortest path:

```bash
uvicorn backend.main:app --port 8000          # terminal 1
cd frontend && npm install && npm run dev     # terminal 2 → http://localhost:5173
# dashboard → Upload → "Load synthetic-v2 fixture" → auto-reconcile → every panel
```

Expected: 100 records · 71% match · precision 100% (0 false auto-matches) ·
variance −₹1,500 · 29 exceptions · top exposure pay_069 ₹4,64,175.68 ·
confirmed/pending/forecast cash as separate labelled series.

Readiness: [FINAL_CHECKLIST.md](FINAL_CHECKLIST.md) · [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) ·
[evaluation/demo_readiness.md](evaluation/demo_readiness.md)

## Benchmark — dataset `synthetic-v2` (seed 42)

```bash
python scripts/generate_data.py --out-dir data --seed 42   # regenerate
python scripts/run_benchmark.py --data-dir data            # evaluate vs ground truth
```

Scenario plan (100 logical payments): 57 clean + 3 same-amount clean,
10 delayed bank credits, 8 missing-UTR (resolved via description reference),
6 amount mismatches, 5 missing settlements, 4 missing bank credits,
3 duplicates (ledger / bank / settlement), 2 refunds, 1 adjustment,
1 deliberately ambiguous pair. Every injected error's representation is
documented in `scripts/generate_data.py`.

Latest committed run: match rate 71% (71/100), precision 100%, recall 100%,
**0 false auto-matches**, 29/29 planted anomalies captured (all 13 scenarios
100%), total variance exactly the planted −₹1,500, ~2,500+ records/s.
Ground truth is consumed **only** by `scripts/run_benchmark.py` and the
dataset tests — never by the runtime engine.
