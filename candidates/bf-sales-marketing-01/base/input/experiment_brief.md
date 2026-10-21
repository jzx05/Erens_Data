# Experiment Brief: Personalized Email Subject Lines (90% CI / Holm Re-analysis)

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
