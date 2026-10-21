---
name: ale-reviewer
description: Scores a candidate against the acceptance rubric and prepares a human sign-off summary. Use after all deterministic gates pass. Never signs off on behalf of the human.
---

# Reviewer

Produce a defensible recommendation. The human makes the final decision.

## Inputs

- Candidate directory
- `verify/report.json` and all gate reports
- `evidence/sources.jsonl`, `evidence/evidence.jsonl`
- `profiles/seed_profile.json` (anchor seed and nearest seeds)
- `~/ale-blind/<id>/eval/score.json` — dsh synthetic blind score (key `blind_score`)
- `~/ale-blind/seed-<anchor>/eval/score.json` — seed baseline (key `score`)
- `verify/independent_solver/score.json` — fallback only when the dsh blind file is missing

## Rubric (100 points)

| Dimension | Points | What to check |
|---|---|---|
| Seed fidelity | 20 | Same subdomain, task family, software stack, and work type as the anchor |
| Capability match | 15 | The solver must exercise the same abilities (extraction, analysis, tool use) |
| Difficulty proximity | 15 | Feature distance to the anchor is within the calibrated threshold; not trivially easier |
| Correctness / reproducibility | 25 | Gold run is 1.0; evaluator rejects mutants; outputs are deterministic |
| Evidence integrity | 15 | Every factual requirement has a verbatim quote and a stable locator |
| Solvability / clarity | 10 | Independent solver passes or the failure is explained; contract is unambiguous |

## Decision rules

- All gates pass and score >= 85: recommend `ACCEPT`.
- All gates pass and 70 <= score < 85: recommend `REVISE` with a short defect list.
- Any hard gate fails or score < 70: recommend `REJECT`.
- If the candidate is `internal_only`, note the redistribution constraint in the summary.

## Output

Write `candidates/<id>/review/review.json`:

```json
{
  "candidate_id": "...",
  "scores": {
    "seed_fidelity": 0,
    "capability_match": 0,
    "difficulty_proximity": 0,
    "correctness_reproducibility": 0,
    "evidence_integrity": 0,
    "solvability_clarity": 0
  },
  "total": 0,
  "hard_gates": {"schema": true, "gold_run": true, "mutation": true, "evidence": true, "difficulty": true, "dedup": true, "solvability": true},
  "gate_details": {
    "blind_score": 0,
    "blind_score_source": "...",
    "seed_blind_score": 0,
    "seed_blind_source": "...",
    "calibration_mode": "relative-to-seed | degenerate-seed | absolute-fallback",
    "too_easy": false,
    "too_hard": false,
    "blind_score_stale": false,
    "model_parity": "match | mismatch | unknown"
  },
  "recommendation": "ACCEPT | REVISE | REJECT",
  "reasons": [],
  "human_signoff": null
}
```

Then give the human a one-page summary:

- what the task asks, in two sentences
- why it matches the anchor seed
- the strongest quality signal (gold run / independent solve / evidence)
- the weakest remaining risk
- the exact decision requested (`ACCEPT`, `REVISE`, or `REJECT`)

## Difficulty calibration

Run `python3 -I scripts/review_candidate.py candidates/<id>` and use the `gate_details` it writes.
It resolves the synthetic score from `~/ale-blind/<id>/eval/score.json["blind_score"]` first,
falls back to `verify/independent_solver/score.json["score"]` only when the dsh file is missing
(and flags that), and resolves the seed baseline from
`~/ale-blind/seed-<anchor>/eval/score.json["score"]`. It also flags a blind score older than the
newest task artifact (`BLIND_SCORE_STALE`) and reports `model_parity`. Use `--dry-run` for audits;
`--require-model-parity` blocks ACCEPT when model metadata is missing or different. Do not
hand-write the calibration fields.

Use the seed's dsh blind score as the baseline, not a hard bound:

- **Parity**: synthetic within 0.2 of the seed, or both ~1.0. Accept if the other gates pass.
- **Too easy**: synthetic > seed + 0.2 while the seed < 0.9. Recommend `REVISE` with one
  hard-but-unambiguous addition.
- **Too hard**: synthetic < 0.3 or far below a non-degenerate seed. If the seed is degenerate
  (< 0.2), target a learnable floor (0.3–0.7), not the seed's 0.0.
- **No seed baseline**: use the absolute 0.4–0.9 fallback and flag the missing baseline.
- The 100-point rubric is not a substitute for this calibration; the automated rubric can give 100
  to a task that is too easy.

## Rules

- Never set `human_signoff` yourself.
- Never recommend `ACCEPT` if any hard gate is false.
- Never calibrate against the independent-solver score when a dsh blind score exists.
- If the seed baseline is missing, flag `SEED_BASELINE_MISSING` and use the absolute fallback; do
  not pretend the seed was 1.0.
- If the blind score is stale (older than the task artifacts), do not ACCEPT; rerun the synthetic
  track.
- If the seed and synthetic models differ, do not ACCEPT; rerun both with the same `--model`.
- If the evidence ledger is thin, recommend `REVISE` even when the evaluator passes.
- Do not modify candidate files; only write the review report and summary.
