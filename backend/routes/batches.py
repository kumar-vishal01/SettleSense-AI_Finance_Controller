"""Batch API: create validated batches, inspect them, page results.

Phase 4 boundary: POST validates + persists and NEVER claims reconciliation
(status stays 'validated'; results endpoints are empty until the
reconciliation phase fills them, and they say so explicitly in `note`).

Idempotency: the source hash of the three exact file contents identifies a
batch; re-uploading identical files returns the existing batch with
``idempotent: true`` and writes nothing (ARCHITECTURE.md section 7).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from backend.config import ReconciliationConfig
from backend.database import Database
from backend.exceptions import IngestionError
from backend.ingestion import read_csv_source, summarize_input
from backend.models import BatchStatus, ReconciliationStatus, Source
from backend.normalization import (
    normalize_bank_statement,
    normalize_internal_ledger,
    normalize_settlement_report,
)
from backend.repositories import (
    MAX_PAGE_SIZE,
    AuditRepository,
    BatchRepository,
    ReconciliationResultRepository,
    create_batch_transactionally,
)
from backend.schemas import (
    BatchCreateResponse,
    ErrorResponse,
    BatchDetailResponse,
    FileCounts,
    PaginatedResults,
    ResultItem,
    ValidationView,
)

router = APIRouter(prefix="/api/v1/batches", tags=["batches"])

#: API responses cap the row-error list; the database keeps every error.
MAX_RESPONSE_ERRORS = 100

#: The only server-side fixture allowed (loads the committed synthetic-v2
#: dataset). Fixed slug — no user-controlled paths, no traversal.
ALLOWED_FIXTURES: dict[str, list[tuple[str, Source]]] = {
    "synthetic-v2": [
        ("internal_ledger.csv", Source.INTERNAL_LEDGER),
        ("settlements.csv", Source.SETTLEMENT_REPORT),
        ("bank_statement.csv", Source.BANK_STATEMENT),
    ],
}


def get_database() -> Database:
    """Request-scoped database factory. Reads the path from the environment
    each call so tests can point at an isolated file."""
    return Database(os.environ.get("SETTLESENSE_DB_PATH", "settlesense.db"))


def compute_source_hash(parts: list[tuple[str, Source, bytes]]) -> str:
    """Stable hash over the exact uploaded bytes, domain-separated by part
    name so (A,B,C) and (B,A,C) can never collide."""
    digest = hashlib.sha256()
    for name, _source, content in parts:
        digest.update(f"{name}:{len(content)}:".encode())
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _sanitize_file_name(name: str) -> str:
    """Basenames only, length-capped: echoed into error items, never used
    as a path."""
    return Path(name).name[:120] or "upload"


@router.post(
    "",
    status_code=201,
    response_model=BatchCreateResponse,
    responses={
        413: {"model": ErrorResponse, "description": "upload exceeds size limit"},
        422: {"model": ErrorResponse, "description": "invalid files or request"},
        500: {"model": ErrorResponse, "description": "internal error"},
    },
)
async def create_batch(
    response: Response,
    internal_ledger: UploadFile | None = File(default=None),
    settlements: UploadFile | None = File(default=None),
    bank_statement: UploadFile | None = File(default=None),
    fixture: str | None = Query(default=None, description="server-side test fixture slug"),
    db: Database = Depends(get_database),
) -> BatchCreateResponse:
    """Create a validated batch from three uploaded CSVs (multipart) or a
    whitelisted server-side fixture. Does not reconcile."""
    parts: list[tuple[str, Source, bytes]] = []

    if fixture is not None:
        if internal_ledger or settlements or bank_statement:
            raise HTTPException(422, detail={
                "code": "invalid_request",
                "message": "provide either uploaded files or a fixture, not both"})
        if fixture not in ALLOWED_FIXTURES:
            raise HTTPException(422, detail={
                "code": "invalid_fixture",
                "message": f"unknown fixture {fixture!r}; allowed: synthetic-v2"})
        base = Path(__file__).resolve().parents[2] / "data"
        for file_name, source in ALLOWED_FIXTURES[fixture]:
            parts.append((file_name, source, (base / file_name).read_bytes(), file_name))
    else:
        uploads = [
            ("internal_ledger.csv", Source.INTERNAL_LEDGER, internal_ledger),
            ("settlements.csv", Source.SETTLEMENT_REPORT, settlements),
            ("bank_statement.csv", Source.BANK_STATEMENT, bank_statement),
        ]
        if any(f is None for _, _, f in uploads):
            raise HTTPException(
                422,
                detail={
                    "code": "missing_files",
                    "message": "three files are required: internal_ledger, "
                               "settlements, bank_statement "
                               "(or use ?fixture=synthetic-v2)",
                },
            )
        limits = ReconciliationConfig()
        for name, source, upload in uploads:
            display = _sanitize_file_name(upload.filename or name)
            # bounded read: never load an oversized upload into memory
            content = await upload.read(limits.max_file_bytes + 1)
            if len(content) > limits.max_file_bytes:
                raise HTTPException(
                    413,
                    detail={
                        "code": "file_too_large",
                        "message": f"{display} exceeds {limits.max_file_bytes} bytes",
                    },
                )
            parts.append((name, source, content, display))

    return _create_from_parts(parts, db, response)


def _create_from_parts(
    parts: list[tuple[str, Source, bytes, str]], db: Database, response: Response
) -> BatchCreateResponse:
    source_hash = compute_source_hash(
        [(name, source, content) for name, source, content, _display in parts]
    )

    tables = []
    for _name, source, content, display in parts:
        try:
            tables.append(read_csv_source(content, source, file_name=display))
        except IngestionError as exc:
            raise HTTPException(
                422,
                detail={
                    "code": "ingestion_error",
                    "message": f"{display}: {exc}",
                },
            ) from exc

    summary = summarize_input(*tables)

    ledger = normalize_internal_ledger(tables[0])
    settlements = normalize_settlement_report(tables[1])
    bank = normalize_bank_statement(tables[2])

    conn = db.connect(init=False)
    try:
        existing = BatchRepository(conn).find_by_source_hash(source_hash)
    finally:
        conn.close()
    if existing is not None:
        response.status_code = 200  # idempotent re-upload, not a new resource
        return _existing_batch_response(existing, source_hash)

    row_counts = {
        "ledger_rows": summary.files[0].valid_rows,
        "settlement_rows": summary.files[1].valid_rows,
        "bank_rows": summary.files[2].valid_rows,
        "skipped_rows": summary.skipped_rows,
        "duplicate_rows": summary.duplicate_rows,
        "conflicting_rows": summary.conflicting_rows,
    }
    try:
        batch = create_batch_transactionally(
            db,
            ledger=ledger,
            settlements=settlements,
            bank=bank,
            source_hash=source_hash,
            validation_errors=[e.model_dump() for e in summary.errors],
            row_counts=row_counts,
        )
    except sqlite3.IntegrityError:
        # UNIQUE(source_hash) backstop: a concurrent request created this
        # batch between our check and the insert. Return theirs, idempotently.
        conn = db.connect(init=False)
        try:
            existing = BatchRepository(conn).find_by_source_hash(source_hash)
        finally:
            conn.close()
        if existing is None:
            raise
        response.status_code = 200
        return _existing_batch_response(existing, source_hash)

    return BatchCreateResponse(
        batch_id=batch.id,
        source_hash=source_hash,
        status=batch.status.value,
        idempotent=False,
        record_count=batch.record_count,
        counts=FileCounts(
            ledger_rows=batch.ledger_rows,
            settlement_rows=batch.settlement_rows,
            bank_rows=batch.bank_rows,
        ),
        validation=_validation_view(summary),
        started_at=batch.started_at,
    )


def _capped_errors(errors: list) -> tuple[list, bool]:
    return errors[:MAX_RESPONSE_ERRORS], len(errors) > MAX_RESPONSE_ERRORS


def _validation_view(summary) -> ValidationView:
    errors, truncated = _capped_errors(summary.errors)
    return ValidationView(
        valid=summary.valid,
        total_rows=summary.total_rows,
        valid_rows=summary.valid_rows,
        skipped_rows=summary.skipped_rows,
        duplicate_rows=summary.duplicate_rows,
        conflicting_rows=summary.conflicting_rows,
        errors=errors,
        errors_truncated=truncated,
    )


def _existing_batch_response(existing: dict, source_hash: str) -> BatchCreateResponse:
    errors, truncated = _capped_errors(existing["validation_errors"])
    return BatchCreateResponse(
        batch_id=existing["batch_id"],
        source_hash=source_hash,
        status=existing["status"],
        idempotent=True,
        record_count=existing["record_count"],
        counts=FileCounts(
            ledger_rows=existing["ledger_rows"],
            settlement_rows=existing["settlement_rows"],
            bank_rows=existing["bank_rows"],
        ),
        validation=ValidationView(
            valid=existing["skipped_rows"] == 0,
            total_rows=existing["record_count"] + existing["skipped_rows"],
            valid_rows=existing["record_count"],
            skipped_rows=existing["skipped_rows"],
            duplicate_rows=existing["duplicate_rows"],
            conflicting_rows=existing["conflicting_rows"],
            errors=errors,
            errors_truncated=truncated,
        ),
        started_at=existing["started_at"],
    )


def _get_batch_or_404(conn, batch_id: str) -> dict:
    batch = BatchRepository(conn).find_by_id(batch_id)
    if batch is None:
        raise HTTPException(
            404,
            detail={"code": "batch_not_found", "message": f"no batch with id {batch_id!r}"},
        )
    return batch


@router.get(
    "/{batch_id}",
    response_model=BatchDetailResponse,
    responses={404: {"model": ErrorResponse, "description": "unknown batch"}},
)
def get_batch(batch_id: str, db: Database = Depends(get_database)) -> BatchDetailResponse:
    conn = db.connect(init=False)
    try:
        batch = _get_batch_or_404(conn, batch_id)
        results = ReconciliationResultRepository(conn)
        result_count = results.list_page(batch_id, page=1, page_size=1)[1]
        audit = AuditRepository(conn).list_for_batch(batch_id, limit=10)
    finally:
        conn.close()
    return BatchDetailResponse(
        batch_id=batch["batch_id"],
        source_hash=batch["source_hash"],
        status=batch["status"],
        record_count=batch["record_count"],
        counts=FileCounts(
            ledger_rows=batch["ledger_rows"],
            settlement_rows=batch["settlement_rows"],
            bank_rows=batch["bank_rows"],
        ),
        skipped_rows=batch["skipped_rows"],
        duplicate_rows=batch["duplicate_rows"],
        conflicting_rows=batch["conflicting_rows"],
        validation_errors=batch["validation_errors"],
        started_at=batch["started_at"],
        completed_at=batch["completed_at"],
        result_count=result_count,
        audit_events=audit,
    )


def _results_response(
    batch_id: str,
    *,
    status: ReconciliationStatus | None,
    requires_review: bool | None,
    page: int,
    page_size: int,
    db: Database,
) -> PaginatedResults:
    conn = db.connect(init=False)
    try:
        batch = _get_batch_or_404(conn, batch_id)
        items, total = ReconciliationResultRepository(conn).list_page(
            batch_id,
            status=status.value if status else None,
            requires_review=requires_review,
            page=page,
            page_size=page_size,
        )
    finally:
        conn.close()
    total_pages = (total + page_size - 1) // page_size if total else 0
    note = None
    if batch["status"] == BatchStatus.VALIDATED.value:
        note = "batch is validated only; reconciliation has not been run"
    return PaginatedResults(
        items=[ResultItem(**item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        batch_status=batch["status"],
        note=note,
    )


@router.get(
    "/{batch_id}/results",
    response_model=PaginatedResults,
    responses={
        404: {"model": ErrorResponse, "description": "unknown batch"},
        422: {"model": ErrorResponse, "description": "invalid filter/pagination"},
    },
)
def get_results(
    batch_id: str,
    status: ReconciliationStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Database = Depends(get_database),
) -> PaginatedResults:
    return _results_response(
        batch_id, status=status, requires_review=None,
        page=page, page_size=page_size, db=db,
    )


@router.get(
    "/{batch_id}/exceptions",
    response_model=PaginatedResults,
    responses={
        404: {"model": ErrorResponse, "description": "unknown batch"},
        422: {"model": ErrorResponse, "description": "invalid filter/pagination"},
    },
)
def get_exceptions(
    batch_id: str,
    status: ReconciliationStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Database = Depends(get_database),
) -> PaginatedResults:
    return _results_response(
        batch_id, status=status, requires_review=True,
        page=page, page_size=page_size, db=db,
    )
