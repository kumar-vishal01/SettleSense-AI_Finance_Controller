# Testing strategy — SettleSense

## Principles

- Tests exist **before** matching behavior changes (AGENTS.md section 3).
- Money rules are tested directly: every paise field is an `int`; rupee
  conversion uses `Decimal` with half-up rounding; floats never appear in
  financial comparisons.
- The end-to-end test is the PRD section 9 success gate: all planted
  anomalies identified, **zero false auto-matches**, reproducible metrics.
- Ground truth is loaded only by evaluation code (`run_benchmark.py`,
  `tests/integration/`), never by the engine.

## How to run

```bash
python -m pytest tests/ -q              # everything
python -m pytest tests/unit -q          # rule-level
python -m pytest tests/integration -q   # end-to-end success gate
python scripts/run_benchmark.py         # printed benchmark + ground truth
```

## Coverage map

| Area | File | Key guarantees |
|---|---|---|
| Money parsing | `tests/unit/test_money.py` | integer paise, rejects decimals/negatives, half-up rupee conversion |
| Normalization | `tests/unit/test_normalization.py` | trimming, UTR casing, UTC dates, type mapping, raw payload preserved |
| Ingestion | `tests/unit/test_ingestion.py` | file-level rejection vs row-level quarantine, formula-injection, nullable references |
| Matching | `tests/unit/test_matching.py` | payment-id precedence, order-id fallback, UTR/reference candidates, amount+date-only never auto-matches |
| Statuses | `tests/unit/test_reconciliation.py` | all 7 statuses, waterfall math, tolerance boundary, severity bands, duplicates, ambiguity → review, idempotency |
| Metrics | `tests/unit/test_metrics.py` | summary math, exception queue ordering, precision/recall/false-auto/capture |
| Validation (phase 3) | `tests/unit/test_validation.py` | typed rows, columns, paise, INR, types, dates, duplicates kept+reported, blank-vs-zero, injection, batch summary |
| Calculations (phase 5) | `tests/unit/test_calculations.py` | waterfall, refund/adjustment, tolerance boundary, variance signs, fee/tax deltas, exact formatting |
| Statuses & bands | `tests/unit/test_matching.py` (TestBandsAreEnforced) + `test_reconciliation.py` | band gate enforcement, demotion under strict thresholds, loose-threshold negative control |
| App config | `tests/unit/test_app_config.py` | wildcard-CORS rejection outside local |
| Docs sync | `tests/unit/test_docs_sync.py` | VERIFICATION/README follow the shipped version + API |
| API health | `tests/unit/test_api_health.py` | `/health` contract, OpenAPI docs, no premature domain routes, no secrets in payload |
| Dataset (phase 2) | `tests/test_data_generation.py` | 100 logical records, schemas, integer paise, scenario distribution, planted representations, seed reproducibility, engine-vs-ground-truth agreement |
| Reconciliation scenarios (phase 5) | `tests/integration/test_reconciliation.py` | all 13 fixture scenarios through real ingestion + engine; dataset stability |
| Batch APIs (phase 4) | `tests/integration/test_batches.py` | creation, idempotency, rollback, pagination, filters, envelope, bounded uploads |
| End-to-end | `tests/integration/test_end_to_end.py` | committed synthetic-v2 batch: exact status counts, precision/recall 1.0, 0 false auto-matches, variance equals planted deltas, idempotent rerun |

API tests use `fastapi.testclient` (in-process; no server, no network).
Future phases add an `tests/api/` suite that follows the same rule: each
endpoint gets a contract test before its handler grows logic.

| Evaluation (phase 6) | `tests/evaluation/test_benchmark.py` | metric contract + denominators, FP identification vs unresolved, artifacts, seed reproducibility, GT isolation |

## Benchmark reproducibility

The dataset is a versioned artifact: `data/manifest.json` records
`dataset_version`, seed, and the planted anomaly plan. Regenerating with the
same seed reproduces identical rows and identical benchmark claims:

```bash
python scripts/generate_data.py --out-dir data --seed 42
python scripts/run_benchmark.py --data-dir data
```

## Before changing matching behavior

1. Write the failing test that pins the intended behavior.
2. Make the change.
3. Full suite green + benchmark still reports 0 false auto-matches.
