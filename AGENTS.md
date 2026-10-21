# AgentHLE Task Factory

Build new AgentHLE-style `business_finance` tasks from the 19 seed tasks. Target: 20 accepted tasks for training data.

## Hard rules

1. **Seed data is read-only.** Never modify anything under
   `~/下载/business_finance_extracted/business_finance`.
2. **Gold-first, evaluator-first.** For every candidate, write the reference solution, gold outputs,
   and evaluator before finalizing the task prompt. The prompt is derived from the gold and contract.
3. **No self-approval.** The author never marks a candidate ACCEPTED. Only the deterministic gates
   plus `ale-reviewer` plus a human sign-off can do that.
4. **Every factual requirement needs evidence.** Record source id, locator, and an exact quote in
   `evidence/evidence.jsonl`. No evidence, no acceptance.
5. **No answer leakage.** The task prompt and `base/input` must not contain the gold answer.
6. **License first.** Every source pack entry needs `license` and `redistributable` fields. Seed data
   must not be redistributed. If a source is not redistributable, mark the candidate internal-only.
   An **internal variant** may reuse a seed source pack with new questions: set
   `source_policy: internal_only`, `internal_only: true`, and `variant_of: <seed-slug>` in
   `candidate.json`. Dedup reports identical source hashes as a warning, not a failure; text
   similarity must still stay below the duplicate threshold.
7. **One candidate at a time per worker.** Do not edit two candidates concurrently.
8. **Local verifiability first.** Prefer pure-Python/file-based task families. Defer GUI-heavy
   tasks (Odoo, Metabase, Flowable, LibreOffice) unless a headless environment is verified.

## Paths

- Factory root: `~/ale-task-factory`
- Skills source: `skills/` (also visible via `.claude/skills` and `.dsh/skills` symlinks)
- Seed root: `~/下载/business_finance_extracted/business_finance`
- Candidates: `candidates/<candidate-id>/`
- State: `state/candidates.jsonl`, `state/decisions.jsonl`
- Profiles: `profiles/seed_profile.json`, `profiles/quotas.json`
- Export: `exports/business_finance_20/`

## Skills

| Skill | Use when |
|---|---|
| `ale-factory` | Orchestrating one candidate end-to-end; reading state; enforcing gates |
| `ale-seed-analyst` | Building/refreshing the seed profile and quota plan |
| `ale-source-scout` | Finding and recording evidence-bearing source packs |
| `ale-task-author` | Authoring a candidate task, gold, and evaluator |
| `ale-corrector` | Repairing a candidate from a verifier report |
| `ale-reviewer` | Rubric review and human sign-off |

`ale-factory` is user-invocable only. The other skills are model-invocable and are dispatched by
`ale-factory`.

## State machine

```
QUEUED -> SCOUTED -> AUTHORED -> VERIFIED -> REVIEWED -> ACCEPTED
             ^          |          |
             |          v          v
             +------ REVISE <-- REJECTED (reason codes)
```

Reason codes: `SCHEMA`, `SOURCE_LICENSE`, `GOLD_RUN_FAIL`, `EVALUATOR_MUTANT_PASS`,
`EVIDENCE_MISMATCH`, `DIFFICULTY_DRIFT`, `LEAKAGE`, `SOLVABILITY_FAIL`, `HUMAN_REJECT`.
Calibration codes: `TOO_EASY`, `TOO_HARD`, `SEED_BASELINE_MISSING`,
`SEED_NOT_BLIND_TESTABLE`, `BLIND_SCORE_MISSING`, `BLIND_SCORE_FALLBACK`,
`BLIND_SCORE_STALE`, `MODEL_MISMATCH`, `MODEL_UNKNOWN`.

Max 2 revise attempts per gate. After that, move the candidate to the human queue and do not retry
automatically.

## Data-analysis tasks

- State the denominator of every rate explicitly in both the brief and the task prompt. For example:
  "every metric rate uses delivered emails (`delivered == '1'`) as the denominator; the full raw
  population is used only for the SRM check." The pilot solver failed this gate by using all
  randomized customers as the denominator.
- State the confidence level, test type, correction method, tolerance, and required report strings
  exactly. The evaluator must be able to check them mechanically.
- Generate synthetic datasets with a fixed seed and record the generation parameters in
  `source_pack/dataset_manifest.txt`. Set `source_policy: synthetic` and `redistributable: true`.
- The gold outputs must be produced by a reference solution, not hand-written.

## Schema wording

- State whether a field is a list or an object. For a single rule in a list field, write "a list
  containing one object", not "one object". The segmentation pilot failed this wording check.
- Use `==` for equality operators in JSON predicates. Human-readable definitions may use `=`.
- The generic mutation test changes the first scalar to `value * 10 + 1000`, so a tolerance-based
  evaluator cannot absorb the mutation. Do not lower tolerances just to make a mutation pass.
- If an independent solve is blocked by an external API balance error, record `API_BALANCE_BLOCKED`
  and leave the candidate in `VERIFIED`. Do not mark it `ACCEPTED` without the solve.

## Blind verification (dsh via Docker)

dsh's sandbox limits writes, not reads. Copying `base/input` to a temp directory is **not** a
blind test; use OS/container isolation.

### Docker/host decoupling

```
HOST (answers, evaluator, state)          CONTAINER (solver only)
  candidates/<id>/base/reference   --X-->  not present
  candidates/<id>/scripts/evaluate.py --X--> not present
  candidates/<id>/base/input        ----->  /workspace/base/input
  TASK.md (taskPrompt + mustDo)     ----->  /workspace/TASK.md
  host dsh package (read-only)      ----->  /opt/dsh
  blind output                      <-----  /workspace/base/output
  evaluator runs on host, reads reference + blind output
```

- The container mounts only `~/ale-blind/<id>` at `/workspace` plus the host dsh package at
  `/opt/dsh:ro`. It never mounts the factory, seed root, `~/.dsh`, or `exports/`.
- `blind_prepare.py` copies only `base/input` and generates `TASK.md`; it never copies
  `base/reference`, `evidence/`, `verify/`, `review/`, `scripts/`, `source_pack/`, `candidate.json`,
  or `task_card.json`.
- `blind_score.py` runs the candidate evaluator on the host; the solver never sees the reference.
- Three images: `ale-blind-dsh` (Node-only), `ale-blind-dsh-py` (Python 3.12 + Node; use
  `--python`), and `ale-blind-dsh-data` (Python + pandas/pyarrow/numpy/scipy/openpyxl; use
  `--data`). The seed scorer runs in `ale-blind-dsh-data`.
- Do not put `DEEPSEEK_API_KEY` in the blind workspace; pass it as an environment variable.
- bwrap is not used on this host (AppArmor userns restriction); Docker is the supported path.
- `/tmp` must use `exec` (Docker's tmpfs default `noexec` breaks native addons).
- If the docker group is not active, run the script under `sg docker -c '...'`.

### Two blind tracks

Both the seed and the synthetic candidate use the same Docker pipeline. Run the seed baseline
first, once per anchor, then the synthetic candidate, then review.

**Track A — seed baseline (once per anchor):**

```bash
python3 -I scripts/blind_prepare.py --seed <anchor>
scripts/blind_docker.sh --seed <anchor> --data [--model ID]
python3 -I scripts/blind_seed_score.py --seed <anchor>
```

- Output: `~/ale-blind/seed-<anchor>/eval/score.json`, top-level `"score"`.
- One baseline per anchor; reuse it for every candidate with that anchor. Rerun only if the seed
  input, the scorer, or the model changes.
- The seed root is mounted read-only only in the scoring container (`/seed:ro`); it is never
  mounted in the solver container.
- Only five seeds have scorer adapters (`sse`, `ab_test`, `segmentation`, `american_option`,
  `basel_bia`). Missing `base/input`, GUI-only seeds, and other seeds are
  `SEED_NOT_BLIND_TESTABLE`; do not invent a baseline.
- A partial baseline (< 1.0) exits 1; read the JSON score.

**Track B — synthetic candidate:**

```bash
python3 -I scripts/blind_prepare.py <id>
scripts/blind_docker.sh <id> [--python|--data] [--model ID]
python3 -I scripts/blind_score.py <id>
```

- Output: `~/ale-blind/<id>/eval/score.json`, top-level `"blind_score"`.
- `review_candidate.py` reads this file first. The independent-solver score is a fallback only and
  is flagged when used.
- Use the same `--model` for both tracks; the score files record `run_meta` (model, image, start
  time). A model mismatch blocks ACCEPT; `--require-model-parity` also blocks when metadata is
  missing.
- A blind score older than the newest task artifact (`task_card.json`, `scripts/evaluate.py`,
  `base/input/**`, `base/reference/**`) is stale; rerun the affected track. The review flags
  `BLIND_SCORE_STALE` and fails the `blind_current` gate.
- `blind.patch.yml` disables web, subagents, workflows, and skills; keep it that way.

## Difficulty and style calibration

- Use the seed's blind score as the **baseline**, not a hard bound. A synthetic `1.0` is acceptable
  when the seed is also ~`1.0` (parity); `1.0` alone does not mean "too easy".
- Relative calibration (default seed margin 0.2):
  - **Too easy**: synthetic score is materially above the seed (e.g. `> seed + 0.2`) while the seed
    is below ~0.9.
  - **Too hard**: synthetic score is near `0.0` or materially below the seed (`< 0.3`). If the seed
    is degenerate (`< 0.2`), do **not** target the seed's 0.0; target a learnable floor, e.g.
    0.3–0.7.
  - **Parity / acceptable**: synthetic is within the margin of the seed, or both are ~1.0.
- If no seed blind baseline exists, use the absolute fallback band **0.4–0.9** and flag the missing
  baseline. Do not force the synthetic score to be `<=` the seed; too hard is not trainable.
- The synthetic side is the **dsh blind score** in `~/ale-blind/<id>/eval/score.json`
  (`blind_score`), not the Claude Code independent-solver score. `review_candidate.py` reads the
  dsh score first; the independent-solver score is a flagged fallback only when the dsh file is
  missing.
- The seed side is `~/ale-blind/seed-<anchor>/eval/score.json` (`score`). It is established once per
  anchor by the seed track in `ale-blind-verifier`; use the same model as the synthetic run.
- `review_candidate.py` is the authoritative calibration implementation. It also reports
  `model_parity` and `blind_score_stale`; use `--dry-run` for audits and
  `--require-model-parity` for strict model checks.
- **Mimic the seed's speaking style**: read the anchor seed's `taskPrompt` and `base/input/*brief*`
  and mirror the section structure, tone, terminology, level of detail, and output-contract
  phrasing. Copy style, not content or answers.
- For classification tasks, prefer partial credit or a threshold that yields a learnable score.
  Avoid 100% all-or-nothing unless the seed is intentionally all-or-nothing and the task is
  calibrated.
- Record the blind score and the calibration decision in `review/review.json` and the pilot note.

## Candidate layout

```
candidates/<id>/
  candidate.json          # id, seed_refs, stratum, status, attempts, scores
  task_card.json
  main.py                 # optional AgentHLE adapter
  base/input/
  base/reference/
  base/software/
  scripts/evaluate.py     # standalone evaluator (required)
  scripts/run_reference.py
  evidence/sources.jsonl
  evidence/evidence.jsonl
  verify/report.json
  review/review.json
~/ale-blind/seed-<anchor>/eval/score.json  # seed baseline (external, not committed)
~/ale-blind/<id>/eval/score.json           # synthetic blind score (external, not committed)
```

## Quality gates (all must pass)

| Gate | Command | Pass |
|---|---|---|
| Schema | `python3 -I scripts/validate_task.py <cand>` | 0 errors |
| Gold run | `python3 -I scripts/run_reference.py <cand>` | evaluator score = 1.0 |
| Mutation | `python3 -I scripts/mutation_test.py <cand>` | 3/3 mutants rejected |
| Evidence | `python3 -I scripts/evidence_check.py <cand>` | 0 missing / 0 mismatch |
| Difficulty | `python3 -I scripts/difficulty.py <cand>` | distance <= calibrated threshold |
| Dedup | `python3 -I scripts/dedup.py <cand>` | no near duplicate |
| Blind calibration | `python3 -I scripts/review_candidate.py <cand>` | `too_easy=false`, `too_hard=false`, `blind_current=true`, model parity not mismatched |
| Solvability | independent solver + human | pass or human override with reason |
| Human | `ale-reviewer` + person | explicit sign-off |

## Commands

```bash
cd ~/ale-task-factory

# Refresh seed profile and quotas
python3 -I scripts/seed_profile.py \
  --seeds "$HOME/下载/business_finance_extracted/business_finance" \
  --out profiles --target 20

# Run all gates for one candidate
python3 -I scripts/validate_task.py candidates/<id>
python3 -I scripts/run_reference.py candidates/<id>
python3 -I scripts/mutation_test.py candidates/<id>
python3 -I scripts/evidence_check.py candidates/<id>
python3 -I scripts/difficulty.py candidates/<id>
python3 -I scripts/dedup.py candidates/<id>

# Interactive (Claude Code primary)
claude

# One-shot (Claude Code primary)
claude -p "读取 state/candidates.jsonl，推进下一个 QUEUED 候选"

# dsh mirror
dsh web
dsh --profile headless "读取 state/candidates.jsonl，推进下一个 QUEUED 候选"
```

## Runtime notes

- Claude Code is the primary runtime. Use subagents for the independent-solver gate and for parallel
  source scouting.
- dsh mirrors the same skills through `.dsh/skills`. dsh agent presets are not used in phase 1.
- dsh is `0.2.0-rc.2`; plugin APIs may change. Skills and Python scripts are the stable layer.
- `pnpm` is not installed. Do not rely on `dsh plugin add`; use project-local skills or absolute-path
  patches.

## Output language

Task artifacts follow the seed language conventions: `task_card.json` fields in English, task prompts
may be English or Chinese matching the target subdomain. Evidence quotes must be verbatim in the
source language.
