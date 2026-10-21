#!/usr/bin/env python3
"""Standalone evaluator for bf-quant-finance-01 (CRR American option pricing).

Compares the submission under --output-dir with the gold files in
base/reference/gold/. Numeric cells are compared with the tolerance declared in
base/reference/verification_contract.json; structural checks are exact.

Usage:
  python3 -I scripts/evaluate.py --candidate-root <dir> --output-dir <dir>
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def main() -> None:
    args = parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    output_dir = (args.output_dir or root / "base" / "output").resolve()
    contract = load_json(root / "base" / "input" / "output_contract.json")
    verification = load_json(root / "base" / "reference" / "verification_contract.json")
    tolerance = float(verification.get("tolerance", 1e-4))
    gold_dir = root / "base" / "reference" / "gold"

    gold_summary = load_json(gold_dir / "summary.json")
    gold_fields, gold_rows = read_rows(gold_dir / "pricing_results.csv")

    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, expected: Any = None, actual: Any = None) -> None:
        checks.append(
            {
                "name": name,
                "passed": bool(passed),
                "expected": expected,
                "actual": actual,
            }
        )

    def check_number(name: str, actual: Any, expected: float) -> None:
        number = as_number(actual)
        passed = number is not None and abs(number - expected) <= tolerance
        check(name, passed, expected, actual)

    # ---------------------------------------------------------------- pricing CSV
    pricing_path = output_dir / "pricing_results.csv"
    submitted_fields: list[str] = []
    submitted_rows: list[dict[str, str]] = []
    pricing_readable = False
    if not pricing_path.is_file():
        check("pricing_results.csv exists", False, "present", "missing")
    else:
        try:
            submitted_fields, submitted_rows = read_rows(pricing_path)
            pricing_readable = True
        except (OSError, UnicodeError, csv.Error) as exc:
            check("pricing_results.csv parses", False, "valid CSV", str(exc))

    if pricing_readable:
        check("pricing_results.csv exists", True, "present", "present")
        check(
            "pricing_results.csv header",
            submitted_fields == gold_fields,
            gold_fields,
            submitted_fields,
        )
        check(
            "pricing_results.csv row count",
            len(submitted_rows) == len(gold_rows),
            len(gold_rows),
            len(submitted_rows),
        )
        numeric_columns = [
            "price",
            "delta",
            "gamma",
            "intrinsic_value",
            "early_exercise_premium",
        ]
        for index, gold_row in enumerate(gold_rows):
            label = gold_row["scenario_id"]
            if index >= len(submitted_rows):
                check(f"{label} row present", False, label, "missing")
                continue
            row = submitted_rows[index]
            check(
                f"{label} scenario_id",
                row.get("scenario_id") == gold_row["scenario_id"],
                gold_row["scenario_id"],
                row.get("scenario_id"),
            )
            for column in numeric_columns:
                check_number(
                    f"{label} {column}",
                    row.get(column),
                    float(gold_row[column]),
                )
    else:
        for gold_row in gold_rows:
            label = gold_row["scenario_id"]
            check(f"{label} row present", False, label, "missing")
            for column in (
                "price",
                "delta",
                "gamma",
                "intrinsic_value",
                "early_exercise_premium",
            ):
                check(f"{label} {column}", False, float(gold_row[column]), None)

    # ---------------------------------------------------------------- summary JSON
    summary_path = output_dir / "summary.json"
    submitted_summary: Any = None
    summary_readable = False
    if not summary_path.is_file():
        check("summary.json exists", False, "present", "missing")
    else:
        try:
            submitted_summary = load_json(summary_path)
            summary_readable = True
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            check("summary.json parses", False, "valid JSON object", str(exc))

    if summary_readable:
        check("summary.json exists", True, "present", "present")
        if not isinstance(submitted_summary, dict):
            check("summary.json is an object", False, "object", type(submitted_summary).__name__)
            check("summary.json keys", False, sorted(gold_summary), None)
            for key in ("base_case_price", "base_case_delta", "base_case_gamma"):
                check(f"summary {key}", False, float(gold_summary[key]), None)
            check("summary scenario_count", False, gold_summary["scenario_count"], None)
            check(
                "summary highest_price_scenario",
                False,
                gold_summary["highest_price_scenario"],
                None,
            )
        else:
            check(
                "summary.json keys",
                set(submitted_summary) == set(gold_summary),
                sorted(gold_summary),
                sorted(submitted_summary),
            )
            for key in ("base_case_price", "base_case_delta", "base_case_gamma"):
                check_number(
                    f"summary {key}", submitted_summary.get(key), float(gold_summary[key])
                )
            count_value = as_number(submitted_summary.get("scenario_count"))
            check(
                "summary scenario_count",
                count_value is not None and count_value == float(gold_summary["scenario_count"]),
                gold_summary["scenario_count"],
                submitted_summary.get("scenario_count"),
            )
            check(
                "summary highest_price_scenario",
                submitted_summary.get("highest_price_scenario")
                == gold_summary["highest_price_scenario"],
                gold_summary["highest_price_scenario"],
                submitted_summary.get("highest_price_scenario"),
            )
    else:
        check("summary.json keys", False, sorted(gold_summary), None)
        for key in ("base_case_price", "base_case_delta", "base_case_gamma"):
            check(f"summary {key}", False, float(gold_summary[key]), None)
        check("summary scenario_count", False, gold_summary["scenario_count"], None)
        check(
            "summary highest_price_scenario",
            False,
            gold_summary["highest_price_scenario"],
            None,
        )

    passed = sum(1 for item in checks if item["passed"])
    total = len(checks)
    score = passed / total if total else 0.0
    print(
        json.dumps(
            {
                "score": score,
                "passed": score == 1.0,
                "checks_passed": passed,
                "checks_total": total,
                "tolerance": tolerance,
                "checks": checks,
                "notes": [
                    "Numeric values are compared with an absolute tolerance of "
                    f"{tolerance}; structure and identifiers are exact."
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
