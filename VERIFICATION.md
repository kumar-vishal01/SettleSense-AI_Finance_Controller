# Verification Guide — "is it working or not?"

Every claim below was executed against this repository. Copy-paste each
command from the repo root (`settlesense/`) and compare against the
**expected** block. If output differs, see the failure-meaning table at the
bottom.

Quick index:

| # | What you're verifying | Section |
|---|---|---|
| 1 | Environment + dependencies | [§1](#1-environment) |
| 2 | Backend imports cleanly | [§2](#2-backend-import-check) |
| 3 | Full automated test suite (what each file proves) | [§3](#3-test-suite) |
| 4 | Health endpoint (live) | [§4](#4-health-endpoint) |
| 5 | Dataset generator + determinism | [§5](#5-dataset--determinism) |
| 6 | Benchmark: the master check | [§6](#6-benchmark--the-master-check) |
| 7 | Money is integer paise (no floats) | [§7](#7-money-safety) |
| 8 | No false auto-matches / ambiguity handling | [§8](#8-match-safety) |
| 9 | Ground truth never touches runtime | [§9](#9-ground-truth-isolation) |
| 10 | Idempotency (same input → same result) | [§10](#10-idempotency) |
| 11 | Single-payment deep dive (trace-style) | [§11](#11-single-payment-deep-dive) |
| 12 | Frontend build + dashboard | [§12](#12-frontend) |
| 13 | Docker stack | [§13](#13-docker-stack) |
| 14 | Reading failures | [§14](#14-if-something-fails) |

---

## 1. Environment

```bash
python3 --version          # expect: 3.12+ (repo developed/tested on 3.12 & 3.13)
pip install -r requirements.txt
node --version             # expect: v18+ (built/tested on v20) — only needed for §12
```

**Pass:** install completes with no errors.
**Fail meaning:** wrong Python (needs 3.12+) or no network for pip/npm.

## 2. Backend import check

```bash
python -c "import backend.main; print('OK', backend.main.SERVICE_VERSION)"
```

**Expected:** `OK 0.1.0`

This proves the FastAPI app, settings, schemas, and the whole domain engine
import without circular imports or missing dependencies.

## 3. Test suite

```bash
python -m pytest tests/ -q          # full suite (count grows each phase)
python -m pytest tests/unit -q      # rule-level + API contract
python -m pytest tests/integration  # end-to-end success gate
python -m pytest tests/test_data_generation.py  # dataset contract
```

**Expected:** `110 passed` (a single third-party Starlette warning is known
and harmless — it comes from FastAPI's own testclient import, not our code).

What each file actually proves — a failure in that file means:

| File | Proves | A failure means |
|---|---|---|
| `test_money.py` | paise parsing/rounding, no float money paths | money handling regressed |
| `test_normalization.py` | trimming, UTR casing, UTC dates, **no fabricated dates**, raw values preserved | canonical model drift |
| `test_ingestion.py` | file vs row errors, quarantine, CSV injection (`= + - @`), type vocabulary, nullable UTRs | unsafe/invalid rows could crash or leak in |
| `test_matching.py` | payment-id precedence, order-id fallback, UTR/reference candidates, **prefix-ID boundary**, amount+date alone never auto-matches | false-match risk |
| `test_reconciliation.py` | all 7 statuses, waterfall math + **breakdown in results**, tolerance boundary, severity bands, duplicates, contested claims, orphan-row visibility, idempotency, exact rupee formatting | the core financial decision logic changed |
| `test_metrics.py` | summary math, exception ordering, precision/recall/false-auto/capture, scenario capture | evaluation math wrong → benchmark lies |
| `test_api_health.py` | `/health` contract, OpenAPI, **no premature domain routes**, no secrets in payload | API surface leaked or contract drifted |
| `test_data_generation.py` | 100 records, schemas, integer paise, scenario distribution, planted representations, **byte-identical regeneration**, engine-vs-ground-truth agreement | the benchmark dataset itself is broken |
| `test_end_to_end.py` | committed dataset hits the PRD §9 gate: exact status counts, precision/recall 1.0, variance = planted deltas, idempotent rerun | the shipped artifact no longer meets the success criteria |

## 4. Health endpoint

```bash
uvicorn backend.main:app --port 8000        # starts the service
# in another terminal:
curl -s http://localhost:8000/health
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health
```

**Expected:**

```json
{"status":"ok","service":"settlesense-backend","version":"0.7.0","environment":"local","timezone":"Asia/Kolkata"}
```

and `200`. Also open <http://localhost:8000/docs> — the documented surface is
exactly these eleven paths: `/health`, `/api/v1/batches`,
`/api/v1/batches/{batch_id}`, `/api/v1/batches/{batch_id}/results`,
`/api/v1/batches/{batch_id}/exceptions`,
`/api/v1/batches/{batch_id}/cash-position`,
`/api/v1/batches/{batch_id}/reconcile`, `/api/v1/batches/{batch_id}/metrics`,
`/api/v1/batches/{batch_id}/export`, `/api/v1/ai/query`,
`/api/v1/transactions/{payment_id}/trace`. Anything else = premature
surface (reconcile/metrics/export/trace/AI arrive in later phases
deliberately).

**Reconcile + metrics (phase 9):** `POST /api/v1/batches/{id}/reconcile` →
persists results + one audit event per decision atomically, idempotent on
rerun (results and events never duplicate); `GET …/metrics` → runtime totals
(match rate, variance, throughput) — honest `available: false` + note until
reconciled. **Batch API (phase 4):** `POST /api/v1/batches` (three multipart files, or
`?fixture=synthetic-v2`) → `201 validated`; identical re-upload → `200
idempotent: true`; `GET …/{batch_id}` → detail + audit events;
`GET …/results|exceptions?page=&page_size=&status=` → paginated (empty with
an honest `note` until reconciliation runs). All errors:
`{"error": {"code", "message"}}`.

**Cash position (phase 7):**
`GET /api/v1/batches/{batch_id}/cash-position?opening_balance_paise=…&horizon=7`
→ confirmed credits/debits, actual cash, pending settlements, expected cash,
variance (with `bank_charges_paise` breakout and
`unattributed_or_excluded_paise`), a day-by-day forecast labelled *not booked
cash*, assumptions, and `confidence` (high/medium/low). On the fixture:
`confidence: "low"` (duplicates + ambiguous cases exist), variance negative
(missing credits + mismatch deltas + ₹71 known bank charges).

**AI assistant (phase 8):**
`POST /api/v1/ai/query` with `{"batch_id": "...", "question": "..."}` — answers
are built ONLY from read-only backend tools (summary, exceptions by exposure,
cash position, payment trace, exception explain, description parsing); record
IDs and paise amounts are always cited; unknown questions get an honest
"needs human review" with nothing invented; missing batch → structured 404;
prompt injection inside bank descriptions is treated as data and cannot steer
answers; if the optional model layer is absent or times out, the
deterministic answer is served (`fallback: true`).

## 5. Dataset + determinism

```bash
python scripts/generate_data.py --out-dir data --seed 42
```

**Expected (manifest tail):** `"dataset_version": "synthetic-v2"`,
`"total_payments": 100`, scenario plan matching §6's table, and file line
counts ≈ `102 / 100 / 85 / 101` (ledger/settlements/bank/ground-truth,
duplicates included by design).

Determinism — same seed must produce byte-identical files:

```bash
python scripts/generate_data.py --out-dir /tmp/run_a --seed 42
python scripts/generate_data.py --out-dir /tmp/run_b --seed 42
diff -r /tmp/run_a /tmp/run_b && echo "DETERMINISTIC"
# Windows (PowerShell): Compare-Object (Get-ChildItem /tmp/run_a) (Get-ChildItem /tmp/run_b)
```

**Expected:** `DETERMINISTIC` (no diff output).
Different seed must change the data: repeat with `--seed 43` → `diff` shows
differences. (Both properties are also pinned by automated tests.)

## 6. Benchmark — the master check

```bash
python scripts/run_benchmark.py --data-dir data
```

**Expected output — memorize these five lines:**

```text
validation       : clean (0 skipped rows)
match rate       : 71.0%
auto matches     : 71 (correct 71, FALSE 0)
precision        : 100.0%
recall           : 100.0%
exception capture: 29/29 = 100.0%
status mismatches: none
```

Plus every scenario line in `scenario capture:` must read `n/n` (13
scenarios: adjustment 1/1, ambiguous_review 1/1, amount_mismatch 6/6,
clean 57/57, delayed_bank_credit 10/10, duplicate_bank 1/1,
duplicate_ledger 1/1, duplicate_settlement 1/1, missing_bank_credit 4/4,
missing_settlement 5/5, missing_utr 8/8, refund 2/2, same_amount_clean 3/3).

Also expected: `variance : total -150000 paise, max |single| 120000 paise` —
exactly the six planted deltas (−30000, −45000, −120000, +15000, −60000,
+90000). Processing time is machine-dependent (~tens of ms); only
`records_per_second > 0` matters for correctness.

**Any of these = broken, investigate before demoing:**
`FALSE 1` or more · `precision < 100%` · any scenario `< n/n` (shows a
`<-- MISS` marker) · `status mismatches` listing payment IDs · `SKIPPED ROWS`
in the validation line.

## 7. Money safety

Automated: `test_money.py` + the exact-formatting test in
`test_reconciliation.py` (`format_paise_as_rupees`).

Manual audit that no float arithmetic touches money:

```bash
grep -rn "/ 100" backend/ scripts/
# expected: only backend/reconciliation.py  rupees = format_paise_as_rupees(...)
# (a Decimal-based display helper) — plus throughput math in run_benchmark.py
# (records/second, not money)

grep -rn "float(" backend/ scripts/     # expected: no matches
```

All paise columns in the dataset must be unsigned integers:

```bash
# any output line = problem:
awk -F, 'NR>1 && $5 !~ /^[0-9]+$/ {print FILENAME": "$0}' data/internal_ledger.csv
```

## 8. Match safety

Automated proofs (`test_matching.py`, `test_reconciliation.py`): exact
payment-ID beats everything; amount+date-only evidence scores 0.35 (below
the 0.60 review floor) and can **never** auto-match; ambiguous pairs →
`NEEDS_HUMAN_REVIEW`; one bank entry claimed by two payments → both
downgraded (contested); prefix IDs (`setl_20` vs `setl_202`) don't
reference-match.

Manual spot-checks inside the benchmark output: `same_amount_clean 3/3`
(three identical amounts still reconcile by UTR) and `ambiguous_review 1/1`
(the unresolvable pair is honestly flagged, never force-matched).

## 9. Ground-truth isolation

```bash
grep -rn "ground_truth" backend/
# expected: ONLY backend/metrics.py (the evaluation function, docmarked
# "evaluation only") — no engine/service module reads it
```

And by construction the engine runs on three files only — see §11's snippet:
it passes exactly `internal_ledger.csv`, `settlements.csv`,
`bank_statement.csv`; ground truth enters only via
`scripts/run_benchmark.py`.

## 10. Idempotency

Automated: `test_rerun_is_idempotent` + `test_same_inputs_same_outputs`.
Manual:

```bash
python scripts/run_benchmark.py --data-dir data --json /tmp/r1.json
python scripts/run_benchmark.py --data-dir data --json /tmp/r2.json
python - <<'EOF'
import json
a = json.load(open("/tmp/r1.json")); b = json.load(open("/tmp/r2.json"))
print("IDEMPOTENT" if a["summary"] == b["summary"] else "DRIFT DETECTED")
EOF
```

**Expected:** `IDEMPOTENT` (timing fields live in `batch`, not `summary`, so
they don't pollute the comparison).

## 11. Single-payment deep dive

When someone asks "show me one mismatch end-to-end":

```bash
python - <<'EOF'
from pathlib import Path
from backend.ingestion import read_csv_source
from backend.models import Source
from backend.normalization import (normalize_bank_statement,
    normalize_internal_ledger, normalize_settlement_report)
from backend.reconciliation import reconcile_batch

d = Path("data")
r = lambda n, s: read_csv_source((d / n).read_text(), s)
out = reconcile_batch(
    normalize_internal_ledger(r("internal_ledger.csv", Source.INTERNAL_LEDGER)),
    normalize_settlement_report(r("settlements.csv", Source.SETTLEMENT_REPORT)),
    normalize_bank_statement(r("bank_statement.csv", Source.BANK_STATEMENT)))
by_id = {x.payment_id: x for x in out.results}

x = by_id["pay_010"]                      # a planted AMOUNT_MISMATCH
print(x.status.value)                     # AMOUNT_MISMATCH
print(x.variance_paise)                   # -30000  (bank ₹300 short)
print(x.expected_amount_paise, x.actual_amount_paise)
print(x.expected_breakdown_paise)         # the gross-to-net formula inputs
print(x.reason, "|", x.evidence)
EOF
```

**Expected:** status `AMOUNT_MISMATCH`, variance `-30000`, a breakdown dict
with all five waterfall components, and evidence listing
pay/settlement/UTR/bank IDs. Swap in other planted IDs (find them via
`awk -F, '$6=="scenario_name"' data/ground_truth.csv`): e.g. `refund`,
`duplicate_bank`, `ambiguous_review`, `missing_utr` rows.

## 12. Frontend

```bash
cd frontend
npm install
npm run build        # expected: "✓ built in ..." — no errors
npm run dev          # open http://localhost:5173 with the backend running (§4)
```

**Expected in browser:** the SettleSense shell with a green
**"Backend healthy — settlesense-backend v0.1.0"** banner and
environment/timezone values. Red "Backend unreachable" = backend not running
or not on port 8000 (the dashboard calls same-origin `/health` through the
Vite proxy — never a hardcoded host).

Note: `npm run preview` has **no** proxy — demo via `dev` or Docker instead.

## 13. Docker stack

```bash
docker compose up --build
curl -s http://localhost:8000/health      # same JSON as §4, environment "docker"
# dashboard: http://localhost:5173  (green banner)
docker compose down                        # data survives in the settlesense_data volume
```

**Expected:** backend container passes its healthcheck (compose waits for
it before starting the frontend), `/health` returns `environment: "docker"`.

## 14. If something fails

| Symptom | Meaning |
|---|---|
| `FALSE 1+` or precision < 100% | the engine auto-matched something it shouldn't — treat as release blocker |
| scenario `<-- MISS` | one planted error class is no longer detected — open `data/ground_truth.csv`, find that scenario's payments, run §11 on them |
| `status mismatches: pay_XXX expected A, actual B` | exactly which payment and which way it drifted |
| `SKIPPED ROWS` in validation | input rows are being quarantined — read the printed row/column/reason |
| `diff` shows changes in §5 | nondeterminism crept into the generator (check for wall-clock/`now()` usage) |
| `DRIFT DETECTED` in §10 | batch rerun changed results — idempotency broken |
| `/health` returns extra fields or routes | API contract drift vs `test_api_health.py` |
| green banner missing | frontend can't reach backend — check §4, ports, proxy |
| `ModuleNotFoundError: fastapi` | run `pip install -r requirements.txt` (fresh venv/session) |
| multipart upload smoke returns `HTTP 000` / curl exit 26 | the client could not READ the local CSV before sending — check the file exists (`ls data/`); in this sandbox the workspace file layer can transiently return ENOENT while background servers spawn. The API itself is covered by `tests/integration/test_batches.py`; retry, or test with `?fixture=synthetic-v2` which reads server-side |

**The one-command pre-demo smoke test:**

```bash
python -m pytest tests/ -q && python scripts/run_benchmark.py --data-dir data | tail -6
```

If that prints `110 passed` and the §6 five-line block, the system is
working as specified.
