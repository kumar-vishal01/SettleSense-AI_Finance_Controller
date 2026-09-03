"""SQLite persistence for SettleSense (MVP), PostgreSQL-compatible design.

Choices that keep the door open to PostgreSQL (TECHNICAL_DESIGN section 2):
- plain TEXT/INTEGER/REAL columns, no SQLite-only types or generated columns
- ISO-8601 UTC strings for all timestamps (internals are UTC; display
  timezone is applied at the API/UI edge)
- money is integer paise in INTEGER columns — never REAL
- explicit foreign keys with PRAGMA foreign_keys = ON
- no AUTOINCREMENT reliance for business identity (batch ids are generated)

The schema is created idempotently (CREATE TABLE IF NOT EXISTS) so any
connection can bootstrap an empty database safely.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# v3 (phase 9): reconciliation_results.order_id persisted for the dashboard
# table; older files are migrated in place by _ensure_column.SCHEMA_VERSION = 3

#: Postgres-compatible DDL for the five core tables (TECHNICAL_DESIGN §4).
DDL = """
CREATE TABLE IF NOT EXISTS batches (
    id                   TEXT PRIMARY KEY,
    source_hash          TEXT NOT NULL UNIQUE,
    status               TEXT NOT NULL,
    record_count         INTEGER NOT NULL,
    ledger_rows          INTEGER NOT NULL DEFAULT 0,
    settlement_rows      INTEGER NOT NULL DEFAULT 0,
    bank_rows            INTEGER NOT NULL DEFAULT 0,
    skipped_rows         INTEGER NOT NULL DEFAULT 0,
    duplicate_rows       INTEGER NOT NULL DEFAULT 0,
    conflicting_rows     INTEGER NOT NULL DEFAULT 0,
    validation_errors_json TEXT NOT NULL DEFAULT '[]',
    started_at           TEXT NOT NULL,
    completed_at         TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY,
    batch_id            TEXT NOT NULL REFERENCES batches(id),
    source              TEXT NOT NULL,
    source_row_id       TEXT NOT NULL,
    entity_id           TEXT,
    transaction_type    TEXT NOT NULL,
    payment_id          TEXT,
    order_id            TEXT,
    settlement_id       TEXT,
    settlement_utr      TEXT,
    currency            TEXT NOT NULL DEFAULT 'INR',
    gross_amount_paise  INTEGER NOT NULL DEFAULT 0,
    fee_paise           INTEGER NOT NULL DEFAULT 0,
    tax_paise           INTEGER NOT NULL DEFAULT 0,
    debit_paise         INTEGER NOT NULL DEFAULT 0,
    credit_paise        INTEGER NOT NULL DEFAULT 0,
    transaction_at      TEXT NOT NULL,
    raw_payload_json    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transactions_batch
    ON transactions(batch_id);
CREATE INDEX IF NOT EXISTS idx_transactions_payment
    ON transactions(batch_id, payment_id);

CREATE TABLE IF NOT EXISTS bank_entries (
    id               INTEGER PRIMARY KEY,
    batch_id         TEXT NOT NULL REFERENCES batches(id),
    bank_txn_id      TEXT NOT NULL,
    value_date       TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    utr              TEXT,
    credit_paise     INTEGER NOT NULL DEFAULT 0,
    debit_paise      INTEGER NOT NULL DEFAULT 0,
    raw_payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bank_entries_batch ON bank_entries(batch_id);

CREATE TABLE IF NOT EXISTS reconciliation_results (
    id                      INTEGER PRIMARY KEY,
    batch_id                TEXT NOT NULL REFERENCES batches(id),
    payment_id              TEXT NOT NULL,
    order_id                TEXT,
    settlement_id           TEXT,
    bank_entry_id           INTEGER,
    bank_txn_id             TEXT,
    status                  TEXT NOT NULL,
    confidence              REAL NOT NULL,
    match_method            TEXT NOT NULL DEFAULT '',
    expected_amount_paise   INTEGER,
    actual_amount_paise     INTEGER,
    variance_paise          INTEGER,
    expected_breakdown_json TEXT,
    severity                TEXT NOT NULL DEFAULT 'none',
    reason                  TEXT NOT NULL DEFAULT '',
    evidence_json           TEXT NOT NULL DEFAULT '[]',
    requires_review         INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_results_batch_status
    ON reconciliation_results(batch_id, status);
CREATE INDEX IF NOT EXISTS idx_results_batch_review
    ON reconciliation_results(batch_id, requires_review);

CREATE TABLE IF NOT EXISTS audit_events (
    id            INTEGER PRIMARY KEY,
    batch_id      TEXT NOT NULL,
    record_id     TEXT NOT NULL DEFAULT '',
    action        TEXT NOT NULL,
    actor         TEXT NOT NULL,
    details_json  TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_batch ON audit_events(batch_id);
"""


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, column_ddl: str
) -> None:
    """Add a missing column to an existing table (no-op when present)."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_ddl}")


class Database:
    """Connection factory + idempotent schema bootstrap for one DB file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self, *, init: bool = True) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if init:
            self.init_schema(conn)
        return conn

    @staticmethod
    def init_schema(conn: sqlite3.Connection) -> None:
        conn.executescript(DDL)
        # Idempotent in-place upgrades for files created on older schemas
        # (a persisted Docker volume must never crash after an image bump).
        _ensure_column(conn, "transactions", "entity_id", "entity_id TEXT")
        _ensure_column(conn, "reconciliation_results", "order_id", "order_id TEXT")
        conn.commit()
