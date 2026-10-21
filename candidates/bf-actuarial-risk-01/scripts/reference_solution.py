#!/usr/bin/env python3
"""Reference solution for bf-actuarial-risk-01.

Reads the staged ledger and gross-income inputs, applies the taxonomy policy in
``base/input/risk_taxonomy_policy.md`` (the per-event classification decisions
are recorded in ``event_catalog.py``), computes the BIA capital and writes the
three contracted gold outputs.

Usage:
  python3 -I scripts/reference_solution.py [--candidate-root <dir>] [--out <dir>]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from event_catalog import EVENT_BY_ID

ALPHA = Decimal("0.15")
TWO_PLACES = Decimal("0.01")
EXPECTED_EVENT_COUNT = 60

EXECUTION_LOG = """Huachen Bank - operational risk classification and BIA capital
==================================================================

Inputs inspected
- operational_risk_events.csv: 60 loss events read and checked against the ledger.
- risk_taxonomy_policy.md and business_line_guide.csv: EL and BL definitions applied.
- gross_income.csv: 6 fiscal years read.

Classification method
1. For each event, assign the loss-event category from the proximate cause using the EL1-EL7 precedence order.
2. Assign the business line from the product, customer or activity that generated the loss; the recorded department is corroborating evidence only.
3. Copy the loss amount from the ledger without any adjustment.

BIA capital steps
1. Include only fiscal years whose gross income is strictly greater than zero.
2. Sum the included gross income values and divide by the count of positive years.
3. Multiply the unrounded average by alpha = 0.15.
4. Round the average and the capital charge to two decimals using round-half-up.

Result
- The positive-year count, the positive gross-income sum, the rounded average and the capital charge are recorded in capital_calculation.json.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def round_half_up(value: Decimal) -> Decimal:
    rounded = value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return Decimal("0.00") if rounded == 0 else rounded


def main() -> None:
    args = parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    input_dir = root / "base" / "input"
    out_dir = (args.out or root / "base" / "output").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    events = read_csv(input_dir / "operational_risk_events.csv")
    if len(events) != EXPECTED_EVENT_COUNT:
        raise SystemExit(f"expected {EXPECTED_EVENT_COUNT} events, found {len(events)}")

    classified_rows: list[list[object]] = []
    seen: set[str] = set()
    for row in events:
        event_id = row["Event_ID"].strip()
        if event_id in seen:
            raise SystemExit(f"duplicate Event_ID in ledger: {event_id}")
        seen.add(event_id)
        spec = EVENT_BY_ID.get(event_id)
        if spec is None:
            raise SystemExit(f"unknown Event_ID in ledger: {event_id}")
        if row["Event_Description_CN"].strip() != spec["description_cn"]:
            raise SystemExit(f"description mismatch for {event_id}")
        if row["Involved_Department"].strip() != spec["department"]:
            raise SystemExit(f"department mismatch for {event_id}")
        amount = int(row["Loss_Amount_CNY"])
        classified_rows.append([event_id, spec["el"], spec["bl"], amount])

    if seen != set(EVENT_BY_ID):
        missing = sorted(set(EVENT_BY_ID) - seen)
        raise SystemExit("ledger is missing Event_IDs: " + ", ".join(missing))

    with (out_dir / "classified_events.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Event_ID", "Loss_Event_Category", "Business_Line", "Loss_Amount_CNY"])
        writer.writerows(classified_rows)

    income_rows = read_csv(input_dir / "gross_income.csv")
    gross_income_years: dict[str, float] = {}
    positive_values: list[Decimal] = []
    for row in income_rows:
        year = row["year"].strip()
        value = Decimal(row["gross_income_cny"].strip())
        gross_income_years[year] = float(value)
        if value > 0:
            positive_values.append(value)

    positive_count = len(positive_values)
    if positive_count:
        total = sum(positive_values, Decimal("0"))
        average = total / Decimal(positive_count)
    else:
        total = Decimal("0")
        average = Decimal("0")
    capital = ALPHA * average

    payload = {
        "alpha": float(ALPHA),
        "gross_income_years": gross_income_years,
        "positive_year_count": positive_count,
        "positive_gi_sum_cny": float(total),
        "average_positive_gi_cny": float(round_half_up(average)),
        "or_capital_cny": float(round_half_up(capital)),
    }
    (out_dir / "capital_calculation.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    (out_dir / "execution_log.txt").write_text(EXECUTION_LOG, encoding="utf-8")

    print(f"wrote {len(classified_rows)} classified events and BIA capital to {out_dir}")


if __name__ == "__main__":
    main()
