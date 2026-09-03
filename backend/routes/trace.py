"""Transaction trace API (read-only): the structured chain behind one
payment — ledger row, settlement rows, bank entry, engine decision with
waterfall breakdown and evidence. Reuses the AI tool's loader, so the API
and the assistant can never disagree about a record."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database import Database
from backend.routes.batches import get_database
from backend.schemas import ErrorResponse
from backend.tools import get_transaction_trace

router = APIRouter(prefix="/api/v1/transactions", tags=["trace"])


@router.get(
    "/{payment_id}/trace",
    response_model=None,
    responses={
        404: {"model": ErrorResponse, "description": "unknown payment/batch"},
        422: {"model": ErrorResponse, "description": "missing batch_id"},
    },
)
def trace(payment_id: str, batch_id: str = Query(min_length=1),
          db: Database = Depends(get_database)) -> dict:
    result = get_transaction_trace(payment_id, batch_id, db)
    if not result.get("ok"):
        raise HTTPException(404, detail={
            "code": result["error"]["code"],
            "message": result["error"]["message"]})
    return result
