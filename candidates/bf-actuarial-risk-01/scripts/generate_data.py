#!/usr/bin/env python3
"""Deterministically generate the synthetic operational-risk ledger inputs.

Outputs (under ``--out``, normally ``base/input``):

* ``operational_risk_events.csv`` - 60 loss events (no labels)
* ``gross_income.csv``            - six fiscal years of audited gross income

The event narratives, departments, categories and business lines are fixed in
``event_catalog.py``.  A single Mersenne-Twister stream seeded with
``RANDOM_SEED`` drives two draws per event: a multiplicative loss-amount
jitter of +/-3% (rounded to the nearest 100 CNY) and a date offset of +/-20
days from the anchor date.  Gross income is a fixed audited series containing
one loss year and one zero year.

Run:
  python3 -I scripts/generate_data.py --out base/input
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from event_catalog import EVENT_SPECS

RANDOM_SEED = 20261021
AMOUNT_JITTER = 0.03
DATE_JITTER_DAYS = 20

# (fiscal year, audited gross income in CNY, note)
GROSS_INCOME_ROWS = [
    (2019, "3148620123.45", "Audited annual accounts"),
    (2020, "3526940287.18", "Audited annual accounts"),
    (2021, "-486200000.00", "Loss year: restructuring and credit provisions"),
    (2022, "4012375011.36", "Audited annual accounts"),
    (2023, "0.00", "No gross income recorded; overseas subsidiary divested"),
    (2024, "4368150042.28", "Audited annual accounts"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("base/input"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(RANDOM_SEED)
    rows = []
    for spec in EVENT_SPECS:
        jittered = spec["amount_anchor"] * (1.0 + rng.uniform(-AMOUNT_JITTER, AMOUNT_JITTER))
        amount = int(round(jittered / 100.0) * 100)
        anchor_date = date.fromisoformat(spec["date_anchor"])
        event_date = anchor_date + timedelta(days=rng.randint(-DATE_JITTER_DAYS, DATE_JITTER_DAYS))
        rows.append(
            (
                spec["event_id"],
                spec["description_cn"],
                amount,
                event_date.isoformat(),
                spec["department"],
            )
        )

    with (args.out / "operational_risk_events.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["Event_ID", "Event_Description_CN", "Loss_Amount_CNY", "Event_Date", "Involved_Department"]
        )
        writer.writerows(rows)

    with (args.out / "gross_income.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["year", "gross_income_cny", "notes"])
        writer.writerows(GROSS_INCOME_ROWS)

    print(f"wrote {len(rows)} events and {len(GROSS_INCOME_ROWS)} gross-income years to {args.out}")


if __name__ == "__main__":
    main()
