#!/usr/bin/env python3
"""Reference solution for bf-accounting-01 (corporate income tax and deferred tax).

Reads financials.csv and writes tax_computation.csv and tax_summary.json.

Usage:
  python3 -I scripts/reference_solution.py --input-dir base/input --out base/reference/gold
"""

from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CENTS = Decimal("0.01")
HUNDRED = Decimal("100")

CSV_COLUMNS = [
    "entity",
    "current_tax_usd",
    "deferred_tax_expense_usd",
    "total_tax_expense_usd",
    "effective_tax_rate_pct",
    "deferred_tax_balance_usd",
]


def money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def compute(input_dir: Path) -> tuple[list[dict], dict]:
    with (input_dir / "financials.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    computed: list[dict] = []
    for row in rows:
        pretax = Decimal(row["pretax_income_usd"].strip())
        permanent = Decimal(row["permanent_differences_usd"].strip())
        temporary = Decimal(row["temporary_differences_usd"].strip())
        rate = Decimal(row["statutory_tax_rate"].strip())
        prior = Decimal(row["prior_deferred_tax_balance_usd"].strip())

        current = (pretax + permanent) * rate
        deferred = temporary * rate
        total = current + deferred
        effective = total / pretax * HUNDRED
        balance = prior + deferred

        computed.append(
            {
                "entity": row["entity"].strip(),
                "current_tax_usd": money(current),
                "deferred_tax_expense_usd": money(deferred),
                "total_tax_expense_usd": money(total),
                "effective_tax_rate_pct": money(effective),
                "deferred_tax_balance_usd": money(balance),
                "pretax_income_usd": pretax,
            }
        )

    computed.sort(key=lambda item: item["entity"])

    total_current = money(sum(item["current_tax_usd"] for item in computed))
    total_deferred = money(sum(item["deferred_tax_expense_usd"] for item in computed))
    total_tax = money(sum(item["total_tax_expense_usd"] for item in computed))
    total_pretax = sum(item["pretax_income_usd"] for item in computed)
    weighted_effective = money(total_tax / total_pretax * HUNDRED)

    # Deterministic tie-break: largest amount, then lexicographically smallest entity.
    max_deferred = max(item["deferred_tax_expense_usd"] for item in computed)
    largest_entity = min(
        item["entity"] for item in computed if item["deferred_tax_expense_usd"] == max_deferred
    )

    summary = {
        "total_current_tax_usd": float(total_current),
        "total_deferred_tax_expense_usd": float(total_deferred),
        "total_tax_expense_usd": float(total_tax),
        "weighted_effective_tax_rate_pct": float(weighted_effective),
        "entity_with_largest_deferred_tax_expense": largest_entity,
    }
    return computed, summary


def write_outputs(input_dir: Path, out_dir: Path) -> None:
    computed, summary = compute(input_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "tax_computation.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=CSV_COLUMNS, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        for item in computed:
            writer.writerow({key: str(item[key]) for key in CSV_COLUMNS})

    (out_dir / "tax_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    input_dir = (args.input_dir or root / "base" / "input").resolve()
    write_outputs(input_dir, args.out.resolve())
    print(f"wrote gold outputs to {args.out}")


if __name__ == "__main__":
    main()
