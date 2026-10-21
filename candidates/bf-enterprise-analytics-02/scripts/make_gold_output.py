#!/usr/bin/env python3
"""Write the gold dashboard_metrics.json for the SQLite BI task."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def load_metrics():
    path = Path(__file__).with_name("metrics.py")
    spec = importlib.util.spec_from_file_location("bi_metrics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--candidate-root", type=Path, default=None)
    args = parser.parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    metrics = load_metrics()
    result = metrics.compute(root)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "dashboard_metrics.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out / 'dashboard_metrics.json'}")


if __name__ == "__main__":
    main()
