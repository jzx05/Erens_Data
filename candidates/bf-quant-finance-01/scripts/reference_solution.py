#!/usr/bin/env python3
"""Reference solution for bf-quant-finance-01 (CRR American option pricing).

Reads the staged inputs under base/input, prices the base case and every
scenario with a Cox-Ross-Rubinstein binomial tree, and writes exactly the two
contracted output files.

Usage:
  python3 -I scripts/reference_solution.py [--out <dir>]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

FOUR_PLACES = Decimal("0.0001")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args()


def round4(value: float) -> float:
    """Round half-up to 4 decimal places and normalise negative zero."""
    rounded = Decimal(repr(float(value))).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
    result = float(rounded)
    return 0.0 if result == 0.0 else result


def price_crr(
    spot: float,
    strike: float,
    rate: float,
    volatility: float,
    maturity: float,
    steps: int,
    dividend_yield: float,
    option_type: str,
) -> dict[str, float]:
    """Price an American option with a CRR tree and return price/Greeks.

    The European price from the same tree (without the early-exercise max) is
    returned as well so the caller can form the early-exercise premium.
    """
    dt = maturity / steps
    up = math.exp(volatility * math.sqrt(dt))
    down = 1.0 / up
    growth = math.exp((rate - dividend_yield) * dt)
    probability = (growth - down) / (up - down)
    discount = math.exp(-rate * dt)
    sign = 1.0 if option_type == "call" else -1.0

    up_powers = [up**j for j in range(steps + 1)]
    down_powers = [down**k for k in range(steps + 1)]

    terminal_spots = [
        spot * up_powers[j] * down_powers[steps - j] for j in range(steps + 1)
    ]
    american = [max(sign * (node - strike), 0.0) for node in terminal_spots]
    european = american[:]

    layer_one: list[float] | None = None
    layer_two: list[float] | None = None

    for level in range(steps - 1, -1, -1):
        next_american: list[float] = []
        next_european: list[float] = []
        for j in range(level + 1):
            node_spot = spot * up_powers[j] * down_powers[level - j]
            continuation_american = discount * (
                probability * american[j + 1] + (1.0 - probability) * american[j]
            )
            continuation_european = discount * (
                probability * european[j + 1] + (1.0 - probability) * european[j]
            )
            exercise = max(sign * (node_spot - strike), 0.0)
            next_american.append(
                continuation_american if continuation_american >= exercise else exercise
            )
            next_european.append(continuation_european)
        american = next_american
        european = next_european
        if level == 2:
            layer_two = next_american[:]
        if level == 1:
            layer_one = next_american[:]

    if layer_one is None or layer_two is None:
        raise ValueError("steps must be at least 2 to compute Delta and Gamma")

    spot_one_up = spot * up
    spot_one_down = spot * down
    spot_two_down = spot * down * down
    spot_two_mid = spot
    spot_two_up = spot * up * up

    delta = (layer_one[1] - layer_one[0]) / (spot_one_up - spot_one_down)
    delta_up = (layer_two[2] - layer_two[1]) / (spot_two_up - spot_two_mid)
    delta_down = (layer_two[1] - layer_two[0]) / (spot_two_mid - spot_two_down)
    gamma = (delta_up - delta_down) / (0.5 * (spot_two_up - spot_two_down))

    return {
        "price": american[0],
        "delta": delta,
        "gamma": gamma,
        "european_price": european[0],
    }


def read_scenarios(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def main() -> None:
    args = parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    input_dir = root / "base" / "input"
    out_dir = (args.out or root / "base" / "output").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    terms = json.loads((input_dir / "option_terms.json").read_text(encoding="utf-8"))
    option_type = str(terms["option_type"]).lower()
    if option_type not in {"put", "call"}:
        raise ValueError(f"unsupported option_type: {option_type}")

    def value(params: dict) -> dict[str, float]:
        return price_crr(
            spot=float(params["spot"]),
            strike=float(params["strike"]),
            rate=float(params["risk_free_rate"]),
            volatility=float(params["volatility"]),
            maturity=float(params["maturity_years"]),
            steps=int(params["steps"]),
            dividend_yield=float(params["dividend_yield"]),
            option_type=option_type,
        )

    # Base case: exactly the terms in option_terms.json.
    base = value(terms)

    rows: list[dict[str, object]] = []
    rounded_prices: list[float] = []
    for scenario in read_scenarios(input_dir / "scenario_grid.csv"):
        params = dict(terms)
        params["spot"] = scenario["spot"]
        params["volatility"] = scenario["volatility"]
        params["steps"] = scenario["steps"]
        result = value(params)
        intrinsic = max(
            (float(params["strike"]) - float(params["spot"]))
            if option_type == "put"
            else (float(params["spot"]) - float(params["strike"])),
            0.0,
        )
        premium = result["price"] - result["european_price"]
        rounded_prices.append(round4(result["price"]))
        rows.append(
            {
                "scenario_id": scenario["scenario_id"],
                "price": round4(result["price"]),
                "delta": round4(result["delta"]),
                "gamma": round4(result["gamma"]),
                "intrinsic_value": round4(intrinsic),
                "early_exercise_premium": round4(premium),
            }
        )

    with (out_dir / "pricing_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "scenario_id",
                "price",
                "delta",
                "gamma",
                "intrinsic_value",
                "early_exercise_premium",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (f"{value:.4f}" if isinstance(value, float) else value)
                    for key, value in row.items()
                }
            )

    best_index = 0
    for index in range(1, len(rounded_prices)):
        if rounded_prices[index] > rounded_prices[best_index]:
            best_index = index

    summary = {
        "base_case_price": round4(base["price"]),
        "base_case_delta": round4(base["delta"]),
        "base_case_gamma": round4(base["gamma"]),
        "scenario_count": len(rows),
        "highest_price_scenario": rows[best_index]["scenario_id"],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
