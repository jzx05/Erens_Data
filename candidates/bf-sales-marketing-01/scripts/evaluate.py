#!/usr/bin/env python3
"""Evaluate the 90% CI + Holm A/B test task."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path


def load_stats():
    path = Path(__file__).with_name("stats.py")
    spec = importlib.util.spec_from_file_location("ab_stats", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path, delimiter: str = ",") -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def numbers_close(actual, expected, tolerance: float = 1e-6) -> bool:
    try:
        return abs(float(actual) - float(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    output_dir = (args.output_dir or root / "base" / "output").resolve()
    stats = load_stats()
    expected = stats.compute(root)

    checks: list[dict] = []

    def check(name: str, passed: bool, expected_value=None, actual_value=None) -> None:
        checks.append(
            {
                "name": name,
                "passed": bool(passed),
                "expected": expected_value,
                "actual": actual_value,
            }
        )

    assignment_path = output_dir / "randomization_assignment.csv"
    assignment = {}
    if assignment_path.is_file():
        assignment = {row["metric"]: row["value"] for row in read_csv(assignment_path)}
    else:
        check("assignment file exists", False, "randomization_assignment.csv", None)
    for key in ("n_control", "n_treatment"):
        value = assignment.get(key)
        check(f"assignment {key}", value is not None and int(float(value)) == expected[key], expected[key], value)
    for key in ("ratio", "srm_chi2", "srm_pvalue"):
        value = assignment.get(key)
        check(f"assignment {key}", value is not None and numbers_close(value, expected[key]), expected[key], value)
    value = assignment.get("srm_pass")
    check("assignment srm_pass", value == str(expected["srm_pass"]), str(expected["srm_pass"]), value)
    check("assignment row count", len(assignment) == 6, 6, len(assignment))

    results_path = output_dir / "experiment_results.tsv"
    rows = []
    if results_path.is_file():
        rows = read_csv(results_path, delimiter="\t")
    else:
        check("results file exists", False, "experiment_results.tsv", None)
    by_metric = {row.get("metric"): row for row in rows}
    check("results row count", len(rows) == 4, 4, len(rows))
    for metric, _, _ in stats.METRICS:
        item = expected["metrics"][metric]
        row = by_metric.get(metric)
        if row is None:
            check(f"{metric} row exists", False, metric, None)
            continue
        check(f"{metric} is_primary", row.get("is_primary") == str(item["is_primary"]), str(item["is_primary"]), row.get("is_primary"))
        for column in ("control_rate", "treatment_rate", "absolute_lift", "relative_lift_pct", "ci_lower_90", "ci_upper_90", "z_statistic", "p_value_raw"):
            check(
                f"{metric} {column}",
                numbers_close(row.get(column), item[column]),
                item[column],
                row.get(column),
            )
        check(
            f"{metric} significant_at_05",
            row.get("significant_at_05") == str(item["significant_at_05"]),
            str(item["significant_at_05"]),
            row.get("significant_at_05"),
        )
        if item["is_primary"]:
            check(
                f"{metric} holm blank",
                not row.get("holm_rank") and not row.get("holm_threshold") and not row.get("holm_significant"),
                "blank",
                [row.get("holm_rank"), row.get("holm_threshold"), row.get("holm_significant")],
            )
        else:
            check(f"{metric} holm_rank", row.get("holm_rank") == str(item["holm_rank"]), str(item["holm_rank"]), row.get("holm_rank"))
            check(
                f"{metric} holm_threshold",
                numbers_close(row.get("holm_threshold"), item["holm_threshold"]),
                item["holm_threshold"],
                row.get("holm_threshold"),
            )
            check(
                f"{metric} holm_significant",
                row.get("holm_significant") == str(item["holm_significant"]),
                str(item["holm_significant"]),
                row.get("holm_significant"),
            )

    report_path = output_dir / "experiment_report.md"
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    check("report file exists", bool(report), "experiment_report.md", None)
    check("report recommendation heading", "## Recommendation" in report, "## Recommendation", None)
    check("report decision", expected["decision"] in report.lower(), expected["decision"], None)
    lift_text = f"{expected['metrics']['opened_rate']['absolute_lift'] * 100:.2f} percentage points"
    check("report observed lift", lift_text in report, lift_text, None)
    check("report required sample size", str(expected["required_per_arm"]) in report, expected["required_per_arm"], None)

    passed = sum(1 for item in checks if item["passed"])
    score = passed / len(checks) if checks else 0.0
    print(
        json.dumps(
            {
                "score": score,
                "passed": score == 1.0,
                "checks_passed": passed,
                "checks_total": len(checks),
                "checks": checks,
                "expected_decision": expected["decision"],
                "expected_required_per_arm": expected["required_per_arm"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
