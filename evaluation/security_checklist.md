# Security & Privacy Checklist — SettleSense

| Area | Control | Status |
|---|---|---|
| Secrets in repo | `git grep` for token/key patterns; `.env` untracked (verified); keys only in env/.env at runtime | ✅ |
| Browser secrets | no keys/absolute hosts in `frontend/src` (scan clean); same-origin relative URLs only | ✅ |
| Upload size | per-file byte cap enforced BEFORE full read (413), plus ingestion-level caps | ✅ tested |
| Upload content | UTF-8 validation, null-byte rejection, CSV formula-injection prefixes (= + - @ tab), row caps | ✅ tested |
| Filename handling | sanitized to basename + length cap; never used as a path | ✅ |
| Path traversal | server fixture is a fixed slug whitelist (`../../etc` → 422) | ✅ tested |
| SQL injection | all queries parameterized; no string-built SQL | ✅ |
| Error leakage | unified envelope; 500s carry no stack/paths; key excluded from provider errors (tested) | ✅ |
| CORS | wildcard rejected outside local env (fail-fast) | ✅ tested |
| Ground-truth isolation | engine/service grep-clean; metrics endpoint asserts no precision/recall; runtime Docker image excludes ground_truth.csv | ✅ |
| AI safety | tools read-only (DB-hash test); rephrase evidence guard (IDs/amounts/statuses); injection-as-data; timeout/cap fallback | ✅ tested |
| Financial safety | no route writes ledger/settlement/bank/accounting tables (reconcile writes derived + audit tables only) | ✅ verified |
| PII | synthetic data only; no real customer/bank data anywhere | ✅ |
| Not yet done | API authentication (none by MVP decision), rate limiting beyond the AI daily cap, dependency lockfile, dependency CVE audit | ⚠ see KNOWN_LIMITATIONS |
