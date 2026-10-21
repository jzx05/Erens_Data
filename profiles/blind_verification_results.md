# Blind dsh Verification Results (2026-10-21)

## Setup

- Docker installed (`docker.io 29.1.3`), daemon proxy configured at
  `/etc/systemd/system/docker.service.d/http-proxy.conf` (`http://127.0.0.1:7890`).
- Images:
  - `ale-blind-dsh`: `node:24-bookworm-slim`.
  - `ale-blind-dsh-py`: `python:3.12-slim-bookworm` + Node 24.22.0 (installed from the official
    portable tarball via Python's stdlib; no apt).
  - `ale-blind-dsh-data`: `ale-blind-dsh-py` + pandas, pyarrow, numpy, scipy, openpyxl; used for
    seed tasks and data-heavy synthetic tasks.
  The host dsh package (`~/.nvm/versions/node/v24.22.0/lib/node_modules/@deepseek-ai/dsh`) is
  mounted read-only at `/opt/dsh`; entrypoint is `node /opt/dsh/lib/bin.js`.
- Container mounts only `~/ale-blind/<id>` at `/workspace` and the host dsh package at `/opt/dsh`.
  The factory, `base/reference`, seed root, and `~/.dsh` are not mounted in the solver container.
- `/tmp` is a tmpfs with `exec`; Docker's default `noexec` breaks dsh's native addon materialization.
- Docker is used through `sg docker -c '...'` (the user's shell does not yet have the docker group).
- The seed root is mounted read-only only in the separate seed-scoring container
  (`/seed:ro`, `--network none`).

## Two-track workflow

The workflow skill now runs both tracks:

1. **Seed baseline (once per anchor):**
   `blind_prepare.py --seed <anchor>` -> `blind_docker.sh --seed <anchor> --data` ->
   `blind_seed_score.py --seed <anchor>`.
   Output: `~/ale-blind/seed-<anchor>/eval/score.json` (`score`).
2. **Synthetic candidate:**
   `blind_prepare.py <id>` -> `blind_docker.sh <id> [--python|--data]` ->
   `blind_score.py <id>`.
   Output: `~/ale-blind/<id>/eval/score.json` (`blind_score`).
3. **Review:** `review_candidate.py` reads the dsh synthetic score first and the seed baseline;
   the Claude Code independent-solver score is a flagged fallback only.

## Results

| Candidate | Blind score | Seed baseline | Calibration | Notes |
|---|---:|---:|---|---|
| `bf-compliance-02` | **1.0** | 0.667 | too easy relative to seed | Document forensics; all three questions accepted; reopened as `REVISE` under the corrected calibration |
| `bf-sales-marketing-02` | **1.0** | 0.942 | parity | Audience segmentation; exact contract followed |
| `bf-sales-marketing-01` | **0.706** | 1.0 | harder but above floor | Numeric values correct; TSV used `opened` instead of `opened_rate`, report used `3,116` |
| `bf-enterprise-analytics-02` | **1.0** | missing | absolute fallback | SQLite BI metrics; ran with `--python`; reopened as `REVISE` (`SEED_BASELINE_MISSING`, `TOO_EASY`) |
| `bf-quant-finance-01` | **1.0** | 1.0 | parity | CRR American option pricing |
| `bf-actuarial-risk-01` | **1.0** (fresh) | 0.0 (degenerate) | too easy; target 0.3–0.7 | Basel BIA capital; 60-event classification added; rerun 22:44 with `--python --model deepseek-flash` after the 22:22 revision; only OR046 business-line mismatch, score still 1.0 |
| `bf-accounting-01` | **1.0** | missing | absolute fallback; `SEED_BASELINE_MISSING` | Corporate/deferred tax computation |
| `bf-hr-pm-01` | **1.0** | missing | absolute fallback; `SEED_BASELINE_MISSING` | Attrition/headcount analysis |
| `bf-sales-marketing-03` | **1.0** | 1.0 | parity | Multi-channel ROI and budget reallocation |

### Seed vs synthetic

The paired seed/synthetic blind results are in `profiles/blind_seed_vs_synthetic.md`.

**Calibration:** seed-relative. A synthetic 1.0 is parity when the seed is also ~1.0; it is not
automatically too easy. `bf-quant-finance-01` and `bf-sales-marketing-03` are parity and were moved
to `REVIEWED`. `bf-actuarial-risk-01` remains `REVISE` against a degenerate 0.0 seed; it should
target 0.3–0.7, not the seed's 0.0. `bf-accounting-01` and `bf-hr-pm-01` remain `REVISE` under the
absolute fallback because their anchors have no baseline. `bf-compliance-02` (1.0 vs seed 0.667)
and `bf-enterprise-analytics-02` (1.0, no seed baseline) were reopened as `REVISE`; their previous
human sign-off is cleared in `review.json`.

For `bf-sales-marketing-01`, the evaluator rejected only the metric-name strings and the
thousands-separator format. The SRM, rates, 90% CIs, z-tests, Holm decisions, power sample size,
and `hold` recommendation were all numerically correct. This is a model contract-following failure,
not a data/answer error.

## Audit

- `blind_prepare.py` leakage scan: clean for all prepared workspaces.
- Blind workspaces contain only `TASK.md`, `base/input/**`, `base/software/**`, an empty
  `base/output/`, `.dsh-home/`, `run/`, `eval/`, and `blind.patch.yml`.
- The only "answer"-named file is the solver's own `base/output/research_answers.json`; that is
  expected.
- `blind.patch.yml` disables `tool-web`, subagents, workflows, and skills.
- Seed scoring runs in a separate `--network none` container; the seed root is never mounted in the
  solver container.

## Limitations

- `DEEPSEEK_API_KEY` is passed as an environment variable; the model's bash tool can read it from
  the process environment. Use a scoped key or a key-injecting proxy.
- `--network host` allows `curl` egress even though `tool-web` is disabled. For strict closed-book
  runs, add an egress allowlist that only permits `api.deepseek.com`.
- The Node-only image lacks Python. Use `--python` (`ale-blind-dsh-py`) for Python/SQLite tasks and
  `--data` for pandas/scipy/openpyxl.
- Seed scorer adapters cover only five seeds; other seeds are `SEED_NOT_BLIND_TESTABLE`.
- A score below 1.0 exits 1 on both tracks; use the JSON score.
- dsh is `0.2.0-rc.2`; native addon and profile behavior may change.

## Next steps

1. Keep the two-track workflow in `ale-blind-verifier` as the only documented blind path.
2. Build a baseline for `taxform_4_1` or `internal_employee_agent_instance_1` if a runnable adapter
   can be added; otherwise keep the absolute fallback and `SEED_BASELINE_MISSING`.
3. Calibrate `bf-actuarial-risk-01` into 0.3–0.7 without an all-or-nothing 100% gate.
4. `bf-compliance-02` and `bf-enterprise-analytics-02` are reopened as `REVISE`; add one
   hard-but-unambiguous requirement, rerun Track B, and re-review before a new sign-off.
5. Rerun seed and synthetic tracks with the same model whenever the model changes.
