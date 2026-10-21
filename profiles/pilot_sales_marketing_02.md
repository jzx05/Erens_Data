# Pilot: bf-sales-marketing-02 (2026-10-21)

Synthetic audience-segmentation task generated from seed 20261022. Target stratum:
sales_marketing. Seed anchor: `digital_marketing_audience_segmentation_1`.

## Dataset

- 10,000 synthetic customer profiles with the seed schema.
- Target: `ltv >= 1500`, `recency_days >= 45`, `has_app = 1`, `app_sessions_30d >= 2`,
  `email_opens_30d <= 2`, `last_email_open_days_ago > 30`.
- Suppression: `support_tickets_90d > 0`.
- Channels: SMS (`sms_opt_in = 1`), push (`push_opt_in = 1`).
- PII removed: age, gender, city, state.
- Governance minimum: 50.

## Expected results

- Total qualifying after suppression: **71**
- SMS eligible: **45**, push eligible: **36**, any channel: **58**
- Overlaps: AUD-101 6 (8.45%), AUD-102 0, AUD-103 52 (73.24%, high), AUD-104 0,
  AUD-105 0, AUD-106 2 (2.82%).

## Deterministic gates

| Gate | Result |
|---|---|
| Schema | pass |
| Gold run | 1.0 (61/61 checks) |
| Mutation | 3/3 rejected |
| Evidence | 0 errors, 0 warnings |
| Difficulty | structural distance 0.4965 <= 2.0 |
| Dedup | text similarity 0.4002 < 0.85; source hash overlap 0.1429 |

## Independent solve

The first attempt was blocked by an external API error (HTTP 402 Insufficient Balance on
`deepseek-flash`) before writing any output. The retry used the main `deepseek-flash[1m]` model.
The first retry scored 59/61 because the brief said "one object" for `suppression_rules` and used
`has_app = 1`, while the schema expected a list and `==`. After clarifying the brief
(`has_app == 1`, "a list containing one object"), a fresh solver scored **1.0 (61/61 checks)**.

Review total: **100/100**; recommendation **ACCEPT**; human sign-off recorded.

## Status

Human sign-off recorded; candidate marked **ACCEPTED** on 2026-10-21. Exported in
`exports/accepted-4`.
