"""Repositories: the ONLY modules that touch SQL. Routes and services see
plain rows/dicts; domain logic stays persistence-free.

Safety properties:
- batch creation (batch row + transactions + bank entries + audit event) is
  one SQLite transaction — a failure anywhere rolls everything back, so a
  half-created batch can never exist (tested);
- audit_events has insert/list only — append-only by construction;
- all money columns are written as integer paise.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from backend.database import Database
from backend.models import (
    BatchStatus,
    CanonicalBankEntry,
    CanonicalTransaction,
    Source,
    TransactionType,
)

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BatchRow:
    id: str
    source_hash: str
    status: BatchStatus
    record_count: int
    ledger_rows: int
    settlement_rows: int
    bank_rows: int
    skipped_rows: int
    duplicate_rows: int
    conflicting_rows: int
    validation_errors: list[dict[str, Any]]
    started_at: str
    completed_at: str | None = None

class BatchRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, batch: BatchRow) -> None:
        self.conn.execute(
            """INSERT INTO batches (id, source_hash, status, record_count,
               ledger_rows, settlement_rows, bank_rows, skipped_rows,
               duplicate_rows, conflicting_rows, validation_errors_json,
               started_at, completed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                batch.id, batch.source_hash, batch.status.value,
                batch.record_count, batch.ledger_rows, batch.settlement_rows,
                batch.bank_rows, batch.skipped_rows, batch.duplicate_rows,
                batch.conflicting_rows,
                json.dumps(batch.validation_errors, default=str),
                batch.started_at, batch.completed_at,
            ),
        )

    def find_by_id(self, batch_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM batches WHERE id = ?", (batch_id,)
        ).fetchone()
        return self._to_dict(row) if row else None

    def find_by_source_hash(self, source_hash: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM batches WHERE source_hash = ?", (source_hash,)
        ).fetchone()
        return self._to_dict(row) if row else None

    def status_counts(self, batch_id: str) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) n FROM reconciliation_results "
            "WHERE batch_id = ? GROUP BY status", (batch_id,)).fetchall()
        return {r["status"]: r["n"] for r in rows}

    def mark_reconciled(self, batch_id: str, completed_at: str) -> None:
        self.conn.execute(
            "UPDATE batches SET status = ?, completed_at = ? WHERE id = ?",
            (BatchStatus.RECONCILED.value, completed_at, batch_id))

    def find_audit_detail(self, batch_id: str, action: str) -> dict | None:
        row = self.conn.execute(
            "SELECT details_json FROM audit_events WHERE batch_id = ? AND action = ? "
            "ORDER BY id DESC LIMIT 1", (batch_id, action)).fetchone()
        return json.loads(row["details_json"]) if row else None

    def count_for_batch(self, batch_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM transactions WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()["n"]

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "batch_id": row["id"],
            "source_hash": row["source_hash"],
            "status": row["status"],
            "record_count": row["record_count"],
            "ledger_rows": row["ledger_rows"],
            "settlement_rows": row["settlement_rows"],
            "bank_rows": row["bank_rows"],
            "skipped_rows": row["skipped_rows"],
            "duplicate_rows": row["duplicate_rows"],
            "conflicting_rows": row["conflicting_rows"],
            "validation_errors": json.loads(row["validation_errors_json"]),
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
        }


class TransactionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert_many(self, batch_id: str, rows: Iterable[CanonicalTransaction]) -> int:
        payload = [
            (
                batch_id, r.source.value, r.source_row_id, r.entity_id,
                r.transaction_type.value,
                r.payment_id, r.order_id, r.settlement_id, r.settlement_utr,
                r.currency, r.gross_amount_paise, r.fee_paise, r.tax_paise,
                r.debit_paise, r.credit_paise,
                r.transaction_at.isoformat(), json.dumps(r.raw_payload),
            )
            for r in rows
        ]
        self.conn.executemany(
            """INSERT INTO transactions (batch_id, source, source_row_id,
               entity_id, transaction_type, payment_id, order_id, settlement_id,
               settlement_utr, currency, gross_amount_paise, fee_paise,
               tax_paise, debit_paise, credit_paise, transaction_at,
               raw_payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            payload,
        )
        return len(payload)

    def count_for_batch(self, batch_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM transactions WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()["n"]

    def list_canonical(self, batch_id: str) -> list[CanonicalTransaction]:
        """Load stored rows back into canonical domain objects."""
        rows = self.conn.execute(
            "SELECT * FROM transactions WHERE batch_id = ? ORDER BY id",
            (batch_id,)).fetchall()
        return [
            CanonicalTransaction(
                source=Source(r["source"]),
                source_row_id=r["source_row_id"],
                transaction_type=TransactionType(r["transaction_type"]),
                transaction_at=datetime.fromisoformat(r["transaction_at"]),
                entity_id=r["entity_id"], payment_id=r["payment_id"],
                order_id=r["order_id"], settlement_id=r["settlement_id"],
                settlement_utr=r["settlement_utr"], currency=r["currency"],
                gross_amount_paise=r["gross_amount_paise"],
                fee_paise=r["fee_paise"], tax_paise=r["tax_paise"],
                debit_paise=r["debit_paise"], credit_paise=r["credit_paise"],
                raw_payload=json.loads(r["raw_payload_json"]),
            )
            for r in rows
        ]


class BankEntryRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def count_for_batch(self, batch_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM bank_entries WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()["n"]

    def insert_many(self, batch_id: str, rows: Iterable[CanonicalBankEntry]) -> int:
        payload = [
            (
                batch_id, e.bank_txn_id, e.value_date.isoformat(),
                e.description, e.utr, e.credit_paise, e.debit_paise,
                json.dumps(e.raw_payload),
            )
            for e in rows
        ]
        self.conn.executemany(
            """INSERT INTO bank_entries (batch_id, bank_txn_id, value_date,
               description, utr, credit_paise, debit_paise, raw_payload_json)
               VALUES (?,?,?,?,?,?,?,?)""",
            payload,
        )
        return len(payload)

    def list_canonical(self, batch_id: str) -> list[CanonicalBankEntry]:
        rows = self.conn.execute(
            "SELECT * FROM bank_entries WHERE batch_id = ? ORDER BY id",
            (batch_id,)).fetchall()
        return [
            CanonicalBankEntry(
                source_row_id=r["bank_txn_id"], bank_txn_id=r["bank_txn_id"],
                value_date=datetime.fromisoformat(r["value_date"]),
                description=r["description"], utr=r["utr"],
                credit_paise=r["credit_paise"], debit_paise=r["debit_paise"],
                raw_payload=json.loads(r["raw_payload_json"]),
            )
            for r in rows
        ]


class AuditRepository:
    """Append-only: insert and list only. No update, no delete — by design."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def append(
        self,
        batch_id: str,
        record_id: str,
        action: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        self.conn.execute(
            """INSERT INTO audit_events (batch_id, record_id, action, actor,
               details_json, created_at) VALUES (?,?,?,?,?,?)""",
            (
                batch_id, record_id, action, actor,
                json.dumps(details, default=str), utc_now_iso(),
            ),
        )

    def list_for_batch(self, batch_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT action, actor, record_id, details_json, created_at
               FROM audit_events WHERE batch_id = ?
               ORDER BY id DESC LIMIT ?""",
            (batch_id, limit),
        ).fetchall()
        return [
            {
                "action": r["action"],
                "actor": r["actor"],
                "record_id": r["record_id"],
                "details": json.loads(r["details_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


class ReconciliationResultRepository:
    """Read side for results/exceptions. Phase 4 wires the table; the
    reconciliation phase will fill it."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert_many(self, batch_id: str, results: list,
                    order_ids: dict[str, str] | None = None) -> int:
        order_ids = order_ids or {}
        payload = []
        for r in results:
            payload.append(
                (
                    batch_id, r.payment_id, order_ids.get(r.payment_id),
                    r.settlement_id, None, r.bank_txn_id,
                    r.status.value, r.confidence, r.match_method,
                    r.expected_amount_paise, r.actual_amount_paise,
                    r.variance_paise,
                    json.dumps(r.expected_breakdown_paise) if r.expected_breakdown_paise else None,
                    r.severity.value, r.reason, json.dumps(r.evidence),
                    int(r.requires_review), utc_now_iso(),
                )
            )
        self.conn.executemany(
            """INSERT INTO reconciliation_results (batch_id, payment_id,
               order_id, settlement_id, bank_entry_id, bank_txn_id, status,
               confidence, match_method, expected_amount_paise, actual_amount_paise,
               variance_paise, expected_breakdown_json, severity, reason,
               evidence_json, requires_review, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            payload,
        )
        return len(payload)

    def list_page(
        self,
        batch_id: str,
        *,
        status: str | None = None,
        requires_review: bool | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[dict[str, Any]], int]:
        page = max(1, page)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        where = ["batch_id = ?"]
        params: list[Any] = [batch_id]
        if status is not None:
            where.append("status = ?")
            params.append(status)
        if requires_review is not None:
            where.append("requires_review = ?")
            params.append(int(requires_review))
        clause = " AND ".join(where)

        total = self.conn.execute(
            f"SELECT COUNT(*) AS n FROM reconciliation_results WHERE {clause}",
            params,
        ).fetchone()["n"]
        rows = self.conn.execute(
            f"""SELECT * FROM reconciliation_results WHERE {clause}
                ORDER BY id LIMIT ? OFFSET ?""",
            (*params, page_size, (page - 1) * page_size),
        ).fetchall()
        items = [self._to_dict(r) for r in rows]
        return items, total

    def status_counts(self, batch_id: str) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) n FROM reconciliation_results "
            "WHERE batch_id = ? GROUP BY status", (batch_id,)).fetchall()
        return {r["status"]: r["n"] for r in rows}

    def mark_reconciled(self, batch_id: str, completed_at: str) -> None:
        self.conn.execute(
            "UPDATE batches SET status = ?, completed_at = ? WHERE id = ?",
            (BatchStatus.RECONCILED.value, completed_at, batch_id))

    def find_audit_detail(self, batch_id: str, action: str) -> dict | None:
        row = self.conn.execute(
            "SELECT details_json FROM audit_events WHERE batch_id = ? AND action = ? "
            "ORDER BY id DESC LIMIT 1", (batch_id, action)).fetchone()
        return json.loads(row["details_json"]) if row else None

    def count_for_batch(self, batch_id: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM transactions WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()["n"]

    @staticmethod
    def _recommended_action(status: str) -> str:
        # Derived from the canonical status map so the API exposes the same
        # action the deterministic engine used, without duplicating state.
        from backend.statuses import RECOMMENDED_ACTIONS
        return RECOMMENDED_ACTIONS.get(status, "Review the evidence before taking action.")

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "payment_id": row["payment_id"],
            "order_id": row["order_id"],
            "status": row["status"],
            "confidence": row["confidence"],
            "match_method": row["match_method"],
            "expected_amount_paise": row["expected_amount_paise"],
            "actual_amount_paise": row["actual_amount_paise"],
            "variance_paise": row["variance_paise"],
            "expected_breakdown_paise": json.loads(row["expected_breakdown_json"])
            if row["expected_breakdown_json"] else None,
            "severity": row["severity"],
            "reason": row["reason"],
            "evidence": json.loads(row["evidence_json"]),
            "requires_review": bool(row["requires_review"]),
            "recommended_action": ReconciliationResultRepository._recommended_action(row["status"]),
            "settlement_id": row["settlement_id"],
            "bank_txn_id": row["bank_txn_id"],
            "created_at": row["created_at"],
        }


def create_batch_transactionally(
    db: Database,
    *,
    ledger: list[CanonicalTransaction],
    settlements: list[CanonicalTransaction],
    bank: list[CanonicalBankEntry],
    source_hash: str,
    validation_errors: list[dict[str, Any]],
    row_counts: dict[str, int],
    actor: str = "api",
) -> BatchRow:
    """Persist one validated batch atomically.

    Batch row + all transactions + bank entries + the creation audit event
    commit together or not at all; the unique source_hash makes re-uploads
    idempotent at the caller level (callers check find_by_source_hash first,
    and the UNIQUE constraint is the hard backstop against races).
    """
    batch = BatchRow(
        id=f"batch_{uuid4().hex[:12]}",
        source_hash=source_hash,
        status=BatchStatus.VALIDATED,
        record_count=(
            row_counts.get("ledger_rows", len(ledger))
            + row_counts.get("settlement_rows", len(settlements))
            + row_counts.get("bank_rows", len(bank))
        ),
        ledger_rows=row_counts.get("ledger_rows", len(ledger)),
        settlement_rows=row_counts.get("settlement_rows", len(settlements)),
        bank_rows=row_counts.get("bank_rows", len(bank)),
        skipped_rows=row_counts.get("skipped_rows", 0),
        duplicate_rows=row_counts.get("duplicate_rows", 0),
        conflicting_rows=row_counts.get("conflicting_rows", 0),
        validation_errors=validation_errors,
        started_at=utc_now_iso(),
    )
    conn = db.connect(init=False)  # schema is initialized at app startup
    try:
        with conn:  # single transaction: commit or roll back everything
            BatchRepository(conn).insert(batch)
            TransactionRepository(conn).insert_many(batch.id, ledger)
            TransactionRepository(conn).insert_many(batch.id, settlements)
            BankEntryRepository(conn).insert_many(batch.id, bank)
            AuditRepository(conn).append(
                batch_id=batch.id,
                record_id=batch.id,
                action="batch_created",
                actor=actor,
                details={
                    "source_hash": source_hash,
                    "record_count": batch.record_count,
                    "rows": {
                        "ledger": batch.ledger_rows,
                        "settlements": batch.settlement_rows,
                        "bank": batch.bank_rows,
                    },
                    "skipped_rows": batch.skipped_rows,
                    "duplicate_rows": batch.duplicate_rows,
                    "conflicting_rows": batch.conflicting_rows,
                    "status": batch.status.value,
                    "note": "batch validated only; reconciliation not run",
                },
            )
    finally:
        conn.close()
    return batch
