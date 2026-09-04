"""Shared canonical-record factories for tests.

Default amounts: gross 100000 paise (INR 1,000.00), 2% fee = 2000,
18% tax on fee = 360, expected net = 97640 paise.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.models import (
    CanonicalBankEntry,
    CanonicalTransaction,
    Source,
    TransactionType,
)

DEFAULT_GROSS = 100_000
DEFAULT_FEE = 2_000
DEFAULT_TAX = 360
DEFAULT_NET = DEFAULT_GROSS - DEFAULT_FEE - DEFAULT_TAX  # 97_640

T0 = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
AS_OF = datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)


def ledger_txn(
    payment_id: str = "pay_001",
    order_id: str | None = "order_001",
    amount_paise: int = DEFAULT_GROSS,
    at: datetime = T0,
    row_id: str = "int_001",
    entity_id: str | None = None,
    settlement_id: str | None = None,
) -> CanonicalTransaction:
    return CanonicalTransaction(
        source=Source.INTERNAL_LEDGER,
        source_row_id=row_id,
        transaction_type=TransactionType.PAYMENT,
        payment_id=payment_id,
        order_id=order_id,
        entity_id=entity_id,
        settlement_id=settlement_id,
        gross_amount_paise=amount_paise,
        transaction_at=at,
        raw_payload={"internal_id": row_id, "payment_id": payment_id},
    )


def settlement_txn(
    payment_id: str = "pay_001",
    entity_id: str = "ent_001",
    settlement_id: str = "setl_001",
    utr: str | None = "UTR100001",
    gross: int = DEFAULT_GROSS,
    fee: int = DEFAULT_FEE,
    tax: int = DEFAULT_TAX,
    debit: int = 0,
    credit: int = 0,
    at: datetime = T1,
    order_id: str | None = "order_001",
    row_id: str | None = None,
) -> CanonicalTransaction:
    return CanonicalTransaction(
        source=Source.SETTLEMENT_REPORT,
        source_row_id=row_id or entity_id,
        entity_id=entity_id,
        transaction_type=TransactionType.PAYMENT,
        payment_id=payment_id,
        order_id=order_id,
        settlement_id=settlement_id,
        settlement_utr=utr,
        gross_amount_paise=gross,
        fee_paise=fee,
        tax_paise=tax,
        debit_paise=debit,
        credit_paise=credit,
        transaction_at=at,
        raw_payload={"entity_id": entity_id},
    )


def bank_entry(
    txn_id: str = "bank_001",
    credit: int = DEFAULT_NET,
    utr: str | None = "UTR100001",
    at: datetime = T2,
    description: str = "NEFT CR-UTR:UTR100001 SETTL setl_001",
    debit: int = 0,
    currency: str = "INR",
) -> CanonicalBankEntry:
    return CanonicalBankEntry(
        source_row_id=txn_id,
        bank_txn_id=txn_id,
        value_date=at,
        description=description,
        utr=utr,
        currency=currency,
        credit_paise=credit,
        debit_paise=debit,
        raw_payload={"bank_txn_id": txn_id},
    )
