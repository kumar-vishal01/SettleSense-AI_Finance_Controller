# Final Test Report — SettleSense (phase 10)

Run date: 2026-08-22 · HEAD after phase 10 · all commands reproducible from VERIFICATION.md.

## Run matrix

| Suite | Command | Result |
|---|---|---|
| Full backend suite | `python -m pytest tests/ -q` | **304 passed, 0 failed** |
| Unit (money/validation/matching/engine/AI) | `pytest tests/unit` | green |
| Integration (batches/reconcile/cash/AI/export/e2e) | `pytest tests/integration` | green |
| Evaluation benchmark | `python scripts/run_benchmark.py` | see evaluation/report.md |
| API contract (OpenAPI surface + envelope) | included in unit/integration | green |
| Frontend lint (tsc strict) | `npm run lint` | clean |
| Frontend build | `npm run build` | ✓ |
| Security scans | see evaluation/security_checklist.md | clean |

## Benchmark summary (dataset synthetic-v2, seed 42)

100 records · match rate 71% · **precision 100% · recall 100% · 0 false
automatic matches** · exception capture 29/29 · total variance −150,000 paise
(exactly the planted deltas) · ~830 records/s. Precision/recall/exception
capture come from ground truth used ONLY by the evaluation command.

## Required scenario coverage (all pinned by committed tests)

| Scenario | Test |
|---|---|
| Repeated batch upload | `test_duplicate_upload_returns_existing_batch`, `test_concurrent_duplicate_upload_is_idempotent_not_500` |
| Malformed CSV | `TestMalformedCsv` (binary garbage → 422; semicolon delimiter → 422; nothing persisted) |
| Oversized CSV | `test_oversized_upload_rejected_before_full_read` (413, bounded read) |
| Missing fields | `test_blank_required_field_skips_only_that_row` + row-level quarantine suite |
| Same-amount ambiguity | `test_ambiguous_amount_date_candidates`, dataset `ambiguous_review` scenario |
| Duplicate source records | ingestion keep+report suite; engine DUPLICATE suite; dataset 3 scenarios |
| Missing bank credit | engine + API + dataset scenarios |
| Amount mismatch | engine + API + export row-level assertions |
| Refund and adjustment | calculations suite + 13-scenario integration suite |
| AI timeout | `test_timeout_falls_back_to_deterministic_answer` |
| AI hallucination attempt | `TestEvidenceGuardAmountsAndStatuses`, ID-drop/ID-invent/tamper rejections |
| Prompt injection in bank description | `test_injected_description_cannot_steer_the_answer` + parse-as-data |
| Database failure/rollback | `test_failed_persist_leaves_no_partial_batch` |

## Defects found and fixed in this phase

1. **Unhandled UnicodeDecodeError** (found by the new malformed-CSV test):
   binary uploads crashed with 500; ingestion now raises a structured
   `ingestion_error` 422 (`backend/ingestion.py`).
2. **Export unpacking bug** (`items, total` swapped) — caught by the export
   tests before release.
3. One test-fixture arithmetic error (bank credit equal to expected net was
   labeled a mismatch) — fixed in the test, not by weakening assertions.

## Known failing / not-run

- Docker/compose build: not run (no Docker daemon in this environment) —
  configs are review-verified only.
- Browser-level UI tests: none (no component test runner); coverage is
  `tsc` strict + build + the API-side e2e flow the dashboard performs.
