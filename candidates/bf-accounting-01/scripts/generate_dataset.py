#!/usr/bin/env python3
"""Generate the deterministic synthetic tax dataset for bf-accounting-01.

Usage:
  python3 -I scripts/generate_dataset.py --out base/input/financials.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

SEED = 20261024

ENTITIES = [
    "Arcadia",
    "Bluewater",
    "Crestline",
    "Duneshore",
]

COLUMNS = [
    "entity",
    "pretax_income_usd",
    "permanent_differences_usd",
    "temporary_differences_usd",
    "statutory_tax_rate",
    "prior_deferred_tax_balance_usd",
]

# Fixed generation parameters (also recorded in source_pack/dataset_manifest.txt).
PRETAX_RANGE = (400_000, 2_600_000)
PRETAX_STEP = 1_000
PERMANENT_RANGE = (-60_000, 60_000)
PERMANENT_STEP = 500
TEMPORARY_RANGE = (-90_000, 90_000)
TEMPORARY_STEP = 1_000
STATUTORY_RATES = [0.21, 0.215, 0.24, 0.25]
PRIOR_BALANCE_RANGE = (-30_000, 200_000)
PRIOR_BALANCE_STEP = 500


def rounded_draw(rng: random.Random, low: int, high: int, step: int) -> int:
    steps = (high - low) // step
    return low + rng.randint(0, steps) * step


def build_rows() -> list[dict]:
    rng = random.Random(SEED)
    rows = []
    for index, entity in enumerate(ENTITIES):
        rows.append(
            {
                "entity": entity,
                "pretax_income_usd": f"{rounded_draw(rng, *PRETAX_RANGE, PRETAX_STEP)}",
                "permanent_differences_usd": f"{rounded_draw(rng, *PERMANENT_RANGE, PERMANENT_STEP)}",
                "temporary_differences_usd": f"{rounded_draw(rng, *TEMPORARY_RANGE, TEMPORARY_STEP)}",
                "statutory_tax_rate": f"{STATUTORY_RATES[rng.randrange(len(STATUTORY_RATES))]:.3f}",
                "prior_deferred_tax_balance_usd": f"{rounded_draw(rng, *PRIOR_BALANCE_RANGE, PRIOR_BALANCE_STEP)}",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
