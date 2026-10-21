#!/usr/bin/env python3
"""Evaluator for bf-sales-marketing-03 (multi-channel campaign ROI reallocation).

Compares submitted files under --output-dir with the gold files under
base/reference/gold/. Supports JSON (recursive, numeric tolerance), CSV/TSV
(cell comparison, numeric tolerance), and text (exact after trailing-space strip).

verification_contract.json fields:
  required_outputs: [filename, ...]
  tolerance: 0.005
  text_outputs: [filename, ...]        # optional; exact text comparison
  json_outputs: [filename, ...]        # optional; JSON comparison
  table_outputs: [{"file": "...", "delimiter": "\t"}]  # optional

Usage:
  python3 -I scripts/evaluate.py --candidate-root <dir> --output-dir <dir>
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def equal(left: Any, right: Any, tolerance: float) -> tuple[bool, str]:
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right, "" if left == right else f"{left!r} != {right!r}"
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if math.isnan(float(left)) and math.isnan(float(right)):
            return True, ""
        return abs(float(left) - float(right)) <= tolerance, f"{left!r} != {right!r}"
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return False, f"keys differ: {sorted(set(left) ^ set(right))}"
        for key in left:
            ok, message = equal(left[key], right[key], tolerance)
            if not ok:
                return False, f"{key}: {message}"
        return True, ""
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False, f"length {len(left)} != {len(right)}"
        for index, (a, b) in enumerate(zip(left, right)):
            ok, message = equal(a, b, tolerance)
            if not ok:
                return False, f"[{index}]: {message}"
        return True, ""
    return left == right, "" if left == right else f"{left!r} != {right!r}"


def compare_json(submitted: Path, gold: Path, tolerance: float) -> tuple[bool, str]:
    return equal(load_json(submitted), load_json(gold), tolerance)


def compare_table(submitted: Path, gold: Path, delimiter: str, tolerance: float) -> tuple[bool, str]:
    def rows(path: Path):
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.reader(handle, delimiter=delimiter))

    left, right = rows(submitted), rows(gold)
    if len(left) != len(right):
        return False, f"row count {len(left)} != {len(right)}"
    for row_index, (a, b) in enumerate(zip(left, right)):
        if len(a) != len(b):
            return False, f"row {row_index}: column count differs"
        for column, (x, y) in enumerate(zip(a, b)):
            try:
                ok = abs(float(x) - float(y)) <= tolerance
            except ValueError:
                ok = x.strip() == y.strip()
            if not ok:
                return False, f"row {row_index} col {column}: {x!r} != {y!r}"
    return True, ""


def compare_text(submitted: Path, gold: Path) -> tuple[bool, str]:
    left = submitted.read_text(encoding="utf-8").rstrip()
    right = gold.read_text(encoding="utf-8").rstrip()
    return left == right, "" if left == right else "text differs"


def main() -> None:
    args = parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    output_dir = (args.output_dir or root / "base" / "output").resolve()
    reference_dir = root / "base" / "reference"
    contract = load_json(root / "base" / "input" / "output_contract.json")
    verification = load_json(reference_dir / "verification_contract.json")
    tolerance = float(verification.get("tolerance", 0.005))
    required = verification.get("required_outputs") or contract.get("required_outputs", [])
    gold_dir = reference_dir / "gold"

    text_outputs = set(verification.get("text_outputs", []))
    json_outputs = set(verification.get("json_outputs", []))
    table_config = {
        item["file"]: item.get("delimiter", ",")
        for item in verification.get("table_outputs", [])
        if isinstance(item, dict) and item.get("file")
    }

    results = []
    for filename in required:
        submitted = output_dir / filename
        gold = gold_dir / filename
        if not submitted.is_file():
            results.append({"file": filename, "passed": False, "reason": "missing submission"})
            continue
        if not gold.is_file():
            results.append({"file": filename, "passed": False, "reason": "missing gold"})
            continue
        if filename in json_outputs or filename.endswith(".json"):
            passed, reason = compare_json(submitted, gold, tolerance)
        elif filename in table_config or filename.endswith((".csv", ".tsv")):
            delimiter = table_config.get(filename, "\t" if filename.endswith(".tsv") else ",")
            passed, reason = compare_table(submitted, gold, delimiter, tolerance)
        elif filename in text_outputs or filename.endswith((".md", ".txt")):
            passed, reason = compare_text(submitted, gold)
        else:
            passed, reason = compare_text(submitted, gold)
        results.append({"file": filename, "passed": passed, "reason": reason})

    score = sum(1.0 for item in results if item["passed"]) / len(required) if required else 0.0
    print(
        json.dumps(
            {
                "score": score,
                "files": results,
                "required_outputs": required,
                "tolerance": tolerance,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
