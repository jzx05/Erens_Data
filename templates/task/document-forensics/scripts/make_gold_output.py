#!/usr/bin/env python3
"""Write the perfect submission from the answer key.

Usage:
  python3 -I scripts/make_gold_output.py --out <dir> [--candidate-root <dir>]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--candidate-root", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    input_dir = root / "base" / "input"
    reference_dir = root / "base" / "reference"
    contract = json.loads((input_dir / "output_contract.json").read_text(encoding="utf-8"))
    output_file = contract.get("output_file", "research_answers.json")
    answer_key = json.loads((reference_dir / "answer_key.json").read_text(encoding="utf-8"))

    submission = {}
    for key, spec in answer_key.items():
        citations = spec.get("accepted_citations", [])
        if not citations:
            raise SystemExit(f"{key}: accepted_citations is empty")
        submission[key] = {
            "conclusion": spec["expected_conclusion"],
            "citation_document": citations[0],
            "evidence_snippet": spec["positive_evidence"],
            "answer_text": spec["positive_answer_text"],
        }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / output_file).write_text(
        json.dumps(submission, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out / output_file} ({len(submission)} questions)")


if __name__ == "__main__":
    main()
