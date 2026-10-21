#!/usr/bin/env python3
"""Check that a candidate evaluator rejects obviously wrong outputs.

Generates three mutants from the gold output and runs the candidate evaluator on
each one. A mutant is "rejected" when the evaluator score is below 1.0.

Usage:
  python3 -I scripts/mutation_test.py candidates/<id>
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml"}


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
    return {}


STRUCTURED_PRIORITY = {
    ".json": 0,
    ".csv": 1,
    ".tsv": 2,
    ".yaml": 3,
    ".yml": 4,
    ".txt": 5,
    ".md": 6,
}


def output_files(root: Path) -> list[Path]:
    files = [path for path in root.rglob("*") if path.is_file()]
    return sorted(
        files,
        key=lambda path: (STRUCTURED_PRIORITY.get(path.suffix.lower(), 9), str(path)),
    )


def first_leaf(value):
    if isinstance(value, dict):
        for key, item in value.items():
            found = first_leaf(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = first_leaf(item)
            if found is not None:
                return found
    elif isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return None


def set_first_leaf(value, replacement) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                if set_first_leaf(item, replacement):
                    return True
            else:
                value[key] = replacement
                return True
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, (dict, list)):
                if set_first_leaf(item, replacement):
                    return True
            else:
                value[index] = replacement
                return True
    return False


def mutate_scalar(path: Path) -> bool:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            leaf = first_leaf(data)
            if isinstance(leaf, bool):
                replacement = not leaf
            elif isinstance(leaf, (int, float)):
                # Use a large relative change so a 0.5% tolerance cannot absorb it.
                replacement = leaf * 10 + 1000
            elif isinstance(leaf, str):
                replacement = leaf + "-MUTANT"
            else:
                replacement = "MUTANT"
            if not set_first_leaf(data, replacement):
                return False
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        if suffix in {".csv", ".tsv"}:
            delimiter = "\t" if suffix == ".tsv" else ","
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle, delimiter=delimiter))
            if len(rows) < 2 or not rows[1]:
                return False
            rows[1][0] = "MUTANT"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter=delimiter)
                writer.writerows(rows)
            return True
        if suffix in TEXT_SUFFIXES:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for index, line in enumerate(lines):
                if line.strip():
                    lines[index] = "MUTANT"
                    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    return True
    except (OSError, ValueError, json.JSONDecodeError, csv.Error):
        return False
    return False


def mutate_structure(path: Path) -> bool:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data:
                data.pop(next(iter(data)))
            elif isinstance(data, list) and data:
                data.pop(0)
            else:
                data = {"MUTANT": True}
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        if suffix in {".csv", ".tsv"}:
            delimiter = "\t" if suffix == ".tsv" else ","
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle, delimiter=delimiter))
            if len(rows) < 2:
                return False
            rows.pop(1)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter=delimiter)
                writer.writerows(rows)
            return True
        if suffix in TEXT_SUFFIXES:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for index, line in enumerate(lines):
                if line.strip():
                    lines.pop(index)
                    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    return True
            path.write_text("", encoding="utf-8")
            return True
    except (OSError, ValueError, json.JSONDecodeError, csv.Error):
        return False
    return False


def make_mutant(source: Path, target: Path, mutation: str) -> bool:
    shutil.copytree(source, target)
    files = output_files(target)
    for path in files:
        if mutation == "drop":
            path.unlink()
            return True
        if mutation == "scalar" and mutate_scalar(path):
            return True
        if mutation == "structure" and mutate_structure(path):
            return True
    return False


def run_evaluator(root: Path, output_dir: Path, timeout: int) -> tuple[float, dict, str]:
    evaluate = root / "scripts" / "evaluate.py"
    completed = subprocess.run(
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
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    parsed = extract_json(completed.stdout)
    score = float(parsed.get("score", 0.0) or 0.0)
    return score, parsed, completed.stderr[-1000:]


def main() -> int:
    args = parse_args()
    root = args.candidate.expanduser().resolve()
    make_gold = root / "scripts" / "make_gold_output.py"
    evaluate = root / "scripts" / "evaluate.py"
    if not make_gold.is_file() or not evaluate.is_file():
        raise SystemExit(f"{root}: need scripts/make_gold_output.py and scripts/evaluate.py")

    with tempfile.TemporaryDirectory(prefix="ale-mutants-") as tmp:
        tmp_path = Path(tmp)
        gold = tmp_path / "gold"
        gold.mkdir()
        made = subprocess.run(
            [sys.executable, "-I", str(make_gold), "--out", str(gold)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            check=False,
        )
        if made.returncode != 0:
            raise SystemExit(f"make_gold_output failed: {made.stderr}")
        if not output_files(gold):
            raise SystemExit("make_gold_output produced no files")

        results = []
        for mutation in ("drop", "scalar", "structure"):
            target = tmp_path / mutation
            if not make_mutant(gold, target, mutation):
                results.append(
                    {"mutation": mutation, "applied": False, "rejected": False, "score": None}
                )
                continue
            score, parsed, stderr = run_evaluator(root, target, args.timeout)
            results.append(
                {
                    "mutation": mutation,
                    "applied": True,
                    "rejected": score < 1.0,
                    "score": score,
                    "evaluator_notes": parsed.get("notes", []),
                    "stderr_tail": stderr,
                }
            )

    rejected = sum(1 for item in results if item["rejected"])
    report = {
        "candidate": str(root),
        "mutants": results,
        "rejected": rejected,
        "required": 3,
        "passed": rejected >= 3 and all(item["applied"] for item in results),
    }
    (root / "verify").mkdir(exist_ok=True)
    (root / "verify" / "mutation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
