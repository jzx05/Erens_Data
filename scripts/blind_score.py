#!/usr/bin/env python3
"""Score a blind dsh run on the host, outside the container.

The candidate evaluator sees base/reference; the blind solver never did.

Usage:
  python3 -I scripts/blind_score.py <candidate-id> [--threshold 1.0]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BLIND_ROOT = Path.home() / "ale-blind"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_id")
    parser.add_argument("--blind-root", type=Path, default=DEFAULT_BLIND_ROOT)
    parser.add_argument("--threshold", type=float, default=1.0)
    return parser.parse_args()


def extract_json(text: str) -> dict:
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(text[start:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        start = text.find("{", start + 1)
    return {}


def main() -> int:
    args = parse_args()
    candidate = ROOT / "candidates" / args.candidate_id
    blind = args.blind_root.expanduser().resolve() / args.candidate_id
    output_dir = blind / "base" / "output"
    evaluator = candidate / "scripts" / "evaluate.py"

    if not blind.is_dir():
        raise SystemExit(f"missing blind workspace: {blind}")
    if not output_dir.is_dir():
        raise SystemExit(f"missing blind output dir: {output_dir}")
    if not any(output_dir.rglob("*")):
        raise SystemExit(f"blind output dir is empty: {output_dir}")
    if not evaluator.is_file():
        raise SystemExit(f"missing evaluator: {evaluator}")

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            str(evaluator),
            "--candidate-root",
            str(candidate),
            "--output-dir",
            str(output_dir),
        ],
        cwd=candidate,
        capture_output=True,
        text=True,
        check=False,
    )
    parsed = extract_json(completed.stdout)
    score = float(parsed.get("score", 0.0) or 0.0)
    passed = score >= args.threshold

    independent = {}
    independent_path = candidate / "verify" / "independent_solver" / "score.json"
    if independent_path.is_file():
        try:
            independent = json.loads(independent_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            independent = {}

    run_meta = {}
    for name in ("model.txt", "image.txt", "started_at.txt"):
        path = blind / "run" / name
        if path.is_file():
            run_meta[name.removesuffix(".txt")] = path.read_text(
                encoding="utf-8"
            ).strip()

    report = {
        "candidate_id": args.candidate_id,
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "blind_output_dir": str(output_dir),
        "blind_score": score,
        "threshold": args.threshold,
        "blind_passed": passed,
        "run_meta": run_meta,
        "independent_solver_score": independent.get("score"),
        "independent_solver_passed": independent.get("passed"),
        "evaluator_returncode": completed.returncode,
        "evaluator_stdout_tail": completed.stdout[-2000:],
        "evaluator_stderr_tail": completed.stderr[-2000:],
        "evaluator_result": parsed,
    }
    (blind / "eval").mkdir(exist_ok=True)
    (blind / "eval" / "score.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
