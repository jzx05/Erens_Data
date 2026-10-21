#!/usr/bin/env python3
"""Aggregate gate reports into review/review.json.

Does not sign off for the human. Preserves an existing human_signoff value.

Usage:
  python3 -I scripts/review_candidate.py candidates/<id> \
      [--seed-score 0.0] [--seed-margin 0.2] [--solvability-threshold 0.3] \
      [--learnable-max 0.9]

The synthetic side is the dsh blind score in
``~/ale-blind/<id>/eval/score.json`` (key ``blind_score``); if that file is
missing, the independent-solver score in
``verify/independent_solver/score.json`` is used as a fallback and flagged.
A blind score older than the newest task artifact is flagged stale. Use
``--dry-run`` to audit without rewriting ``review.json``, and
``--require-model-parity`` to block ACCEPT when run metadata is missing or the
two tracks used different models.

Calibration is relative to the paired seed blind score when available:

  - parity: synthetic within ``seed_margin`` of the seed, or both ~1.0
  - too easy: synthetic > seed + margin while the seed is below ~0.9
  - too hard: synthetic < 0.3; if the seed is degenerate (< 0.2), target
    0.3-0.7 instead of the seed's 0.0
  - no seed baseline: absolute fallback band 0.4-0.9, flagged in the report

A synthetic 1.0 is therefore acceptable when the seed is also ~1.0.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--seed-score",
        type=float,
        default=None,
        help="Override the seed blind score instead of reading ~/ale-blind/seed-<anchor>/eval/score.json",
    )
    parser.add_argument(
        "--solver-score",
        type=float,
        default=None,
        help="Override the synthetic blind score instead of reading ~/ale-blind/<id>/eval/score.json",
    )
    parser.add_argument(
        "--blind-root",
        type=Path,
        default=Path.home() / "ale-blind",
        help="Root containing <candidate-id>/eval/score.json",
    )
    parser.add_argument(
        "--seed-margin",
        type=float,
        default=0.2,
        help="Allowed synthetic-minus-seed gap before a task is too easy",
    )
    parser.add_argument(
        "--solvability-threshold",
        type=float,
        default=0.3,
        help="Learnable floor for the synthetic score",
    )
    parser.add_argument(
        "--learnable-max",
        type=float,
        default=0.9,
        help="Absolute fallback ceiling when no seed baseline exists",
    )
    parser.add_argument(
        "--seed-degenerate",
        type=float,
        default=0.2,
        help="Seed scores below this are degenerate; do not copy them",
    )
    parser.add_argument(
        "--degenerate-seed-max",
        type=float,
        default=0.7,
        help="Target ceiling when the seed is degenerate",
    )
    parser.add_argument(
        "--fallback-floor",
        type=float,
        default=0.4,
        help="Learnable floor when no seed baseline exists",
    )
    parser.add_argument(
        "--seed-easy-ceiling",
        type=float,
        default=0.9,
        help="When the seed is at least this high, a synthetic 1.0 is parity, not too easy",
    )
    parser.add_argument(
        "--seed-blind-root",
        type=Path,
        default=Path.home() / "ale-blind",
        help="Root containing seed-<anchor>/eval/score.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report without writing review/review.json",
    )
    parser.add_argument(
        "--require-model-parity",
        action="store_true",
        help="Block ACCEPT when the seed/synthetic model metadata is missing or different",
    )
    return parser.parse_args()


def load(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def newest_task_mtime(root: Path) -> tuple[float, str | None]:
    """Newest mtime among the files that define the task and its gold."""
    paths: list[Path] = [root / "task_card.json", root / "scripts" / "evaluate.py"]
    for base in (root / "base" / "input", root / "base" / "reference"):
        if base.is_dir():
            paths.extend(path for path in base.rglob("*") if path.is_file())
    newest = 0.0
    newest_path: str | None = None
    for path in paths:
        if not path.is_file():
            continue
        mtime = path.stat().st_mtime
        if mtime > newest:
            newest, newest_path = mtime, str(path)
    return newest, newest_path


def score_run_meta(path: str | None) -> dict:
    if not path:
        return {}
    data = load(Path(path), {})
    meta = data.get("run_meta")
    return meta if isinstance(meta, dict) else {}


def resolve_blind_score(
    args: argparse.Namespace, candidate_id: str, root: Path
) -> tuple[float, str, str]:
    """Return (score, source, kind) for the synthetic side.

    Priority: --solver-score, dsh blind score, independent-solver fallback.
    """
    if args.solver_score is not None:
        return float(args.solver_score), "cli", "cli"

    blind_path = args.blind_root.expanduser() / candidate_id / "eval" / "score.json"
    data = load(blind_path, {})
    value = data.get("blind_score")
    if value is not None:
        try:
            return float(value), str(blind_path), "dsh-blind"
        except (TypeError, ValueError):
            return 0.0, f"invalid blind_score in {blind_path}", "missing"

    fallback = root / "verify" / "independent_solver" / "score.json"
    data = load(fallback, {})
    value = data.get("score")
    if value is not None:
        try:
            return float(value), str(fallback), "independent"
        except (TypeError, ValueError):
            return 0.0, f"invalid score in {fallback}", "missing"

    return 0.0, "missing synthetic blind score", "missing"


def load_independent_solver(root: Path) -> tuple[float | None, str | None]:
    data = load(root / "verify" / "independent_solver" / "score.json", {})
    value = data.get("score")
    if value is None:
        return None, None
    try:
        return float(value), str(root / "verify" / "independent_solver" / "score.json")
    except (TypeError, ValueError):
        return None, None


def resolve_seed_score(args: argparse.Namespace, candidate: dict) -> tuple[float | None, str]:
    """Return (seed_score, source). A missing baseline returns (None, reason)."""
    if args.seed_score is not None:
        return float(args.seed_score), "cli"

    anchor = candidate.get("seed_anchor")
    if not anchor:
        return None, "candidate has no seed_anchor"

    path = args.seed_blind_root.expanduser() / f"seed-{anchor}" / "eval" / "score.json"
    data = load(path, {})
    value = data.get("score")
    if value is None:
        return None, f"missing {path}"
    try:
        return float(value), str(path)
    except (TypeError, ValueError):
        return None, f"invalid score in {path}"


def main() -> int:
    args = parse_args()
    root = args.candidate.expanduser().resolve()
    candidate = load(root / "candidate.json", {})
    schema = load(root / "verify" / "schema.json", {})
    gold = load(root / "verify" / "gold_run.json", {})
    mutation = load(root / "verify" / "mutation.json", {})
    evidence = load(root / "verify" / "evidence.json", {})
    difficulty = load(root / "verify" / "difficulty.json", {})
    dedup = load(root / "verify" / "dedup.json", {})
    existing_review = load(root / "review" / "review.json", {})

    candidate_id = candidate.get("id", root.name)
    solver_score, solver_source, solver_kind = resolve_blind_score(args, candidate_id, root)
    legacy_solver_score, legacy_solver_source = load_independent_solver(root)
    seed_score, seed_source = resolve_seed_score(args, candidate)

    newest_mtime, newest_path = newest_task_mtime(root)
    blind_mtime: float | None = None
    if solver_kind == "dsh-blind":
        try:
            blind_mtime = Path(solver_source).stat().st_mtime
        except OSError:
            blind_mtime = None
    blind_stale = bool(
        blind_mtime is not None and newest_mtime and blind_mtime < newest_mtime
    )

    seed_meta = score_run_meta(seed_source if seed_score is not None else None)
    synthetic_meta = score_run_meta(solver_source if solver_kind == "dsh-blind" else None)
    seed_model = seed_meta.get("model")
    synthetic_model = synthetic_meta.get("model")
    if seed_model and synthetic_model:
        model_parity = "match" if seed_model == synthetic_model else "mismatch"
    else:
        model_parity = "unknown"
    model_parity_ok = model_parity == "match" or (
        model_parity == "unknown" and not args.require_model_parity
    )

    if seed_score is None:
        mode = "absolute-fallback"
        floor = args.fallback_floor
        too_hard = solver_score < floor
        too_easy = solver_score > args.learnable_max
        calibration_note = (
            f"seed blind baseline unavailable ({seed_source}); "
            f"using the absolute fallback band {floor:.2f}-{args.learnable_max:.2f}"
        )
    elif seed_score < args.seed_degenerate:
        mode = "degenerate-seed"
        floor = args.solvability_threshold
        too_hard = solver_score < floor
        too_easy = solver_score > args.degenerate_seed_max
        calibration_note = (
            f"seed baseline {seed_score:.3f} is degenerate (< {args.seed_degenerate:.2f}); "
            f"target {floor:.2f}-{args.degenerate_seed_max:.2f}, not the seed's 0.0"
        )
    else:
        mode = "relative-to-seed"
        floor = args.solvability_threshold
        too_hard = solver_score < floor
        too_easy = (
            solver_score - seed_score > args.seed_margin
            and seed_score < args.seed_easy_ceiling
        )
        if solver_score >= args.seed_easy_ceiling and seed_score >= args.seed_easy_ceiling:
            calibration_note = (
                f"seed baseline {seed_score:.3f} and blind score {solver_score:.3f} "
                f"are both ~1.0 (parity); 1.0 alone is not too easy"
            )
        elif abs(solver_score - seed_score) <= args.seed_margin:
            calibration_note = (
                f"blind score {solver_score:.3f} is within {args.seed_margin:.2f} "
                f"of the seed baseline {seed_score:.3f}"
            )
        elif solver_score < seed_score:
            calibration_note = (
                f"blind score {solver_score:.3f} is below the seed baseline "
                f"{seed_score:.3f} by {seed_score - solver_score:.3f}; "
                f"still above the learnable floor {floor:.2f}, acceptable"
            )
        else:
            calibration_note = (
                f"blind score {solver_score:.3f} exceeds the seed baseline "
                f"{seed_score:.3f} by {solver_score - seed_score:.3f} "
                f"(margin {args.seed_margin:.2f})"
            )

    hard_gates = {
        "schema": bool(schema.get("ok")),
        "gold_run": bool(gold.get("passed")),
        "mutation": bool(mutation.get("passed")),
        "evidence": bool(evidence.get("ok")),
        "difficulty": bool(difficulty.get("passed")),
        "dedup": bool(dedup.get("passed")),
        "solvability": not too_hard,
        "blind_current": not blind_stale,
        "model_parity": model_parity_ok,
    }
    scores = {
        "seed_fidelity": 20 if difficulty.get("stratum_ok") else 10,
        "capability_match": 15
        if candidate.get("task_family") in {"document-forensics", "data-analysis"}
        else 10,
        "difficulty_proximity": 15 if difficulty.get("passed") else 0,
        "correctness_reproducibility": (
            25
            if gold.get("passed") and mutation.get("passed")
            else 15
            if gold.get("passed") or mutation.get("passed")
            else 0
        ),
        "evidence_integrity": 15 if evidence.get("ok") else 0,
        "solvability_clarity": 10
        if not too_hard and not too_easy
        else 5
        if solver_score > 0
        else 0,
    }
    total = sum(scores.values())

    if all(hard_gates.values()) and total >= 85:
        recommendation = "ACCEPT"
    elif total >= 70:
        recommendation = "REVISE"
    else:
        recommendation = "REJECT"
    if not all(hard_gates.values()) and recommendation == "ACCEPT":
        recommendation = "REVISE"
    if (too_easy or too_hard) and recommendation == "ACCEPT":
        recommendation = "REVISE"

    reasons = []
    for gate, passed in hard_gates.items():
        if not passed:
            reasons.append(f"hard gate failed: {gate}")
    if solver_kind == "independent":
        reasons.append(
            f"synthetic dsh blind score missing; using independent solver score "
            f"{solver_score:.3f} from {solver_source} (run the dsh blind track for a valid calibration)"
        )
    elif solver_kind == "missing":
        reasons.append("synthetic blind score missing; treated as 0.0 and flagged too hard")
    if blind_stale:
        reasons.append(
            f"BLIND_SCORE_STALE: blind score is older than {newest_path}; rerun the synthetic track"
        )
    if model_parity == "mismatch":
        reasons.append(
            f"MODEL_MISMATCH: seed model {seed_model!r} != synthetic model "
            f"{synthetic_model!r}; rerun both tracks with the same --model"
        )
    elif model_parity == "unknown" and args.require_model_parity:
        reasons.append(
            "MODEL_UNKNOWN: --require-model-parity is set but the score files lack "
            "run_meta.model; rerun both tracks"
        )
    if seed_score is None:
        reasons.append(
            f"seed blind baseline missing ({seed_source}); "
            f"absolute fallback band {args.fallback_floor:.2f}-{args.learnable_max:.2f} used"
        )
    if too_easy:
        if mode == "relative-to-seed":
            reasons.append(
                f"blind score {solver_score:.3f} is above the seed baseline "
                f"{seed_score:.3f} by {solver_score - seed_score:.3f} "
                f"(margin {args.seed_margin:.2f}); add one hard-but-unambiguous requirement"
            )
        elif mode == "degenerate-seed":
            reasons.append(
                f"blind score {solver_score:.3f} is above the degenerate-seed target "
                f"ceiling {args.degenerate_seed_max:.2f}; the seed's 0.0 is not a target, "
                f"aim for {args.solvability_threshold:.2f}-{args.degenerate_seed_max:.2f}"
            )
        else:
            reasons.append(
                f"blind score {solver_score:.3f} is above the absolute learnable band "
                f"(max {args.learnable_max:.2f}); add one hard-but-unambiguous requirement"
            )
    if too_hard:
        reasons.append(
            f"blind score {solver_score:.3f} is below the learnable floor {floor:.2f}; "
            f"clarify or simplify the task"
        )
    if total < 85:
        reasons.append(f"total score {total} < 85")
    if not reasons:
        reasons.append("all hard gates passed and total score >= 85")

    reason_codes: list[str] = []
    if too_easy:
        reason_codes.append("TOO_EASY")
    if too_hard:
        reason_codes.append("TOO_HARD")
    if seed_score is None:
        reason_codes.append("SEED_BASELINE_MISSING")
    if solver_kind == "independent":
        reason_codes.append("BLIND_SCORE_FALLBACK")
    if solver_kind == "missing":
        reason_codes.append("BLIND_SCORE_MISSING")
    if blind_stale:
        reason_codes.append("BLIND_SCORE_STALE")
    if model_parity == "mismatch":
        reason_codes.append("MODEL_MISMATCH")
    elif model_parity == "unknown" and args.require_model_parity:
        reason_codes.append("MODEL_UNKNOWN")
    for gate, passed in hard_gates.items():
        if not passed:
            reason_codes.append(f"HARD_GATE_{gate.upper()}")

    report = {
        "candidate_id": candidate.get("id", root.name),
        "scores": scores,
        "total": total,
        "hard_gates": hard_gates,
        "gate_details": {
            "schema_errors": schema.get("errors", []),
            "gold_score": gold.get("score"),
            "mutation_rejected": mutation.get("rejected"),
            "evidence_errors": evidence.get("errors", []),
            "difficulty_distance": difficulty.get("anchor_distance"),
            "dedup_matches": dedup.get("matches", []),
            "blind_score": solver_score,
            "blind_score_source": solver_source,
            "blind_score_kind": solver_kind,
            "independent_solver_score": legacy_solver_score,
            "independent_solver_source": legacy_solver_source,
            "seed_blind_score": seed_score,
            "seed_blind_source": seed_source,
            "calibration_mode": mode,
            "calibration_note": calibration_note,
            "seed_margin": args.seed_margin,
            "learnable_floor": floor,
            "learnable_ceiling": args.learnable_max,
            "degenerate_seed_ceiling": args.degenerate_seed_max,
            "too_easy": too_easy,
            "too_hard": too_hard,
            "blind_score_stale": blind_stale,
            "blind_score_mtime": blind_mtime,
            "newest_task_mtime": newest_mtime,
            "newest_task_path": newest_path,
            "seed_model": seed_model,
            "synthetic_model": synthetic_model,
            "model_parity": model_parity,
            "dry_run": args.dry_run,
        },
        "recommendation": recommendation,
        "reasons": reasons,
        "reason_codes": reason_codes,
        "human_signoff": existing_review.get("human_signoff"),
    }
    if not args.dry_run:
        (root / "review").mkdir(exist_ok=True)
        (root / "review" / "review.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if recommendation == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
