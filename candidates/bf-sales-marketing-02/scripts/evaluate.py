#!/usr/bin/env python3
"""Evaluate the synthetic audience-segmentation task."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path


def load_stats():
    path = Path(__file__).with_name("stats.py")
    spec = importlib.util.spec_from_file_location("segmentation_stats", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path, delimiter: str = ",") -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        return list(reader.fieldnames or []), list(reader)


def numbers_close(actual, expected, tolerance: float = 1e-6) -> bool:
    try:
        return abs(float(actual) - float(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


def predicate_key(item: dict) -> tuple:
    value = item.get("value")
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = str(value)
    return (item.get("field"), item.get("operator"), value)


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

    definition_path = output_dir / "segment_definition.json"
    definition = {}
    if definition_path.is_file():
        try:
            definition = json.loads(definition_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            definition = {}
        check("segment_definition parses", isinstance(definition, dict), "object", type(definition).__name__)
    else:
        check("segment_definition exists", False, "segment_definition.json", None)

    expected_definition = expected["segment_definition"]
    for key in ("segment_name", "created_date", "version"):
        check(f"definition {key}", definition.get(key) == expected_definition[key], expected_definition[key], definition.get(key))

    actual_filters = {predicate_key(item) for item in definition.get("filter_predicates", []) if isinstance(item, dict)}
    expected_filters = {predicate_key(item) for item in expected_definition["filter_predicates"]}
    check("definition filter_predicates", actual_filters == expected_filters, sorted(map(str, expected_filters)), sorted(map(str, actual_filters)))

    def suppression_key(item: dict) -> tuple:
        return predicate_key(item) + (item.get("reason"),)

    actual_suppression = {
        suppression_key(item) for item in definition.get("suppression_rules", []) if isinstance(item, dict)
    }
    expected_suppression = {suppression_key(item) for item in expected_definition["suppression_rules"]}
    check("definition suppression_rules", actual_suppression == expected_suppression, sorted(map(str, expected_suppression)), sorted(map(str, actual_suppression)))

    check("definition activation_channels", definition.get("activation_channels") == expected_definition["activation_channels"], expected_definition["activation_channels"], definition.get("activation_channels"))

    governance = definition.get("governance_applied", {})
    expected_governance = expected_definition["governance_applied"]
    check("definition pii_fields_removed", set(governance.get("pii_fields_removed", [])) == set(expected_governance["pii_fields_removed"]), expected_governance["pii_fields_removed"], governance.get("pii_fields_removed"))
    check("definition opt_out_compliance", governance.get("opt_out_compliance") is True, True, governance.get("opt_out_compliance"))
    check("definition support_suppression", governance.get("support_suppression") is True, True, governance.get("support_suppression"))

    actual_stats = definition.get("audience_stats", {})
    expected_stats = expected_definition["audience_stats"]
    for key in ("total_qualifying", "sms_eligible", "push_eligible", "any_channel_eligible"):
        check(f"stats {key}", numbers_close(actual_stats.get(key), expected_stats[key]), expected_stats[key], actual_stats.get(key))
    check("stats pct_of_total_profiles", numbers_close(actual_stats.get("pct_of_total_profiles"), expected_stats["pct_of_total_profiles"], 0.011), expected_stats["pct_of_total_profiles"], actual_stats.get("pct_of_total_profiles"))
    check("governance minimum audience", expected_stats["total_qualifying"] >= expected["min_audience_size"], f">= {expected['min_audience_size']}", expected_stats["total_qualifying"])

    roster_path = output_dir / "audience_roster.csv"
    roster_header, roster_rows = [], []
    if roster_path.is_file():
        roster_header, roster_rows = read_csv(roster_path)
    else:
        check("roster exists", False, "audience_roster.csv", None)
    check("roster header", set(roster_header) == set(stats.ROSTER_COLUMNS), sorted(stats.ROSTER_COLUMNS), sorted(roster_header))
    check("roster no PII", not (set(roster_header) & set(stats.PII_FIELDS)), "no PII", sorted(set(roster_header) & set(stats.PII_FIELDS)))
    expected_by_id = {row["customer_id"]: row for row in expected["roster"]}
    actual_by_id = {row.get("customer_id"): row for row in roster_rows}
    check("roster customer_id set", set(actual_by_id) == set(expected_by_id), len(expected_by_id), len(actual_by_id))
    check("roster row count", len(roster_rows) == len(expected["roster"]), len(expected["roster"]), len(roster_rows))
    for column in stats.ROSTER_COLUMNS:
        if column == "customer_id":
            continue
        if column == "loyalty_tier":
            ok = all(
                actual_by_id.get(customer_id, {}).get(column) == row[column]
                for customer_id, row in expected_by_id.items()
            )
        else:
            ok = all(
                numbers_close(actual_by_id.get(customer_id, {}).get(column), row[column])
                for customer_id, row in expected_by_id.items()
            )
        check(f"roster column {column}", ok, f"all {column} values match", None)

    overlap_path = output_dir / "overlap_report.tsv"
    overlap_header, overlap_rows = [], []
    if overlap_path.is_file():
        overlap_header, overlap_rows = read_csv(overlap_path, delimiter="\t")
    else:
        check("overlap exists", False, "overlap_report.tsv", None)
    check("overlap header", set(overlap_header) == {"existing_audience_id", "existing_audience_name", "overlap_count", "overlap_pct", "flag_high_overlap"}, "required columns", overlap_header)
    expected_overlaps = {row["existing_audience_id"]: row for row in expected["overlaps"]}
    actual_overlaps = {row.get("existing_audience_id"): row for row in overlap_rows}
    check("overlap audience set", set(actual_overlaps) == set(expected_overlaps), sorted(expected_overlaps), sorted(actual_overlaps))
    check("overlap row count", len(overlap_rows) == len(expected["overlaps"]), len(expected["overlaps"]), len(overlap_rows))
    for audience_id, expected_row in expected_overlaps.items():
        actual_row = actual_overlaps.get(audience_id, {})
        check(f"{audience_id} name", actual_row.get("existing_audience_name") == expected_row["existing_audience_name"], expected_row["existing_audience_name"], actual_row.get("existing_audience_name"))
        check(f"{audience_id} count", numbers_close(actual_row.get("overlap_count"), expected_row["overlap_count"]), expected_row["overlap_count"], actual_row.get("overlap_count"))
        check(f"{audience_id} pct", numbers_close(actual_row.get("overlap_pct"), expected_row["overlap_pct"], 0.011), expected_row["overlap_pct"], actual_row.get("overlap_pct"))
        check(f"{audience_id} flag", actual_row.get("flag_high_overlap") == str(expected_row["flag_high_overlap"]), str(expected_row["flag_high_overlap"]), actual_row.get("flag_high_overlap"))

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
                "expected_stats": expected_stats,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
