# Collaborator Onboarding

This is the shortest path for someone who has been invited to the private repository
`https://github.com/jzx05/Erens_Data`. The full reference is [`usage.md`](usage.md); the blind-test
details are in [`blind-verification.md`](blind-verification.md).

## 1. Get access and clone

The repository is private. The owner invites a collaborator with:

```bash
gh api repos/jzx05/Erens_Data/collaborators/<github-username> \
  -X PUT -f permission=push
```

After accepting the invitation:

```bash
git clone https://github.com/jzx05/Erens_Data.git
cd Erens_Data
```

The repository already contains `.claude/skills -> ../skills` and `.dsh/skills -> ../skills`. If
your platform did not preserve the symlinks, recreate them:

```bash
mkdir -p .claude .dsh
ln -sfn ../skills .claude/skills
ln -sfn ../skills .dsh/skills
```

## 2. Install the runtime

```bash
python3 --version                 # 3.12
node --version                    # 24.x
npm install -g @deepseek-ai/dsh@0.2.0-rc.2
dsh --version
```

Docker:

```bash
sudo apt install -y docker.io
sudo usermod -aG docker "$USER"
# log out and back in, or use:
# sg docker -c '<command>'
docker info
```

Optional proxy for image pulls and the DeepSeek API:

```ini
# /etc/systemd/system/docker.service.d/http-proxy.conf
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1,::1"
```

Then `sudo systemctl daemon-reload && sudo systemctl restart docker`.

Use your **own** `DEEPSEEK_API_KEY`; do not share the owner's key:

```bash
export DEEPSEEK_API_KEY="..."
# or put DEEPSEEK_API_KEY in ~/.dsh/.credentials.yaml
```

## 3. Point at the seed data

The seed data is not in the repository. Put it outside the repo:

```bash
export SEED_ROOT="$HOME/下载/business_finance_extracted/business_finance"
test -d "$SEED_ROOT"
```

The blind scripts also honor `SEED_ROOT` and `BLIND_ROOT`:

```bash
export BLIND_ROOT="${BLIND_ROOT:-$HOME/ale-blind}"
```

If you need a fresh queue from your own seed root (this overwrites `state/candidates.jsonl`):

```bash
python3 -I scripts/seed_profile.py \
  --seeds "$SEED_ROOT" \
  --out profiles \
  --target 20 \
  --reset
```

Otherwise reuse the checked-in queue:

```bash
python3 -I scripts/state.py summary
python3 -I scripts/state.py next
```

## 4. Advance one candidate

The intended entry point is the `ale-factory` skill (user-invocable):

```bash
claude
# then invoke: ale-factory
```

It runs exactly one candidate through scout -> author -> deterministic gates -> independent solve ->
blind verification -> review. The other skills (`ale-seed-analyst`, `ale-source-scout`,
`ale-task-author`, `ale-corrector`, `ale-reviewer`, `ale-blind-verifier`) are dispatched by it.

Manual gates:

```bash
python3 -I scripts/validate_task.py candidates/<id>
python3 -I scripts/run_reference.py candidates/<id>
python3 -I scripts/mutation_test.py candidates/<id>
python3 -I scripts/evidence_check.py candidates/<id>
python3 -I scripts/difficulty.py candidates/<id>
python3 -I scripts/dedup.py candidates/<id>
```

Expected: schema 0 errors, gold 1.0, 3/3 mutants rejected, evidence 0 missing, difficulty within
threshold, no near duplicate.

## 5. Blind-test: seed baseline, then synthetic

Always run the seed baseline first for the candidate's anchor. Reuse it for every candidate with
that anchor; do not rerun it per candidate.

### Track A — seed baseline (once per anchor)

```bash
python3 -I scripts/blind_prepare.py --seed <anchor> --seed-root "$SEED_ROOT"

# First time or when the data image is missing:
scripts/blind_docker.sh --seed <anchor> --data --build

scripts/blind_docker.sh --seed <anchor> --data --preflight
scripts/blind_docker.sh --seed <anchor> --data
python3 -I scripts/blind_seed_score.py --seed <anchor> --seed-root "$SEED_ROOT"
```

Output: `~/ale-blind/seed-<anchor>/eval/score.json` (key `score`).

If the Docker group is not active in the current shell:

```bash
sg docker -c 'scripts/blind_docker.sh --seed <anchor> --data'
```

### Track B — synthetic candidate

```bash
python3 -I scripts/blind_prepare.py <candidate-id>
scripts/blind_docker.sh <candidate-id> --build --preflight
scripts/blind_docker.sh <candidate-id> --data       # or --python
python3 -I scripts/blind_score.py <candidate-id>
```

Output: `~/ale-blind/<candidate-id>/eval/score.json` (key `blind_score`).

Image selection:

| Task | Flag | Image |
|---|---|---|
| Text / Node | default | `ale-blind-dsh` |
| Python / SQLite | `--python` | `ale-blind-dsh-py` |
| pandas / scipy / openpyxl | `--data` | `ale-blind-dsh-data` |

The seed scorer always runs in `ale-blind-dsh-data`. Use the same `--model` for both tracks.

### Non-testable seeds

Only five seeds have scorer adapters:

`sse_northbound_programmatic_trading_01`, `digital_marketing_ab_test_analysis_1`,
`digital_marketing_audience_segmentation_1`, `american_option_pricing_ls`,
`basel_operational_risk_bia_cn`.

For a seed with no `base/input`, no adapter, or a GUI-only workflow, record
`SEED_NOT_BLIND_TESTABLE` and use the absolute 0.4–0.9 fallback. Do not invent a baseline.

## 6. Review and calibration

```bash
python3 -I scripts/review_candidate.py candidates/<id>
```

Resolution order:

1. Synthetic: `~/ale-blind/<id>/eval/score.json["blind_score"]`.
2. Fallback: `candidates/<id>/verify/independent_solver/score.json["score"]` (flagged).
3. Seed: `~/ale-blind/seed-<anchor>/eval/score.json["score"]`.
4. CLI overrides: `--seed-score`, `--solver-score`.

Calibration:

| Situation | Verdict |
|---|---|
| Synthetic within 0.2 of the seed, or both ~1.0 | parity; acceptable |
| Synthetic > seed + 0.2 while seed < 0.9 | too easy; `TOO_EASY` |
| Synthetic < 0.3, or far below a non-degenerate seed | too hard; `TOO_HARD` |
| Seed < 0.2 (degenerate) | target 0.3–0.7, not the seed's 0.0 |
| No seed baseline | absolute 0.4–0.9; `SEED_BASELINE_MISSING` |

Useful flags:

- `--dry-run` — print the report without rewriting `review.json`.
- `--require-model-parity` — block `ACCEPT` when `run_meta.model` is missing or the two tracks used
  different models.
- `--blind-root` / `--seed-blind-root` — use a custom blind root.

A blind score older than the newest task artifact is stale; the review flags `BLIND_SCORE_STALE`
and fails the `blind_current` gate. Rerun the synthetic track.

## 7. Human sign-off

Only a human moves a candidate to `ACCEPTED`:

```bash
python3 -I scripts/state.py set-status <id> ACCEPTED
python3 -I scripts/state.py append-decision <id> ACCEPTED human-signoff
```

Never sign off from a blind score alone. Review the gate reports, the blind comparison, and the task
contract first.

## 8. Security and licensing

- The seed root is read-only and is not redistributed.
- Never publish the private repository or its `internal_only` candidates.
- Never commit `~/.dsh/`, `DEEPSEEK_API_KEY`, `exports/`, `~/ale-blind/`, or seed reference answers.
- The solver container mounts only `~/ale-blind/<id>` plus the host dsh package; the seed root is
  mounted read-only only in the separate seed-scoring container.
- `--network host` still permits external `curl`; for strict closed-book runs, add an egress
  allowlist for `api.deepseek.com`.

## 9. Where to read more

- [`../README.md`](../README.md) — overview and quick start.
- [`usage.md`](usage.md) — full manual.
- [`blind-verification.md`](blind-verification.md) — threat model, Docker mounts, troubleshooting.
- [`../docker/README.md`](../docker/README.md) — image build order and selection.
- [`publishing.md`](publishing.md) — private-repo policy and sanitization checklist.
