# Pilot: bf-enterprise-analytics-02 (2026-10-21)

Synthetic SQLite BI task generated from seed 20261023. Target stratum: enterprise_analytics.
Seed anchor: `metabase_bi_dashboard_01`.

## Design

The seed uses a Metabase GUI and browser. This candidate keeps the same 11-metric output contract
but replaces the GUI with a local SQLite database and Python `sqlite3`, so the task is fully
verifiable without a browser.

## Dataset

- 500 customers, 2,000 orders, 2,753 events.
- Orders span 2025-01 through 2025-12.
- 1,417 completed orders; total revenue 286,726.45; 469 unique purchasing customers;
  conversion rate 93.8%; top customer spend 2,265.37.

## Metrics

`total_revenue`, `average_order_value`, `conversion_rate`, `total_completed_orders`,
`unique_purchasing_customers`, `revenue_by_category`, `monthly_revenue`, `orders_by_device`,
`orders_by_channel`, `event_funnel`, `top_10_customers`.

## Deterministic gates

| Gate | Result |
|---|---|
| Schema | pass |
| Gold run | 1.0 |
| Mutation | 3/3 rejected |
| Evidence | 0 errors, 0 warnings |
| Difficulty | structural distance 0.7452 <= 2.0 |
| Dedup | text similarity 0.2578; no file overlap |

## Independent solve

Retried on the main `deepseek-flash[1m]` model. The solver produced `dashboard_metrics.json` with
total revenue 286,726.45, 1,417 completed orders, 93.8% conversion, and top customer CUST-010436
(2,265.37). The evaluator scored **1.0**. Review total: **100/100**; recommendation **ACCEPT**;
human sign-off recorded.

## Status

Human sign-off recorded; candidate marked **ACCEPTED** on 2026-10-21. Exported in
`exports/accepted-4`.
