"""L2: a database file created on the v1 schema must survive a v2 init."""

from __future__ import annotations

import sqlite3

from backend.database import Database

V1_BATCHES = """
CREATE TABLE batches (
    id TEXT PRIMARY KEY, source_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL, record_count INTEGER NOT NULL,
    ledger_rows INTEGER NOT NULL DEFAULT 0,
    settlement_rows INTEGER NOT NULL DEFAULT 0,
    bank_rows INTEGER NOT NULL DEFAULT 0,
    skipped_rows INTEGER NOT NULL DEFAULT 0,
    duplicate_rows INTEGER NOT NULL DEFAULT 0,
    conflicting_rows INTEGER NOT NULL DEFAULT 0,
    validation_errors_json TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id),
    source TEXT NOT NULL, source_row_id TEXT NOT NULL,
    transaction_type TEXT NOT NULL, payment_id TEXT, order_id TEXT,
    settlement_id TEXT, settlement_utr TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    gross_amount_paise INTEGER NOT NULL DEFAULT 0,
    fee_paise INTEGER NOT NULL DEFAULT 0, tax_paise INTEGER NOT NULL DEFAULT 0,
    debit_paise INTEGER NOT NULL DEFAULT 0, credit_paise INTEGER NOT NULL DEFAULT 0,
    transaction_at TEXT NOT NULL, raw_payload_json TEXT NOT NULL
);
"""


def test_v1_database_is_upgraded_in_place(tmp_path):
    db_path = tmp_path / "v1.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(V1_BATCHES)
    conn.execute(
        "INSERT INTO batches (id, source_hash, status, record_count, started_at)"
        " VALUES ('batch_v1', 'hash', 'validated', 0, '2026-08-01T00:00:00+00:00')")
    conn.commit()
    conn.close()

    upgraded = Database(db_path).connect()  # init_schema migrates v1 -> v2
    try:
        cols = {r[1] for r in upgraded.execute("PRAGMA table_info(transactions)")}
        assert "entity_id" in cols, "v1 file was not upgraded with entity_id"
        # and the loader works against the upgraded file
        from backend.repositories import TransactionRepository
        TransactionRepository(upgraded).list_canonical("batch_v1")  # no crash
    finally:
        upgraded.close()
