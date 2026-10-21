#!/usr/bin/env python3
"""Build bf-enterprise-analytics-02: SQLite BI dashboard metrics.

This is a locally verifiable replacement for the Metabase GUI seed. The synthetic
SQLite database is generated deterministically from seed 20261023.

Usage:
  python3 -I scripts/build_bf_enterprise_analytics_02.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_ID = "bf-enterprise-analytics-02"
CAND = ROOT / "candidates" / CANDIDATE_ID
EXAMPLE = ROOT / "templates" / "task" / "data-analysis" / "examples" / "bi_metrics"

RANDOM_SEED = 20261023
CUSTOMER_COUNT = 500
ORDER_COUNT = 2000
CATEGORIES = ["Beauty", "Electronics", "Home", "Sports", "Toys"]
DEVICES = ["desktop", "mobile", "tablet"]
CHANNELS = ["email", "organic", "paid_search", "social"]
COUNTRIES = ["AU", "CA", "DE", "UK", "US"]
STATUSES = ["completed", "cancelled", "refunded", "pending"]
STATUS_WEIGHTS = [70, 10, 10, 10]
AMOUNT_RANGES = {
    "Beauty": (20, 200),
    "Electronics": (100, 800),
    "Home": (50, 400),
    "Sports": (30, 300),
    "Toys": (15, 150),
}

REQUIREMENTS = """# Business Analytics Dashboard Requirements

## Database

`base/input/business_analytics.sqlite` contains three tables:

- `customers(customer_id, customer_name, signup_date, device, channel, country)`
- `orders(order_id, customer_id, order_date, status, amount, category, device, channel)`
- `events(event_id, customer_id, event_type, event_date)`

## Global Rules

- Revenue and order metrics include only orders with `status = 'completed'`.
- Round all monetary values and rates to 2 decimal places.
- `conversion_rate` is a percentage in the range 0-100.
- `monthly_revenue` covers every month from the earliest to the latest `order_date` in `orders`,
  inclusive; months with no completed revenue are `0.00`.
- `revenue_by_category` includes every category that appears in at least one completed order.
- `orders_by_device` and `orders_by_channel` include every value that appears in at least one
  completed order.
- `event_funnel` counts distinct customers per event type. The `purchase` stage is the number of
  distinct customers with at least one completed order.
- `top_10_customers` uses completed orders only. Sort by `total_spend` descending, then
  `customer_id` ascending; return exactly 10 objects with `customer_id`, `customer_name`, and
  `total_spend`.

## Required Metrics

1. `total_revenue`: sum of `amount` over completed orders.
2. `average_order_value`: `total_revenue / total_completed_orders`.
3. `conversion_rate`: distinct purchasing customers / total customers * 100.
4. `total_completed_orders`: count of completed orders.
5. `unique_purchasing_customers`: distinct customers with at least one completed order.
6. `revenue_by_category`: mapping category -> completed revenue.
7. `monthly_revenue`: mapping `YYYY-MM` -> completed revenue, zero-filled across the full month
   range.
8. `orders_by_device`: mapping order device -> completed order count.
9. `orders_by_channel`: mapping order channel -> completed order count.
10. `event_funnel`: mapping event stage (`view`, `add_to_cart`, `checkout`, `purchase`) to distinct
    customer count.
11. `top_10_customers`: ordered list of the top 10 customers by completed spend.

## Output

Write `base/output/dashboard_metrics.json` conforming to `base/input/output_schema.json`.
"""

TASK_PROMPT = """You are a business analyst producing a metrics report from a SQLite database.

## Inputs

- Database: `base/input/business_analytics.sqlite`
- Metric definitions: `base/input/requirements.md`
- Output schema: `base/input/output_schema.json`

## Task

1. Read the requirements and output schema.
2. Query the SQLite database directly with Python 3.12 and `sqlite3`.
3. Compute all 11 required metrics with the exact definitions and rounding rules.
4. Write exactly one file: `base/output/dashboard_metrics.json`, conforming to the output schema.

Do not use Metabase, a browser, or any external data. The standard library is sufficient.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "total_revenue",
        "average_order_value",
        "conversion_rate",
        "total_completed_orders",
        "unique_purchasing_customers",
        "revenue_by_category",
        "monthly_revenue",
        "orders_by_device",
        "orders_by_channel",
        "event_funnel",
        "top_10_customers",
    ],
    "properties": {
        "total_revenue": {"type": "number"},
        "average_order_value": {"type": "number"},
        "conversion_rate": {"type": "number"},
        "total_completed_orders": {"type": "integer"},
        "unique_purchasing_customers": {"type": "integer"},
        "revenue_by_category": {"type": "object", "additionalProperties": {"type": "number"}},
        "monthly_revenue": {"type": "object", "additionalProperties": {"type": "number"}},
        "orders_by_device": {"type": "object", "additionalProperties": {"type": "integer"}},
        "orders_by_channel": {"type": "object", "additionalProperties": {"type": "integer"}},
        "event_funnel": {"type": "object", "additionalProperties": {"type": "integer"}},
        "top_10_customers": {
            "type": "array",
            "minItems": 10,
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["customer_id", "customer_name", "total_spend"],
                "properties": {
                    "customer_id": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "total_spend": {"type": "number"},
                },
            },
        },
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_metrics():
    path = EXAMPLE / "metrics.py"
    spec = importlib.util.spec_from_file_location("bi_metrics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate() -> tuple[list[tuple], list[tuple], list[tuple]]:
    rng = random.Random(RANDOM_SEED)
    customers = []
    for index in range(CUSTOMER_COUNT):
        customer_id = f"CUST-{10001 + index:06d}"
        customers.append(
            (
                customer_id,
                f"Customer {index + 1:04d}",
                f"2024-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                rng.choice(DEVICES),
                rng.choice(CHANNELS),
                rng.choice(COUNTRIES),
            )
        )
    customer_ids = [row[0] for row in customers]

    orders = []
    for index in range(ORDER_COUNT):
        order_id = f"ORD-{index + 1:06d}"
        customer_id = rng.choice(customer_ids)
        month = index % 12 + 1
        order_date = f"2025-{month:02d}-{rng.randint(1, 28):02d}"
        status = rng.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
        category = rng.choice(CATEGORIES)
        low, high = AMOUNT_RANGES[category]
        amount = round(rng.uniform(low, high), 2)
        orders.append(
            (
                order_id,
                customer_id,
                order_date,
                status,
                amount,
                category,
                rng.choice(DEVICES),
                rng.choice(CHANNELS),
            )
        )

    buyers = {
        row[1] for row in orders if row[3] == "completed"
    }
    events = []
    event_id = 1
    for customer in customers:
        customer_id = customer[0]
        for _ in range(rng.randint(1, 5)):
            events.append(
                (
                    event_id,
                    customer_id,
                    "view",
                    f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                )
            )
            event_id += 1
        cart_count = rng.randint(1, 2) if customer_id in buyers else rng.randint(0, 1)
        for _ in range(cart_count):
            events.append(
                (
                    event_id,
                    customer_id,
                    "add_to_cart",
                    f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                )
            )
            event_id += 1
        if customer_id in buyers:
            events.append(
                (
                    event_id,
                    customer_id,
                    "checkout",
                    f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                )
            )
            event_id += 1
    return customers, orders, events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if CAND.exists():
        if not args.force:
            raise SystemExit(f"candidate already exists: {CAND} (pass --force to rebuild)")
        shutil.rmtree(CAND)
    for relative in ("base/input", "base/reference", "base/software", "scripts", "evidence", "source_pack"):
        (CAND / relative).mkdir(parents=True, exist_ok=True)

    customers, orders, events = generate()
    database_path = CAND / "base/input/business_analytics.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE customers(
                customer_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                signup_date TEXT NOT NULL,
                device TEXT NOT NULL,
                channel TEXT NOT NULL,
                country TEXT NOT NULL
            );
            CREATE TABLE orders(
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                device TEXT NOT NULL,
                channel TEXT NOT NULL
            );
            CREATE TABLE events(
                event_id INTEGER PRIMARY KEY,
                customer_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_date TEXT NOT NULL
            );
            """
        )
        connection.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", customers)
        connection.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", orders)
        connection.executemany("INSERT INTO events VALUES (?,?,?,?)", events)
        connection.commit()
    finally:
        connection.close()

    (CAND / "base/input/requirements.md").write_text(REQUIREMENTS, encoding="utf-8")
    write_json(CAND / "base/input/output_schema.json", OUTPUT_SCHEMA)
    (CAND / "base/software/README.md").write_text(
        "Python 3.12 with the standard library (including sqlite3) is sufficient. "
        "Metabase and a browser are not required.\n",
        encoding="utf-8",
    )

    for name in ("metrics.py", "make_gold_output.py", "evaluate.py"):
        shutil.copy2(EXAMPLE / name, CAND / "scripts" / name)

    metrics = load_metrics()
    expected = metrics.compute(CAND)

    write_json(
        CAND / "candidate.json",
        {
            "id": CANDIDATE_ID,
            "status": "AUTHORED",
            "stratum": "enterprise_analytics",
            "seed_anchor": "metabase_bi_dashboard_01",
            "seed_refs": ["metabase_bi_dashboard_01", "internal_employee_agent_instance_1"],
            "difficulty_target": 94.28,
            "task_family": "data-analysis",
            "source_policy": "synthetic",
            "internal_only": False,
            "synthetic_data": True,
            "attempts": 0,
            "reason_codes": [],
            "paths": {},
        },
    )

    task_id = "business_finance/sqlite_bi_dashboard_metrics_01"
    write_json(
        CAND / "task_card.json",
        {
            "taskId": task_id,
            "title": "SQLite BI Dashboard Metrics",
            "summary": (
                "Query a synthetic business analytics SQLite database and produce an 11-field JSON "
                "metrics report with revenue, conversion, category/monthly revenue, device/channel "
                "counts, an event funnel, and the top 10 customers."
            ),
            "category": "business_finance",
            "software": ["Python 3.12", "SQLite"],
            "taskPrompt": TASK_PROMPT,
            "agentMustDo": [
                "Read requirements.md and output_schema.json.",
                "Query business_analytics.sqlite with Python 3.12 and sqlite3.",
                "Apply the completed-order filter and 2-decimal rounding rules.",
                "Compute all 11 required metrics, including the zero-filled monthly series and the ordered top-10 list.",
                "Write exactly one dashboard_metrics.json under base/output.",
            ],
            "inputFiles": [
                {"name": "business_analytics.sqlite", "format": "SQLite", "path": "input/business_analytics.sqlite", "description": "Synthetic customers, orders, and events database."},
                {"name": "requirements.md", "format": "Markdown", "path": "input/requirements.md", "description": "Exact metric definitions, filters, rounding, and ordering rules."},
                {"name": "output_schema.json", "format": "JSON Schema", "path": "input/output_schema.json", "description": "Required JSON structure and types."},
            ],
            "referenceFiles": [
                {"name": "dashboard_metrics.json", "format": "JSON", "path": "output/dashboard_metrics.json", "description": "Required 11-field metrics report."},
            ],
            "evaluation": (
                "Hard gates: missing or unparsable output, missing top-level keys, or wrong types. "
                "Score 11 fields with equal weight: scalars within 0.5% relative tolerance, exact "
                "integers, per-key partial credit for dicts, and order-sensitive top-10 matching. "
                "Only a fully correct report scores 1.0."
            ),
            "vm": {"machineType": "c4-standard-4", "snapshot": "cpu-free-ubuntu", "timeout": 7200},
            "taxonomy": {
                "domain_id": "6",
                "domain_code": "business_finance",
                "subdomain_id": "6.3",
                "subdomain_code": "enterprise_analytics",
                "subdomain_name": "Enterprise Analytics & Planning",
                "classifier": {
                    "model": "manual",
                    "classified_at": "2026-10-21T00:00:00Z",
                    "source": {"submission_id": "factory", "fields": ["taskPrompt", "title", "summary", "software"], "mode": "manual"},
                    "rationale": "The task computes business intelligence metrics from a SQLite analytics database.",
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
            "required_outputs": ["dashboard_metrics.json"],
            "hard_checks": [
                "all 11 top-level keys present with correct types",
                "revenue and order metrics use completed orders only",
                "all monetary values and rates rounded to 2 decimals",
                "monthly_revenue is zero-filled across the full month range",
                "top_10_customers is sorted by total_spend desc then customer_id asc",
                "scalars within 0.5% relative tolerance; integers exact",
            ],
        },
    )

    manifest_text = (
        "dataset_id=sqlite_bi_dashboard_metrics_01\n"
        f"random_seed={RANDOM_SEED}\n"
        f"customers={len(customers)}\n"
        f"orders={len(orders)}\n"
        f"events={len(events)}\n"
        "order_date_range=2025-01-01..2025-12-31\n"
        "categories=Beauty,Electronics,Home,Sports,Toys\n"
        "devices=desktop,mobile,tablet\n"
        "channels=email,organic,paid_search,social\n"
        "generated_by=ale-task-factory\n"
    )
    (CAND / "source_pack/dataset_manifest.txt").write_text(manifest_text, encoding="utf-8")

    sources = [
        ("src-dataset-manifest", "Synthetic dataset generation manifest", "source_pack/dataset_manifest.txt", "synthetic data generated by the ALE Task Factory"),
        ("src-requirements", "BI metric requirements", "base/input/requirements.md", "factory-authored task requirements"),
        ("src-schema", "Output JSON schema", "base/input/output_schema.json", "factory-authored output schema"),
        ("src-database", "Synthetic business analytics SQLite database", "base/input/business_analytics.sqlite", "synthetic data generated by the ALE Task Factory"),
    ]
    with (CAND / "evidence/sources.jsonl").open("w", encoding="utf-8") as handle:
        for source_id, title, path, license_name in sources:
            record = {
                "source_id": source_id,
                "title": title,
                "publisher": "ALE Task Factory",
                "local_path": path,
                "retrieved_at": "2026-10-21T00:00:00Z",
                "license": license_name,
                "redistributable": True,
                "sha256": sha256(CAND / path),
                "locators": ["full file"],
                "notes": "Synthetic or factory-authored material; safe to redistribute.",
            }
            if path.endswith((".md", ".json", ".txt")):
                record["text_path"] = path
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    claims = [
        ("dataset_generation", "src-dataset-manifest", "generation parameters", "random_seed=20261023"),
        ("completed_filter", "src-requirements", "Global Rules", "- Revenue and order metrics include only orders with `status = 'completed'`."),
        ("rounding", "src-requirements", "Global Rules", "- Round all monetary values and rates to 2 decimal places."),
        ("monthly_zero_fill", "src-requirements", "Global Rules", "- `monthly_revenue` covers every month from the earliest to the latest `order_date` in `orders`,"),
        ("top10_order", "src-requirements", "Global Rules", "- `top_10_customers` uses completed orders only. Sort by `total_spend` descending, then"),
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
    print(f"  customers={len(customers)} orders={len(orders)} events={len(events)}")
    print(f"  total_revenue={expected['total_revenue']} completed_orders={expected['total_completed_orders']}")
    print(f"  conversion_rate={expected['conversion_rate']} unique_customers={expected['unique_purchasing_customers']}")
    print(f"  top1={expected['top_10_customers'][0] if expected['top_10_customers'] else None}")


if __name__ == "__main__":
    main()
