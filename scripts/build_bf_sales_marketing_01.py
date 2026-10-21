#!/usr/bin/env python3
"""Build bf-sales-marketing-01: a synthetic 90% CI + Holm A/B test task.

The dataset is generated deterministically from seed 20261021. It avoids the
degenerate clicked/converted columns found in the seed AB task.

Usage:
  python3 -I scripts/build_bf_sales_marketing_01.py [--force]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_ID = "bf-sales-marketing-01"
CAND = ROOT / "candidates" / CANDIDATE_ID
EXAMPLE = ROOT / "templates" / "task" / "data-analysis" / "examples" / "ab_test_90ci_holm"

RANDOM_SEED = 20261021
N_CONTROL = 6000
N_TREATMENT = 6050
DELIVERED_PROB = 0.98
P = {
    "control": {
        "open": 0.215,
        "click_given_open": 0.18,
        "convert_given_click": 0.18,
        "unsubscribe": 0.0015,
    },
    "treatment": {
        "open": 0.245,
        "click_given_open": 0.20,
        "convert_given_click": 0.20,
        "unsubscribe": 0.0055,
    },
}

HIST_OPEN = [0.215, 0.218, 0.212, 0.220, 0.217, 0.223, 0.219, 0.216, 0.221, 0.214, 0.218, 0.222]
HIST_CLICK = [0.0385, 0.0401, 0.0392, 0.0410, 0.0398, 0.0422, 0.0405, 0.0391, 0.0415, 0.0388, 0.0402, 0.0418]
HIST_CONVERT = [0.0078, 0.0081, 0.0075, 0.0084, 0.0080, 0.0086, 0.0082, 0.0079, 0.0085, 0.0077, 0.0081, 0.0083]
HIST_UNSUB = [0.0014, 0.0016, 0.0013, 0.0017, 0.0015, 0.0018, 0.0016, 0.0014, 0.0017, 0.0013, 0.0015, 0.0016]

BRIEF = """# Experiment Brief: Personalized Email Subject Lines (90% CI / Holm Re-analysis)

## Context

The growth team ran a two-arm email subject-line experiment. After a methodology review, the team
pre-registered a re-analysis of the supplied raw data under a 90% confidence interval and a
Holm-Bonferroni multiple-testing protocol. Use the staged files only.

## Variants

- **Control (A):** Generic subject line.
- **Treatment (B):** Personalized subject line with the customer's first name and recent category.

## Primary Metric

- Email open rate (opens / delivered emails)

## Secondary Metrics

- Click-through rate (clicks / delivered emails)
- Conversion rate (purchases within 48h / delivered emails)
- Unsubscribe rate (unsubscribes / delivered emails)

## Analysis Population

Use every row in `experiment_results_raw.csv` for the sample-ratio check; do not apply
`exclusion_rules.yaml` (it is retained for future operational use only). For every metric rate, the
denominator is delivered emails (`delivered == "1"`); undelivered rows remain in the raw file for the
SRM check but are not part of the rate denominators.

## Statistical Protocol

- SRM: Pearson chi-square with 1 degree of freedom, no continuity correction; pass if p > 0.05.
- Two-proportion z test: pooled, two-sided, no continuity correction.
- 90% confidence interval: unpooled Wald interval, z = 1.6448536269514722.
- `significant_at_05` is True exactly when the raw p-value is below 0.05.
- Holm-Bonferroni step-down at family-wise error rate 0.05 for the three secondary metrics.
  Sort the secondary p-values ascending; for rank i the threshold is 0.05 / (3 - i + 1).
  Once a null is not rejected, all later ranks are not rejected.

## Power Analysis

- Equal 1:1 allocation, two-sided alpha 0.05, 80% power.
- Baseline = arithmetic mean of historical open_rate; MDE = 3 percentage points absolute.
- Use the normal-approximation two-proportion formula, rounded up to an integer.

## Guardrail

- Unsubscribe rate must not increase by more than 0.3 percentage points in treatment.

## Decision Policy

Recommend Ship if the primary open-rate lift is significant at 0.05 and the unsubscribe guardrail
passes; otherwise recommend Hold. State the observed absolute lift on the primary metric in the
report.
"""

OUTPUT_CONTRACT = {
    "required_outputs": [
        "randomization_assignment.csv",
        "experiment_results.tsv",
        "experiment_report.md",
    ],
    "assignment_columns": ["metric", "value"],
    "assignment_rows": [
        "n_control",
        "n_treatment",
        "ratio",
        "srm_chi2",
        "srm_pvalue",
        "srm_pass",
    ],
    "results_columns": [
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
    ],
    "results_metrics": [
        "opened_rate",
        "clicked_rate",
        "converted_rate",
        "unsubscribed_rate",
    ],
    "primary_metric": "opened_rate",
    "report_requirements": [
        "a ## Recommendation section containing ship or hold",
        "the observed absolute opened-rate lift formatted as X.XX percentage points",
        "the required per-arm sample size",
    ],
}

TASK_PROMPT = """You are a growth analytics engineer at an e-commerce company. The team has
pre-registered a re-analysis of a two-arm email subject-line experiment under a 90% confidence
interval and a Holm-Bonferroni multiple-testing protocol.

## Data Rule

- Use only the staged files under `base/input`.
- Do not use external data or any reference output from another task.

## Inputs

- Experiment brief: `base/input/experiment_brief.md`
- Raw experiment results: `base/input/experiment_results_raw.csv`
- Historical metrics: `base/input/historical_metrics.csv`
- Eligible population: `base/input/eligible_population.csv`
- Active experiment customers: `base/input/active_experiment_customers.csv`
- Exclusion rules (operational only; do not apply): `base/input/exclusion_rules.yaml`
- Output contract: `base/input/output_contract.json`

## Required Outputs

Write exactly these files under `base/output`:

1. `randomization_assignment.csv` — columns `metric,value`; rows `n_control`, `n_treatment`,
   `ratio`, `srm_chi2`, `srm_pvalue`, `srm_pass`.
2. `experiment_results.tsv` — tab-separated; exactly four rows, one per metric:
   `opened_rate`, `clicked_rate`, `converted_rate`, `unsubscribed_rate`. Columns:
   `metric`, `is_primary`, `control_rate`, `treatment_rate`, `absolute_lift`,
   `relative_lift_pct`, `ci_lower_90`, `ci_upper_90`, `z_statistic`, `p_value_raw`,
   `significant_at_05`, `holm_rank`, `holm_threshold`, `holm_significant`.
   Leave the three Holm columns blank for the primary metric.
3. `experiment_report.md` — Markdown report with the required sample size, a
   `## Recommendation` section containing `ship` or `hold`, and the observed absolute lift on the
   primary metric formatted as `X.XX percentage points`.

## Method

- Use every row in the raw file for the SRM check; do not apply exclusion rules.
- For every metric rate, the denominator is delivered emails (`delivered == "1"`).
- SRM: Pearson chi-square with 1 degree of freedom, no continuity correction; pass if p > 0.05.
- Two-proportion z test: pooled, two-sided, no continuity correction.
- 90% CI: unpooled Wald interval, z = 1.6448536269514722.
- `significant_at_05` is True exactly when the raw p-value is below 0.05.
- Holm-Bonferroni step-down at family-wise error rate 0.05 for the three secondary metrics.
- Power: equal 1:1, two-sided alpha 0.05, 80% power, baseline = mean historical open_rate,
  MDE = 3 percentage points, normal approximation, round up.
- Recommend Ship only if the primary metric is significant at 0.05 and the unsubscribe lift is at
  most 0.3 percentage points; otherwise recommend Hold.
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def generate() -> list[dict]:
    rng = random.Random(RANDOM_SEED)
    rows = []
    customer_number = 100000
    for variant, count in (("control", N_CONTROL), ("treatment", N_TREATMENT)):
        params = P[variant]
        for _ in range(count):
            customer_id = f"CUST-{customer_number:06d}"
            customer_number += 1
            delivered = 1 if rng.random() < DELIVERED_PROB else 0
            opened = 1 if delivered and rng.random() < params["open"] else 0
            clicked = 1 if opened and rng.random() < params["click_given_open"] else 0
            converted = 1 if clicked and rng.random() < params["convert_given_click"] else 0
            unsubscribed = 1 if delivered and rng.random() < params["unsubscribe"] else 0
            rows.append(
                {
                    "customer_id": customer_id,
                    "variant": variant,
                    "delivered": delivered,
                    "opened": opened,
                    "clicked": clicked,
                    "converted": converted,
                    "unsubscribed": unsubscribed,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if CAND.exists():
        if not args.force:
            raise SystemExit(f"candidate already exists: {CAND} (pass --force to rebuild)")
        shutil.rmtree(CAND)
    for relative in ("base/input/runtime_env", "base/reference", "base/software", "scripts", "evidence", "source_pack"):
        (CAND / relative).mkdir(parents=True, exist_ok=True)

    rows = generate()
    write_csv(
        CAND / "base/input/experiment_results_raw.csv",
        ["customer_id", "variant", "delivered", "opened", "clicked", "converted", "unsubscribed"],
        [
            [
                row["customer_id"],
                row["variant"],
                row["delivered"],
                row["opened"],
                row["clicked"],
                row["converted"],
                row["unsubscribed"],
            ]
            for row in rows
        ],
    )

    rng = random.Random(RANDOM_SEED + 1)
    eligible = []
    for row in rows:
        score = round(rng.random(), 2)
        loyalty = "gold" if score >= 0.7 else "silver" if score >= 0.35 else "bronze"
        engagement = "high" if score >= 0.67 else "medium" if score >= 0.33 else "low"
        eligible.append(
            [
                row["customer_id"],
                score,
                loyalty,
                rng.randint(0, 20),
                engagement,
            ]
        )
    write_csv(
        CAND / "base/input/eligible_population.csv",
        ["customer_id", "engagement_score", "loyalty_tier", "email_opens_30d", "engagement_tier"],
        eligible,
    )
    active = [[row["customer_id"]] for index, row in enumerate(rows) if index % 4 == 0]
    write_csv(CAND / "base/input/active_experiment_customers.csv", ["customer_id"], active)

    (CAND / "base/input/exclusion_rules.yaml").write_text(
        """rules:
  - name: internal_test_accounts
    field: customer_id
    pattern: "^CUST-9"
  - name: undelivered
    field: delivered
    equals: 0
note: >
  The pre-registered analysis uses the full raw population for SRM and metric rates.
  These rules are retained for future operational exclusion only.
""",
        encoding="utf-8",
    )

    hist_rows = []
    start = date(2025, 1, 6)
    for index in range(12):
        hist_rows.append(
            [
                (start + timedelta(weeks=index)).isoformat(),
                12000 + index * 150,
                HIST_OPEN[index],
                HIST_CLICK[index],
                HIST_CONVERT[index],
                HIST_UNSUB[index],
            ]
        )
    write_csv(
        CAND / "base/input/historical_metrics.csv",
        ["week_start", "emails_delivered", "open_rate", "click_rate", "conversion_rate", "unsubscribe_rate"],
        hist_rows,
    )

    (CAND / "base/input/experiment_brief.md").write_text(BRIEF, encoding="utf-8")
    write_json(CAND / "base/input/output_contract.json", OUTPUT_CONTRACT)
    (CAND / "base/input/runtime_env/pyproject.toml").write_text(
        """[project]
name = "email-ab-reanalysis"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []
""",
        encoding="utf-8",
    )
    (CAND / "base/software/README.md").write_text(
        "Python 3.12 with the standard library is sufficient. pandas, scipy, statsmodels, and uv "
        "may be available in the runtime image but are not required for a correct solution.\n",
        encoding="utf-8",
    )

    for name in ("stats.py", "make_gold_output.py", "evaluate.py"):
        shutil.copy2(EXAMPLE / name, CAND / "scripts" / name)

    write_json(
        CAND / "candidate.json",
        {
            "id": CANDIDATE_ID,
            "status": "AUTHORED",
            "stratum": "sales_marketing",
            "seed_anchor": "digital_marketing_ab_test_analysis_1",
            "seed_refs": [
                "digital_marketing_ab_test_analysis_1",
                "digital_marketing_audience_segmentation_1",
            ],
            "difficulty_target": 100.0,
            "task_family": "data-analysis",
            "source_policy": "synthetic",
            "internal_only": False,
            "synthetic_data": True,
            "attempts": 0,
            "reason_codes": [],
            "paths": {},
        },
    )

    task_id = "business_finance/email_ab_test_90ci_holm_01"
    write_json(
        CAND / "task_card.json",
        {
            "taskId": task_id,
            "title": "Email Campaign A/B Test: 90% CI and Holm Re-analysis",
            "summary": (
                "Re-analyze a two-arm email subject-line experiment with a 90% Wald interval, "
                "Holm-Bonferroni correction for secondary metrics, a power analysis, and a 0.3pp "
                "unsubscribe guardrail."
            ),
            "category": "business_finance",
            "software": ["Python 3.12", "pandas", "scipy", "statsmodels", "uv"],
            "taskPrompt": TASK_PROMPT,
            "agentMustDo": [
                "Read the experiment brief, raw results, historical metrics, and output contract.",
                "Use every raw row for the SRM check; compute each metric rate over delivered emails; do not apply exclusion rules.",
                "Compute the SRM chi-square test, two-proportion z tests, 90% Wald intervals, and Holm-Bonferroni decisions.",
                "Run the normal-approximation power analysis on the historical open rate.",
                "Write the two data files and the Markdown report exactly as contracted.",
            ],
            "inputFiles": [
                {"name": "experiment_brief.md", "format": "Markdown", "path": "input/experiment_brief.md", "description": "Protocol, metrics, guardrail, and decision policy."},
                {"name": "experiment_results_raw.csv", "format": "CSV", "path": "input/experiment_results_raw.csv", "description": "Raw per-customer experiment results."},
                {"name": "historical_metrics.csv", "format": "CSV", "path": "input/historical_metrics.csv", "description": "Historical weekly metrics for the power analysis."},
                {"name": "eligible_population.csv", "format": "CSV", "path": "input/eligible_population.csv", "description": "Eligible population attributes."},
                {"name": "active_experiment_customers.csv", "format": "CSV", "path": "input/active_experiment_customers.csv", "description": "Customers active during the experiment."},
                {"name": "exclusion_rules.yaml", "format": "YAML", "path": "input/exclusion_rules.yaml", "description": "Operational exclusions; do not apply to this analysis."},
                {"name": "output_contract.json", "format": "JSON", "path": "input/output_contract.json", "description": "Required output files, columns, and metrics."},
                {"name": "runtime_env", "format": "TOML directory", "path": "input/runtime_env", "description": "Runtime metadata."},
            ],
            "referenceFiles": [
                {"name": "randomization_assignment.csv", "format": "CSV", "path": "output/randomization_assignment.csv", "description": "SRM and allocation results."},
                {"name": "experiment_results.tsv", "format": "TSV", "path": "output/experiment_results.tsv", "description": "Per-metric rates, intervals, tests, and Holm decisions."},
                {"name": "experiment_report.md", "format": "Markdown", "path": "output/experiment_report.md", "description": "Power analysis and ship/hold recommendation."},
            ],
            "evaluation": (
                "Hard gates: missing output files, malformed tables, wrong row or column sets, "
                "wrong SRM values, wrong rates/intervals/tests/Holm decisions, a wrong recommendation, "
                "a missing required sample size, or a missing observed-lift string. "
                "The score is the fraction of checks passed; only a fully correct submission scores 1.0."
            ),
            "vm": {"machineType": "c4-standard-4", "snapshot": "cpu-free-ubuntu", "timeout": 7200},
            "taxonomy": {
                "domain_id": "6",
                "domain_code": "business_finance",
                "subdomain_id": "6.6",
                "subdomain_code": "sales_marketing",
                "subdomain_name": "Sales & Marketing",
                "classifier": {
                    "model": "manual",
                    "classified_at": "2026-10-21T00:00:00Z",
                    "source": {"submission_id": "factory", "fields": ["taskPrompt", "title", "summary", "software"], "mode": "manual"},
                    "rationale": "The task analyzes a marketing email A/B test with a pre-registered statistical protocol.",
                },
            },
            "requiredSystemPackages": [],
        },
    )

    write_json(
        CAND / "base/reference/verification_contract.json",
        {
            "task_id": task_id,
            "variant_name": "base",
            "required_outputs": ["randomization_assignment.csv", "experiment_results.tsv", "experiment_report.md"],
            "hard_checks": [
                "SRM pass flag matches p > 0.05",
                "all rates use the full raw population and delivered emails",
                "90% unpooled Wald intervals match within 1e-6",
                "pooled two-sided z tests match within 1e-6",
                "Holm step-down applies only to the three secondary metrics",
                "recommendation is hold because the unsubscribe guardrail fails",
                "required per-arm sample size uses the historical mean open_rate and 3pp MDE",
            ],
            "expected_decision": "hold",
        },
    )

    manifest_text = (
        "dataset_id=email_ab_test_90ci_holm_01\n"
        f"random_seed={RANDOM_SEED}\n"
        f"n_control={N_CONTROL}\n"
        f"n_treatment={N_TREATMENT}\n"
        f"delivered_probability={DELIVERED_PROB}\n"
        "control_open_probability=0.215\n"
        "treatment_open_probability=0.245\n"
        "control_click_given_open=0.18\n"
        "treatment_click_given_open=0.20\n"
        "control_convert_given_click=0.18\n"
        "treatment_convert_given_click=0.20\n"
        "control_unsubscribe_probability=0.0015\n"
        "treatment_unsubscribe_probability=0.0055\n"
        "generated_by=ale-task-factory\n"
    )
    (CAND / "source_pack/dataset_manifest.txt").write_text(manifest_text, encoding="utf-8")

    sources = [
        ("src-dataset-manifest", "Synthetic dataset generation manifest", "source_pack/dataset_manifest.txt", "synthetic data generated by the ALE Task Factory"),
        ("src-brief", "Experiment brief and statistical protocol", "base/input/experiment_brief.md", "factory-authored task brief"),
        ("src-raw", "Synthetic raw experiment results", "base/input/experiment_results_raw.csv", "synthetic data generated by the ALE Task Factory"),
        ("src-historical", "Synthetic historical metrics", "base/input/historical_metrics.csv", "synthetic data generated by the ALE Task Factory"),
    ]
    with (CAND / "evidence/sources.jsonl").open("w", encoding="utf-8") as handle:
        for source_id, title, path, license_name in sources:
            record = {
                "source_id": source_id,
                "title": title,
                "publisher": "ALE Task Factory",
                "local_path": path,
                "text_path": path,
                "retrieved_at": "2026-10-21T00:00:00Z",
                "license": license_name,
                "redistributable": True,
                "sha256": sha256(CAND / path),
                "locators": ["full file"],
                "notes": "Synthetic or factory-authored material; safe to redistribute.",
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    claims = [
        ("dataset_generation", "src-dataset-manifest", "generation parameters", "random_seed=20261021"),
        ("primary_metric_definition", "src-brief", "Primary Metric", "Email open rate (opens / delivered emails)"),
        ("srm_protocol", "src-brief", "Statistical Protocol", "SRM: Pearson chi-square with 1 degree of freedom, no continuity correction; pass if p > 0.05."),
        ("holm_protocol", "src-brief", "Statistical Protocol", "Holm-Bonferroni step-down at family-wise error rate 0.05 for the three secondary metrics."),
        ("guardrail", "src-brief", "Guardrail", "Unsubscribe rate must not increase by more than 0.3 percentage points in treatment."),
        ("power_analysis", "src-brief", "Power Analysis", "Baseline = arithmetic mean of historical open_rate; MDE = 3 percentage points absolute."),
    ]
    with (CAND / "evidence/evidence.jsonl").open("w", encoding="utf-8") as handle:
        for claim_id, source_id, locator, quote in claims:
            record = {
                "claim_id": claim_id,
                "source_id": source_id,
                "locator": locator,
                "exact_quote": quote,
                "used_in": ["task_card.json"],
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"built {CAND}")
    print(f"  raw rows: {len(rows)} (control={N_CONTROL}, treatment={N_TREATMENT})")
    print(f"  historical baseline open_rate: {sum(HIST_OPEN)/len(HIST_OPEN):.6f}")


if __name__ == "__main__":
    main()
