"""Reconcile + metrics API (phase 9): closes review finding M1.

POST /reconcile persists the engine's decisions AND one audit event per
decision in a single database transaction — a crash mid-write leaves no
half-reconciled batch. Re-running is idempotent: results and events are
never duplicated.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from backend.config import ReconciliationConfig
from backend.database import Database
from backend.models import BatchStatus, Source
from backend.reconciliation import compute_as_of, reconcile_batch
from backend.repositories import (
    AuditRepository,
    BankEntryRepository,
    BatchRepository,
    ReconciliationResultRepository,
    TransactionRepository,
)
from backend.routes.batches import get_database
from backend.schemas import ErrorResponse
from backend.statuses import severity_for
from backend.calculations import aggregate_settlement_group

from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/batches", tags=["reconcile"])


class ReconcileSummary(BaseModel):
    status_counts: dict[str, int]
    fully_reconciled: int
    exceptions: int
    match_rate: float
    total_variance_paise: int


class ReconcileResponse(BaseModel):
    batch_id: str
    status: str
    idempotent: bool
    result_count: int
    summary: ReconcileSummary
    processing_time_ms: float


class MetricsResponse(BaseModel):
    available: bool
    note: str | None = None
    total_records: int = 0
    records_processed: int = 0
    fully_reconciled: int = 0
    exceptions: int = 0
    match_rate: float = 0.0
    status_counts: dict[str, int] = Field(default_factory=dict)
    total_variance_paise: int = 0
    max_abs_variance_paise: int = 0
    processing_time_ms: float = 0.0
    records_per_second: float = 0.0


@router.post(
    "/{batch_id}/reconcile",
    response_model=ReconcileResponse,
    responses={404: {"model": ErrorResponse, "description": "unknown batch"}},
)
def reconcile(batch_id: str, db: Database = Depends(get_database)) -> ReconcileResponse:
    conn = db.connect(init=False)
    try:
        batch = BatchRepository(conn).find_by_id(batch_id)
        if batch is None:
            raise HTTPException(404, detail={
                "code": "batch_not_found",
                "message": f"no batch with id {batch_id!r}"})
        if batch["status"] == BatchStatus.RECONCILED.value:
            counts = ReconciliationResultRepository(conn).status_counts(batch_id)
            variance = _total_variance(conn, batch_id)
            return _summary_response(batch_id, counts, variance, idempotent=True,
                                     processing_ms=0.0)
        transactions = TransactionRepository(conn).list_canonical(batch_id)
        bank = BankEntryRepository(conn).list_canonical(batch_id)
    finally:
        conn.close()

    ledger = [t for t in transactions if t.source is Source.INTERNAL_LEDGER]
    settlements = [t for t in transactions if t.source is Source.SETTLEMENT_REPORT]
    order_ids = {t.payment_id: t.order_id for t in ledger if t.payment_id}

    started = time.perf_counter()
    if ledger or settlements or bank:
        outcome = reconcile_batch(ledger, settlements, bank, ReconciliationConfig())
    else:
        outcome = None  # empty batch: nothing to compute, no as_of fabricated
    processing_ms = round((time.perf_counter() - started) * 1000, 1)

    conn = db.connect(init=False)
    try:
        with conn:  # results + per-decision audit + status flip: all-or-nothing
            results_repo = ReconciliationResultRepository(conn)
            results_repo.insert_many(
                batch_id, outcome.results if outcome else [], order_ids)
            audit = AuditRepository(conn)
            for r in (outcome.results if outcome else []):
                audit.append(
                    batch_id=batch_id,
                    record_id=r.payment_id,
                    action="result_recorded",
                    actor="engine",
                    details={
                        "status": r.status.value,
                        "confidence": r.confidence,
                        "match_method": r.match_method,
                        "variance_paise": r.variance_paise,
                        "evidence": r.evidence,
                    },
                )
            counts = results_repo.status_counts(batch_id)
            audit.append(
                batch_id=batch_id,
                record_id=batch_id,
                action="batch_reconciled",
                actor="engine",
                details={
                    "result_count": len(outcome.results) if outcome else 0,
                    "processing_time_ms": processing_ms,
                    "records_per_second": round(
                        (len(outcome.results) if outcome else 0) / (processing_ms / 1000), 1)
                    if processing_ms else 0.0,
                    "status_counts": counts,
                },
            )
            BatchRepository(conn).mark_reconciled(batch_id, _utc_now_iso())
    finally:
        conn.close()
    # Read the persisted results, not the in-memory outcome, so the response
    # is exactly consistent with what was committed.
    conn = db.connect(init=False)
    try:
        variance = _total_variance(conn, batch_id)
    finally:
        conn.close()
    return _summary_response(batch_id, counts, variance, idempotent=False,
                             processing_ms=processing_ms)


def _total_variance(conn, batch_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(variance_paise), 0) AS total "
        "FROM reconciliation_results WHERE batch_id = ?",
        (batch_id,),
    ).fetchone()
    return int(row["total"] or 0)


def _summary_response(batch_id: str, counts: dict[str, int], total_variance_paise: int, *,
                      idempotent: bool, processing_ms: float) -> ReconcileResponse:
    total = sum(counts.values())
    fully = counts.get("FULLY_RECONCILED", 0)
    return ReconcileResponse(
        batch_id=batch_id,
        status="reconciled",
        idempotent=idempotent,
        result_count=total,
        summary=ReconcileSummary(
            status_counts=counts,
            fully_reconciled=fully,
            exceptions=total - fully,
            match_rate=round(fully / total, 4) if total else 0.0,
            total_variance_paise=total_variance_paise,
        ),
        processing_time_ms=processing_ms,
    )


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@router.get(
    "/{batch_id}/metrics",
    response_model=MetricsResponse,
    responses={404: {"model": ErrorResponse, "description": "unknown batch"}},
)
def get_metrics(batch_id: str, db: Database = Depends(get_database)) -> MetricsResponse:
    conn = db.connect(init=False)
    try:
        batch = BatchRepository(conn).find_by_id(batch_id)
        if batch is None:
            raise HTTPException(404, detail={
                "code": "batch_not_found",
                "message": f"no batch with id {batch_id!r}"})
        results_repo = ReconciliationResultRepository(conn)
        counts = results_repo.status_counts(batch_id)
        detail = BatchRepository(conn).find_audit_detail(batch_id, "batch_reconciled")
        if detail is None:
            return MetricsResponse(
                available=False,
                note="batch has not been reconciled yet; run POST "
                     f"/api/v1/batches/{batch_id}/reconcile first",
            )
        rows = conn.execute(
            "SELECT variance_paise FROM reconciliation_results WHERE batch_id = ? "
            "AND variance_paise IS NOT NULL", (batch_id,)).fetchall()
    finally:
        conn.close()

    total = sum(counts.values())
    fully = counts.get("FULLY_RECONCILED", 0)
    variances = [r["variance_paise"] for r in rows]
    return MetricsResponse(
        available=True,
        total_records=total,
        records_processed=total,
        fully_reconciled=fully,
        exceptions=total - fully,
        match_rate=round(fully / total, 4) if total else 0.0,
        status_counts=counts,
        total_variance_paise=sum(variances),
        max_abs_variance_paise=max((abs(v) for v in variances), default=0),
        processing_time_ms=detail.get("processing_time_ms", 0.0),
        records_per_second=detail.get("records_per_second", 0.0),
    )
