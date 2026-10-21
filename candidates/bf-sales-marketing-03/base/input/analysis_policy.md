# Campaign ROI Analysis Policy

Policy version 1.0. This policy is normative for the eight-week multi-channel campaign review. Apply
every rule literally; the evaluator checks each stated formula, denominator, rounding rule, ranking
rule, and reallocation rule.

## 1. Analysis Population

- `campaign_data.csv` holds one row per channel per calendar day: 6 channels across 56 consecutive
  days (8 complete weeks), from 2026-07-06 through 2026-08-30.
- Use every row. Do not filter, deduplicate, or exclude any row.
- `prior_quarter_benchmarks.csv` and `weekly_budget_baseline.csv` are context files and are excluded
  from all calculations.
- All monetary amounts are US dollars.

## 2. Channel Totals

For each channel, sum `impressions`, `clicks`, `leads`, `conversions`, `spend_usd`, and
`revenue_usd` across all 56 daily rows for that channel. Every metric in this policy is computed
from these six channel-level totals. Ratios of daily rows must never be averaged.

## 3. Metric Definitions and Denominators

| Metric | Formula | Denominator |
|---|---|---|
| `ctr_pct` | `clicks / impressions * 100` | impressions |
| `lead_rate_pct` | `leads / clicks * 100` | clicks |
| `cvr_pct` | `conversions / clicks * 100` | clicks |
| `cpa_usd` | `spend_usd / conversions` | conversions |
| `roas` | `revenue_usd / spend_usd` | spend |

Notes:

- `ctr_pct` is click-through rate, expressed as a percentage.
- `lead_rate_pct` uses clicks as the denominator. Leads are never a denominator.
- `cvr_pct` uses clicks as the denominator, not leads and not impressions.
- `cpa_usd` is cost per acquisition (cost per conversion).
- `roas` is return on ad spend, expressed as a ratio, not a percentage.

## 4. Rounding

- Round every reported metric and every reported money amount to exactly 2 decimal places using
  round-half-up (half away from zero).
- Round the final reported value only. Do not round intermediate channel totals, intermediate sums,
  or intermediate ratios before the final rounding step.
- `impressions`, `clicks`, `leads`, `conversions`, and `roas_rank` are integers and are not rounded.

## 5. ROAS Ranking

- Rank the six channels by `roas` in descending order. `roas_rank` is 1 for the highest ROAS and 6
  for the lowest ROAS.
- Rank on the full-precision ROAS, before any rounding.
- If two channels have the same full-precision ROAS, the channel with the alphabetically smaller
  name (ASCII order) receives the better rank.

## 6. Budget Reallocation

1. `lowest_roas_channel` is the channel with `roas_rank == 6`.
2. `highest_roas_channel` is the channel with `roas_rank == 1`.
3. `raw_move_usd = 0.20 * current spend of lowest_roas_channel`.
4. `cap_usd = 0.25 * current spend of highest_roas_channel`.
5. `reallocation_amount_usd = min(raw_move_usd, cap_usd)`, rounded to 2 decimals using the rule in
   section 4.
6. `recommended_budget_usd` of the lowest-ROAS channel = its current spend minus
   `reallocation_amount_usd`.
7. `recommended_budget_usd` of the highest-ROAS channel = its current spend plus
   `reallocation_amount_usd`.
8. Every other channel keeps its current spend as its `recommended_budget_usd`.
9. The six recommended budgets sum to exactly the same total as the six current spends.

## 7. Output Contract

Write exactly two files under `base/output`. No other files.

### 7.1 `channel_performance.csv`

- Comma-separated values, one header row plus exactly six data rows.
- Row order: `roas_rank` ascending, so rank 1 is the first data row and rank 6 the last.
- Columns, in this exact order: `channel`, `impressions`, `clicks`, `leads`, `conversions`,
  `spend_usd`, `revenue_usd`, `ctr_pct`, `lead_rate_pct`, `cvr_pct`, `cpa_usd`, `roas`,
  `roas_rank`
- `channel` is the channel name exactly as it appears in `campaign_data.csv`.
- `impressions`, `clicks`, `leads`, `conversions`, and `roas_rank` are integers written without
  thousands separators or decimal points.
- `spend_usd` and `revenue_usd` are the channel totals rounded to 2 decimals.
- `ctr_pct`, `lead_rate_pct`, `cvr_pct`, `cpa_usd`, and `roas` follow sections 3 and 4.

### 7.2 `budget_recommendation.json`

A single JSON object with exactly these keys, in any key order:

| Key | Type | Definition |
|---|---|---|
| `total_spend_usd` | number | sum of the six channel `spend_usd` totals, 2 decimals |
| `total_revenue_usd` | number | sum of the six channel `revenue_usd` totals, 2 decimals |
| `blended_roas` | number | `total_revenue_usd / total_spend_usd`, 2 decimals |
| `lowest_roas_channel` | string | channel with `roas_rank == 6` |
| `lowest_roas` | number | its `roas` value, 2 decimals |
| `highest_roas_channel` | string | channel with `roas_rank == 1` |
| `highest_roas` | number | its `roas` value, 2 decimals |
| `reallocation_amount_usd` | number | `min(0.20 * lowest spend, 0.25 * highest spend)`, 2 decimals |
| `reallocation_cap_usd` | number | `0.25 * highest channel spend`, 2 decimals |
| `recommended_budgets` | list | six objects, ordered by `roas_rank` ascending |

Each object in `recommended_budgets` has exactly these keys:

| Key | Type | Definition |
|---|---|---|
| `channel` | string | channel name |
| `current_spend_usd` | number | channel `spend_usd` total, 2 decimals |
| `recommended_budget_usd` | number | post-reallocation budget, 2 decimals |

## 8. Data Usage Restrictions

- Do not read outputs from any other task.
- Do not use network access.
- Do not infer or copy any value that is not derivable from `campaign_data.csv` under this policy.
