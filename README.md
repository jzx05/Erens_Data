# Eren's Data

A deterministic task-authoring and blind-verification pipeline for AgentHLE-style
`business_finance` tasks. It turns a small seed set into candidate tasks, verifies the gold answer
and evaluator, and uses dsh in Docker as a blind solver. The seed task and the synthetic candidate
are both blind-tested before review, so difficulty is always compared against a real baseline.

The GitHub repository is private and named `Erens_Data` (GitHub repository names cannot contain
apostrophes).

The full manual is in [`docs/usage.md`](docs/usage.md). The blind-verification threat model and
troubleshooting are in [`docs/blind-verification.md`](docs/blind-verification.md).

## What is in the repo

```
AGENTS.md / CLAUDE.md        operating rules and gates
skills/                      factory orchestration and role skills
scripts/                     seed profile, state, validators, blind runner, export
templates/task/              document-forensics and data-analysis templates
candidates/<id>/             task artifacts (base/input, base/reference, scripts, evidence)
profiles/                    seed profile, quotas, pilot notes
state/candidates.jsonl       queue
exports/                     exported datasets (gitignored)
docker/blind-dsh/            Node-only blind solver image
docker/blind-dsh-py/         Python 3.12 + Node blind solver image
docker/blind-dsh-data/       Python + pandas/scipy/openpyxl image and seed scorer
```

## Requirements

- Python 3.12 (`python3 -I` is used throughout).
- Node 24 and dsh (`@deepseek-ai/dsh@0.2.0-rc.2`).
- Docker Engine; the current user must be in the `docker` group or use `DOCKER_CMD='sudo docker'`.
- Optional: a host HTTP proxy for Docker image pulls and dsh API access.

## Quick start

### 1. Clone and link the skills

```bash
git clone <your-repo> erens-data
cd erens-data
mkdir -p .claude .dsh
ln -sfn ../skills .claude/skills
ln -sfn ../skills .dsh/skills
```

### 2. Point at the seed root

The seed data is not redistributed. Put it outside the repo and pass its path explicitly:

```bash
export SEED_ROOT="$HOME/下载/business_finance_extracted/business_finance"
```

### 3. Build the seed profile and quota plan

```bash
python3 -I scripts/seed_profile.py --seeds "$SEED_ROOT" --out profiles --target 20
python3 -I scripts/state.py summary
python3 -I scripts/state.py next
```

### 4. Author the next candidate

Invoke the `ale-factory` skill (or follow its steps manually). One candidate at a time:

```bash
python3 -I scripts/validate_task.py candidates/<id>
python3 -I scripts/run_reference.py candidates/<id>
python3 -I scripts/mutation_test.py candidates/<id>
python3 -I scripts/evidence_check.py candidates/<id>
python3 -I scripts/difficulty.py candidates/<id>
python3 -I scripts/dedup.py candidates/<id>
```

### 5. Blind-test: seed baseline, then synthetic

The seed baseline is run **once per anchor** and reused. The synthetic run uses the same model.

```bash
# Track A — seed baseline (once per anchor)
python3 -I scripts/blind_prepare.py --seed <anchor>
scripts/blind_docker.sh --seed <anchor> --data --build
scripts/blind_docker.sh --seed <anchor> --data --preflight
scripts/blind_docker.sh --seed <anchor> --data
python3 -I scripts/blind_seed_score.py --seed <anchor>

# Track B — synthetic candidate
python3 -I scripts/blind_prepare.py <candidate-id>
scripts/blind_docker.sh <candidate-id> --build --preflight
scripts/blind_docker.sh <candidate-id> --data
python3 -I scripts/blind_score.py <candidate-id>
```

If the current shell does not have the docker group, wrap each command:
`sg docker -c '<command>'`, or set `DOCKER_CMD='sudo docker'`.

### 6. Review

```bash
python3 -I scripts/review_candidate.py candidates/<id>
```

`review_candidate.py` reads the dsh synthetic blind score
(`~/ale-blind/<id>/eval/score.json["blind_score"]`) and the seed baseline
(`~/ale-blind/seed-<anchor>/eval/score.json["score"]`). The Claude Code independent-solver score is
only a fallback when the dsh file is missing, and the report flags it.

## Difficulty calibration

The seed is the baseline, not a hard bound:

| Situation | Verdict |
|---|---|
| Synthetic within 0.2 of the seed, or both ~1.0 | parity; acceptable |
| Synthetic > seed + 0.2 while seed < 0.9 | too easy; add one hard-but-unambiguous requirement |
| Synthetic < 0.3, or far below a non-degenerate seed | too hard; clarify or simplify |
| Seed < 0.2 (degenerate) | target 0.3–0.7, not the seed's 0.0 |
| No seed baseline | absolute 0.4–0.9 fallback; flag `SEED_BASELINE_MISSING` |

A synthetic 1.0 is therefore **not** automatically too easy: if the seed is also ~1.0, it is parity.

## Docker images

| Image | Contents | Flag |
|---|---|---|
| `ale-blind-dsh` | Node 24, dsh mounted read-only from the host | default |
| `ale-blind-dsh-py` | Python 3.12 + Node 24 | `--python` |
| `ale-blind-dsh-data` | `ale-blind-dsh-py` + pandas/pyarrow/numpy/scipy/openpyxl | `--data` |

The seed scorer always runs in `ale-blind-dsh-data`, even if the solver used another image.
Build all three in dependency order with `docker/build.sh`; details are in
[`docker/README.md`](docker/README.md).

## Security boundaries

- The solver container mounts only `~/ale-blind/<id>` at `/workspace` and the host dsh package at
  `/opt/dsh:ro`.
- It never mounts the factory, the seed root, `base/reference`, `evidence/`, `verify/`, `review/`,
  `exports/`, or `~/.dsh`.
- The seed root is mounted read-only only in the separate seed-scoring container (`/seed:ro`,
  `--network none`).
- `DEEPSEEK_API_KEY` is passed as an environment variable, never written into the workspace.
- The blind profile disables `tool-web`, subagents, workflows, and skills.

Known limitation: `--network host` still allows external `curl` access from the model's bash tool.
For strict closed-book runs, add an egress allowlist that only permits `api.deepseek.com`.

## Status

The factory is designed for 20 `business_finance` tasks. Current state is tracked in
`state/candidates.jsonl`; accepted tasks require explicit human sign-off. Seed baselines currently
exist for five anchors (see `docs/blind-verification.md`).

## Publishing

This is a private repository (`Erens_Data`). The sanitization checklist and push workflow are in
[`docs/publishing.md`](docs/publishing.md). Never publish the seed root, `exports/`, blind
workspaces, credentials, or `internal_only` candidate data.
