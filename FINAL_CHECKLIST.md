# Final Checklist — Razorpay AI Buildathon Demo

Every row below was verified in this repository at phase-10 close (`7f8b4ae`+).

## Verification tasks

| # | Task | Status | Evidence |
|---|---|---|---|
| 1 | README setup instructions from clean environment | ✅ | fresh `pip install -r requirements.txt` → suite green; frontend `npm install && npm run dev` verified |
| 2 | Synthetic data generation reproducible | ✅ | `generate_data.py --seed 42` regenerated → **byte-identical** to committed fixture |
| 3 | Batch upload | ✅ | 284 rows validated, 0 skipped, 2 duplicates reported; multipart + fixture paths live |
| 4 | Reconciliation | ✅ | 100 results, ~90 ms, idempotent rerun (zero duplication, audit parity 100) |
| 5 | Benchmark metrics | ✅ | match 71% · precision 100% · recall 100% · 0 false auto-matches · capture 29/29 · variance −150,000 paise (`evaluation/report.md`) |
| 6 | Cash-position view | ✅ | confirmed ₹1,84,44,593.48 · pending ₹30,31,506.25 · forecast separate + "NOT booked" · confidence low · charges broken out |
| 7 | Exception queue | ✅ | 29 visible with status/severity/exposure/reason/action; filters work |
| 8 | AI Q&A | ✅ | "highest monetary impact" → pay_069 with evidence IDs via `list_exceptions`; injection-safe; fallback tested |
| 9 | Export | ✅ | CSV (100 rows, integer paise, evidence column) + JSON scope; byte-identical repeats; headers-only before reconcile |
| 10 | Docker setup | ✅ config / ⚠ unexercised | compose parses (backend+frontend, healthcheck, persistent volume); no Docker daemon in this environment — review-verified only |
| 11 | No secrets or real financial data | ✅ | token/key pattern grep clean; `.env` untracked; dataset synthetic-only (manifest says so) |
| 12 | Demo script with exact commands | ✅ | [DEMO.md](DEMO.md) |
| 13 | Five-minute presentation script | ✅ | [DEMO.md](DEMO.md) (timed beats 0:00–4:30) |
| 14 | Known-limitations section | ✅ | [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) |

## Required demo beats — all present

- [x] Complete 100-record batch (284 source rows)
- [x] Processing time (~90 ms; >1,000 rec/s)
- [x] Match rate (71%)
- [x] Auto-match quality (precision 100%, 0 false matches — benchmark)
- [x] Total monetary variance (−₹1,500, exactly the planted deltas)
- [x] At least one unresolved exception (29 shown)
- [x] One high-value exception trace (pay_069, ₹4,64,175.68 exposure)
- [x] One AI answer with record evidence (pay_069 + evidence IDs)
- [x] Confirmed vs pending vs forecast cash clearly separated

## Honest notes

- Match rate 71% is the honest ceiling for this dataset (29 planted
  anomalies). Precision and exception capture — the safety metrics — are
  100%. Recommendation stands: do NOT raise match rate by loosening
  thresholds.
- Docker (task 10) and browser-level UI tests are the only items not
  exercised end-to-end in this environment; both are config/pipeline
  verified and flagged in KNOWN_LIMITATIONS.md.
