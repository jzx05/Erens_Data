#!/usr/bin/env python3
"""Run a candidate's gold solution through its evaluator.

Contract used by candidates written for this factory:

  scripts/make_gold_output.py --out <dir>     # write the perfect submission
  scripts/evaluate.py --candidate-root <dir> --output-dir <dir>
                                              # print one JSON object with "score"

Usage:
  python3 -I scripts/run_reference.py candidates/<id>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
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
    raise ValueError("evaluator did not print a JSON object")


def run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def main() -> int:
    args = parse_args()
    root = args.candidate.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"candidate directory does not exist: {root}")

    make_gold = root / "scripts" / "make_gold_output.py"
    evaluate = root / "scripts" / "evaluate.py"
    if not evaluate.is_file():
        raise SystemExit(f"missing evaluator: {evaluate}")

    with tempfile.TemporaryDirectory(prefix="ale-gold-") as tmp:
        output_dir = Path(tmp) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        if make_gold.is_file():
            gold = run(
                [sys.executable, "-I", str(make_gold), "--out", str(output_dir)],
                cwd=root,
                timeout=args.timeout,
            )
            if gold.returncode != 0:
                report = {
                    "candidate": str(root),
                    "score": 0.0,
                    "passed": False,
                    "stage": "make_gold_output",
                    "returncode": gold.returncode,
                    "stdout": gold.stdout,
                    "stderr": gold.stderr,
                }
                (root / "verify").mkdir(exist_ok=True)
                (root / "verify" / "gold_run.json").write_text(
                    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 1
        else:
            # Fallback convention: reference outputs live in base/reference/outputs.
            outputs = root / "base" / "reference" / "outputs"
            if not outputs.is_dir():
                raise SystemExit(
                    f"{root}: need scripts/make_gold_output.py or base/reference/outputs/"
                )
            for path in outputs.rglob("*"):
                if path.is_file():
                    target = output_dir / path.relative_to(outputs)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())

        evaluated = run(
            [
                sys.executable,
                "-I",
                str(evaluate),
                "--candidate-root",
                str(root),
                "--output-dir",
                str(output_dir),
            ],
            cwd=root,
            timeout=args.timeout,
        )

    try:
        parsed = extract_json(evaluated.stdout) if evaluated.stdout.strip() else {}
    except ValueError:
        parsed = {}
    score = float(parsed.get("score", 0.0) or 0.0)
    report = {
        "candidate": str(root),
        "score": score,
        "passed": bool(evaluated.returncode == 0 and score == 1.0),
        "returncode": evaluated.returncode,
        "evaluator": parsed,
        "stdout_tail": evaluated.stdout[-2000:],
        "stderr_tail": evaluated.stderr[-2000:],
    }
    (root / "verify").mkdir(exist_ok=True)
    (root / "verify" / "gold_run.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
