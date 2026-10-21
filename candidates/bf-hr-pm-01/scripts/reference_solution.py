#!/usr/bin/env python3
"""Reference solution for bf-hr-pm-01 (employee attrition and headcount).

Reads employees.csv and writes department_attrition.csv and attrition_report.json.

Usage:
  python3 -I scripts/reference_solution.py --input-dir base/input --out base/reference/gold
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CENTS = Decimal("0.01")
HUNDRED = Decimal("100")
REPLACEMENT_MULTIPLIER = Decimal("1.5")

PERIOD_START = date(2025, 1, 1)
PERIOD_END = date(2025, 12, 31)

CSV_COLUMNS = [
    "department",
    "average_headcount",
    "terminations",
    "attrition_pct",
    "regrettable_terminations",
    "replacement_cost_usd",
]


def quantize(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def parse_date(value: str) -> date | None:
    value = value.strip()
    return date.fromisoformat(value) if value else None


def compute(input_dir: Path) -> tuple[list[dict], dict]:
    with (input_dir / "employees.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    departments = sorted({row["department"].strip() for row in rows})
    buckets: dict[str, dict] = {
        department: {
            "start": 0,
            "end": 0,
            "terminations": 0,
            "regrettable": 0,
            "replacement": Decimal("0"),
            "engagement_risk": 0,
        }
        for department in departments
    }

    for row in rows:
        department = row["department"].strip()
        bucket = buckets[department]
        hire = parse_date(row["hire_date"])
        termination = parse_date(row["termination_date"])
        salary = Decimal(row["annual_salary_usd"].strip())
        rating = int(row["performance_rating"].strip())
        engagement = Decimal(row["engagement_score"].strip())

        if hire is None:
            continue
        if hire <= PERIOD_START and (termination is None or termination >= PERIOD_START):
            bucket["start"] += 1
        if hire <= PERIOD_END and (termination is None or termination > PERIOD_END):
            bucket["end"] += 1
            if engagement < Decimal("0.4"):
                bucket["engagement_risk"] += 1
        if termination is not None and PERIOD_START <= termination <= PERIOD_END:
            bucket["terminations"] += 1
            bucket["replacement"] += salary * REPLACEMENT_MULTIPLIER
            if rating >= 4:
                bucket["regrettable"] += 1

    table: list[dict] = []
    for department in departments:
        bucket = buckets[department]
        average = (Decimal(bucket["start"]) + Decimal(bucket["end"])) / Decimal("2")
        if average == 0:
            attrition = Decimal("0")
        else:
            attrition = Decimal(bucket["terminations"]) / average * HUNDRED
        table.append(
            {
                "department": department,
                "average_headcount": quantize(average),
                "terminations": bucket["terminations"],
                "attrition_pct": quantize(attrition),
                "regrettable_terminations": bucket["regrettable"],
                "replacement_cost_usd": quantize(bucket["replacement"]),
            }
        )

    total_start = sum(bucket["start"] for bucket in buckets.values())
    total_end = sum(bucket["end"] for bucket in buckets.values())
    total_terminations = sum(bucket["terminations"] for bucket in buckets.values())
    total_regrettable = sum(bucket["regrettable"] for bucket in buckets.values())
    total_replacement = quantize(sum((bucket["replacement"] for bucket in buckets.values()), Decimal("0")))
    total_engagement_risk = sum(bucket["engagement_risk"] for bucket in buckets.values())

    overall_average = (Decimal(total_start) + Decimal(total_end)) / Decimal("2")
    if overall_average == 0:
        overall_attrition = Decimal("0")
    else:
        overall_attrition = Decimal(total_terminations) / overall_average * HUNDRED

    max_attrition = max(row["attrition_pct"] for row in table)
    highest = min(row["department"] for row in table if row["attrition_pct"] == max_attrition)

    departments_sorted = sorted(table, key=lambda row: (-row["attrition_pct"], row["department"]))

    summary = {
        "overall_attrition_pct": float(quantize(overall_attrition)),
        "regrettable_terminations": total_regrettable,
        "total_replacement_cost_usd": float(total_replacement),
        "highest_attrition_department": highest,
        "engagement_risk_headcount": total_engagement_risk,
        "departments": [
            {"department": row["department"], "attrition_pct": float(row["attrition_pct"])}
            for row in departments_sorted
        ],
    }
    return table, summary


def write_outputs(input_dir: Path, out_dir: Path) -> None:
    table, summary = compute(input_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "department_attrition.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in table:
            writer.writerow({key: str(row[key]) for key in CSV_COLUMNS})

    (out_dir / "attrition_report.json").write_text(
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
