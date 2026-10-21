# Eren's Data — Full Usage Manual

This manual covers the complete workflow: install, seed profiling, candidate authoring, deterministic
gates, blind verification of the seed and the synthetic task, review, and safe publishing.

## 1. Concepts

| Term | Meaning |
|---|---|
| Seed | An original AgentHLE `business_finance` task. Read-only; never redistributed. |
| Anchor | The seed a candidate is derived from: `candidate.json["seed_anchor"]`. |
| Candidate | A synthetic task generated from a seed's domain and capability profile. |
| Gold | The reference answer and evaluator-controlled outputs in `base/reference/`. |
| Blind score | A score produced by dsh solving with only `base/input` visible. |
| Seed baseline | The blind score of the anchor seed itself; established once per anchor. |
| Independent solve | A separate Claude Code solve, used only as a fallback when the dsh blind file is missing. |

Difficulty is always interpreted relative to the seed baseline. A synthetic `1.0` is parity when
the seed is also ~`1.0`; it is not automatically "too easy".

## 2. Prerequisites

### Python

Python 3.12 is expected. Run scripts with `python3 -I` so the current directory cannot inject
modules.

### Node and dsh

```bash
node --version          # 24.x
npm install -g @deepseek-ai/dsh@0.2.0-rc.2
dsh --version
```

The blind runner mounts the host dsh package read-only into the container, so the image does not
need to install dsh.

### Docker

```bash
sudo apt install -y docker.io
sudo usermod -aG docker "$USER"
# log out and back in, or use DOCKER_CMD='sudo docker'
docker info
```

If the current shell does not have the group yet:

```bash
sg docker -c 'scripts/blind_docker.sh <id> --build --preflight'
```

### Proxy

If image pulls or the DeepSeek API need the host proxy, configure the Docker daemon:

```ini
# /etc/systemd/system/docker.service.d/http-proxy.conf
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1,::1"
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### API key

`blind_docker.sh` reads `DEEPSEEK_API_KEY` from the environment, or from
`~/.dsh/.credentials.yaml` without printing it. Never put the key in the repository or in a blind
workspace.

## 3. Repository setup

```bash
git clone <your-repo> erens-data
cd erens-data
mkdir -p .claude .dsh
ln -sfn ../skills .claude/skills
ln -sfn ../skills .dsh/skills
```

The seed root is external and read-only:

```bash
export SEED_ROOT="$HOME/下载/business_finance_extracted/business_finance"
test -d "$SEED_ROOT"
```

## 4. Seed profile and quota plan

```bash
python3 -I scripts/seed_profile.py \
  --seeds "$SEED_ROOT" \
  --out profiles \
  --target 20
```

Outputs:

- `profiles/seed_profile.json` — structural profiles for the 19 seeds.
- `profiles/quotas.json` — stratum quotas for the target dataset.
- `state/candidates.jsonl` — the queue consumed by `state.py` (override with `--queue-out`).

Inspect the queue:

```bash
python3 -I scripts/state.py summary
python3 -I scripts/state.py next
python3 -I scripts/state.py get <id>
```

## 5. Candidate lifecycle

```
QUEUED -> SCOUTED -> AUTHORED -> VERIFIED -> REVIEWED -> ACCEPTED
             ^          |          |
             |          v          v
             +------ REVISE <-- REJECTED
```

Only a human may move a candidate to `ACCEPTED`.

### 5.1 Scout sources

Use the `ale-source-scout` skill. It writes:

```
candidates/<id>/evidence/sources.jsonl
candidates/<id>/source_pack/
```

Every source entry needs `license` and `redistributable`. Seed-derived content that cannot be
redistributed must be marked `internal_only: true`.

### 5.2 Author the task

Use the `ale-task-author` skill. Required layout:

```
candidates/<id>/
  candidate.json
  task_card.json
  base/input/                 # agent-visible only
  base/reference/             # gold, evaluator-controlled
  base/software/
  scripts/evaluate.py
  scripts/run_reference.py
  evidence/evidence.jsonl
```

Authoring order:

1. Write the gold.
2. Write the evaluator.
3. Write the inputs.
4. Derive `taskPrompt` from the gold and contract.
5. Write the evidence ledger (verbatim quote + locator for every factual requirement).

Style: mimic the anchor seed's section headings, tone, terminology, and output-contract phrasing.
Copy style, never content or answers.

### 5.3 Run the deterministic gates

```bash
python3 -I scripts/validate_task.py candidates/<id>
python3 -I scripts/run_reference.py candidates/<id>
python3 -I scripts/mutation_test.py candidates/<id>
python3 -I scripts/evidence_check.py candidates/<id>
python3 -I scripts/difficulty.py candidates/<id>
python3 -I scripts/dedup.py candidates/<id>
```

Expected: schema 0 errors; gold score 1.0; 3/3 mutants rejected; evidence 0 missing / 0 mismatch;
difficulty within the calibrated threshold; no near duplicate.

Reports are written under `candidates/<id>/verify/`.

### 5.4 Independent solve (optional fallback)

Dispatch a fresh-context solver with only `base/input`. Save its output under
`candidates/<id>/verify/independent_solver/` and score it with `scripts/evaluate.py`.

This score is **not** the calibration score when a dsh blind score exists. It is a fallback only.

## 6. Blind verification

Blind verification has two tracks. The seed baseline is established once per anchor; the synthetic
candidate is run for each candidate. Use the same `--model` for both.

### 6.1 Why Docker

dsh's sandbox limits file writes, not reads. Copying `base/input` to a temp directory is not a blind
test. The Docker container contains only the blind workspace and a read-only dsh package; the host
factory and references are not mounted.

### 6.2 Track A — seed baseline

Resolve the anchor from `candidate.json["seed_anchor"]`. The seed root comes from `SEED_ROOT`
(default: `~/下载/business_finance_extracted/business_finance`); pass `--seed-root` to override.

```bash
cd ~/ale-task-factory
export SEED_ROOT="${SEED_ROOT:-$HOME/下载/business_finance_extracted/business_finance}"
export BLIND_ROOT="${BLIND_ROOT:-$HOME/ale-blind}"

python3 -I scripts/blind_prepare.py --seed <anchor> --seed-root "$SEED_ROOT" \
  --blind-root "$BLIND_ROOT"

# First time, or when the data image is missing:
scripts/blind_docker.sh --seed <anchor> --data --build

scripts/blind_docker.sh --seed <anchor> --data --preflight
scripts/blind_docker.sh --seed <anchor> --data
python3 -I scripts/blind_seed_score.py --seed <anchor> --seed-root "$SEED_ROOT" \
  --blind-root "$BLIND_ROOT"
```

Artifacts:

```
~/ale-blind/seed-<anchor>/
  TASK.md
  base/input/          # solver-visible
  base/output/         # solver output
  run/events.ndjson
  run/model.txt
  run/image.txt
  eval/score.json      # top-level "score"
```

Rules:

- `--data` is required for the seed scorer (`ale-blind-dsh-data`).
- The solver container sees only `~/ale-blind/seed-<anchor>`.
- The scoring container mounts the seed root read-only (`/seed:ro`) and the blind output read-only
  (`/blind:ro`), with `--network none`.
- Reuse the baseline for every candidate with the same anchor. Rerun only if the seed input, scorer,
  image, or model changes.
- A partial score exits 1; read `eval/score.json["score"]`.

Supported seed adapters:

| Seed | Baseline |
|---|---|
| `sse_northbound_programmatic_trading_01` | 0.667 |
| `digital_marketing_ab_test_analysis_1` | 1.0 |
| `digital_marketing_audience_segmentation_1` | 0.9417 |
| `american_option_pricing_ls` | 1.0 |
| `basel_operational_risk_bia_cn` | 0.0 |

Other seeds are `SEED_NOT_BLIND_TESTABLE` (no `base/input`, no adapter, or GUI-only). Do not invent
a baseline; use the absolute 0.4–0.9 fallback and record the reason.

### 6.3 Track B — synthetic candidate

```bash
python3 -I scripts/blind_prepare.py <candidate-id> --blind-root "$BLIND_ROOT"
scripts/blind_docker.sh <candidate-id> --build --preflight
scripts/blind_docker.sh <candidate-id> --data        # or --python
python3 -I scripts/blind_score.py <candidate-id> --blind-root "$BLIND_ROOT"
```

Artifacts:

```
~/ale-blind/<candidate-id>/
  TASK.md
  base/input/
  base/output/
  run/events.ndjson
  run/model.txt
  run/image.txt
  eval/score.json      # top-level "blind_score"
```

Image selection:

| Task | Flag | Image |
|---|---|---|
| Text / Node | default | `ale-blind-dsh` |
| Python / SQLite | `--python` | `ale-blind-dsh-py` |
| Data analysis (pandas, scipy, openpyxl) | `--data` | `ale-blind-dsh-data` |

### 6.4 Review and calibration

```bash
python3 -I scripts/review_candidate.py candidates/<id>
```

Resolution order:

1. Synthetic: `~/ale-blind/<id>/eval/score.json["blind_score"]`.
2. Fallback: `candidates/<id>/verify/independent_solver/score.json["score"]` (flagged).
3. Seed: `~/ale-blind/seed-<anchor>/eval/score.json["score"]`.
4. CLI override: `--seed-score`, `--solver-score`.

Calibration:

| Situation | Verdict |
|---|---|
| Synthetic within 0.2 of the seed, or both ~1.0 | parity; acceptable |
| Synthetic > seed + 0.2 while seed < 0.9 | too easy; `TOO_EASY` |
| Synthetic < 0.3, or far below a non-degenerate seed | too hard; `TOO_HARD` |
| Seed < 0.2 (degenerate) | target 0.3–0.7, not 0.0 |
| No seed baseline | absolute 0.4–0.9; `SEED_BASELINE_MISSING` |

The review writes `candidates/<id>/review/review.json` with `gate_details.blind_score`,
`seed_blind_score`, `calibration_mode`, `too_easy`, `too_hard`, `model_parity`,
`blind_score_stale`, and a recommendation. It never sets `human_signoff`.

- `--dry-run` prints the report without rewriting `review.json`.
- `--require-model-parity` blocks ACCEPT when `run_meta.model` is missing or the two tracks used
  different models.
- A blind score older than the newest task artifact is flagged `BLIND_SCORE_STALE` and fails the
  `blind_current` gate; rerun the synthetic track.
- Exit code is 0 for an `ACCEPT` recommendation and 1 for `REVISE`/`REJECT`; it is a
  recommendation, not a script failure. Blind score scripts also exit 1 for partial scores.

### 6.5 Human sign-off

After the reviewer recommends `ACCEPT`, a human explicitly signs off:

```bash
python3 -I scripts/state.py set-status <id> ACCEPTED
python3 -I scripts/state.py append-decision <id> ACCEPTED human-signoff
```

Never mark `ACCEPTED` from a blind score alone.

## 7. Docker images

Build order:

```bash
docker build -t ale-blind-dsh docker/blind-dsh
docker build -t ale-blind-dsh-py docker/blind-dsh-py
docker build -t ale-blind-dsh-data docker/blind-dsh-data
```

`ale-blind-dsh-data` extends `ale-blind-dsh-py`, so build the Python image first. The host dsh
package is mounted at runtime; the images contain Node/Python and the data libraries only.

Details and proxy notes: [`docker/README.md`](../docker/README.md).

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: permission denied` | `newgrp docker`, or `DOCKER_CMD='sudo docker'` after `sudo -v` |
| Image pull timeout | configure the Docker daemon proxy and restart Docker |
| HTTP 402 / balance | use `--model deepseek-v4-pro`, or top up the key |
| Profile init error | first run uses `--from-default-profile headless`; later runs omit it |
| Native addon `failed to map segment` | `/tmp` must be mounted with `exec` (already in the runner) |
| `no blind scorer adapter` | seed is not blind-testable; record `SEED_NOT_BLIND_TESTABLE` |
| `blind output is empty` | rerun the solver before scoring |
| score < 1.0 exits 1 | expected for partial scores; read the JSON |
| `BLIND_SCORE_STALE` | score predates the task artifacts; rerun the synthetic track |
| `MODEL_MISMATCH` | rerun both tracks with the same `--model` |
| `MODEL_UNKNOWN` | score lacks `run_meta.model`; rerun or use `--require-model-parity` |
| seed and synthetic use different models | rerun both with the same `--model` |
| custom `BLIND_ROOT` / `SEED_ROOT` | pass `--blind-root` / `--seed-root` to prepare/score scripts and set the env vars for the runner |

## 9. Security and publishing

Never commit or publish:

- the seed root or any seed `base/reference`,
- `~/ale-blind/` workspaces or score files,
- `exports/` (contains reference and verify artifacts),
- `~/.dsh/` or `DEEPSEEK_API_KEY`,
- `base/reference` of `internal_only` candidates in a public repo.

For a public repository, publish the framework (skills, scripts, Dockerfiles, templates, docs) and
only redistributable synthetic tasks. For a private repository, candidate artifacts may be included,
but secrets and the seed root must still be excluded. See `.gitignore`, the `ale-task-author`
license rules, and [`publishing.md`](publishing.md) for the sanitization checklist and push
workflow.

The intended private repository is `Erens_Data` (GitHub does not allow apostrophes in repository
names, so `Eren's_Data` is written as `Erens_Data`).

## 10. Command reference

```bash
# Queue
python3 -I scripts/state.py summary
python3 -I scripts/state.py next
python3 -I scripts/state.py get <id>
python3 -I scripts/state.py set-status <id> REVIEWED
python3 -I scripts/state.py append-decision <id> REVISE TOO_EASY

# Gates
python3 -I scripts/validate_task.py candidates/<id>
python3 -I scripts/run_reference.py candidates/<id>
python3 -I scripts/mutation_test.py candidates/<id>
python3 -I scripts/evidence_check.py candidates/<id>
python3 -I scripts/difficulty.py candidates/<id>
python3 -I scripts/dedup.py candidates/<id>

# Blind seed baseline
python3 -I scripts/blind_prepare.py --seed <anchor>
scripts/blind_docker.sh --seed <anchor> --data --build
scripts/blind_docker.sh --seed <anchor> --data
python3 -I scripts/blind_seed_score.py --seed <anchor>

# Blind synthetic candidate
python3 -I scripts/blind_prepare.py <id>
scripts/blind_docker.sh <id> --build --preflight
scripts/blind_docker.sh <id> --data
python3 -I scripts/blind_score.py <id>

# Review
python3 -I scripts/review_candidate.py candidates/<id>
```
