# Blind dsh Verification

Verify a generated task with dsh as an independent solver, without letting dsh see the answers.

## Threat model

dsh's sandbox controls **file writes**, not reads. The headless profile includes
`tool-bash`, `tool-fs`, `tool-fs-search`, `tool-skill`, and `tool-web`. A model with those tools can
read any absolute path it can guess. Copying only `base/input` into a temporary directory is
therefore **not** a blind test.

The only reliable boundary used here is a Docker container:

- The container root filesystem contains Node, dsh, and the OS, but not the host factory.
- The only host directory mounted in the **solver** container is `~/ale-blind/<id>` (candidate) or
  `~/ale-blind/seed-<anchor>` (seed) at `/workspace`.
- `base/reference`, `evidence/`, `verify/`, `review/`, the seed root, and the rest of
  `~/ale-task-factory` are not present in the solver container. The seed root is mounted read-only
  only in the separate seed-scoring container (`/seed:ro`).

## Prerequisites

Docker installed and usable by the current user:

```bash
sudo apt install -y docker.io
sudo usermod -aG docker "$USER"   # then new shell, or use DOCKER_CMD='sudo docker'
docker info
```

Docker daemon proxy (needed on this network to pull images):

```bash
# /etc/systemd/system/docker.service.d/http-proxy.conf
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1,::1"
```

Then `sudo systemctl daemon-reload && sudo systemctl restart docker`.

`DEEPSEEK_API_KEY` is read from the environment, or from `~/.dsh/.credentials.yaml` by
`blind_docker.sh` without printing it. Do not copy the credentials file into the workspace.

## Workflow: two tracks

Run the seed baseline first, once per anchor, then the synthetic candidate, then review. The seed
baseline is shared by every candidate with the same `seed_anchor`.

### Track A — seed baseline (once per anchor)

```bash
cd ~/ale-task-factory
python3 -I scripts/blind_prepare.py --seed <anchor>

# First time, or when the data image is missing:
scripts/blind_docker.sh --seed <anchor> --data --build

scripts/blind_docker.sh --seed <anchor> --data --preflight
scripts/blind_docker.sh --seed <anchor> --data
python3 -I scripts/blind_seed_score.py --seed <anchor>
```

- Output: `~/ale-blind/seed-<anchor>/eval/score.json`, top-level key `"score"`.
- The seed scorer runs in `ale-blind-dsh-data`; build it with `--data --build`.
- The solver container sees only `~/ale-blind/seed-<anchor>`. The seed root is mounted read-only
  (`/seed:ro`) only in the scoring container, never in the solver.
- Reuse the baseline for every candidate with the same anchor. Rerun only if the seed input, the
  scorer, or the model changes.
- Supported adapters: `sse_northbound_programmatic_trading_01`,
  `digital_marketing_ab_test_analysis_1`, `digital_marketing_audience_segmentation_1`,
  `american_option_pricing_ls`, `basel_operational_risk_bia_cn`. Other seeds are
  `SEED_NOT_BLIND_TESTABLE`; use the absolute 0.4–0.9 fallback.

### Track B — synthetic candidate

```bash
python3 -I scripts/blind_prepare.py <candidate-id>
scripts/blind_docker.sh <candidate-id> --build --preflight
scripts/blind_docker.sh <candidate-id> [--python|--data]
python3 -I scripts/blind_score.py <candidate-id>
```

- Output: `~/ale-blind/<candidate-id>/eval/score.json`, top-level key `"blind_score"`.
- For Python/SQLite tasks add `--python`; for data-analysis tasks add `--data`.
- Use the same `--model` for both tracks. If the model changes, rerun both baselines.

First run may use `--model deepseek-v4-pro` if `deepseek-flash` returns HTTP 402:

```bash
scripts/blind_docker.sh <candidate-id> --model deepseek-v4-pro
```

A score below 1.0 exits 1 for both tracks. That is expected for partial scores; read the JSON.

## What is copied

`blind_prepare.py` copies:

- `base/input/**`
- `base/software/**` if present
- `TASK.md` generated from `taskCard.taskPrompt` + `agentMustDo`
- `blind.patch.yml` (disables web, subagents, workflows, skills)
- empty `base/output/`, `.dsh-home/`, `run/`, `eval/`

It never copies:

- `base/reference/**`
- `evidence/**`, `verify/**`, `review/**`
- `scripts/**`, `source_pack/**`
- `candidate.json`, `task_card.json`
- the seed root, other candidates, `~/.dsh`

For a seed (`--seed <slug>`), the same rules apply to the seed's `base/input/**` and
`base/software/**`; the seed's `base/reference/**`, evidence, scripts, and task card are not copied.
The seed root is mounted read-only only in the seed scoring container (`/seed:ro`).

The manifest at `~/ale-blind/<id>/blind_manifest.json` records file hashes and warnings.

## Container command

Three images are available:

- `ale-blind-dsh` — plain `node:24-bookworm-slim`; for text/Node tasks.
- `ale-blind-dsh-py` — `python:3.12-slim-bookworm` with Node 24.22.0 installed; for Python and
  SQLite tasks. Use `--python`.
- `ale-blind-dsh-data` — `ale-blind-dsh-py` plus pandas/pyarrow/numpy/scipy/openpyxl; for
  data-analysis tasks and for the seed scorer. Use `--data`.

The seed scorer is run by `blind_seed_score.py` in `ale-blind-dsh-data` with
`--network none`, `/seed:ro`, and `/blind:ro`. It is a separate container from the solver; the
solver never sees the seed root.

The host's already-installed dsh package is mounted read-only at `/opt/dsh`. This avoids npm
installs and native compilation inside the image. The container entrypoint is
`node /opt/dsh/lib/bin.js`.

`blind_docker.sh` runs roughly:

```bash
docker run --rm -i \
  --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,exec,size=256m \
  --network host \
  --cap-drop ALL --security-opt no-new-privileges \
  -v "$BLIND:/workspace:rw" \
  -v "$HOST_DSH:/opt/dsh:ro" \
  -e HOME=/workspace -e DSH_HOME=/workspace/.dsh-home \
  -e DEEPSEEK_API_KEY \
  -e HTTP_PROXY -e HTTPS_PROXY -e ALL_PROXY -e NO_PROXY \
  -w /workspace \
  ale-blind-dsh --profile blind --from-default-profile headless \
    --patch /workspace/blind.patch.yml --json -
```

`/tmp` must be mounted with `exec`: dsh materializes its native addon into `/tmp`, and Docker's
tmpfs defaults include `noexec`, which causes `failed to map segment from shared object`.

Docker access: if the `docker` group is not active in the current shell, run the script through
`sg docker -c '...'` (the user was added to the group), or use `DOCKER_CMD='sudo docker'` after
`sudo -v`.

`--network host` lets the container reach the host proxy. If direct egress works, use
`--network bridge` instead. `--read-only` makes the container root read-only; dsh writes only to
`/workspace` and `/tmp`.

## Scoring

### Synthetic candidate

```bash
python3 -I scripts/blind_score.py <candidate-id>
```

This runs the candidate's own `scripts/evaluate.py` on the host, with:

- `--candidate-root ~/ale-task-factory/candidates/<id>` (sees the reference)
- `--output-dir ~/ale-blind/<id>/base/output` (the blind solver's output)

The score is written to `~/ale-blind/<id>/eval/score.json` as `blind_score`. It also records
`run_meta` (model, image, start time) and any existing independent-solver score for comparison.

### Seed baseline

```bash
python3 -I scripts/blind_seed_score.py --seed <anchor>
```

This runs the seed's own scorer in `ale-blind-dsh-data`, with the seed root and blind output
mounted read-only. The score is written to `~/ale-blind/seed-<anchor>/eval/score.json` as `score`.
Only the five adapter seeds listed above are supported.

### Review

```bash
python3 -I scripts/review_candidate.py candidates/<id>
```

The reviewer resolves the synthetic side from
`~/ale-blind/<id>/eval/score.json["blind_score"]` first, falls back to
`verify/independent_solver/score.json["score"]` only when the dsh file is missing (and flags that),
and resolves the seed side from `~/ale-blind/seed-<anchor>/eval/score.json["score"]`. It applies
the seed-relative calibration rules in `ale-reviewer`, reports `model_parity` and
`blind_score_stale`, and fails the `blind_current` gate when the score predates the task artifacts.
Use `--dry-run` to audit without rewriting `review.json`; `--require-model-parity` also blocks
ACCEPT when model metadata is missing.

A blind score older than the newest of `task_card.json`, `scripts/evaluate.py`,
`base/input/**`, and `base/reference/**` is stale. Rerun the synthetic track; do not accept a stale
score.

## Audit checklist

1. `find ~/ale-blind/<id> -iname '*answer*' -o -iname '*gold*' -o -iname '*reference*'` is empty.
2. The same scan on `~/ale-blind/seed-<anchor>` is empty.
3. `~/ale-blind/<id>/blind_manifest.json` and the seed manifest have no warnings.
4. The container cannot see the factory or the seed root: add a temporary check such as
   `docker run ... ls <factory-root>` (should fail), or inspect the mount list with
   `docker inspect`.
5. `run/events.ndjson` shows tool calls only under `/workspace`.
6. `run/stderr.log` has no permission or sandbox errors.
7. Both score files contain `run_meta.model` and `run_meta.image`; seed and synthetic used the same
   model.

## Limitations

- `DEEPSEEK_API_KEY` is visible to the model's bash tool through the process environment. Use a
  scoped/limited key, or inject the key via a proxy.
- `--network host` still allows external web access via `curl`, even though `tool-web` is disabled.
  For strict closed-book runs, add an egress allowlist that only permits `api.deepseek.com`.
- dsh is `0.2.0-rc.2`; profile init and tool composition can change.
- Seed scorer adapters cover only five seeds; other seeds are not blind-testable without a new
  adapter.
- A partial score (< 1.0) exits 1 on both tracks. Use the JSON score, not the exit code.
- Scores are comparable only when both tracks use the same model and image family; `run_meta`
  records what was used. A mismatch blocks ACCEPT; missing metadata is `MODEL_UNKNOWN`.
- A score older than the task artifacts is stale; rerun the affected track. `review_candidate.py`
  flags `BLIND_SCORE_STALE` and fails the `blind_current` gate.

## Fallback: no-tools profile

If Docker is unavailable, use a dsh profile with `tool-bash`, `tool-fs`, `tool-fs-search`, `tool-web`,
`tool-skill`, subagents, and workflow disabled, and inline the task inputs into the prompt. This
removes filesystem reads entirely but is only practical for small text tasks.

bwrap is **not** used: plain unprivileged bwrap is blocked on this host by the AppArmor userns
restriction. Docker is the supported path.
