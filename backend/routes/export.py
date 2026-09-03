"""Export API (phase 10): reconciliation results / exceptions as CSV or JSON.

Exports are audit-grade: money stays integer paise, evidence IDs are
included, and byte-identical for repeated calls (deterministic ordering).
A batch that has not been reconciled exports an empty (headers-only) file —
it never fabricates results.
"""

from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from backend.database import Database
from backend.repositories import (
    BatchRepository,
    ReconciliationResultRepository,
)
from backend.routes.batches import get_database
from backend.schemas import ErrorResponse

router = APIRouter(prefix="/api/v1/batches", tags=["export"])

CSV_COLUMNS = [
    "payment_id", "order_id", "settlement_id", "bank_txn_id", "status",
    "severity", "confidence", "match_method", "expected_amount_paise",
    "actual_amount_paise", "variance_paise", "requires_review",
    "reason", "evidence",
]


def _load(batch_id: str, db: Database, scope: str):
    conn = db.connect(init=False)
    try:
        batch = BatchRepository(conn).find_by_id(batch_id)
        if batch is None:
            raise HTTPException(404, detail={
                "code": "batch_not_found",
                "message": f"no batch with id {batch_id!r}"})
        items, _total = ReconciliationResultRepository(conn).list_page(
            batch_id, page=1, page_size=100_000,
            requires_review=True if scope == "exceptions" else None)
        status = batch["status"]
    finally:
        conn.close()
    return items, status


@router.get(
    "/{batch_id}/export",
    responses={
        404: {"model": ErrorResponse, "description": "unknown batch"},
        422: {"model": ErrorResponse, "description": "invalid parameters"},
    },
)
def export_batch(
    batch_id: str,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    scope: str = Query(default="results", pattern="^(results|exceptions)$"),
    db: Database = Depends(get_database),
) -> Response:
    items, batch_status = _load(batch_id, db, scope)
    reconciled = batch_status == "reconciled"

    if format == "json":
        return Response(
            content=json.dumps({
                "batch_id": batch_id,
                "scope": scope,
                "reconciled": reconciled,
                "note": None if reconciled else
                    "batch has not been reconciled; export is empty",
                "count": len(items),
                "items": items,
            }, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition":
                     f'attachment; filename="{batch_id}_{scope}.json"'})

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for item in items:
        writer.writerow({
            **{k: item.get(k, "") for k in CSV_COLUMNS if k != "evidence"},
            "evidence": ";".join(item.get("evidence") or []),
            "requires_review": str(bool(item.get("requires_review"))).lower(),
        })
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="{batch_id}_{scope}.csv"'})
