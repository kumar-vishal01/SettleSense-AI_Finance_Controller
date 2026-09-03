"""Metrics and evaluation calculations only (AGENTS.md section 2).

Two strictly separated kinds of reporting:

1. ``summarize`` — runtime batch summary computed from results alone.
2. ``evaluate_against_ground_truth`` — benchmark evaluation. Ground truth
   is passed only by evaluation commands and never touches the runtime
   reconciliation engine (PRD.md section 7).
"""

from __future__ import annotations

from backend.statuses import SEVERITY_ORDER
from backend.models import (
    EXCEPTION_STATUSES,
    BatchSummary,
    EvaluationReport,
    ReconciliationResult,
    ReconciliationStatus,
)


def summarize(results: list[ReconciliationResult]) -> BatchSummary:
    """Aggregate one batch's results. Pure calculation over the result list.

    Denominators (runtime side — no ground truth involved):
    - match rate            = fully_reconciled / total_records
    - total records         = number of logical payments decided
    - records processed     = results produced by the engine for those records
      (equal to total records unless rows were skipped pre-engine)
    """
    total = len(results)
    status_counts: dict[str, int] = {s.value: 0 for s in ReconciliationStatus}
    for r in results:
        status_counts[r.status.value] += 1

    fully = status_counts[ReconciliationStatus.FULLY_RECONCILED.value]
    variances = [abs(r.variance_paise) for r in results if r.variance_paise is not None]
    signed_total = sum(r.variance_paise for r in results if r.variance_paise is not None)

    return BatchSummary(
        total_records=total,
        records_processed=total,
        fully_reconciled=fully,
        exceptions=total - fully,
        status_counts=status_counts,
        match_rate=round(fully / total, 4) if total else 0.0,
        total_variance_paise=signed_total,
        max_abs_variance_paise=max(variances) if variances else 0,
    )


def exception_queue(results: list[ReconciliationResult]) -> list[ReconciliationResult]:
    """All non-reconciled results, worst severity and largest exposure first."""
    exceptions = [r for r in results if r.status in EXCEPTION_STATUSES]
    return sorted(
        exceptions,
        key=lambda r: (
            SEVERITY_ORDER[r.severity.value],
            -(abs(r.variance_paise) if r.variance_paise is not None else 0),
            r.payment_id,
        ),
    )


# ---------------------------------------------------------------------------
# Ground-truth evaluation (benchmark commands only)
# ---------------------------------------------------------------------------


def evaluate_against_ground_truth(
    results: list[ReconciliationResult],
    ground_truth: list[dict[str, str]],
    dataset_version: str,
) -> EvaluationReport:
    """Compare results with labeled ground truth.

    EVALUATION ONLY — never called by the runtime reconciliation path.

    Denominators, exactly:
    - precision            = correct_auto_matches / auto_matches, where
                             auto_matches counts RUNTIME results flagged
                             FULLY_RECONCILED (regardless of labels).
    - recall               = correct_auto_matches / matchable_ground_truth,
                             where matchable_ground_truth counts ground-truth
                             rows labeled FULLY_RECONCILED.
    - match rate           (summarize) = fully_reconciled / total_records.
    - exception capture    = anomalies_correctly_stated / planted_anomalies,
                             where planted_anomalies counts ground-truth rows
                             labeled with any non-reconciled status.

    False positives (wrong auto-matches) are identified per record with the
    expected and actually-linked settlement/bank IDs — separated from
    unresolved cases, which are review-flagged runtime results enumerated by
    summarize()/exception_queue().
    """
    by_payment = {r.payment_id: r for r in results}
    auto_matches = [r for r in results if r.status is ReconciliationStatus.FULLY_RECONCILED]

    correct = 0
    false_auto: list[ReconciliationResult] = []
    false_positive_details: list[dict[str, str]] = []
    matchable = 0
    planted = 0
    captured = 0
    status_mismatches: list[dict[str, str]] = []
    scenario_totals: dict[str, int] = {}
    scenario_captured: dict[str, int] = {}

    for gt in ground_truth:
        payment_id = gt["payment_id"]
        scenario = gt.get("scenario", "")
        expected_status = ReconciliationStatus(gt["expected_status"])
        scenario_totals[scenario] = scenario_totals.get(scenario, 0) + 1
        result = by_payment.get(payment_id)
        if result is None:
            status_mismatches.append(
                {"payment_id": payment_id, "expected": expected_status.value, "actual": "MISSING_RESULT"}
            )
            continue

        if expected_status is ReconciliationStatus.FULLY_RECONCILED:
            matchable += 1
            ids_agree = (
                result.settlement_id == gt.get("expected_settlement_id") or not gt.get("expected_settlement_id")
            ) and (
                result.bank_txn_id == gt.get("expected_bank_txn_id") or not gt.get("expected_bank_txn_id")
            )
            if result.status is ReconciliationStatus.FULLY_RECONCILED and ids_agree:
                correct += 1
                scenario_captured[scenario] = scenario_captured.get(scenario, 0) + 1
            elif result.status is ReconciliationStatus.FULLY_RECONCILED:
                false_auto.append(result)
                false_positive_details.append({
                    "payment_id": payment_id,
                    "expected_status": expected_status.value,
                    "linked_settlement_id": result.settlement_id or "",
                    "expected_settlement_id": gt.get("expected_settlement_id", ""),
                    "linked_bank_txn_id": result.bank_txn_id or "",
                    "expected_bank_txn_id": gt.get("expected_bank_txn_id", ""),
                    "reason": "auto-matched with wrong linked IDs",
                })
        else:
            planted += 1
            if result.status is expected_status:
                captured += 1
                scenario_captured[scenario] = scenario_captured.get(scenario, 0) + 1

        if result.status is not expected_status:
            status_mismatches.append(
                {
                    "payment_id": payment_id,
                    "expected": expected_status.value,
                    "actual": result.status.value,
                }
            )

    # An auto-match against a row labeled as an anomaly is a false match.
    false_auto_ids = {r.payment_id for r in false_auto}
    for gt in ground_truth:
        pid = gt["payment_id"]
        r = by_payment.get(pid)
        if (
            r is not None
            and r.status is ReconciliationStatus.FULLY_RECONCILED
            and ReconciliationStatus(gt["expected_status"]) is not ReconciliationStatus.FULLY_RECONCILED
        ):
            false_auto_ids.add(pid)
            false_positive_details.append({
                "payment_id": pid,
                "expected_status": gt["expected_status"],
                "linked_settlement_id": r.settlement_id or "",
                "expected_settlement_id": gt.get("expected_settlement_id", ""),
                "linked_bank_txn_id": r.bank_txn_id or "",
                "expected_bank_txn_id": gt.get("expected_bank_txn_id", ""),
                "reason": "auto-matched an expected exception",
            })

    return EvaluationReport(
        dataset_version=dataset_version,
        total_ground_truth=len(ground_truth),
        auto_matches=len(auto_matches),
        correct_auto_matches=correct,
        false_auto_matches=len(false_auto_ids),
        precision=round(correct / len(auto_matches), 4) if auto_matches else 0.0,
        recall=round(correct / matchable, 4) if matchable else 0.0,
        matchable_ground_truth=matchable,
        planted_anomalies=planted,
        anomalies_correctly_stated=captured,
        exception_capture_rate=round(captured / planted, 4) if planted else 0.0,
        status_mismatches=status_mismatches,
        scenario_totals=scenario_totals,
        scenario_captured=scenario_captured,
        false_positive_details=false_positive_details,
    )

def high_value_unresolved(
    results: list, threshold_paise: int = 1_000_000
) -> list[dict]:
    """Review-flagged cases ranked by monetary exposure (paise).

    Exposure definition (documented, deterministic):
    - |variance| for linked comparisons (bank credit vs expected net)
    - expected_amount otherwise (money whose whereabouts are unknown — a
      missing credit exposes the full expected amount)

    A case enters the queue when exposure >= threshold_paise (default
    INR 10,000). Returned largest-first.
    """
    queue = []
    for r in results:
        if not r.requires_review:
            continue
        exposure = (
            abs(r.variance_paise) if r.variance_paise is not None
            else r.expected_amount_paise
        )
        if exposure is None or exposure < threshold_paise:
            continue
        queue.append({
            "payment_id": r.payment_id,
            "status": r.status.value,
            "severity": r.severity.value,
            "exposure_paise": exposure,
            "variance_paise": r.variance_paise,
            "expected_amount_paise": r.expected_amount_paise,
            "reason": r.reason,
            "requires_review": True,
        })
    queue.sort(key=lambda c: (-c["exposure_paise"], c["payment_id"]))
    return queue
