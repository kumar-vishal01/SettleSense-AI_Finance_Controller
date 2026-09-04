"""Benchmark evaluation: runtime reconciliation vs ground truth.

Ground truth is loaded HERE and ONLY HERE (plus the evaluation tests) —
never by the runtime engine (PRD section 7; verified by
tests/evaluation/test_benchmark.py).

Usage:
    python scripts/run_benchmark.py [--data-dir data] [--out-dir evaluation]
                                    [--seed-note] [--high-value-paise N]

Outputs (when --out-dir is given, default ``evaluation`` from the CLI):
    <out>/report.json — machine-readable, full metric contract
    <out>/report.md   — human-readable incl. the full exception queue
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:  # allow direct `python scripts/run_benchmark.py`
    sys.path.insert(0, str(_ROOT))

from backend.config import ReconciliationConfig
from backend.ingestion import read_csv_source
from backend.metrics import (
    evaluate_against_ground_truth,
    exception_queue,
    high_value_unresolved,
    summarize,
)
from backend.models import Source
from backend.normalization import (
    normalize_bank_statement,
    normalize_internal_ledger,
    normalize_settlement_report,
)
from backend.reconciliation import reconcile_batch

#: default high-value exposure threshold for the unresolved queue (INR 10k)
DEFAULT_HIGH_VALUE_PAISE = 1_000_000


def load_ground_truth(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run_benchmark(
    data_dir: Path, out_dir: Path | None = None, high_value_paise: int = DEFAULT_HIGH_VALUE_PAISE
) -> dict:
    """Run the full pipeline + evaluation and (optionally) write artifacts.

    Returns the flat metric contract dict (see evaluation/README.md for
    every field and its denominator).
    """
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))

    started = time.perf_counter()

    ledger_table = read_csv_source((data_dir / "internal_ledger.csv").read_text(), Source.INTERNAL_LEDGER)
    settlement_table = read_csv_source((data_dir / "settlements.csv").read_text(), Source.SETTLEMENT_REPORT)
    bank_table = read_csv_source((data_dir / "bank_statement.csv").read_text(), Source.BANK_STATEMENT)

    ledger = normalize_internal_ledger(ledger_table)
    settlements = normalize_settlement_report(settlement_table)
    bank = normalize_bank_statement(bank_table)

    outcome = reconcile_batch(ledger, settlements, bank, ReconciliationConfig())
    processing_ms = (time.perf_counter() - started) * 1000

    summary = summarize(outcome.results)
    ground_truth = load_ground_truth(data_dir / "ground_truth.csv")
    evaluation = evaluate_against_ground_truth(
        outcome.results, ground_truth, manifest["dataset_version"]
    )

    tables = (ledger_table, settlement_table, bank_table)
    exceptions = [
        {
            "payment_id": r.payment_id,
            "status": r.status.value,
            "severity": r.severity.value,
            "variance_paise": r.variance_paise,
            "expected_amount_paise": r.expected_amount_paise,
            "reason": r.reason,
            "evidence": r.evidence,
        }
        for r in exception_queue(outcome.results)
    ]

    report = {
        "dataset_version": manifest["dataset_version"],
        "seed": manifest["seed"],
        # -- the metric contract (denominators in evaluation/README.md) --
        "total_records": summary.total_records,
        "records_processed": summary.records_processed,
        "correctly_matched": evaluation.correct_auto_matches,
        "automatic_matches": evaluation.auto_matches,
        "match_rate": summary.match_rate,
        "precision": evaluation.precision,
        "recall": evaluation.recall,
        "exception_capture_rate": evaluation.exception_capture_rate,
        "monetary_variance_paise": summary.total_variance_paise,
        "max_monetary_variance_paise": summary.max_abs_variance_paise,
        "processing_time_ms": round(processing_ms, 1),
        "records_per_second": round(
            summary.records_processed / (processing_ms / 1000), 1
        ),
        "false_automatic_matches": evaluation.false_positive_details,
        "unresolved_high_value_cases": high_value_unresolved(
            outcome.results, high_value_paise
        ),
        "high_value_threshold_paise": high_value_paise,
        # -- supporting detail --
        "status_counts": summary.status_counts,
        "exception_count": summary.exceptions,
        "scenario_capture": {
            scenario: {
                "captured": evaluation.scenario_captured.get(scenario, 0),
                "total": evaluation.scenario_totals[scenario],
            }
            for scenario in sorted(evaluation.scenario_totals)
        },
        "status_mismatches": evaluation.status_mismatches,
        "validation": {
            "skipped_rows": sum(t.skipped_rows for t in tables),
            "errors": [e.to_dict() for t in tables for e in t.errors][:10],
        },
        "exceptions": exceptions,
        "source_rows": {
            "ledger": outcome.ledger_row_count,
            "settlements": outcome.settlement_row_count,
            "bank": outcome.bank_row_count,
        },
    }

    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8")
        (out_dir / "report.md").write_text(
            _markdown_report(report), encoding="utf-8")
    return report


def _markdown_report(r: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("# SettleSense Benchmark Report")
    add("")
    add(f"Dataset `{r['dataset_version']}` · seed `{r['seed']}` · "
        f"source rows {r['source_rows']['ledger']} ledger + "
        f"{r['source_rows']['settlements']} settlement + "
        f"{r['source_rows']['bank']} bank")
    add("")

    add("## Metrics")
    add("")
    add("| Metric | Value |")
    add("|---|---|")
    rows = [
        ("Total logical records", r["total_records"]),
        ("Records processed", r["records_processed"]),
        ("Correctly matched", r["correctly_matched"]),
        ("Automatic matches", r["automatic_matches"]),
        ("Match rate", f"{r['match_rate']:.1%}"),
        ("Automatic-match precision", f"{r['precision']:.1%}"),
        ("Automatic-match recall", f"{r['recall']:.1%}"),
        ("Exception-capture rate", f"{r['exception_capture_rate']:.1%}"),
        ("Total monetary variance (paise)", r["monetary_variance_paise"]),
        ("Max monetary variance (paise)", r["max_monetary_variance_paise"]),
        ("Processing time", f"{r['processing_time_ms']} ms"),
        ("Records per second", r["records_per_second"]),
        ("False automatic matches", len(r["false_automatic_matches"])),
        ("Unresolved high-value cases", len(r["unresolved_high_value_cases"])),
        ("Validation skipped rows", r["validation"]["skipped_rows"]),
    ]
    for name, value in rows:
        add(f"| {name} | {value} |")
    add("")

    add("## Denominators")
    add("")
    add("- **Match rate** = fully_reconciled / total_records (runtime only)")
    add("- **Precision** = correct_auto_matches / automatic_matches "
        "(automatic_matches = runtime results flagged FULLY_RECONCILED)")
    add("- **Recall** = correct_auto_matches / ground-truth rows labeled "
        "FULLY_RECONCILED")
    add("- **Exception capture** = anomalies with the labeled status / "
        "ground-truth rows labeled with an exception status")
    add("- **High-value threshold** = "
        f"{r['high_value_threshold_paise']} paise exposure "
        "(|variance| for linked cases; expected amount for missing ones)")
    add("")

    add("## Scenario capture")
    add("")
    add("| Scenario | Captured |")
    add("|---|---|")
    for scenario, s in r["scenario_capture"].items():
        marker = "" if s["captured"] == s["total"] else " ⚠ MISS"
        add(f"| {scenario} | {s['captured']}/{s['total']}{marker} |")
    add("")

    add("## False automatic matches")
    add("")
    if r["false_automatic_matches"]:
        add("| payment | expected | linked setl (expected) | linked bank (expected) | reason |")
        add("|---|---|---|---|---|")
        for fp in r["false_automatic_matches"]:
            add(f"| {fp['payment_id']} | {fp['expected_status']} | "
                f"{fp['linked_settlement_id']} ({fp['expected_settlement_id']}) | "
                f"{fp['linked_bank_txn_id']} ({fp['expected_bank_txn_id']}) | "
                f"{fp['reason']} |")
    else:
        add("None — every automatic match agrees with ground truth.")
    add("")

    add("## Status mismatches")
    add("")
    if r["status_mismatches"]:
        for m in r["status_mismatches"]:
            add(f"- {m['payment_id']}: expected {m['expected']}, got {m['actual']}")
    else:
        add("None — all 100 predicted statuses equal the labeled statuses.")
    add("")

    add("## Exception queue")
    add("")
    add("All review-flagged records, worst severity and largest exposure first.")
    add("")
    add("| Payment | Status | Severity | Variance (paise) | Reason |")
    add("|---|---|---|---|---|")
    for e in r["exceptions"]:
        add(f"| {e['payment_id']} | {e['status']} | {e['severity']} | "
            f"{e['variance_paise'] if e['variance_paise'] is not None else '—'} | "
            f"{e['reason']} |")
    add("")

    add("## High-value unresolved cases")
    add("")
    if r["unresolved_high_value_cases"]:
        add(f"Exposure ≥ {r['high_value_threshold_paise']} paise, largest first.")
        add("")
        add("| Payment | Status | Exposure (paise) | Reason |")
        add("|---|---|---|---|")
        for c in r["unresolved_high_value_cases"]:
            add(f"| {c['payment_id']} | {c['status']} | {c['exposure_paise']} | "
                f"{c['reason']} |")
    else:
        add("None at the configured threshold.")
    add("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SettleSense benchmark")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="evaluation")
    parser.add_argument("--high-value-paise", type=int, default=DEFAULT_HIGH_VALUE_PAISE)
    args = parser.parse_args()

    report = run_benchmark(
        Path(args.data_dir), Path(args.out_dir), args.high_value_paise)
    e = report
    print(f"records {e['total_records']} | match {e['match_rate']:.0%} | "
          f"precision {e['precision']:.1%} | recall {e['recall']:.1%} | "
          f"capture {e['exception_capture_rate']:.0%} | "
          f"FALSE {len(e['false_automatic_matches'])} | "
          f"variance {e['monetary_variance_paise']} paise | "
          f"{e['records_per_second']} rec/s")
    print(f"artifacts: {args.out_dir}/report.json, {args.out_dir}/report.md")


if __name__ == "__main__":
    main()
