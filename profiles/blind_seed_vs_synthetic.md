# Blind dsh: Seed vs Synthetic (2026-10-21)

> Calibration update: the strict rule "synthetic <= seed" and the absolute "1.0 = too easy" rule
> have both been replaced by **seed-relative calibration**. The seed's blind score is the baseline;
> a synthetic 1.0 is parity when the seed is also ~1.0. See `AGENTS.md` and
> `skills/ale-task-author/SKILL.md`.

All runs used the Docker blind pipeline. The solver container mounted only `base/input` and the
read-only host dsh package; the seed/synthetic reference stayed on the host and was used only by the
host-side scorer. The seed baseline is stored at `~/ale-blind/seed-<anchor>/eval/score.json`; the
synthetic score is at `~/ale-blind/<id>/eval/score.json`.

## Scores

### Seeds

| Seed | Score | Baseline status | Notes |
|---|---:|---|---|
| `sse_northbound_programmatic_trading_01` | **0.667** | available | q1/q2 accepted; q3 conclusion wrong (seed lacks explicit Yes/No/Unknown semantics) |
| `digital_marketing_ab_test_analysis_1` | **1.0** | available | all checks pass |
| `digital_marketing_audience_segmentation_1` | **0.942** | available | structure/stats/roster/eligibility 1.0; overlap counts 0.667; overlap pct 0.833 |
| `american_option_pricing_ls` | **1.0** | available | tier1/tier2/tier3 all pass; boundary MAE 0 |
| `basel_operational_risk_bia_cn` | **0.0** | available but degenerate | capital correct; business-line accuracy 52/60 = 86.7%, below the seed's 90% gate |
| `metabase_bi_dashboard_01` | not run | missing (GUI) | requires Metabase GUI and browser |
| `taxform_4_1` | not run | missing (no input) | extracted task has no `base/input`/`base/reference`; browser-based seed |
| `internal_employee_agent_instance_1` | not run | missing (no adapter) | hidden suite needs `bash` + `jq`; agent-style KB task |

### Synthetic candidates

| Candidate | Score | Anchor | Seed baseline | Relative verdict |
|---|---:|---|---:|---|
| `bf-compliance-02` | **1.0** | SSE document forensics | 0.667 | too easy relative to seed (accepted before rule) |
| `bf-sales-marketing-01` | **0.706** | A/B test | 1.0 | harder than seed but above floor; acceptable |
| `bf-sales-marketing-02` | **1.0** | audience segmentation | 0.942 | parity; acceptable |
| `bf-enterprise-analytics-02` | **1.0** | Metabase BI | missing | absolute fallback says too easy |
| `bf-quant-finance-01` | **1.0** | American option | 1.0 | parity; acceptable |
| `bf-actuarial-risk-01` | **1.0** (fresh) | Basel BIA | 0.0 (degenerate) | too easy; target 0.3–0.7; rerun 22:44 after the 22:22 revision |
| `bf-accounting-01` | **1.0** | taxform | missing | absolute fallback says too easy |
| `bf-hr-pm-01` | **1.0** | HR agent | missing | absolute fallback says too easy |
| `bf-sales-marketing-03` | **1.0** | A/B test | 1.0 | parity; acceptable |

## Paired comparison

| Capability | Seed | Synthetic | Reading |
|---|---:|---:|---|
| Document forensics | 0.667 | **1.0** | Synthetic is easier than the seed; accepted before relative calibration |
| A/B test analysis | **1.0** | 0.706 / **1.0** | 0.706 is harder but learnable; 1.0 is parity |
| Audience segmentation | 0.942 | **1.0** | Parity (both ~1.0) |
| American option pricing | **1.0** | **1.0** | Parity |
| Basel BIA / operational risk | **0.0** (degenerate) | **1.0** | Too easy relative to a degenerate seed; target 0.3–0.7 |
| BI metrics | not run (GUI) | **1.0** | No baseline; absolute fallback says too easy |
| Tax computation | not run (form/browser) | **1.0** | No baseline; absolute fallback says too easy |
| HR / employee agent | not run (suite/jq) | **1.0** | No baseline; absolute fallback says too easy |
| Campaign ROI | 1.0 (AB seed) | **1.0** | Parity |

## Findings

1. A synthetic 1.0 is not automatically too easy. `bf-quant-finance-01` and
   `bf-sales-marketing-03` are parity with their 1.0 seeds and should not be revised for difficulty.
2. `bf-actuarial-risk-01` sits against a degenerate 0.0 seed. It should target the learnable floor
   (0.3–0.7), not the seed's 0.0; the 100% threshold experiment was too hard and was reverted.
3. `bf-accounting-01` and `bf-hr-pm-01` have no seed baseline. Their 1.0 scores are judged by the
   absolute 0.4–0.9 fallback and flagged `SEED_BASELINE_MISSING`; a baseline or a different anchor
   would make the comparison stronger.
4. `bf-compliance-02` was accepted before relative calibration; its 1.0 is above its 0.667 seed.
   Reopen it only if the human wants strict relative difficulty.
5. The seed tasks have real ambiguities:
   - SSE q3 has no explicit `Yes/No/Unknown` semantics.
   - Segmentation overlap differs on PII-removed columns and the high-overlap threshold.
6. `bf-sales-marketing-01`'s 0.706 is a formatting/compliance failure, not a data error: the SRM,
   rates, 90% CIs, z-tests, Holm decisions, power sample size, and HOLD recommendation were correct.
7. Seeds that depend on Metabase, Chrome, LibreOffice, or a `jq`-based hidden suite cannot be blind
   tested in the current container without adding those runtimes or a GUI.

## Calibration status (seed-relative)

| Candidate | Seed | Synthetic | Mode | Status |
|---|---:|---:|---|---|
| `bf-quant-finance-01` | 1.0 | 1.0 | relative-to-seed | **REVIEWED** (parity) |
| `bf-sales-marketing-03` | 1.0 | 1.0 | relative-to-seed | **REVIEWED** (parity) |
| `bf-actuarial-risk-01` | 0.0 | 1.0 (fresh) | degenerate-seed | **REVISE** (`TOO_EASY`, target 0.3–0.7) |
| `bf-accounting-01` | missing | 1.0 | absolute-fallback | **REVISE** (`SEED_BASELINE_MISSING`, 1.0 above 0.9) |
| `bf-hr-pm-01` | missing | 1.0 | absolute-fallback | **REVISE** (`SEED_BASELINE_MISSING`, 1.0 above 0.9) |

Earlier accepted tasks (not retroactively changed):
`bf-sales-marketing-01` 0.706 vs seed 1.0 (harder, acceptable);
`bf-sales-marketing-02` 1.0 vs seed 0.942 (parity);
`bf-compliance-02` 1.0 vs seed 0.667 (too easy relative; accepted before the rule);
`bf-enterprise-analytics-02` 1.0 with no seed baseline (absolute fallback; accepted before the rule).

## Recommended actions

1. **Do not bump `bf-quant-finance-01` or `bf-sales-marketing-03`**: 1.0/1.0 is parity, not too easy.
2. **Actuarial**: add a few nuanced events or partial credit and target 0.3–0.7. The 22:44 rerun
   after the 22:22 revision is fresh (1.0); do not force 0.0 and do not use an all-or-nothing 100%
   gate.
3. **Accounting and HR**: either build a blind baseline for their anchors (if feasible) or accept
   the absolute fallback with `SEED_BASELINE_MISSING` recorded in review. Do not pretend the seed is
   1.0.
4. **Compliance**: if strict relative difficulty is required, reopen `bf-compliance-02` and add one
   hard-but-unambiguous requirement; otherwise keep the human sign-off and note the exception.
5. **Use the same model** for seed and synthetic runs; record `run_meta` in both score files.
6. **Mimic the seed's speaking style**: section structure, tone, terminology, detail level, and
   output-contract phrasing.
7. Human sign-off only after the calibration pass.
