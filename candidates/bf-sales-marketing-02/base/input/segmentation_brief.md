# Segmentation Brief: High-Value Lapsed App Users — Win-Back Push/SMS

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
