# Tests — layout and conventions

```
tests/
├── conftest.py            puts repo root + scripts/ on sys.path
├── factories.py           canonical-record factories for rule tests
├── unit/                  rule-level, no network, no database
│   ├── test_money.py              integer paise, no floats
│   ├── test_normalization.py      identifiers, UTRs, dates, raw preservation
│   ├── test_ingestion.py          file rejection vs row quarantine
│   ├── test_matching.py           candidate generation + scoring only
│   ├── test_reconciliation.py     status decisions, waterfall, idempotency
│   ├── test_metrics.py            summary + ground-truth evaluation
│   └── test_api_health.py         GET /health contract (phase 1)
├── integration/           end-to-end success gate (dataset -> engine -> metrics)
└── evaluation/            benchmark-related tests (planned)
```

Rules:

- Unit tests import domain modules directly; only `test_api_*` files may
  import FastAPI.
- Nothing under `tests/` may import an LLM client or hit the network.
- Ground-truth files are only read by integration/evaluation tests and by
  `scripts/run_benchmark.py` — never by `backend/` runtime code.
- Fixtures in `factories.py` keep every money value explicit integer paise.

Run:

```bash
python -m pytest tests/ -q          # all
python -m pytest tests/unit -q      # rules + API contract
python -m pytest tests/integration  # end-to-end gate
```
