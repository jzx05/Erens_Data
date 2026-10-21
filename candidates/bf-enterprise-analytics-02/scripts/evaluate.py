#!/usr/bin/env python3
"""Evaluate dashboard_metrics.json for the SQLite BI task."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

SCALARS = ["total_revenue", "average_order_value", "conversion_rate"]
INTEGERS = ["total_completed_orders", "unique_purchasing_customers"]
NUMERIC_DICTS = ["revenue_by_category", "monthly_revenue"]
INTEGER_DICTS = ["orders_by_device", "orders_by_channel", "event_funnel"]
TOP = "top_10_customers"
ALL_FIELDS = SCALARS + INTEGERS + NUMERIC_DICTS + INTEGER_DICTS + [TOP]


def load_metrics():
    path = Path(__file__).with_name("metrics.py")
    spec = importlib.util.spec_from_file_location("bi_metrics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def relative_close(actual, expected, tolerance: float = 0.005) -> bool:
    try:
        actual = float(actual)
        expected = float(expected)
    except (TypeError, ValueError):
        return False
    if expected == 0:
        return abs(actual) <= 0.005
    return abs(actual - expected) / abs(expected) <= tolerance


def numeric_dict_score(actual, expected: dict) -> float:
    if not isinstance(actual, dict) or not expected:
        return 0.0
    matches = sum(
        1 for key, value in expected.items() if relative_close(actual.get(key), value)
    )
    return matches / len(expected)


def integer_dict_score(actual, expected: dict) -> float:
    if not isinstance(actual, dict) or not expected:
        return 0.0
    matches = sum(
        1 for key, value in expected.items() if actual.get(key) == value
    )
    return matches / len(expected)


def top_score(actual, expected: list) -> float:
    if not isinstance(actual, list) or not expected:
        return 0.0
    matches = 0
    for index, expected_item in enumerate(expected):
        if index >= len(actual) or not isinstance(actual[index], dict):
            continue
        item = actual[index]
        if (
            item.get("customer_id") == expected_item["customer_id"]
            and item.get("customer_name") == expected_item["customer_name"]
            and relative_close(item.get("total_spend"), expected_item["total_spend"])
        ):
            matches += 1
    return matches / len(expected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    output_dir = (args.output_dir or root / "base" / "output").resolve()
    metrics = load_metrics()
    expected = metrics.compute(root)

    submission_path = output_dir / "dashboard_metrics.json"
    submission = {}
    parse_error = None
    if submission_path.is_file():
        try:
            submission = json.loads(submission_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
    else:
        parse_error = "missing dashboard_metrics.json"

    field_scores = {}
    checks = []
    if isinstance(submission, dict):
        for field in SCALARS:
            score = 1.0 if relative_close(submission.get(field), expected[field]) else 0.0
            field_scores[field] = score
            checks.append({"field": field, "score": score, "expected": expected[field], "actual": submission.get(field)})
        for field in INTEGERS:
            score = 1.0 if submission.get(field) == expected[field] else 0.0
            field_scores[field] = score
            checks.append({"field": field, "score": score, "expected": expected[field], "actual": submission.get(field)})
        for field in NUMERIC_DICTS:
            score = numeric_dict_score(submission.get(field), expected[field])
            field_scores[field] = score
            checks.append({"field": field, "score": score, "expected_keys": len(expected[field]), "actual_keys": len(submission.get(field, {})) if isinstance(submission.get(field), dict) else None})
        for field in INTEGER_DICTS:
            score = integer_dict_score(submission.get(field), expected[field])
            field_scores[field] = score
            checks.append({"field": field, "score": score, "expected_keys": len(expected[field]), "actual_keys": len(submission.get(field, {})) if isinstance(submission.get(field), dict) else None})
        score = top_score(submission.get(TOP), expected[TOP])
        field_scores[TOP] = score
        checks.append({"field": TOP, "score": score, "expected": expected[TOP], "actual": submission.get(TOP)})
    else:
        for field in ALL_FIELDS:
            field_scores[field] = 0.0
        checks.append({"field": "root", "score": 0.0, "error": parse_error})

    total = sum(field_scores.values()) / len(ALL_FIELDS)
    print(
        json.dumps(
            {
                "score": total,
                "passed": abs(total - 1.0) < 1e-9,
                "field_scores": field_scores,
                "checks": checks,
                "parse_error": parse_error,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
