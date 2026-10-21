# Pilot: bf-sales-marketing-01 (2026-10-21)

Synthetic A/B-test task generated deterministically from seed 20261021. Target stratum:
sales_marketing. Seed anchor: `digital_marketing_ab_test_analysis_1`.

## Why synthetic

The seed AB data is degenerate: `clicked` equals `opened` for control and is all zero for
treatment; `converted` is all zero in both arms. Reusing it would produce a misleading task.
The factory generated a fresh dataset with realistic independent event probabilities.

## Dataset

- 6,000 control + 6,050 treatment customers; delivered probability 0.98.
- Control: open 0.215, click|open 0.18, convert|click 0.18, unsubscribe 0.0015.
- Treatment: open 0.245, click|open 0.20, convert|click 0.20, unsubscribe 0.0055.
- Historical open rates average 0.217917; required per-arm power sample size 3,116.
- Ground-truth decision: **hold** (open-rate lift significant, but unsubscribe lift 0.3357pp >
  0.3pp guardrail).

## Deterministic gates

| Gate | Result |
|---|---|
| Schema | pass |
| Gold run | 1.0 (63/63 checks) |
| Mutation | 3/3 rejected |
| Evidence | 0 errors, 0 warnings |
| Difficulty | structural distance 0.0779 <= 2.0 |
| Dedup | text similarity 0.4851 < 0.85; no file overlap |

## First independent solve

The solver scored 30/63 because it used all randomized customers (6,000/6,050) as the rate
denominator instead of delivered emails (5,887/5,928). All rates and intervals were systematically
off, and the report lift was 2.90pp instead of 2.99pp.

Fix: the task prompt and brief now state the denominator explicitly:
"For every metric rate, the denominator is delivered emails (`delivered == \"1\"`). The full raw
population is used only for the SRM check." The evaluator was not weakened.

## Harness fixes made during this pilot

- `seed_profile.py` difficulty vector now uses only structural features:
  software count, base-input file count, input bytes, reference file count, timeout, modalities.
  Metadata-completeness fields (`inputFiles` count, `agentMustDo` count, evaluation prose) were
  removed because some seed cards omit them, so they measured card formatting rather than
  difficulty.
- `mutation_test.py` now mutates structured outputs (JSON/CSV/TSV) before Markdown reports, so
  report-only mutations cannot pass the evaluator.

## Second independent solve

With the explicit delivered-email denominator, a fresh solver scored **1.0 (63/63 checks)**. It
reproduced the SRM, all four metric rates, 90% CIs, pooled z tests, Holm decisions, power sample
size 3,116, and the **hold** recommendation. Review total: **100/100**; recommendation **ACCEPT**.

## Status

Human sign-off recorded; candidate marked **ACCEPTED** on 2026-10-21. Exported in
`exports/pilot-2` together with `bf-compliance-02`.
