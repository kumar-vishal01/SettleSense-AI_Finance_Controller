"""Synthetic dataset generator for SettleSense — dataset version synthetic-v2.

Produces one versioned, seed-deterministic benchmark:
  data/internal_ledger.csv
  data/settlements.csv
  data/bank_statement.csv
  data/ground_truth.csv   (EVALUATION ONLY — never a runtime engine input)
  data/manifest.json      (version, seed, scenario plan)

Dataset plan (100 logical payments):
  60 clean matches        — 57 plain + 3 sharing one identical amount
                            ("same_amount_clean") to prove UTR-based matching
                            is safe when amounts collide
  10 delayed_bank_credit  — settlement young (<= delay window), no bank row
   8 missing_utr          — settlement + bank UTR fields blank; the bank
                            description still names the settlement ID, so the
                            engine resolves via reference evidence
   6 amount_mismatch      — bank credit differs from expected net by a fixed
                            delta per case (MISMATCH_DELTAS_PAISE)
   5 missing_settlement   — ledger payment with no settlement and no bank row
   4 missing_bank_credit  — settlement older than the delay window, no bank row
   3 duplicates           — one duplicated ledger row, one duplicated bank
                            row, one duplicated settlement entity row
   2 refunds              — extra settlement row (type=refund, debit 25% of
                            gross); bank credit equals the waterfall net
   1 adjustment           — extra settlement row (type=adjustment, credit);
                            bank credit equals the waterfall net
   1 ambiguous_review     — settlement UTR blank, two identical-amount bank
                            credits with no references: ambiguous on purpose

Money: integer paise only. All data synthetic; no real merchant, bank, or
customer identifiers. Same seed -> byte-identical files.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:  # allow direct `python scripts/generate_data.py`
    sys.path.insert(0, str(_ROOT))

DATASET_VERSION = "synthetic-v2"

LEDGER_COLUMNS = [
    "internal_id", "order_id", "payment_id", "created_at",
    "amount_paise", "currency", "payment_status",
]
SETTLEMENT_COLUMNS = [
    "entity_id", "type", "payment_id", "order_id", "settlement_id",
    "settlement_utr", "amount_paise", "fee_paise", "tax_paise",
    "debit_paise", "credit_paise", "settled_at",
]
BANK_COLUMNS = [
    "bank_txn_id", "value_date", "description", "utr",
    "credit_paise", "debit_paise",
]
GROUND_TRUTH_COLUMNS = [
    "payment_id", "expected_status", "expected_settlement_id",
    "expected_bank_txn_id", "expected_variance_paise", "scenario",
    "expected_review_flag",
]

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

#: Fixed per-case bank-credit deltas (paise) for amount_mismatch, applied in
#: order of appearance. Negative = bank credit lower than expected net.
MISMATCH_DELTAS_PAISE = [-30_000, -45_000, -120_000, 15_000, -60_000, 90_000]

#: scenario -> expected engine status. delayed/missing/ambiguous/duplicates
#: are exceptions (expected_review_flag=true); missing_utr resolves through
#: reference evidence, so it is a (noisier) FULLY_RECONCILED.
SCENARIO_STATUS: dict[str, str] = {
    "clean": "FULLY_RECONCILED",
    "same_amount_clean": "FULLY_RECONCILED",
    "delayed_bank_credit": "TIMING_DELAY",
    "missing_utr": "FULLY_RECONCILED",
    "amount_mismatch": "AMOUNT_MISMATCH",
    "missing_settlement": "MISSING_IN_SETTLEMENT",
    "missing_bank_credit": "MISSING_BANK_CREDIT",
    "duplicate_ledger": "DUPLICATE",
    "duplicate_bank": "DUPLICATE",
    "duplicate_settlement": "DUPLICATE",
    "refund": "FULLY_RECONCILED",
    "adjustment": "FULLY_RECONCILED",
    "ambiguous_review": "NEEDS_HUMAN_REVIEW",
}

#: Scenarios whose ground-truth bank_txn_id is unknowable/absent.
NO_BANK_SCENARIOS = {
    "missing_settlement", "missing_bank_credit", "delayed_bank_credit",
    "ambiguous_review",
}


@dataclass(frozen=True)
class DatasetSpec:
    """Planted scenario plan; totals 100 logical payments."""

    clean: int = 60                  # includes same_amount_group
    same_amount_group: int = 3       # clean rows deliberately sharing one amount
    delayed_bank_credit: int = 10
    missing_utr: int = 8
    amount_mismatch: int = 6
    missing_settlement: int = 5
    missing_bank_credit: int = 4
    duplicate_ledger: int = 1
    duplicate_bank: int = 1
    duplicate_settlement: int = 1
    refund: int = 2
    adjustment: int = 1
    ambiguous_review: int = 1

    def __post_init__(self) -> None:
        if self.same_amount_group > self.clean:
            raise ValueError("same_amount_group cannot exceed clean count")

    @property
    def total(self) -> int:
        return (
            self.clean + self.delayed_bank_credit + self.missing_utr
            + self.amount_mismatch + self.missing_settlement
            + self.missing_bank_credit + self.duplicate_ledger
            + self.duplicate_bank + self.duplicate_settlement + self.refund
            + self.adjustment + self.ambiguous_review
        )

    def scenario_plan(self) -> dict[str, int]:
        return {
            "clean": self.clean - self.same_amount_group,
            "same_amount_clean": self.same_amount_group,
            "delayed_bank_credit": self.delayed_bank_credit,
            "missing_utr": self.missing_utr,
            "amount_mismatch": self.amount_mismatch,
            "missing_settlement": self.missing_settlement,
            "missing_bank_credit": self.missing_bank_credit,
            "duplicate_ledger": self.duplicate_ledger,
            "duplicate_bank": self.duplicate_bank,
            "duplicate_settlement": self.duplicate_settlement,
            "refund": self.refund,
            "adjustment": self.adjustment,
            "ambiguous_review": self.ambiguous_review,
        }


@dataclass
class GeneratedDataset:
    ledger_rows: list[dict[str, str]] = field(default_factory=list)
    settlement_rows: list[dict[str, str]] = field(default_factory=list)
    bank_rows: list[dict[str, str]] = field(default_factory=list)
    ground_truth_rows: list[dict[str, str]] = field(default_factory=list)


def _pct(value: int, num: int, den: int) -> int:
    """Exact integer proportion (value * num // den)."""
    return value * num // den


def generate_dataset(spec: DatasetSpec, seed: int, batch_date: datetime) -> GeneratedDataset:
    """Build the full dataset deterministically from spec + seed."""
    rng = random.Random(seed)
    ds = GeneratedDataset()
    used_nets: set[int] = set()
    net_scenarios: dict[int, set[str]] = {}  # safety: a net may belong to ONE scenario

    plan: list[str] = []
    for scenario, count in spec.scenario_plan().items():
        plan.extend([scenario] * count)
    rng.shuffle(plan)

    mismatch_deltas = list(MISMATCH_DELTAS_PAISE)
    mismatch_index = 0  # cycle through deltas for scaled datasets
    # one amount shared by the same_amount_clean group, chosen and reserved
    # up front so no other scenario can ever collide with it
    trio_gross = rng.randrange(2_000, 480_001) * 100
    trio_net = _net_of(trio_gross)
    used_nets.add(trio_net)

    for index, scenario in enumerate(plan, start=1):
        pid = f"pay_{index:03d}"
        oid = f"order_{index:03d}"
        iid = f"int_{index:03d}"
        sid = f"setl_{index:03d}"
        eid = f"ent_{index:03d}"
        utr = f"UTR{index:03d}"
        btx = f"bank_{index:03d}"

        with_refund = scenario == "refund"
        adjustment = rng.randrange(1, 5) * 100 if scenario == "adjustment" else 0

        gross = trio_gross if scenario == "same_amount_clean" else rng.randrange(1_000, 500_001) * 100
        while True:
            fee = _pct(gross, 2, 100)
            tax = _pct(fee, 18, 100)
            net = gross - fee - tax
            if with_refund:
                net -= _pct(gross, 1, 4)   # 25% refund debit
            if adjustment:
                net += adjustment
            if net not in used_nets or (scenario == "same_amount_clean" and net == trio_net):
                break
            gross += 977 * 100            # deterministic collision-free retry
        used_nets.add(net)
        net_scenarios.setdefault(net, set()).add(scenario)

        # -- dates (UTC; anchored so batch as_of = batch_date 23:00) --
        if scenario == "delayed_bank_credit":
            settled = batch_date - timedelta(days=rng.randrange(0, 3)) + timedelta(hours=rng.randrange(1, 9))
        elif scenario == "missing_bank_credit":
            settled = batch_date - timedelta(days=rng.randrange(4, 7)) + timedelta(hours=rng.randrange(1, 9))
        else:
            settled = batch_date - timedelta(days=rng.randrange(3, 12)) + timedelta(hours=rng.randrange(1, 9))
        created = settled - timedelta(days=rng.randrange(1, 3), hours=rng.randrange(0, 12))
        credited = settled + timedelta(days=rng.randrange(0, 2), hours=rng.randrange(1, 6))

        def _fmt(dt: datetime) -> str:
            return dt.strftime(TIME_FORMAT)

        def _settlement_row(entity: str, row_type: str, *, amount: int = 0, fee: int = 0,
                            tax: int = 0, debit: int = 0, credit: int = 0, row_utr: str = utr) -> dict[str, str]:
            return {
                "entity_id": entity, "type": row_type, "payment_id": pid,
                "order_id": oid, "settlement_id": sid, "settlement_utr": row_utr,
                "amount_paise": str(amount), "fee_paise": str(fee),
                "tax_paise": str(tax), "debit_paise": str(debit),
                "credit_paise": str(credit), "settled_at": _fmt(settled),
            }

        def _bank_row(txn_id: str, credit: int, row_utr: str, description: str) -> dict[str, str]:
            return {
                "bank_txn_id": txn_id, "value_date": _fmt(credited),
                "description": description, "utr": row_utr,
                "credit_paise": str(credit), "debit_paise": "0",
            }

        # -- settlement rows --
        if scenario != "missing_settlement":
            payment_utr = "" if scenario in ("missing_utr", "ambiguous_review") else utr
            base_row = _settlement_row(eid, "payment", amount=gross, fee=fee, tax=tax,
                                       row_utr=payment_utr)
            ds.settlement_rows.append(base_row)
            if scenario == "duplicate_settlement":
                ds.settlement_rows.append(dict(base_row))  # exported twice
            if with_refund:
                ds.settlement_rows.append(_settlement_row(
                    f"{eid}_r", "refund", debit=_pct(gross, 1, 4), row_utr=""))
            if adjustment:
                ds.settlement_rows.append(_settlement_row(
                    f"{eid}_a", "adjustment", credit=adjustment, row_utr=""))

        # -- bank rows --
        desc_with_refs = f"NEFT CR-UTR:{utr} SETTL {sid} RZPGROUP"
        if scenario in ("clean", "same_amount_clean", "refund", "adjustment",
                        "duplicate_ledger"):
            ds.bank_rows.append(_bank_row(btx, net, utr, desc_with_refs))
        elif scenario == "duplicate_bank":
            ds.bank_rows.append(_bank_row(btx, net, utr, desc_with_refs))
            ds.bank_rows.append(_bank_row(btx, net, utr, desc_with_refs))  # exact dup
        elif scenario == "missing_utr":
            # UTRs blank on both sides; description names the settlement
            ds.bank_rows.append(_bank_row(btx, net, "", f"NEFT CR SETTL {sid} RZPGROUP"))
        elif scenario == "amount_mismatch":
            delta = mismatch_deltas[mismatch_index % len(mismatch_deltas)]
            mismatch_index += 1
            ds.bank_rows.append(_bank_row(btx, net + delta, utr, desc_with_refs))
        elif scenario == "ambiguous_review":
            ds.bank_rows.append(_bank_row(f"{btx}a", net, "", "NEFT CR-EXTERNAL REF"))
            ds.bank_rows.append(_bank_row(f"{btx}b", net, "", "NEFT CR-EXTERNAL REF"))

        # -- ledger rows --
        ledger_row = {
            "internal_id": iid, "order_id": oid, "payment_id": pid,
            "created_at": _fmt(created), "amount_paise": str(gross),
            "currency": "INR", "payment_status": "captured",
        }
        ds.ledger_rows.append(ledger_row)
        if scenario == "duplicate_ledger":
            ds.ledger_rows.append({**ledger_row, "internal_id": f"{iid}_dup"})

        # -- ground truth (exactly one row per logical payment) --
        status = SCENARIO_STATUS[scenario]
        ds.ground_truth_rows.append({
            "payment_id": pid,
            "expected_status": status,
            "expected_settlement_id": "" if scenario == "missing_settlement" else sid,
            "expected_bank_txn_id": "" if scenario in NO_BANK_SCENARIOS else btx,
            # variance labels are finalized after the loop (deltas pop in
            # appearance order); every non-mismatch scenario expects 0
            "expected_variance_paise": "0",
            "scenario": scenario,
            "expected_review_flag": "true" if status != "FULLY_RECONCILED" else "false",
        })

    # fix variance labels for amount_mismatch rows (cycling through deltas for scaled datasets)
    deltas = list(MISMATCH_DELTAS_PAISE)
    delta_index = 0
    for row in ds.ground_truth_rows:
        if row["scenario"] == "amount_mismatch":
            row["expected_variance_paise"] = str(deltas[delta_index % len(deltas)])
            delta_index += 1

    # -- noise: two debit-only bank charges; first anchors batch as_of --
    ds.bank_rows.append({
        "bank_txn_id": "bank_noise_00", "value_date": _fmt(batch_date.replace(hour=23, minute=0)),
        "description": "BANK CHARGE QUARTERLY", "utr": "UTRNOISE00",
        "credit_paise": "0", "debit_paise": "5900",
    })
    ds.bank_rows.append({
        "bank_txn_id": "bank_noise_01", "value_date": _fmt(batch_date - timedelta(days=1)),
        "description": "BANK CHARGE SMS ALERT", "utr": "UTRNOISE01",
        "credit_paise": "0", "debit_paise": "1200",
    })

    _assert_invariants(spec, ds, net_scenarios)
    return ds


def _net_of(gross: int) -> int:
    """Net for a plain (no refund/adjustment) payment — used only to let the
    same_amount_clean group share one net value intentionally."""
    fee = _pct(gross, 2, 100)
    return gross - fee - _pct(fee, 18, 100)


def _assert_invariants(
    spec: DatasetSpec,
    ds: GeneratedDataset,
    net_scenarios: dict[int, set[str]],
) -> None:
    """Fail loudly rather than emit a dataset the engine would misread."""
    from backend.models import ReconciliationStatus

    counts: dict[str, int] = {}
    for row in ds.ground_truth_rows:
        counts[row["scenario"]] = counts.get(row["scenario"], 0) + 1
    if counts != spec.scenario_plan():
        raise AssertionError(f"scenario counts {counts} != plan {spec.scenario_plan()}")
    if sum(counts.values()) != spec.total:
        raise AssertionError(f"logical payments {sum(counts.values())} != {spec.total}")

    payment_ids = [r["payment_id"] for r in ds.ground_truth_rows]
    if len(set(payment_ids)) != len(payment_ids):
        raise AssertionError("a logical payment has more than one ground-truth row")

    for row in ds.ground_truth_rows:
        ReconciliationStatus(row["expected_status"])  # raises on typo
        expected_flag = row["expected_review_flag"]
        if expected_flag != ("true" if row["expected_status"] != "FULLY_RECONCILED" else "false"):
            raise AssertionError(f"review flag inconsistent for {row['payment_id']}")

    # a net value may only be shared inside ONE scenario (same_amount_clean)
    for net, scenarios in net_scenarios.items():
        if len(scenarios) > 1:
            raise AssertionError(f"net {net} reused across scenarios {scenarios}")
    if any(int(r["credit_paise"]) <= 0 for r in ds.bank_rows if r["credit_paise"] != "0"):
        raise AssertionError("non-positive credit in bank statement")


def write_dataset(ds: GeneratedDataset, spec: DatasetSpec, seed: int, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    def _write(name: str, columns: list[str], rows: list[dict[str, str]]) -> None:
        with open(out_dir / name, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    _write("internal_ledger.csv", LEDGER_COLUMNS, ds.ledger_rows)
    _write("settlements.csv", SETTLEMENT_COLUMNS, ds.settlement_rows)
    _write("bank_statement.csv", BANK_COLUMNS, ds.bank_rows)
    _write("ground_truth.csv", GROUND_TRUTH_COLUMNS, ds.ground_truth_rows)

    status_counts: dict[str, int] = {}
    for row in ds.ground_truth_rows:
        status_counts[row["expected_status"]] = status_counts.get(row["expected_status"], 0) + 1

    manifest = {
        "dataset_version": DATASET_VERSION,
        "seed": seed,
        "total_payments": spec.total,
        "ledger_rows": len(ds.ledger_rows),
        "settlement_rows": len(ds.settlement_rows),
        "bank_rows": len(ds.bank_rows),
        "scenario_plan": spec.scenario_plan(),
        "expected_status_counts": status_counts,
        "currency": "INR",
    }
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the SettleSense synthetic dataset")
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-date", default="2026-08-20", help="anchor date (UTC)")
    parser.add_argument("--scale", type=int, default=1, help="scale factor for dataset size (default: 1 = 100 payments, 5 = 500 payments)")
    args = parser.parse_args()

    # Create base spec and scale it
    base_spec = DatasetSpec()
    scale = args.scale
    if scale != 1:
        scaled_spec = DatasetSpec(
            clean=base_spec.clean * scale,
            same_amount_group=base_spec.same_amount_group * scale,
            delayed_bank_credit=base_spec.delayed_bank_credit * scale,
            missing_utr=base_spec.missing_utr * scale,
            amount_mismatch=base_spec.amount_mismatch * scale,
            missing_settlement=base_spec.missing_settlement * scale,
            missing_bank_credit=base_spec.missing_bank_credit * scale,
            duplicate_ledger=base_spec.duplicate_ledger * scale,
            duplicate_bank=base_spec.duplicate_bank * scale,
            duplicate_settlement=base_spec.duplicate_settlement * scale,
            refund=base_spec.refund * scale,
            adjustment=base_spec.adjustment * scale,
            ambiguous_review=base_spec.ambiguous_review * scale,
        )
    else:
        scaled_spec = base_spec
    
    batch_date = datetime.fromisoformat(args.batch_date).replace(tzinfo=timezone.utc)
    ds = generate_dataset(scaled_spec, args.seed, batch_date)
    manifest = write_dataset(ds, scaled_spec, args.seed, Path(args.out_dir))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
