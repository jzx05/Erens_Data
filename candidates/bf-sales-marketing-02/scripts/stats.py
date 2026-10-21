"""Shared logic for the synthetic audience-segmentation task."""

from __future__ import annotations

import csv
from pathlib import Path

PII_FIELDS = ["age", "gender", "city", "state"]

ROSTER_COLUMNS = [
    "customer_id",
    "tenure_months",
    "loyalty_tier",
    "total_purchases",
    "purchase_count_30d",
    "purchase_count_90d",
    "avg_order_value",
    "ltv",
    "recency_days",
    "has_app",
    "app_sessions_30d",
    "engagement_score",
    "sms_eligible",
    "push_eligible",
    "any_channel_eligible",
]

TARGET_PREDICATES = [
    {"field": "ltv", "operator": ">=", "value": 1500},
    {"field": "recency_days", "operator": ">=", "value": 45},
    {"field": "has_app", "operator": "==", "value": 1},
    {"field": "app_sessions_30d", "operator": ">=", "value": 2},
    {"field": "email_opens_30d", "operator": "<=", "value": 2},
    {"field": "last_email_open_days_ago", "operator": ">", "value": 30},
]

SUPPRESSION_RULES = [
    {
        "field": "support_tickets_90d",
        "operator": ">",
        "value": 0,
        "reason": "Active support ticket suppression",
    }
]

AUDIENCE_NAME = "High-Value Lapsed App Users — Win-Back Push/SMS"
CREATED_DATE = "2026-10-21"
VERSION = "1.0"
HIGH_OVERLAP_PCT = 10.0
MIN_AUDIENCE_SIZE = 50

EXISTING_AUDIENCES = [
    {
        "id": "AUD-101",
        "name": "High LTV",
        "definition": "ltv > 5000",
        "predicate": lambda row: number(row, "ltv") > 5000,
    },
    {
        "id": "AUD-102",
        "name": "Recent Buyers",
        "definition": "recency_days < 30",
        "predicate": lambda row: integer(row, "recency_days") < 30,
    },
    {
        "id": "AUD-103",
        "name": "App Power Users",
        "definition": "app_sessions_30d > 10 AND has_app = 1",
        "predicate": lambda row: integer(row, "app_sessions_30d") > 10
        and integer(row, "has_app") == 1,
    },
    {
        "id": "AUD-104",
        "name": "Email Engaged",
        "definition": "email_opens_30d >= 3",
        "predicate": lambda row: integer(row, "email_opens_30d") >= 3,
    },
    {
        "id": "AUD-105",
        "name": "Support Contacts",
        "definition": "support_tickets_90d > 0",
        "predicate": lambda row: integer(row, "support_tickets_90d") > 0,
    },
    {
        "id": "AUD-106",
        "name": "Platinum Loyalty",
        "definition": "loyalty_tier = 'platinum'",
        "predicate": lambda row: row["loyalty_tier"] == "platinum",
    },
]


def number(row: dict, field: str) -> float:
    return float(row[field])


def integer(row: dict, field: str) -> int:
    return int(float(row[field]))


def is_target(row: dict) -> bool:
    return (
        number(row, "ltv") >= 1500
        and integer(row, "recency_days") >= 45
        and integer(row, "has_app") == 1
        and integer(row, "app_sessions_30d") >= 2
        and integer(row, "email_opens_30d") <= 2
        and integer(row, "last_email_open_days_ago") > 30
    )


def is_suppressed(row: dict) -> bool:
    return integer(row, "support_tickets_90d") > 0


def read_profiles(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def compute(root: Path) -> dict:
    root = Path(root)
    profiles = read_profiles(root / "base" / "input" / "unified_profiles.csv")
    qualifying_all = [row for row in profiles if is_target(row)]
    qualifying = [row for row in qualifying_all if not is_suppressed(row)]

    roster = []
    for row in sorted(qualifying, key=lambda item: item["customer_id"]):
        sms = 1 if integer(row, "sms_opt_in") == 1 else 0
        push = 1 if integer(row, "push_opt_in") == 1 else 0
        output = {column: row[column] for column in ROSTER_COLUMNS if column in row}
        output["sms_eligible"] = sms
        output["push_eligible"] = push
        output["any_channel_eligible"] = 1 if sms or push else 0
        roster.append(output)

    overlaps = []
    for audience in EXISTING_AUDIENCES:
        count = sum(1 for row in qualifying if audience["predicate"](row))
        pct = round(count / len(qualifying) * 100, 2) if qualifying else 0.0
        overlaps.append(
            {
                "existing_audience_id": audience["id"],
                "existing_audience_name": audience["name"],
                "overlap_count": count,
                "overlap_pct": pct,
                "flag_high_overlap": pct >= HIGH_OVERLAP_PCT,
            }
        )

    sms_eligible = sum(item["sms_eligible"] for item in roster)
    push_eligible = sum(item["push_eligible"] for item in roster)
    any_channel = sum(item["any_channel_eligible"] for item in roster)
    segment_definition = {
        "segment_name": AUDIENCE_NAME,
        "created_date": CREATED_DATE,
        "version": VERSION,
        "filter_predicates": [dict(item) for item in TARGET_PREDICATES],
        "suppression_rules": [dict(item) for item in SUPPRESSION_RULES],
        "activation_channels": {
            "sms": {"eligibility_field": "sms_opt_in", "required_value": 1},
            "push": {"eligibility_field": "push_opt_in", "required_value": 1},
        },
        "governance_applied": {
            "pii_fields_removed": list(PII_FIELDS),
            "opt_out_compliance": True,
            "support_suppression": True,
        },
        "audience_stats": {
            "total_qualifying": len(qualifying),
            "sms_eligible": sms_eligible,
            "push_eligible": push_eligible,
            "any_channel_eligible": any_channel,
            "pct_of_total_profiles": round(len(qualifying) / len(profiles) * 100, 2),
        },
    }
    return {
        "profiles": profiles,
        "qualifying": qualifying,
        "roster": roster,
        "overlaps": overlaps,
        "segment_definition": segment_definition,
        "min_audience_size": MIN_AUDIENCE_SIZE,
    }
