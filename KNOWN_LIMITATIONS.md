# Known Limitations — SettleSense (honest list)

1. **Single currency (INR).** Non-INR ledger rows are rejected at ingestion;
   bank-side currency conflicts go to human review. Multi-currency needs
   explicit FX policy (ARCHITECTURE future work).
2. **SQLite, single writer.** Fine for the 50–1,000 record buildathon scale;
   PostgreSQL migration path is designed (schema is Postgres-compatible)
   but not exercised.
3. **No API authentication / rate limiting** on general endpoints (MVP
   decision); only the optional AI layer has a daily call cap.
4. **AI assistant**: deterministic by default; the Groq layer is an optional
   rephrasing service requiring a key in `.env`. Without it, answers are
   complete but plainly worded.
5. **Exception date filter** in the dashboard is partial (API has no date
   filter; the UI labels this and defers to trace).
6. **No REST trace route** (`/transactions/{payment_id}/trace` from the
   original design) — trace is served through the constrained AI surface.
7. **Transfer transaction type** has no distinct waterfall semantics yet
   (documented policy: aggregated as a generic row).
8. **Threshold tuning is manual**: score bands (0.95/0.80/0.60) are
   enforced and configurable, but no auto-tuning exists — by design
   (thresholds are never lowered to inflate match rate).
9. **Match rate is 71% on synthetic-v2** — that is the honest ceiling given
   29 deliberately planted anomalies; the quality metrics that matter
   (precision, exception capture) are 100%. Do not chase a higher match
   rate by loosening safety.
10. **Frontend has no component tests** (strict-tsc + build only); Docker
    images untested in this environment; no CI pipeline configured in the
    repo yet.
