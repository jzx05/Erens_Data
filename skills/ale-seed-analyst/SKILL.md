---
name: ale-seed-analyst
description: Profiles the AgentHLE seed tasks, computes difficulty features and nearest seeds, and proposes the 20-task quota plan. Use when the seed profile is missing or stale, or when the quota plan needs to change.
---

# Seed Analyst

Build the shared picture of the seed corpus. Do not modify the seed root.

## Inputs

- Seed root: `~/下载/business_finance_extracted/business_finance`
- Target count: default 20
- Existing `profiles/seed_profile.json` and `profiles/quotas.json` (to detect staleness)

## Steps

1. Run:

   ```bash
   python3 -I scripts/seed_profile.py \
     --seeds "$HOME/下载/business_finance_extracted/business_finance" \
     --out profiles --target 20 --reset
   ```

2. Inspect `profiles/seed_profile.json`:
   - `task_count` must equal the number of `*/task_card.json` files.
   - Every task must have `features`, `tier`, `difficulty_score`, and `nearest_seeds`.
   - `subdomains` must include accounting, enterprise_analytics, compliance, sales_marketing,
     quant_finance, actuarial_risk, supply_chain, litigation, hr_pm, graphic_design.

3. Inspect `profiles/quotas.json`:
   - Sum of `count` must equal the target.
   - `graphic_design` must be 0 or explicitly justified.
   - Tier B subdomains may be quoted, but the author must pick a locally verifiable task family.

4. Summarize for the user:
   - seed count per subdomain
   - tier A vs tier B counts
   - quota per subdomain
   - the nearest-seed anchors for the next few candidates

## Rules

- Never edit a seed task card, input, reference, or evaluator.
- Do not hand-write profile JSON. If the script is wrong, fix the script and re-run.
- Treat `difficulty_score` as a heuristic. The difficulty gate compares the candidate's features to
  the anchor seed; it is not a ground-truth label.
- If the seed corpus changes, re-run with `--reset` only after confirming the queue is empty or the
  user wants to rebuild it.
