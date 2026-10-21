# Task Brief: Multi-Channel Campaign ROI Review and Budget Reallocation

## Context

You are a marketing analyst on the growth team at an e-commerce retailer. The marketing operations
team has exported eight weeks of daily performance data for six paid and owned channels. Finance
has asked for two deliverables:

1. a channel-level performance table that consolidates the eight weeks into one row per channel and
   reports the standard funnel and efficiency metrics;
2. a budget reallocation recommendation that shifts money from the weakest channel by return on ad
   spend (ROAS) to the strongest channel, subject to a spend cap.

## Data Rule

- Use only the staged files under `base/input`.
- `campaign_data.csv` is the only source of campaign amounts. `prior_quarter_benchmarks.csv` and
  `weekly_budget_baseline.csv` are context files: they must not feed any calculation.
- Do not use external data, and do not use any reference output from another task.

## Inputs

- `campaign_data.csv` — daily campaign rows for 6 channels across 56 consecutive days
  (8 complete weeks), from 2026-07-06 through 2026-08-30.
- `analysis_policy.md` — the metric, rounding, ranking, and reallocation policy.
- `output_contract.json` — the required output files, columns, and JSON keys.
- `channel_registry.yaml` — channel metadata (group, owner, active status).
- `prior_quarter_benchmarks.csv` — prior-quarter ROAS context only.
- `weekly_budget_baseline.csv` — pre-campaign planned budgets, context only.
- `runtime_env/pyproject.toml` — runtime metadata.

## Method

### Channel totals

For each channel, sum `impressions`, `clicks`, `leads`, `conversions`, `spend_usd`, and
`revenue_usd` over every daily row for that channel. All metrics below use these channel totals.
Never average the daily ratios.

### Metric definitions

| Metric | Formula | Denominator |
|---|---|---|
| `ctr_pct` | `clicks / impressions * 100` | impressions |
| `lead_rate_pct` | `leads / clicks * 100` | clicks |
| `cvr_pct` | `conversions / clicks * 100` | clicks |
| `cpa_usd` | `spend_usd / conversions` | conversions |
| `roas` | `revenue_usd / spend_usd` | spend |

`roas` is a ratio, not a percentage. `lead_rate_pct` and `cvr_pct` both use clicks as the
denominator; leads are not a denominator anywhere.

### Rounding

Round every reported metric and money amount to exactly 2 decimal places using round-half-up
(the half-away-from-zero rule). Round only the final reported value; do not round intermediate sums
or intermediate ratios. `impressions`, `clicks`, `leads`, `conversions`, and `roas_rank` are
integers.

### Ranking

Rank the six channels by `roas` in descending order: `roas_rank` 1 is the highest ROAS and
`roas_rank` 6 is the lowest. Rank on the full-precision ROAS before rounding. If two channels have
the same full-precision ROAS, the alphabetically smaller channel name (ASCII order) receives the
better rank.

### Budget reallocation

1. `lowest_roas_channel` is the channel with `roas_rank == 6`; `highest_roas_channel` is the
   channel with `roas_rank == 1`.
2. `raw_move_usd = 0.20 * current spend of lowest_roas_channel`.
3. `cap_usd = 0.25 * current spend of highest_roas_channel`.
4. `reallocation_amount_usd = min(raw_move_usd, cap_usd)`, rounded to 2 decimals.
5. New budget for the lowest-ROAS channel = current spend - `reallocation_amount_usd`.
6. New budget for the highest-ROAS channel = current spend + `reallocation_amount_usd`.
7. Every other channel keeps its current spend as its recommended budget.
8. The six recommended budgets sum to the same total as the six current spends.

## Required Outputs

Write exactly these files under `base/output`:

1. `channel_performance.csv` — a header row plus exactly six data rows, one per channel, in
   `roas_rank` ascending order (rank 1 first). Columns, in order: `channel`, `impressions`,
   `clicks`, `leads`, `conversions`, `spend_usd`, `revenue_usd`, `ctr_pct`, `lead_rate_pct`,
   `cvr_pct`, `cpa_usd`, `roas`, `roas_rank`.
2. `budget_recommendation.json` — a JSON object with keys `total_spend_usd`, `total_revenue_usd`,
   `blended_roas`, `lowest_roas_channel`, `lowest_roas`, `highest_roas_channel`, `highest_roas`,
   `reallocation_amount_usd`, `reallocation_cap_usd`, and `recommended_budgets`.
   `blended_roas = total_revenue_usd / total_spend_usd`, rounded to 2 decimals.
   `recommended_budgets` is a list of six objects, ordered by `roas_rank` ascending, each with keys
   `channel`, `current_spend_usd`, and `recommended_budget_usd`.

Do not write any other files.
