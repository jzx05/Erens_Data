#!/usr/bin/env python3
"""Build bf-sales-marketing-02: synthetic audience segmentation for app win-back.

The 10,000-profile dataset is generated deterministically from seed 20261022.
It matches the seed schema but uses a new target segment and new governance rules.

Usage:
  python3 -I scripts/build_bf_sales_marketing_02.py [--force]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_ID = "bf-sales-marketing-02"
CAND = ROOT / "candidates" / CANDIDATE_ID
EXAMPLE = ROOT / "templates" / "task" / "data-analysis" / "examples" / "audience_segmentation"
SEED = (
    Path.home()
    / "下载"
    / "business_finance_extracted"
    / "business_finance"
    / "digital_marketing_audience_segmentation_1"
)

RANDOM_SEED = 20261022
PROFILE_COUNT = 10000

PROFILE_COLUMNS = [
    "customer_id",
    "age",
    "gender",
    "state",
    "city",
    "tenure_months",
    "loyalty_tier",
    "total_purchases",
    "purchase_count_30d",
    "purchase_count_90d",
    "avg_order_value",
    "ltv",
    "recency_days",
    "email_opens_30d",
    "email_opens_90d",
    "email_clicks_30d",
    "last_email_open_days_ago",
    "email_opt_out",
    "sms_opt_in",
    "has_app",
    "app_sessions_30d",
    "push_opt_in",
    "page_views_30d",
    "support_tickets_90d",
    "engagement_score",
]

BRIEF = """# Segmentation Brief: High-Value Lapsed App Users — Win-Back Push/SMS

## Target Audience

Include a customer only when ALL of the following are true:

- `ltv >= 1500`
- `recency_days >= 45`
- `has_app == 1`
- `app_sessions_30d >= 2`
- `email_opens_30d <= 2`
- `last_email_open_days_ago > 30`

## Purpose

Identify high-value, lapsed customers who have the app installed but are not engaging with email,
so the team can run a win-back campaign through push notifications and SMS.

## Suppression

- Exclude customers with `support_tickets_90d > 0` from all outbound campaigns.
- Record this rule with the exact reason: `Active support ticket suppression`.

## Activation Channels

- **SMS:** eligible when `sms_opt_in = 1`.
- **Push:** eligible when `push_opt_in = 1`.
- `any_channel_eligible` is 1 when SMS or push eligibility is 1.

## PII

Remove `age`, `gender`, `city`, and `state` from the roster and all external activation exports.

## Governance

- Minimum audience size: 50.
- Opt-out compliance: only customers with the channel opt-in flag set are eligible for that channel.
- Support-ticket suppression applies before channel eligibility is computed.

## Overlap Analysis

For each existing audience in `existing_audiences.csv`, apply its definition to the qualifying
audience after suppression.

- `overlap_count` = number of qualifying customers who also match the existing audience.
- `overlap_pct = overlap_count / total_qualifying * 100`, rounded to 2 decimals.
- `flag_high_overlap` = `True` when `overlap_pct >= 10.0`, otherwise `False`.

## Deliverables

### `segment_definition.json`

Use exactly these values:

- `segment_name`: `High-Value Lapsed App Users — Win-Back Push/SMS`
- `created_date`: `2026-10-21`
- `version`: `1.0`
- `filter_predicates`: one object per target condition, with keys `field`, `operator`, `value`,
  in the order listed under Target Audience. Use `==` for equality predicates in the JSON.
- `suppression_rules`: a list containing one object with `field`, `operator`, `value`, `reason`.
- `activation_channels`: `{"sms": {"eligibility_field": "sms_opt_in", "required_value": 1},
  "push": {"eligibility_field": "push_opt_in", "required_value": 1}}`
- `governance_applied`: `{"pii_fields_removed": ["age", "gender", "city", "state"],
  "opt_out_compliance": true, "support_suppression": true}`
- `audience_stats`: `total_qualifying`, `sms_eligible`, `push_eligible`,
  `any_channel_eligible`, `pct_of_total_profiles` (rounded to 2 decimals).

### `audience_roster.csv`

One row per qualifying customer after suppression. Columns exactly:

`customer_id,tenure_months,loyalty_tier,total_purchases,purchase_count_30d,purchase_count_90d,avg_order_value,ltv,recency_days,has_app,app_sessions_30d,engagement_score,sms_eligible,push_eligible,any_channel_eligible`

### `overlap_report.tsv`

Tab-separated with columns:

`existing_audience_id,existing_audience_name,overlap_count,overlap_pct,flag_high_overlap`

One row per existing audience, in the order they appear in `existing_audiences.csv`.
"""

TASK_PROMPT = """You are a digital marketing analyst building a re-engagement audience from customer
profiles.

## Task Directory

`base`

## Your Task

1. Read `base/input/segmentation_brief.md`, `base/input/governance_policies.yaml`, and
   `base/input/data_dictionary.tsv`.
2. Load `base/input/unified_profiles.csv`.
3. Identify customers matching every target condition in the brief.
4. Suppress customers with active support tickets, then compute SMS and push eligibility.
5. Remove `age`, `gender`, `city`, and `state` from the output roster.
6. Compute overlap against each audience in `base/input/existing_audiences.csv`.
7. Write exactly the three contracted output files under `base/output`.

## Required Outputs

- `base/output/segment_definition.json`
- `base/output/audience_roster.csv`
- `base/output/overlap_report.tsv`

The exact schemas, target conditions, channel rules, PII rules, overlap formula, and required
constant values are in `base/input/segmentation_brief.md`. Follow them exactly.

## Environment

Python 3.12 is available. The standard library is sufficient; pandas and pyarrow are optional.
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_stats():
    path = EXAMPLE / "stats.py"
    spec = importlib.util.spec_from_file_location("segmentation_stats", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def generate_profiles() -> list[dict]:
    rng = random.Random(RANDOM_SEED)
    profiles = []
    for index in range(PROFILE_COUNT):
        customer_id = f"CUST-{index + 1:06d}"
        age = rng.randint(18, 85)
        gender = rng.choice(["M", "F", "NB", "U"])
        state = rng.choice(["CA", "NY", "TX", "FL", "WA", "IL", "MA", "GA", "NC", "AZ"])
        city = f"City{rng.randint(1, 40)}"
        tenure = rng.randint(1, 120)
        loyalty = rng.choices(["bronze", "silver", "gold", "platinum"], weights=[45, 30, 18, 7])[0]
        ltv = round(rng.lognormvariate(7.0, 0.8), 2)
        recency = min(365, int(rng.expovariate(1 / 60)))
        total_purchases = rng.randint(0, 50)
        p30 = rng.randint(0, 10)
        p90 = min(40, p30 + rng.randint(0, 15))
        aov = round(rng.uniform(10, 300), 2)
        has_app = rng.choices([0, 1], weights=[35, 65])[0]
        sessions = rng.randint(0, 50) if has_app else 0
        opens = rng.randint(0, 30)
        opens90 = min(60, opens + rng.randint(0, 20))
        clicks = rng.randint(0, 20)
        last_open = rng.randint(1, 365)
        email_opt_out = rng.choices([0, 1], weights=[85, 15])[0]
        sms = rng.choices([0, 1], weights=[40, 60])[0]
        push = rng.choices([0, 1], weights=[45, 55])[0]
        tickets = rng.choices([0, 1, 2, 3], weights=[88, 8, 3, 1])[0]
        eng = round(rng.random(), 4)
        page_views = rng.randint(0, 100)
        profiles.append(
            {
                "customer_id": customer_id,
                "age": age,
                "gender": gender,
                "state": state,
                "city": city,
                "tenure_months": tenure,
                "loyalty_tier": loyalty,
                "total_purchases": total_purchases,
                "purchase_count_30d": p30,
                "purchase_count_90d": p90,
                "avg_order_value": aov,
                "ltv": ltv,
                "recency_days": recency,
                "email_opens_30d": opens,
                "email_opens_90d": opens90,
                "email_clicks_30d": clicks,
                "last_email_open_days_ago": last_open,
                "email_opt_out": email_opt_out,
                "sms_opt_in": sms,
                "has_app": has_app,
                "app_sessions_30d": sessions,
                "push_opt_in": push,
                "page_views_30d": page_views,
                "support_tickets_90d": tickets,
                "engagement_score": eng,
            }
        )
    return profiles


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

    profiles = generate_profiles()
    with (CAND / "base/input/unified_profiles.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROFILE_COLUMNS)
        writer.writeheader()
        writer.writerows(profiles)

    stats = load_stats()
    result = stats.compute(CAND)

    (CAND / "base/input/segmentation_brief.md").write_text(BRIEF, encoding="utf-8")
    (CAND / "base/input/governance_policies.yaml").write_text(
        """policies:
  - name: PII Restriction
    description: No personally identifiable information in external activation exports.
    restricted_fields:
      - age
      - gender
      - city
      - state
  - name: Opt-Out Compliance
    description: Only customers with the channel opt-in flag set are eligible for that channel.
    rules:
      - channel: sms
        exclude_condition: sms_opt_in = 0
      - channel: push
        exclude_condition: push_opt_in = 0
  - name: Minimum Audience Size
    description: Audiences must contain at least 50 members for statistical validity.
    min_size: 50
  - name: Suppression List
    description: Customers with active support tickets must be suppressed from all outbound campaigns.
    suppress_condition: support_tickets_90d > 0
""",
        encoding="utf-8",
    )
    shutil.copy2(SEED / "base/input/data_dictionary.tsv", CAND / "base/input/data_dictionary.tsv")

    audience_rows = []
    for audience in stats.EXISTING_AUDIENCES:
        size = sum(1 for row in profiles if audience["predicate"](row))
        audience_rows.append([audience["id"], audience["name"], audience["definition"], size])
    with (CAND / "base/input/existing_audiences.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["audience_id", "name", "definition", "size"])
        writer.writerows(audience_rows)

    (CAND / "base/input/runtime_env/pyproject.toml").write_text(
        """[project]
name = "audience-segmentation"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []
""",
        encoding="utf-8",
    )
    (CAND / "base/software/README.md").write_text(
        "Python 3.12 with the standard library is sufficient. pandas and pyarrow are optional.\n",
        encoding="utf-8",
    )
    write_json(
        CAND / "base/input/output_contract.json",
        {
            "required_outputs": ["segment_definition.json", "audience_roster.csv", "overlap_report.tsv"],
            "roster_columns": stats.ROSTER_COLUMNS,
            "pii_fields_removed": stats.PII_FIELDS,
            "segment_definition_required_keys": [
                "segment_name",
                "created_date",
                "version",
                "filter_predicates",
                "suppression_rules",
                "activation_channels",
                "governance_applied",
                "audience_stats",
            ],
            "overlap_columns": [
                "existing_audience_id",
                "existing_audience_name",
                "overlap_count",
                "overlap_pct",
                "flag_high_overlap",
            ],
        },
    )

    for name in ("stats.py", "make_gold_output.py", "evaluate.py"):
        shutil.copy2(EXAMPLE / name, CAND / "scripts" / name)

    write_json(
        CAND / "candidate.json",
        {
            "id": CANDIDATE_ID,
            "status": "AUTHORED",
            "stratum": "sales_marketing",
            "seed_anchor": "digital_marketing_audience_segmentation_1",
            "seed_refs": [
                "digital_marketing_audience_segmentation_1",
                "basel_operational_risk_bia_cn",
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

    task_id = "business_finance/audience_segmentation_app_winback_01"
    write_json(
        CAND / "task_card.json",
        {
            "taskId": task_id,
            "title": "High-Value Lapsed App Users — Win-Back Segmentation",
            "summary": (
                "Segment a synthetic customer base into high-value, lapsed, app-installed, "
                "email-disengaged customers; apply support suppression, channel opt-ins, PII removal, "
                "and overlap analysis against six existing audiences."
            ),
            "category": "business_finance",
            "software": ["Python 3.12", "pandas", "pyarrow"],
            "taskPrompt": TASK_PROMPT,
            "agentMustDo": [
                "Read the segmentation brief, governance policies, and data dictionary.",
                "Filter unified_profiles.csv to the target conditions; suppress active support tickets.",
                "Compute SMS, push, and any-channel eligibility after suppression.",
                "Remove age, gender, city, and state from the roster.",
                "Compute overlaps against all six existing audiences using overlap_count / total_qualifying * 100.",
                "Write segment_definition.json, audience_roster.csv, and overlap_report.tsv exactly as contracted.",
            ],
            "inputFiles": [
                {"name": "unified_profiles.csv", "format": "CSV", "path": "input/unified_profiles.csv", "description": "10,000 synthetic customer profiles."},
                {"name": "segmentation_brief.md", "format": "Markdown", "path": "input/segmentation_brief.md", "description": "Target conditions, governance, and output contract."},
                {"name": "governance_policies.yaml", "format": "YAML", "path": "input/governance_policies.yaml", "description": "PII, opt-in, minimum-size, and suppression policies."},
                {"name": "existing_audiences.csv", "format": "CSV", "path": "input/existing_audiences.csv", "description": "Six existing audience definitions."},
                {"name": "data_dictionary.tsv", "format": "TSV", "path": "input/data_dictionary.tsv", "description": "Field names, types, and permitted values."},
                {"name": "runtime_env", "format": "TOML directory", "path": "input/runtime_env", "description": "Runtime metadata."},
            ],
            "referenceFiles": [
                {"name": "segment_definition.json", "format": "JSON", "path": "output/segment_definition.json", "description": "Segment predicates, suppression, channels, governance, and stats."},
                {"name": "audience_roster.csv", "format": "CSV", "path": "output/audience_roster.csv", "description": "Qualifying roster with PII removed and eligibility flags."},
                {"name": "overlap_report.tsv", "format": "TSV", "path": "output/overlap_report.tsv", "description": "Overlap counts and percentages against six audiences."},
            ],
            "evaluation": (
                "Hard gates: missing or unparsable outputs, PII columns in the roster, audience below "
                "the governance minimum, wrong target set, wrong eligibility flags, wrong stats, or "
                "wrong overlap counts/percentages. The score is the fraction of checks passed; only a "
                "fully correct submission scores 1.0."
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
                    "rationale": "The task performs marketing audience segmentation with governance and overlap analysis.",
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
            "required_outputs": ["segment_definition.json", "audience_roster.csv", "overlap_report.tsv"],
            "hard_checks": [
                "target set matches the six target predicates",
                "support-ticket suppression applied before eligibility",
                "age, gender, city, and state absent from the roster",
                "sms_eligible, push_eligible, any_channel_eligible match per customer",
                "audience_stats counts and pct_of_total_profiles match",
                "overlap_report counts and percentages match, high-overlap flag uses 10% threshold",
                "total_qualifying >= 50",
            ],
            "expected_total_qualifying": result["segment_definition"]["audience_stats"]["total_qualifying"],
        },
    )

    manifest_text = (
        "dataset_id=audience_segmentation_app_winback_01\n"
        f"random_seed={RANDOM_SEED}\n"
        f"profile_count={PROFILE_COUNT}\n"
        "target=ltv>=1500,recency_days>=45,has_app=1,app_sessions_30d>=2,email_opens_30d<=2,last_email_open_days_ago>30\n"
        "suppression=support_tickets_90d>0\n"
        "channels=sms_opt_in,push_opt_in\n"
        "pii_removed=age,gender,city,state\n"
        "generated_by=ale-task-factory\n"
    )
    (CAND / "source_pack/dataset_manifest.txt").write_text(manifest_text, encoding="utf-8")

    sources = [
        ("src-dataset-manifest", "Synthetic dataset generation manifest", "source_pack/dataset_manifest.txt", "synthetic data generated by the ALE Task Factory"),
        ("src-brief", "Segmentation brief and governance rules", "base/input/segmentation_brief.md", "factory-authored task brief"),
        ("src-profiles", "Synthetic customer profiles", "base/input/unified_profiles.csv", "synthetic data generated by the ALE Task Factory"),
        ("src-audiences", "Existing audience definitions", "base/input/existing_audiences.csv", "factory-authored audience definitions"),
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
        ("dataset_generation", "src-dataset-manifest", "generation parameters", "random_seed=20261022"),
        ("target_ltv", "src-brief", "Target Audience", "- `ltv >= 1500`"),
        ("target_recency", "src-brief", "Target Audience", "- `recency_days >= 45`"),
        ("suppression", "src-brief", "Suppression", "- Exclude customers with `support_tickets_90d > 0` from all outbound campaigns."),
        ("pii", "src-brief", "PII", "Remove `age`, `gender`, `city`, and `state` from the roster and all external activation exports."),
        ("overlap_formula", "src-brief", "Overlap Analysis", "- `overlap_pct = overlap_count / total_qualifying * 100`, rounded to 2 decimals."),
        ("minimum_audience", "src-brief", "Governance", "- Minimum audience size: 50."),
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
    print(f"  profiles: {len(profiles)}")
    print(f"  total_qualifying: {result['segment_definition']['audience_stats']['total_qualifying']}")
    print(f"  sms: {result['segment_definition']['audience_stats']['sms_eligible']}, push: {result['segment_definition']['audience_stats']['push_eligible']}, any: {result['segment_definition']['audience_stats']['any_channel_eligible']}")
    for row in result["overlaps"]:
        print(f"  overlap {row['existing_audience_id']}: {row['overlap_count']} ({row['overlap_pct']}%) flag={row['flag_high_overlap']}")


if __name__ == "__main__":
    main()
