---
name: ale-blind-verifier
description: Runs dsh as a blind independent solver on a seed task and on a synthetic candidate, then scores both on the host. Use when the user asks to verify generated tasks with dsh without exposing base/reference.
disable-model-invocation: true
user-invocable: true
---

# Blind dsh Verifier

Run dsh in a Docker container that contains only the blind workspace. The candidate's
`base/reference`, `evidence/`, `verify/`, `review/`, seed data, and the rest of the factory are not
mounted as solver inputs and therefore cannot be read.

Blind verification has **two tracks**: a seed baseline, then a synthetic candidate. Run the seed
track once per anchor and reuse it; do not rerun it for every candidate.

## Track A — Seed baseline (once per anchor)

1. **Resolve the anchor.** Read `candidate.json["seed_anchor"]` (or the queue item printed by
   `scripts/state.py next`). Use the exact slug; the blind workspace is
   `~/ale-blind/seed-<anchor>`.

2. **Reuse an existing baseline when possible.**
   ```bash
   test -f ~/ale-blind/seed-<anchor>/eval/score.json && \
     python3 -I -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["score"], d.get("run_meta"))' \
     ~/ale-blind/seed-<anchor>/eval/score.json
   ```
   Reuse it only when `run_meta.model` and `run_meta.image` match the model/image you will use for
   the synthetic run, and the score is newer than the seed's task files (`task_card.json`,
   `scripts/`, `base/input`, `base/reference`). If the metadata is missing/different or the score is
   stale, rerun the baseline.

3. **Prepare, solve, score.**
   ```bash
   cd ~/ale-task-factory
   python3 -I scripts/blind_prepare.py --seed <anchor>

   # First time, or when the data image is missing:
   scripts/blind_docker.sh --seed <anchor> --data --build

   # Same model as the synthetic run:
   scripts/blind_docker.sh --seed <anchor> --data --model <model-id> --preflight
   python3 -I scripts/blind_seed_score.py --seed <anchor>
   ```
   - `--data` is required: `blind_seed_score.py` runs the seed's own scorer in
     `ale-blind-dsh-data` (Python 3.12 + pandas/pyarrow/numpy/scipy/openpyxl).
   - Use `--python` for the solver only if the seed needs Python stdlib/SQLite but not data
     libraries; the scoring container still uses the data image.
   - The solver container mounts only `~/ale-blind/seed-<anchor>`. The scoring container mounts the
     seed root read-only at `/seed` and the blind output read-only at `/blind`, with
     `--network none`.
   - Docker group inactive: prefix with `sg docker -c '<command>'`, or set
     `DOCKER_CMD='sudo docker'`.

4. **Record the result.** Output:
   `~/ale-blind/seed-<anchor>/eval/score.json`, top-level key `"score"`.
   A score below 1.0 exits 1. That is normal for a partial baseline; read the JSON, not the exit
   code.

5. **Not blind-testable seeds.** A seed cannot produce a baseline when:
   - it has no `base/input` (e.g. `taxform_4_1`),
   - `blind_seed_score.py` has no scorer adapter (only the five seeds below are supported),
   - it needs a GUI (Metabase, Odoo, Flowable, LibreOffice).

   Supported baselines:

   | Seed slug | Score |
   |---|---|
   | `sse_northbound_programmatic_trading_01` | 0.667 |
   | `digital_marketing_ab_test_analysis_1` | 1.0 |
   | `digital_marketing_audience_segmentation_1` | 0.9417 |
   | `american_option_pricing_ls` | 1.0 |
   | `basel_operational_risk_bia_cn` | 0.0 |

   For any other seed, record `SEED_NOT_BLIND_TESTABLE` (or `SEED_BASELINE_MISSING` if a run was
   attempted but no score was produced) and use the absolute 0.4–0.9 fallback in review. Do not
   invent a seed score.

## Track B — Synthetic candidate

1. **Prepare the blind workspace.**
   ```bash
   cd ~/ale-task-factory
   python3 -I scripts/blind_prepare.py <candidate-id>
   ```
   This copies only `base/input` (and `base/software` if present), writes `TASK.md` from
   `taskPrompt` + `agentMustDo`, and creates an empty `base/output/`.

2. **Build the image once.**
   ```bash
   scripts/blind_docker.sh <candidate-id> --build --preflight
   ```
   Images:
   - `ale-blind-dsh`: Node-only (default)
   - `ale-blind-dsh-py`: Python 3.12 + Node (`--python`)
   - `ale-blind-dsh-data`: Python + pandas/pyarrow/numpy/scipy/openpyxl (`--data`)

   The host dsh package is mounted read-only at `/opt/dsh` at runtime, so no npm install/native
   build happens in the image.

3. **Run the blind solve.**
   ```bash
   scripts/blind_docker.sh <candidate-id> --model <same-model-as-seed>
   # Python/SQLite task:
   scripts/blind_docker.sh <candidate-id> --python --model <same-model-as-seed>
   # Data-analysis task:
   scripts/blind_docker.sh <candidate-id> --data --model <same-model-as-seed>
   ```
   The container mounts only `~/ale-blind/<candidate-id>` at `/workspace` and the host dsh package
   read-only at `/opt/dsh`.

4. **Score on the host.**
   ```bash
   python3 -I scripts/blind_score.py <candidate-id>
   ```
   Output: `~/ale-blind/<candidate-id>/eval/score.json`, top-level key `"blind_score"`.
   A score below the threshold exits 1; read the JSON. If the score file is older than the
   candidate's task files, rerun the synthetic track; `review_candidate.py` flags
   `BLIND_SCORE_STALE`.

## Order and calibration

1. Seed baseline (or reuse) -> synthetic blind run -> `review_candidate.py`.
2. `review_candidate.py` resolves the synthetic side first from
   `~/ale-blind/<id>/eval/score.json["blind_score"]`. If that file is missing, it falls back to
   `candidates/<id>/verify/independent_solver/score.json["score"]` and flags the fallback. The seed
   side comes from `~/ale-blind/seed-<anchor>/eval/score.json["score"]`; a `--seed-score` CLI value
   overrides it.
3. Calibration (see `ale-reviewer`):
   - **Parity**: synthetic within 0.2 of the seed, or both ~1.0. A synthetic 1.0 with a seed ~1.0
     is not too easy.
   - **Too easy**: synthetic > seed + 0.2 while the seed < 0.9.
   - **Too hard**: synthetic < 0.3, or far below a non-degenerate seed.
   - **Degenerate seed** (< 0.2): target 0.3–0.7, not the seed's 0.0.
   - **No seed baseline**: absolute 0.4–0.9 fallback; flag `SEED_BASELINE_MISSING`.
4. Use the same `--model` for both tracks. If the model changes, rerun both; the review is not
   comparable across models. `review_candidate.py` reports `model_parity` (`match` / `mismatch` /
   `unknown`) and blocks ACCEPT on a mismatch; `--require-model-parity` also blocks on unknown.
5. If a score is older than the newest task artifact (`task_card.json`, `scripts/evaluate.py`,
   `base/input/**`, `base/reference/**`), it is stale; rerun the affected track. The review flags
   `BLIND_SCORE_STALE` and fails the `blind_current` gate.

## Hard rules

- Never copy `base/reference`, `evidence/`, `verify/`, `review/`, `scripts/`, `source_pack/`,
  `candidate.json`, or `task_card.json` into the blind workspace.
- Never use `exports/` as the blind source; exports deliberately contain reference and verify
  artifacts.
- The evaluator runs on the host, not in the container. The seed scorer runs in a separate
  `--network none` data container; the seed root is never mounted in the solver container.
- Do not mark a candidate `ACCEPTED` from a blind score alone; the normal review and human sign-off
  still apply.
- Do not put `DEEPSEEK_API_KEY` in the blind workspace. It is passed as an environment variable.
- Do not use the independent-solver score for calibration when a dsh blind score exists; it is a
  fallback only and is flagged in the review.
- The blind profile disables `tool-web`, subagents, workflows, and skills; keep it that way.
- The seed root is read-only and must never be modified.

## Troubleshooting

- **Docker permission denied**: run `newgrp docker`, or use
  `DOCKER_CMD='sudo docker'` after `sudo -v`. If the script runs under `sg docker`, pass the whole
  command to `sg docker -c '...'`.
- **Image pull timeout**: the Docker daemon needs the host proxy in
  `/etc/systemd/system/docker.service.d/http-proxy.conf`; restart Docker.
- **HTTP 402 / balance**: use `--model deepseek-v4-pro`, or top up the DeepSeek key. If you change
  the model for one track, rerun the other track with the same model.
- **Profile init error**: the first run uses `--from-default-profile headless` with a custom profile
  name (`blind`); later runs omit it.
- **Tool failure**: the image was built with native install scripts (`koffi`, `node-pty`,
  `dsh-subprocess-local`). Rebuild if bash tools fail.
- **Missing data image**: build it with
  `scripts/blind_docker.sh --seed <anchor> --data --build`, or
  `docker build -t ale-blind-dsh-data docker/blind-dsh-data`.
- **No seed scorer adapter**: the seed is not blind-testable with the current adapters; record
  `SEED_NOT_BLIND_TESTABLE` and use the absolute fallback.
- **Partial score exits 1**: expected for any score below 1.0; use the JSON score.
- **`BLIND_SCORE_STALE`**: the score is older than the task artifacts; rerun the affected track.
- **`MODEL_MISMATCH`**: the seed and synthetic runs used different models; rerun both with the same
  `--model`. `MODEL_UNKNOWN` means the score predates `run_meta`; rerun or use
  `--require-model-parity` for a strict audit.
- **Custom roots**: pass `--blind-root` to `blind_prepare.py`, `blind_docker.sh` (via `BLIND_ROOT`),
  `blind_score.py`, and `blind_seed_score.py`; pass `--seed-root` or set `SEED_ROOT` for seed
  commands. The review uses `--blind-root`/`--seed-blind-root`.

## Output

Report:

- seed baseline score, source path, and whether it was reused or rerun
- synthetic blind score, source path, and whether the dsh file or the independent-solver fallback
  was used
- model/image metadata from both runs
- output files produced
- any failed evaluator checks
- whether the leakage scan was clean
- the calibration decision and next action (`ACCEPT`, `REVISE` with `TOO_EASY`/`TOO_HARD`, or
  `SEED_BASELINE_MISSING`)
