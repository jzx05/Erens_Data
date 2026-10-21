---
name: ale-factory
description: Orchestrates one AgentHLE candidate through scout, author, verify, correct, and review gates. Use when the user asks to run the task factory, advance the candidate queue, or produce the next business_finance task.
disable-model-invocation: true
user-invocable: true
---

# ALE Task Factory

Orchestrate exactly one candidate at a time. The deterministic scripts are the authority; you are the
dispatcher and repair coordinator, not the judge.

## Read first

1. `AGENTS.md` for hard rules and paths.
2. `state/candidates.jsonl` for the queue.
3. `profiles/seed_profile.json` and `profiles/quotas.json`.
4. `state/decisions.jsonl` for prior decisions.

## One-candidate workflow

1. **Pick the candidate.**
   Run `python3 -I scripts/state.py next`. If no candidate is `QUEUED`, report the final summary and stop.
2. **Ensure profiles exist.**
   If `profiles/seed_profile.json` or `profiles/quotas.json` is missing or older than the seed root,
   invoke the `ale-seed-analyst` skill. Do not hand-edit the profile.
3. **Scout sources.**
   Invoke `ale-source-scout` with the candidate id, stratum, seed anchor, and target difficulty.
   It must produce `candidates/<id>/evidence/sources.jsonl` and a source pack.
4. **Author the candidate.**
   Invoke `ale-task-author`. It must produce the full candidate layout, including
   `scripts/evaluate.py`, `base/reference/`, `task_card.json`, and `evidence/evidence.jsonl`.
5. **Run the deterministic gates.**
   ```bash
   python3 -I scripts/validate_task.py candidates/<id>
   python3 -I scripts/run_reference.py candidates/<id>
   python3 -I scripts/mutation_test.py candidates/<id>
   python3 -I scripts/evidence_check.py candidates/<id>
   python3 -I scripts/difficulty.py candidates/<id>
   python3 -I scripts/dedup.py candidates/<id>
   ```
   Record every report under `candidates/<id>/verify/`.
6. **Repair on failure.**
   If any gate fails, invoke `ale-corrector` with the failing report. Re-run all gates after each
   repair. Stop after 2 repair attempts and move the candidate to the human queue.
7. **Independent solve.**
   Dispatch a fresh-context solver with access only to the candidate's `base/input`. It must not see
   `base/reference`, `evidence/`, or the seed reference answers. Save its output under
   `candidates/<id>/verify/independent_solver/` and score it with `scripts/evaluate.py`.
   If it fails, record `SOLVABILITY_FAIL` and send the candidate to `ale-corrector`.
8. **Blind calibration (seed + synthetic).**
   Run the `ale-blind-verifier` skill. Do the two tracks in order:
   1. **Seed baseline (once per anchor).** Read `candidate.json["seed_anchor"]`. If
      `~/ale-blind/seed-<anchor>/eval/score.json` is missing (or its model/image differs from the
      run you are about to do, or the score is older than the seed's task files), run Track A:
      `blind_prepare.py --seed <anchor>` -> `blind_docker.sh --seed <anchor> --data [--model ID]`
      -> `blind_seed_score.py --seed <anchor>`. Reuse the baseline for every candidate with that
      anchor; do not rerun per candidate.
   2. **Synthetic blind run.** Run Track B: `blind_prepare.py <id>` -> `blind_docker.sh <id>
      [--python|--data] [--model ID]` -> `blind_score.py <id>`. Use the same `--model` as the seed
      baseline. If the score is older than the candidate's task files, rerun; stale scores are
      flagged `BLIND_SCORE_STALE`.
   3. **Review.** Run `python3 -I scripts/review_candidate.py candidates/<id>`. It reads the dsh
      synthetic score from `~/ale-blind/<id>/eval/score.json["blind_score"]` and the seed score
      from `~/ale-blind/seed-<anchor>/eval/score.json["score"]`, and reports `seed_blind_score`,
      `calibration_mode`, `too_easy`, `too_hard`, `model_parity`, and `blind_score_stale`. Use
      `--dry-run` for audits and `--require-model-parity` for strict model checks.
   Calibration: parity within 0.2 of the seed or both ~1.0; too easy = synthetic > seed + 0.2 while
   seed < 0.9; too hard = synthetic < 0.3 or far below a non-degenerate seed; degenerate seed
   (< 0.2) -> target 0.3–0.7, not 0.0; no seed baseline -> absolute 0.4–0.9 fallback flagged
   `SEED_BASELINE_MISSING`. Send too-easy/too-hard candidates to `ale-corrector` with `TOO_EASY` /
   `TOO_HARD`. Record both scores, the model, and the calibration decision.
9. **Review.**
   Invoke `ale-reviewer`. It writes `candidates/<id>/review/review.json` with scores and a
   recommendation. Never set `human_signoff` yourself.
10. **Update state.**
   ```bash
   python3 -I scripts/state.py set-status <id> REVIEWED
   python3 -I scripts/state.py append-decision <id> REVIEWED <reason-codes...>
   ```
   Only a human may move a candidate to `ACCEPTED`. When the user explicitly signs off, run:
   ```bash
   python3 -I scripts/state.py set-status <id> ACCEPTED
   python3 -I scripts/state.py append-decision <id> ACCEPTED human-signoff
   ```

## Hard rules

- Never modify the seed root.
- Never change `base/reference` just to make a gate pass. Fix the actual defect.
- Never mark `ACCEPTED` without an explicit human sign-off.
- Never put gold answers in `task_card.json`, `base/input`, or any agent-visible file.
- Calibrate against the dsh synthetic blind score, not the Claude Code independent-solver score.
  The independent score is only a fallback when the dsh blind file is missing, and `review_candidate.py`
  flags that fallback.
- Never fake a seed baseline. If the anchor is not blind-testable, record
  `SEED_NOT_BLIND_TESTABLE` and use the absolute fallback.
- A blind score older than the newest task artifact is stale; rerun before ACCEPT.
- The seed and synthetic tracks must use the same `--model`; a mismatch blocks ACCEPT.
- One candidate at a time. Do not parallelize authoring.
- If a source is not redistributable, mark the candidate `internal_only: true` in `candidate.json`.

## Output to the user

After each candidate, report:

- candidate id, stratum, seed anchor, task family
- gate results: schema / gold / mutation / evidence / difficulty / dedup / solvability
- review score and decision
- exact next action (repair, human review, or next candidate)

## References

- `AGENTS.md` for the full gate table and reason codes.
- `skills/ale-task-author/SKILL.md` for the artifact contract.
- `templates/task/document-forensics/` and `templates/task/data-analysis/`.
