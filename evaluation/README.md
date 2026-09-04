# Evaluation — benchmark against ground truth

The benchmark compares **runtime reconciliation output** against the labeled
synthetic dataset. Ground truth influences nothing at runtime: the engine
reads only the three source CSVs (`internal_ledger.csv`, `settlements.csv`,
`bank_statement.csv`); `ground_truth.csv` is opened **only** by
`scripts/run_benchmark.py` and the evaluation tests
(`tests/evaluation/`) — verified structurally by
`test_ground_truth_never_enters_runtime_tables`.

## Run it

```bash
python scripts/generate_data.py --out-dir data --seed 42   # reproducible fixture
python scripts/run_benchmark.py --data-dir data --out-dir evaluation
```

Outputs: `evaluation/report.json` (machine contract) and
`evaluation/report.md` (human-readable, includes the full exception queue).
Reproducibility: same seed → byte-identical dataset → identical metrics
(timing fields aside).

## Metrics and their exact denominators

| # | Metric | Definition |
|---|---|---|
| 1 | Total logical records | unique payments decided by the engine |
| 2 | Records processed | results produced for those records |
| 3 | Correctly matched | auto-matches whose **linked settlement AND bank IDs** equal the labels |
| 4 | Automatic matches | runtime results flagged `FULLY_RECONCILED` (denominator of precision) |
| 5 | Match rate | fully_reconciled / total_records |
| 6 | Precision | correctly matched / automatic matches |
| 7 | Recall | correctly matched / ground-truth rows labeled `FULLY_RECONCILED` |
| 8 | Exception-capture rate | anomalies whose final status equals the label / ground-truth rows labeled with an exception status |
| 9 | Total monetary variance | Σ variance_paise over linked comparisons (signed) |
| 10 | Max monetary variance | max |variance| (absolute) |
| 11 | Processing time | ingest + normalize + reconcile wall time |
| 12 | Records per second | records processed / processing time |
| 13 | False automatic matches | **list** of wrong auto-matches: ID mismatches on linked settlement/bank, or auto-matching a labeled exception — reported separately from unresolved cases |
| 14 | Unresolved high-value cases | review-flagged records with exposure ≥ threshold (default 1,000,000 paise = ₹10,000), largest first. Exposure = \|variance\| for linked cases, expected amount when the money's whereabouts are unknown |

## False positives vs unresolved cases

- A **false positive** is a *decision error*: the engine claimed
  `FULLY_RECONCILED` and ground truth disagrees (wrong linked IDs, or the
  record was a planted anomaly). This number must stay at **0**; the
  benchmark never trades it for match rate.
- An **unresolved case** is an *honest exception*: the engine flagged it for
  review (`requires_review: true`). These are enumerated in full in
  `report.md`'s exception queue, never hidden, never force-matched.

## Safety invariants the benchmark protects

- thresholds are never lowered to improve the match rate
  (`test_default_thresholds_keep_reference_match_auto` pins band behavior);
- ambiguous amount twins stay in review even with deliberately loosened
  thresholds (negative control);
- precision 100% is required for the success gate — a single false
  automatic match fails the benchmark.
