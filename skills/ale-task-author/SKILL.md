---
name: ale-task-author
description: Authors a complete AgentHLE-style candidate task from a source pack, including inputs, gold reference, standalone evaluator, task card, and evidence ledger. Use after source scouting and before verification.
---

# Task Author

Write a self-contained candidate. The gold and evaluator come first; the task prompt is derived from
them. Never copy a seed task wholesale; derive a new scenario from the source pack.

## Inputs

- `candidates/<id>/candidate.json`
- `candidates/<id>/evidence/sources.jsonl`
- `candidates/<id>/source_pack/`
- Seed anchor and nearest seeds from `profiles/seed_profile.json`
- Template: `templates/task/document-forensics/` or `templates/task/data-analysis/`

## Outputs

```
candidates/<id>/
  candidate.json          # status AUTHORED; task_family; difficulty_target; source_policy
  task_card.json
  base/input/             # agent-visible only
  base/reference/         # evaluator-controlled gold
  base/software/
  scripts/evaluate.py     # standalone, deterministic
  scripts/run_reference.py
  evidence/evidence.jsonl
```

## Authoring order

1. **Choose the task family.** Document-forensics: closed-book extraction from staged sources with
   exact citations. Data-analysis: a small dataset plus a precise output contract and a deterministic
   checker. Prefer the family that fits the source pack and is locally verifiable.
2. **Write the gold first.** Create `base/reference/` with the canonical answer key or gold output
   files, plus `verification_contract.json` describing hard checks and tolerances.
3. **Write the evaluator.** `scripts/evaluate.py` must:
   - take `--candidate-root` (default: its own task root),
   - read `base/reference/` and the submission under `base/output/`,
   - print one JSON object with `score` in `[0, 1]`, per-item breakdown, and `notes`,
   - be deterministic, dependency-light, and runnable with `python3 -I`,
   - reject wrong answers, missing fields, and unsupported citations.
4. **Write `scripts/run_reference.py`.** Copy the gold into a temporary `base/output/`, run the
   evaluator, and exit non-zero unless the score is 1.0.
5. **Write the inputs.** `base/input/` contains only agent-visible material: brief, question set or
   dataset, output contract, and source manifest. The manifest maps citation aliases to source files.
6. **Write `task_card.json`.** Mirror the seed schema:
   `taskId`, `title`, `summary`, `category`, `software`, `taskPrompt`, `agentMustDo`, `inputFiles`,
   `referenceFiles`, `evaluation`, `vm`, `taxonomy`. The prompt must state:
   - what is visible under `base/input`,
   - what to write under `base/output`,
   - the exact output contract,
   - whether the task is closed-book.
7. **Write evidence.** One record per factual requirement:
   ```json
   {"claim_id":"q1","source_id":"src-001","locator":"section 2.3","exact_quote":"...","used_in":["task_card.taskPrompt","base/reference/answer_key.json"]}
   ```
   Quotes must be verbatim and findable in the source pack. No evidence, no claim.
8. **Update state.**
   ```bash
   python3 -I scripts/state.py set-status <id> AUTHORED
   ```

## Quality rules

- Every required output must be unambiguous and testable.
- For closed-book label questions, define `Yes` / `No` / `Unknown` explicitly in the task brief.
  In particular, `Unknown` means the source does not provide the requested value; it is not a
  synonym for `No`. This was the defect found in the SSE seed pilot.
- Require each `evidence_snippet` to be one contiguous excerpt from one cited source. Do not let a
  solver concatenate non-adjacent clauses or articles; put that reasoning in `answer_text`. This was
  the defect found in the first independent solve of `bf-compliance-02`.
- For data-analysis tasks, state the denominator of every rate explicitly in the brief and the task
  prompt. Also state the CI level, test type, correction method, tolerance, and the exact strings the
  report must contain. This was the defect found in the first independent solve of
  `bf-sales-marketing-01` (it used all randomized customers instead of delivered emails).
- **Mimic the anchor seed's speaking style.** Read the seed `taskPrompt` and its input brief; mirror
  the section headings, tone, terminology, level of detail, and output-contract phrasing. Copy the
  style, never the content or answers.
- **Calibrate relative to the seed.** The seed's blind score is the baseline, not a hard bound. A
  synthetic 1.0 is acceptable when the seed is also ~1.0 (parity). Too easy = synthetic >
  seed + 0.2 while seed < 0.9. Too hard = synthetic < 0.3 or far below the seed; if the seed is
  degenerate (< 0.2), target a learnable floor (0.3–0.7), not the seed's 0.0. If no seed baseline
  exists, use the absolute 0.4–0.9 fallback and flag it. Both scores come from the dsh blind tracks
  in `ale-blind-verifier`; the Claude Code independent solve is not the calibration score.
- For classification tasks, prefer partial credit or a threshold that yields a learnable score;
  avoid 100% all-or-nothing unless the seed is intentionally all-or-nothing and calibrated.
- For synthetic datasets, use a fixed random seed, record the generation parameters in
  `source_pack/dataset_manifest.txt`, and set `source_policy: synthetic` and
  `redistributable: true`. The gold outputs must be produced by a reference solution.
- Gold must be reproducible from the inputs by a competent solver.
- No gold answer or hidden hint in `task_card.json` or `base/input/`.
- No hidden dependency on the seed workspace, the internet, or an unstated package.
- Keep inputs small enough to bundle; prefer UTF-8 text mirrors for documents.
- Match the anchor seed's difficulty features: software count, input count/modalities, output
  contract complexity, and reasoning steps.
- If a source is not redistributable, mark the candidate internal-only.

## Templates

- `templates/task/document-forensics/` — task brief, question set, output contract, document manifest,
  answer key, evaluator skeleton.
- `templates/task/data-analysis/` — brief, dataset placeholder, output contract, gold outputs,
  evaluator skeleton.
