#!/usr/bin/env python3
"""Copy the gold outputs from base/reference/gold/ into --out.

Usage:
  python3 -I scripts/make_gold_output.py --out <dir> [--candidate-root <dir>]
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--candidate-root", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    gold = root / "base" / "reference" / "gold"
    if not gold.is_dir():
        raise SystemExit(f"missing gold directory: {gold}")
    args.out.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in gold.rglob("*"):
        if path.is_file():
            target = args.out / path.relative_to(gold)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            count += 1
    print(f"copied {count} gold files to {args.out}")


if __name__ == "__main__":
    main()
