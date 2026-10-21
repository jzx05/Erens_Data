#!/usr/bin/env python3
"""Generate the deterministic synthetic employee dataset for bf-hr-pm-01.

Usage:
  python3 -I scripts/generate_dataset.py --out base/input/employees.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261028

COLUMNS = [
    "employee_id",
    "department",
    "hire_date",
    "termination_date",
    "annual_salary_usd",
    "performance_rating",
    "engagement_score",
    "manager_id",
]

DEPARTMENTS = {
    "Engineering": {"headcount": 40, "base_salary": 118_000, "termination_probability": 0.20, "managers": ["MGR-ENG-01", "MGR-ENG-02", "MGR-ENG-03"]},
    "Finance": {"headcount": 30, "base_salary": 94_000, "termination_probability": 0.23, "managers": ["MGR-FIN-01", "MGR-FIN-02"]},
    "Human Resources": {"headcount": 20, "base_salary": 72_000, "termination_probability": 0.18, "managers": ["MGR-HR-01", "MGR-HR-02"]},
    "Marketing": {"headcount": 25, "base_salary": 81_000, "termination_probability": 0.30, "managers": ["MGR-MKT-01", "MGR-MKT-02"]},
    "Sales": {"headcount": 35, "base_salary": 76_000, "termination_probability": 0.36, "managers": ["MGR-SLS-01", "MGR-SLS-02", "MGR-SLS-03"]},
}

HIRE_START = date(2022, 1, 1).toordinal()
HIRE_END = date(2025, 12, 10).toordinal()

# Termination event distribution: pre-period, in-period, post-period.
TERMINATION_YEAR_WEIGHTS = [(2023, 0.05), (2024, 0.10), (2025, 0.55), (2026, 0.30)]

PERFORMANCE_WEIGHTS = [(1, 0.05), (2, 0.10), (3, 0.45), (4, 0.28), (5, 0.12)]


def weighted_choice(rng: random.Random, pairs: list[tuple[int, float]]) -> int:
    total = sum(weight for _, weight in pairs)
    point = rng.random() * total
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += weight
        if point <= cumulative:
            return value
    return pairs[-1][0]


def random_date_in_year(rng: random.Random, year: int) -> date:
    start = date(year, 1, 1).toordinal()
    end = date(year, 12, 31).toordinal()
    return date.fromordinal(rng.randint(start, end))


def build_rows(seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    counter = 0
    for department, config in DEPARTMENTS.items():
        for _ in range(config["headcount"]):
            counter += 1
            employee_id = f"E{counter:04d}"
            hire = date.fromordinal(rng.randint(HIRE_START, HIRE_END))

            termination: date | None = None
            if rng.random() < config["termination_probability"]:
                year = weighted_choice(rng, TERMINATION_YEAR_WEIGHTS)
                candidate = random_date_in_year(rng, year)
                if candidate >= hire + timedelta(days=45):
                    termination = candidate

            salary = int(round(config["base_salary"] * rng.uniform(0.72, 1.34), -2))
            rating = weighted_choice(rng, PERFORMANCE_WEIGHTS)
            engagement = round(rng.uniform(0.05, 0.99), 2)
            manager_id = rng.choice(config["managers"])

            rows.append(
                {
                    "employee_id": employee_id,
                    "department": department,
                    "hire_date": hire.isoformat(),
                    "termination_date": termination.isoformat() if termination else "",
                    "annual_salary_usd": str(salary),
                    "performance_rating": str(rating),
                    "engagement_score": f"{engagement:.2f}",
                    "manager_id": manager_id,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    rows = build_rows(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
