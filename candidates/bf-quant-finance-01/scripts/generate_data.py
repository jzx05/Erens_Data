#!/usr/bin/env python3
"""Generate the synthetic input data for bf-quant-finance-01.

The generation is fully deterministic: a fixed Mersenne-Twister seed drives the
small multiplicative jitter applied to the hand-chosen scenario anchors.

Usage:
  python3 -I scripts/generate_data.py --out base/input
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

RANDOM_SEED = 20261024

OPTION_TERMS = {
    "underlying": "SYNTH-EQ-100",
    "option_type": "put",
    "spot": 100.0,
    "strike": 105.0,
    "risk_free_rate": 0.045,
    "volatility": 0.25,
    "maturity_years": 1.0,
    "steps": 500,
    "dividend_yield": 0.015,
}

# (scenario_id, anchor spot, anchor volatility, steps)
SCENARIO_ANCHORS = [
    ("S1", 60.0, 0.12, 300),
    ("S2", 80.0, 0.30, 300),
    ("S3", 95.0, 0.22, 400),
    ("S4", 110.0, 0.28, 600),
    ("S5", 120.0, 0.35, 800),
    ("S6", 100.0, 0.15, 200),
    ("S7", 105.0, 0.40, 1000),
    ("S8", 90.0, 0.20, 500),
]

SPOT_JITTER = 0.03
VOL_JITTER = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("base/input"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    (args.out / "option_terms.json").write_text(
        json.dumps(OPTION_TERMS, indent=2) + "\n", encoding="utf-8"
    )

    rng = random.Random(RANDOM_SEED)
    rows = []
    for scenario_id, spot_anchor, vol_anchor, steps in SCENARIO_ANCHORS:
        spot = round(spot_anchor * (1.0 + rng.uniform(-SPOT_JITTER, SPOT_JITTER)), 2)
        volatility = round(
            vol_anchor * (1.0 + rng.uniform(-VOL_JITTER, VOL_JITTER)), 4
        )
        rows.append([scenario_id, spot, volatility, steps])

    with (args.out / "scenario_grid.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario_id", "spot", "volatility", "steps"])
        writer.writerows(rows)

    print(f"wrote option_terms.json and scenario_grid.csv ({len(rows)} scenarios) to {args.out}")


if __name__ == "__main__":
    main()
