# SettleSense Benchmark Report

Dataset `synthetic-v2` · seed `42` · source rows 101 ledger + 99 settlement + 84 bank

## Metrics

| Metric | Value |
|---|---|
| Total logical records | 100 |
| Records processed | 100 |
| Correctly matched | 71 |
| Automatic matches | 71 |
| Match rate | 71.0% |
| Automatic-match precision | 100.0% |
| Automatic-match recall | 100.0% |
| Exception-capture rate | 100.0% |
| Total monetary variance (paise) | -150000 |
| Max monetary variance (paise) | 120000 |
| Processing time | 93.5 ms |
| Records per second | 1070.0 |
| False automatic matches | 0 |
| Unresolved high-value cases | 22 |
| Validation skipped rows | 0 |

## Denominators

- **Match rate** = fully_reconciled / total_records (runtime only)
- **Precision** = correct_auto_matches / automatic_matches (automatic_matches = runtime results flagged FULLY_RECONCILED)
- **Recall** = correct_auto_matches / ground-truth rows labeled FULLY_RECONCILED
- **Exception capture** = anomalies with the labeled status / ground-truth rows labeled with an exception status
- **High-value threshold** = 1000000 paise exposure (|variance| for linked cases; expected amount for missing ones)

## Scenario capture

| Scenario | Captured |
|---|---|
| adjustment | 1/1 |
| ambiguous_review | 1/1 |
| amount_mismatch | 6/6 |
| clean | 57/57 |
| delayed_bank_credit | 10/10 |
| duplicate_bank | 1/1 |
| duplicate_ledger | 1/1 |
| duplicate_settlement | 1/1 |
| missing_bank_credit | 4/4 |
| missing_settlement | 5/5 |
| missing_utr | 8/8 |
| refund | 2/2 |
| same_amount_clean | 3/3 |

## False automatic matches

None — every automatic match agrees with ground truth.

## Status mismatches

None — all 100 predicted statuses equal the labeled statuses.

## Exception queue

All review-flagged records, worst severity and largest exposure first.

| Payment | Status | Severity | Variance (paise) | Reason |
|---|---|---|---|---|
| pay_027 | AMOUNT_MISMATCH | high | -120000 | UTR matched, but bank credit is INR 1200.00 lower than the expected net (bank entry bank_027) |
| pay_003 | MISSING_BANK_CREDIT | high | — | no bank credit found and settlement is 5 days old (beyond the delay window) |
| pay_018 | MISSING_BANK_CREDIT | high | — | no bank credit found and settlement is 5 days old (beyond the delay window) |
| pay_029 | MISSING_IN_SETTLEMENT | high | — | no settlement row matches the payment by payment_id or order_id |
| pay_039 | MISSING_IN_SETTLEMENT | high | — | no settlement row matches the payment by payment_id or order_id |
| pay_069 | MISSING_BANK_CREDIT | high | — | no bank credit found and settlement is 6 days old (beyond the delay window) |
| pay_072 | DUPLICATE | high | — | settlement entity_id(s) ent_072 appear more than once in the settlement report |
| pay_074 | DUPLICATE | high | — | payment_id appears 2 times in the internal ledger (rows: int_074, int_074_dup) |
| pay_076 | MISSING_BANK_CREDIT | high | — | no bank credit found and settlement is 5 days old (beyond the delay window) |
| pay_079 | MISSING_IN_SETTLEMENT | high | — | no settlement row matches the payment by payment_id or order_id |
| pay_084 | MISSING_IN_SETTLEMENT | high | — | no settlement row matches the payment by payment_id or order_id |
| pay_091 | MISSING_IN_SETTLEMENT | high | — | no settlement row matches the payment by payment_id or order_id |
| pay_097 | DUPLICATE | high | — | bank statement contains repeated rows for this settlement's reference (bank_097) |
| pay_100 | AMOUNT_MISMATCH | medium | 90000 | UTR matched, but bank credit is INR 900.00 higher than the expected net (bank entry bank_100) |
| pay_067 | AMOUNT_MISMATCH | medium | -60000 | UTR matched, but bank credit is INR 600.00 lower than the expected net (bank entry bank_067) |
| pay_025 | AMOUNT_MISMATCH | medium | -45000 | UTR matched, but bank credit is INR 450.00 lower than the expected net (bank entry bank_025) |
| pay_010 | AMOUNT_MISMATCH | medium | -30000 | UTR matched, but bank credit is INR 300.00 lower than the expected net (bank entry bank_010) |
| pay_065 | AMOUNT_MISMATCH | medium | 15000 | UTR matched, but bank credit is INR 150.00 higher than the expected net (bank entry bank_065) |
| pay_005 | TIMING_DELAY | medium | — | settled 0 day(s) before batch as_of; credit plausibly still in transit |
| pay_034 | TIMING_DELAY | medium | — | settled 2 day(s) before batch as_of; credit plausibly still in transit |
| pay_046 | TIMING_DELAY | medium | — | settled 0 day(s) before batch as_of; credit plausibly still in transit |
| pay_047 | TIMING_DELAY | medium | — | settled 1 day(s) before batch as_of; credit plausibly still in transit |
| pay_048 | TIMING_DELAY | medium | — | settled 0 day(s) before batch as_of; credit plausibly still in transit |
| pay_051 | NEEDS_HUMAN_REVIEW | medium | — | 2 bank entries are plausible on amount and date alone; no identifier evidence distinguishes them |
| pay_058 | TIMING_DELAY | medium | — | settled 0 day(s) before batch as_of; credit plausibly still in transit |
| pay_060 | TIMING_DELAY | medium | — | settled 1 day(s) before batch as_of; credit plausibly still in transit |
| pay_064 | TIMING_DELAY | medium | — | settled 1 day(s) before batch as_of; credit plausibly still in transit |
| pay_081 | TIMING_DELAY | medium | — | settled 1 day(s) before batch as_of; credit plausibly still in transit |
| pay_090 | TIMING_DELAY | medium | — | settled 0 day(s) before batch as_of; credit plausibly still in transit |

## High-value unresolved cases

Exposure ≥ 1000000 paise, largest first.

| Payment | Status | Exposure (paise) | Reason |
|---|---|---|---|
| pay_069 | MISSING_BANK_CREDIT | 46417568 | no bank credit found and settlement is 6 days old (beyond the delay window) |
| pay_097 | DUPLICATE | 44773408 | bank statement contains repeated rows for this settlement's reference (bank_097) |
| pay_072 | DUPLICATE | 44166700 | settlement entity_id(s) ent_072 appear more than once in the settlement report |
| pay_034 | TIMING_DELAY | 41414202 | settled 2 day(s) before batch as_of; credit plausibly still in transit |
| pay_058 | TIMING_DELAY | 41386765 | settled 0 day(s) before batch as_of; credit plausibly still in transit |
| pay_090 | TIMING_DELAY | 40689029 | settled 0 day(s) before batch as_of; credit plausibly still in transit |
| pay_018 | MISSING_BANK_CREDIT | 40263417 | no bank credit found and settlement is 5 days old (beyond the delay window) |
| pay_064 | TIMING_DELAY | 38166402 | settled 1 day(s) before batch as_of; credit plausibly still in transit |
| pay_081 | TIMING_DELAY | 35787892 | settled 1 day(s) before batch as_of; credit plausibly still in transit |
| pay_084 | MISSING_IN_SETTLEMENT | 34202700 | no settlement row matches the payment by payment_id or order_id |
| pay_029 | MISSING_IN_SETTLEMENT | 31269900 | no settlement row matches the payment by payment_id or order_id |
| pay_005 | TIMING_DELAY | 30628692 | settled 0 day(s) before batch as_of; credit plausibly still in transit |
| pay_051 | NEEDS_HUMAN_REVIEW | 26713035 | 2 bank entries are plausible on amount and date alone; no identifier evidence distinguishes them |
| pay_060 | TIMING_DELAY | 25405538 | settled 1 day(s) before batch as_of; credit plausibly still in transit |
| pay_003 | MISSING_BANK_CREDIT | 20543456 | no bank credit found and settlement is 5 days old (beyond the delay window) |
| pay_074 | DUPLICATE | 19975900 | payment_id appears 2 times in the internal ledger (rows: int_074, int_074_dup) |
| pay_048 | TIMING_DELAY | 17049604 | settled 0 day(s) before batch as_of; credit plausibly still in transit |
| pay_047 | TIMING_DELAY | 16901777 | settled 1 day(s) before batch as_of; credit plausibly still in transit |
| pay_091 | MISSING_IN_SETTLEMENT | 16154000 | no settlement row matches the payment by payment_id or order_id |
| pay_046 | TIMING_DELAY | 15720724 | settled 0 day(s) before batch as_of; credit plausibly still in transit |
| pay_079 | MISSING_IN_SETTLEMENT | 8896900 | no settlement row matches the payment by payment_id or order_id |
| pay_076 | MISSING_BANK_CREDIT | 2763896 | no bank credit found and settlement is 5 days old (beyond the delay window) |
