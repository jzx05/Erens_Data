#!/usr/bin/env python3
"""Generate the deterministic synthetic campaign dataset for bf-sales-marketing-03.

The generator uses a fixed seed (20261021) and a fixed weekday seasonality
curve. Running it twice produces byte-identical output.

Usage:
  python3 -I scripts/generate_dataset.py [--out <path>]
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261021
START_DATE = date(2026, 7, 6)  # Monday
N_DAYS = 56  # 8 consecutive weeks
WEEKDAY_FACTORS = [0.92, 1.03, 1.05, 1.04, 1.02, 0.90, 0.84]  # Monday..Sunday
WEEKLY_GROWTH = 0.02  # +2% week over week

# name, channel_group, owner, base daily impressions, ctr, lead_rate, cvr, cpm_usd, aov_usd
CHANNELS = [
    ("Paid Search", "Search", "Performance Marketing", 66700, 0.0450, 0.100, 0.0500, 45.00, 110.00),
    ("Paid Social", "Social", "Brand & Social", 100000, 0.0120, 0.080, 0.0350, 18.00, 95.00),
    ("Display", "Display", "Programmatic", 525000, 0.0050, 0.040, 0.0200, 8.00, 95.00),
    ("Email", "Owned", "Lifecycle CRM", 238000, 0.0250, 0.120, 0.0700, 9.00, 60.00),
    ("Affiliate", "Partner", "Partnerships", 36000, 0.0200, 0.150, 0.0600, 25.00, 85.00),
    ("Podcast", "Audio", "Brand & Social", 30000, 0.0100, 0.050, 0.0300, 20.00, 130.00),
]

COLUMNS = [
    "date",
    "channel",
    "impressions",
    "clicks",
    "leads",
    "conversions",
    "spend_usd",
    "revenue_usd",
]


def build_rows() -> list[dict]:
    rng = random.Random(SEED)
    rows: list[dict] = []
    for day_index in range(N_DAYS):
        current = START_DATE + timedelta(days=day_index)
        weekday_factor = WEEKDAY_FACTORS[current.weekday()]
        growth_factor = 1.0 + WEEKLY_GROWTH * (day_index // 7)
        for name, _group, _owner, base_impressions, ctr, lead_rate, cvr, cpm, aov in CHANNELS:
            impressions = max(
                1,
                int(round(base_impressions * weekday_factor * growth_factor * rng.uniform(0.90, 1.10))),
            )
            clicks = max(1, int(round(impressions * ctr * rng.uniform(0.92, 1.08))))
            leads = max(0, int(round(clicks * lead_rate * rng.uniform(0.85, 1.15))))
            conversions = max(1, int(round(clicks * cvr * rng.uniform(0.85, 1.15))))
            spend = round(impressions / 1000.0 * cpm * rng.uniform(0.94, 1.06), 2)
            revenue = round(conversions * aov * rng.uniform(0.90, 1.10), 2)
            rows.append(
                {
                    "date": current.isoformat(),
                    "channel": name,
                    "impressions": impressions,
                    "clicks": clicks,
                    "leads": leads,
                    "conversions": conversions,
                    "spend_usd": f"{spend:.2f}",
                    "revenue_usd": f"{revenue:.2f}",
                }
            )
    return rows


def write_csv(path: Path) -> int:
    rows = build_rows()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default_out = Path(__file__).resolve().parent.parent / "base" / "input" / "campaign_data.csv"
    parser.add_argument("--out", type=Path, default=default_out)
    args = parser.parse_args()
    count = write_csv(args.out)
    print(f"wrote {count} rows to {args.out}")


if __name__ == "__main__":
    main()
