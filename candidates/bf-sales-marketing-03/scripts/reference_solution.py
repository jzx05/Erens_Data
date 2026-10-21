#!/usr/bin/env python3
"""Reference solution for bf-sales-marketing-03.

Reads `base/input/campaign_data.csv` and writes the two contracted outputs:
`channel_performance.csv` and `budget_recommendation.json`.

All arithmetic uses Decimal with round-half-up at the final reporting step, as required by
`base/input/analysis_policy.md`. Python 3.12 standard library only.

Usage:
  python3 -I scripts/reference_solution.py [--candidate-root <dir>] [--out <dir>]
"""

from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path

getcontext().prec = 50
CENT = Decimal("0.01")
HUNDRED = Decimal("100")
MOVE_RATE = Decimal("0.20")
CAP_RATE = Decimal("0.25")

TOTAL_FIELDS = ("impressions", "clicks", "leads", "conversions", "spend_usd", "revenue_usd")
CSV_COLUMNS = [
    "channel",
    "impressions",
    "clicks",
    "leads",
    "conversions",
    "spend_usd",
    "revenue_usd",
    "ctr_pct",
    "lead_rate_pct",
    "cvr_pct",
    "cpa_usd",
    "roas",
    "roas_rank",
]


def q2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def money(value: Decimal) -> str:
    return f"{q2(value):.2f}"


def load_channel_totals(path: Path) -> dict[str, dict[str, Decimal]]:
    totals: dict[str, dict[str, Decimal]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in ("date", "channel", *TOTAL_FIELDS) if column not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path}: missing columns: {missing}")
        for row in reader:
            channel = row["channel"]
            bucket = totals.setdefault(channel, {field: Decimal("0") for field in TOTAL_FIELDS})
            for field in TOTAL_FIELDS:
                bucket[field] += Decimal(row[field])
    if not totals:
        raise SystemExit(f"{path}: no data rows")
    return totals


def compute(totals: dict[str, dict[str, Decimal]]) -> dict:
    metrics: dict[str, dict[str, Decimal]] = {}
    for channel, bucket in totals.items():
        if bucket["impressions"] <= 0 or bucket["clicks"] <= 0 or bucket["conversions"] <= 0:
            raise SystemExit(f"{channel}: zero denominator in the metric definitions")
        if bucket["spend_usd"] <= 0:
            raise SystemExit(f"{channel}: zero spend")
        metrics[channel] = {
            "ctr_pct": bucket["clicks"] / bucket["impressions"] * HUNDRED,
            "lead_rate_pct": bucket["leads"] / bucket["clicks"] * HUNDRED,
            "cvr_pct": bucket["conversions"] / bucket["clicks"] * HUNDRED,
            "cpa_usd": bucket["spend_usd"] / bucket["conversions"],
            "roas": bucket["revenue_usd"] / bucket["spend_usd"],
        }

    ranked = sorted(totals, key=lambda name: (-metrics[name]["roas"], name))
    ranks = {channel: index for index, channel in enumerate(ranked, 1)}

    total_spend = sum((bucket["spend_usd"] for bucket in totals.values()), Decimal("0"))
    total_revenue = sum((bucket["revenue_usd"] for bucket in totals.values()), Decimal("0"))
    blended_roas = total_revenue / total_spend

    lowest = ranked[-1]
    highest = ranked[0]
    lowest_spend = totals[lowest]["spend_usd"]
    highest_spend = totals[highest]["spend_usd"]
    raw_move = MOVE_RATE * lowest_spend
    cap = CAP_RATE * highest_spend
    reallocation = q2(min(raw_move, cap))

    budgets = []
    for channel in ranked:
        current = totals[channel]["spend_usd"]
        recommended = current
        if channel == lowest:
            recommended = current - reallocation
        elif channel == highest:
            recommended = current + reallocation
        budgets.append(
            {
                "channel": channel,
                "current_spend_usd": float(q2(current)),
                "recommended_budget_usd": float(q2(recommended)),
            }
        )

    report = {
        "total_spend_usd": float(q2(total_spend)),
        "total_revenue_usd": float(q2(total_revenue)),
        "blended_roas": float(q2(blended_roas)),
        "lowest_roas_channel": lowest,
        "lowest_roas": float(q2(metrics[lowest]["roas"])),
        "highest_roas_channel": highest,
        "highest_roas": float(q2(metrics[highest]["roas"])),
        "reallocation_amount_usd": float(reallocation),
        "reallocation_cap_usd": float(q2(cap)),
        "recommended_budgets": budgets,
    }

    return {
        "totals": totals,
        "metrics": metrics,
        "ranks": ranks,
        "ranked": ranked,
        "report": report,
    }


def write_channel_performance(path: Path, computed: dict) -> None:
    totals = computed["totals"]
    metrics = computed["metrics"]
    ranks = computed["ranks"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for channel in computed["ranked"]:
            bucket = totals[channel]
            metric = metrics[channel]
            writer.writerow(
                [
                    channel,
                    int(bucket["impressions"]),
                    int(bucket["clicks"]),
                    int(bucket["leads"]),
                    int(bucket["conversions"]),
                    money(bucket["spend_usd"]),
                    money(bucket["revenue_usd"]),
                    money(metric["ctr_pct"]),
                    money(metric["lead_rate_pct"]),
                    money(metric["cvr_pct"]),
                    money(metric["cpa_usd"]),
                    money(metric["roas"]),
                    ranks[channel],
                ]
            )


def write_budget_recommendation(path: Path, computed: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(computed["report"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, default=root)
    parser.add_argument("--out", type=Path, default=None,
                        help="Output directory; defaults to <candidate-root>/base/reference/gold")
    parser.add_argument("--input", type=Path, default=None,
                        help="campaign_data.csv path; defaults to <candidate-root>/base/input/campaign_data.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.candidate_root.expanduser().resolve()
    out_dir = (args.out or (root / "base" / "reference" / "gold")).expanduser().resolve()
    input_path = (args.input or (root / "base" / "input" / "campaign_data.csv")).expanduser().resolve()

    totals = load_channel_totals(input_path)
    computed = compute(totals)
    write_channel_performance(out_dir / "channel_performance.csv", computed)
    write_budget_recommendation(out_dir / "budget_recommendation.json", computed)
    print(f"wrote channel_performance.csv and budget_recommendation.json to {out_dir}")


if __name__ == "__main__":
    main()
