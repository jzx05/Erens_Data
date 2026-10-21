---
name: ale-corrector
description: Repairs a candidate from a verifier report, using its reason codes to fix only the failing parts. Use after a schema, gold-run, mutation, evidence, difficulty, dedup, or solvability failure.
---

# Corrector

Repair the defect, not the gate. Never weaken an evaluator or delete a hard check to make a candidate
pass.

## Inputs

- `candidates/<id>/verify/report.json` (or the specific failing report)
- Candidate files
- `state/candidates.jsonl` attempts count
- `~/ale-blind/<id>/eval/score.json` and `~/ale-blind/seed-<anchor>/eval/score.json` for the
  calibration reason codes

## Reason-code playbook

| Code | Fix |
|---|---|
| `SCHEMA` | Add missing files/fields; align `task_card.json` with the output contract |
| `SOURCE_LICENSE` | Replace the source, or mark `redistributable: false` and `internal_only: true` |
| `GOLD_RUN_FAIL` | Fix the reference solution or gold outputs; make the evaluator deterministic |
| `EVALUATOR_MUTANT_PASS` | Tighten the evaluator so wrong answers, missing fields, and wrong citations fail |
| `EVIDENCE_MISMATCH` | Correct the quote/locator; if the claim is unsupported, revise the task |
| `DIFFICULTY_DRIFT` | Adjust inputs/output complexity toward the anchor seed, or pick a closer anchor |
| `TOO_EASY` | Compare with the seed baseline first: if the seed is also ~1.0, parity is acceptable and no change is needed. Otherwise add one hard-but-unambiguous requirement, more events, or a stricter but fair contract. If the seed is degenerate (< 0.2), target 0.3–0.7, not the seed's 0.0. Do not add ambiguity |
| `TOO_HARD` | Clarify rules, add worked examples, reduce event count/complexity, or raise a threshold that is accidentally all-or-nothing. Target at least 0.3; if the seed is degenerate, 0.3–0.7 is the target |
| `SEED_BASELINE_MISSING` | Build the anchor's seed baseline with the Track A commands if it is blind-testable. If it is not (missing `base/input`, no scorer adapter, GUI-only), record `SEED_NOT_BLIND_TESTABLE` and use the absolute 0.4–0.9 fallback; do not invent a seed score |
| `BLIND_SCORE_MISSING` | Run the synthetic Track B (`blind_prepare.py` -> `blind_docker.sh` -> `blind_score.py`). Do not substitute the Claude Code independent-solver score for calibration |
| `BLIND_SCORE_STALE` | The blind score predates the task artifacts; rerun Track B, then review again |
| `MODEL_MISMATCH` | Rerun the seed baseline and the synthetic track with the same `--model`; do not compare scores across models |
| `LEAKAGE` | Remove the answer from the prompt/inputs; redesign the question |
| `SOLVABILITY_FAIL` | Clarify the contract or add necessary input; do not leak the answer |

## Steps

1. Read the report and list only the failing gates.
2. Make the minimal change that addresses the root cause.
3. If the evaluator was wrong, fix it and re-run the gold and mutation gates.
4. Re-run every gate:
   ```bash
   python3 -I scripts/validate_task.py candidates/<id>
   python3 -I scripts/run_reference.py candidates/<id>
   python3 -I scripts/mutation_test.py candidates/<id>
   python3 -I scripts/evidence_check.py candidates/<id>
   python3 -I scripts/difficulty.py candidates/<id>
   python3 -I scripts/dedup.py candidates/<id>
   ```
5. Append a decision record with the reason codes and the fix summary.
6. After 2 failed repair attempts, stop and move the candidate to the human queue.

## Rules

- Do not alter `base/reference` to match a buggy submitted answer.
- Do not relax a hard check without a written justification in `verify/report.json`.
- Do not edit the seed root.
- Keep the task family and core scenario stable; a repair is not a rewrite unless the report says the
  scenario itself is unsalvageable.
