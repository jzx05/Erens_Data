#!/usr/bin/env python3
"""Write the gold outputs for the 90% CI + Holm A/B test task."""

from __future__ import annotations

import argparse
import csv
import importlib.util
from pathlib import Path


def load_stats():
    path = Path(__file__).with_name("stats.py")
    spec = importlib.util.spec_from_file_location("ab_stats", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--candidate-root", type=Path, default=None)
    args = parser.parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    stats = load_stats()
    result = stats.compute(root)
    args.out.mkdir(parents=True, exist_ok=True)

    with (args.out / "randomization_assignment.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for key in ("n_control", "n_treatment", "ratio", "srm_chi2", "srm_pvalue", "srm_pass"):
            writer.writerow([key, fmt(result[key])])

    columns = [
        "metric",
        "is_primary",
        "control_rate",
        "treatment_rate",
        "absolute_lift",
        "relative_lift_pct",
        "ci_lower_90",
        "ci_upper_90",
        "z_statistic",
        "p_value_raw",
        "significant_at_05",
        "holm_rank",
        "holm_threshold",
        "holm_significant",
    ]
    with (args.out / "experiment_results.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        for metric, _, _ in stats.METRICS:
            item = result["metrics"][metric]
            writer.writerow([metric] + [fmt(item[column]) for column in columns[1:]])

    primary = result["metrics"]["opened_rate"]
    lines = [
        "# Email Campaign A/B Test: 90% CI and Holm Re-analysis",
        "",
        "## Randomization",
        "",
        f"- Control: {result['n_control']} customers",
        f"- Treatment: {result['n_treatment']} customers",
        f"- SRM chi-square: {result['srm_chi2']:.6f}",
        f"- SRM p-value: {result['srm_pvalue']:.6f} (pass at 0.05: {result['srm_pass']})",
        "",
        "## Primary Metric: opened_rate",
        "",
        f"- Control rate: {primary['control_rate']:.6f}",
        f"- Treatment rate: {primary['treatment_rate']:.6f}",
        f"- Absolute lift: {primary['absolute_lift'] * 100:.2f} percentage points",
        f"- 90% CI: [{primary['ci_lower_90']:.6f}, {primary['ci_upper_90']:.6f}]",
        f"- z-statistic: {primary['z_statistic']:.6f}",
        f"- p-value: {primary['p_value_raw']:.6g}",
        "",
        "## Secondary Metrics",
        "",
        "| metric | control_rate | treatment_rate | absolute_lift | p_value_raw | holm_rank | holm_threshold | holm_significant |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for metric in stats.SECONDARY:
        item = result["metrics"][metric]
        lines.append(
            f"| {metric} | {item['control_rate']:.6f} | {item['treatment_rate']:.6f} | "
            f"{item['absolute_lift']:.6f} | {item['p_value_raw']:.6g} | "
            f"{item['holm_rank']} | {item['holm_threshold']:.6f} | "
            f"{item['holm_significant']} |"
        )
    lines.extend(
        [
            "",
            "## Power Analysis",
            "",
            f"- Historical baseline open rate: {result['historical_open_baseline']:.6f}",
            "- Minimum detectable effect: 3 percentage points",
            "- Two-sided alpha: 0.05; power: 0.80; allocation: 1:1",
            f"- Required per-arm sample size: {result['required_per_arm']}",
            "",
            "## Recommendation",
            "",
        ]
    )
    if result["decision"] == "ship":
        lines.append(
            "**Ship.** The primary opened-rate lift is significant at 0.05 and the unsubscribe "
            "guardrail is satisfied."
        )
    else:
        lines.append(
            "**Hold.** The unsubscribe-rate lift exceeds the 0.3 percentage-point guardrail, so the "
            "experiment should not ship despite the significant opened-rate lift."
        )
    (args.out / "experiment_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote gold outputs to {args.out}")


if __name__ == "__main__":
    main()
