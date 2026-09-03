"""Cash position API (phase 7).

The engine runs deterministically over the batch's stored canonical rows —
identical inputs always produce an identical position. No route mutates
anything: cash endpoints are read-only views.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.cash_forecast import CashForecastConfig, compute_cash_position
from backend.config import ReconciliationConfig
from backend.database import Database
from backend.models import Source
from backend.reconciliation import compute_as_of, reconcile_batch
from backend.repositories import (
    AuditRepository,
    BankEntryRepository,
    BatchRepository,
    TransactionRepository,
)
from backend.routes.batches import get_database
from backend.schemas import CashPositionResponse, ErrorResponse

router = APIRouter(prefix="/api/v1/batches", tags=["cash"])


@router.get(
    "/{batch_id}/cash-position",
    response_model=CashPositionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "unknown batch"},
        422: {"model": ErrorResponse, "description": "invalid parameters"},
    },
)
def get_cash_position(
    batch_id: str,
    opening_balance_paise: int = Query(default=0, ge=0),
    horizon: int = Query(default=7, ge=1, le=30),
    db: Database = Depends(get_database),
) -> CashPositionResponse:
    conn = db.connect(init=False)
    try:
        batch = BatchRepository(conn).find_by_id(batch_id)
        if batch is None:
            raise HTTPException(404, detail={
                "code": "batch_not_found",
                "message": f"no batch with id {batch_id!r}"})
        transactions = TransactionRepository(conn).list_canonical(batch_id)
        bank = BankEntryRepository(conn).list_canonical(batch_id)
    finally:
        conn.close()

    ledger = [t for t in transactions if t.source is Source.INTERNAL_LEDGER]
    settlements = [t for t in transactions if t.source is Source.SETTLEMENT_REPORT]
    if not (ledger or settlements or bank):
        # empty batch: no date anchor exists and none is fabricated (L5)
        position = compute_cash_position(
            [], [], opening_balance_paise=opening_balance_paise,
            as_of=None, config=CashForecastConfig(horizon_days=horizon))
        return CashPositionResponse(
            **position, batch_id=batch_id, batch_status=batch["status"],
            as_of="")
    as_of = compute_as_of(ledger, settlements, bank)
    outcome = reconcile_batch(ledger, settlements, bank, ReconciliationConfig())

    position = compute_cash_position(
        outcome.results, bank,
        opening_balance_paise=opening_balance_paise,
        as_of=as_of,
        config=CashForecastConfig(horizon_days=horizon),
    )
    return CashPositionResponse(
        **position,
        batch_id=batch_id,
        batch_status=batch["status"],
        as_of=as_of.isoformat(),
    )
