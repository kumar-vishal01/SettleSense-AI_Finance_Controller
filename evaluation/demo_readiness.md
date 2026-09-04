# Demo Readiness Checklist — SettleSense

## Setup (5 minutes)
- [ ] `pip install -r requirements.txt && python -m pytest tests/ -q` → all pass
- [ ] `uvicorn backend.main:app --port 8000` → `curl localhost:8000/health` = ok
- [ ] `cd frontend && npm install && npm run dev` → dashboard at :5173, green "Backend healthy"
- [ ] (optional) paste Groq key into `.env` for the LLM wording layer; restart backend

## Demo script (upload → dashboard)
- [ ] Upload page → "Load synthetic-v2 fixture" → 284 rows validated, 0 skipped, 2 duplicates reported
- [ ] Auto-reconcile runs → Overview: 100 records · 71 reconciled · 29 exceptions · match 71%
- [ ] Overview cash cards: actual / expected / variance (bank charges ₹71 broken out)
- [ ] Results table: 10 columns, pagination, status filter (try AMOUNT_MISMATCH → 6 rows, red variance)
- [ ] Exceptions: filters work; top exposure ≈ ₹464k (pay_069, MISSING_BANK_CREDIT)
- [ ] Cash: forecast line dashed & labelled "NOT booked cash"; assumptions listed; confidence "low"
- [ ] Trace: `pay_010` → full chain with evidence IDs
- [ ] AI: "Which unresolved exception has the highest monetary impact?" → pay_069 + evidence; provider badge
- [ ] Export: results CSV opens in Excel/Sheets; row count = 100; money in paise

## Expected numbers (synthetic-v2, seed 42)
100 records · 71 FULLY_RECONCILED · 10 TIMING_DELAY · 6 AMOUNT_MISMATCH ·
5 MISSING_IN_SETTLEMENT · 4 MISSING_BANK_CREDIT · 3 DUPLICATE ·
1 NEEDS_HUMAN_REVIEW · total variance −₹1,500 · precision/recall 100% (benchmark only)

## If something breaks mid-demo
- AI question fails → deterministic fallback answers still serve (or provider=none)
- Backend down → dashboard shows red banner; restart uvicorn; batches are idempotent, nothing lost
- Wrong file uploaded → validation errors shown row-by-row; re-upload correct files
- Never claim reconciliation for a "validated"-only batch — the UI/API label it explicitly

## Talking points
paise-integer money · enforced score bands (thresholds cannot buy matches) ·
every exception visible with evidence · decision audit trail (one event per record) ·
ground truth never touches runtime · synthetic data notice always visible
