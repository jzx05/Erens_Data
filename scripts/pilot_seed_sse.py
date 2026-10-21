#!/usr/bin/env python3
"""Build a perfect submission from an AgentHLE answer key.

This is a local pilot helper: it proves that the seed task's reference answer,
evaluator documents, and manifest are mutually consistent before we use the
task as a template. It does not modify the seed task.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-task", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reference = args.seed_task / "base" / "reference"
    answer_key = json.loads((reference / "answer_key.json").read_text(encoding="utf-8"))

    submission = {}
    for question_key, spec in answer_key.items():
        submission[question_key] = {
            "conclusion": spec["expected_conclusion"],
            "citation_document": spec["accepted_citations"][0],
            "evidence_snippet": spec["positive_evidence"],
            "answer_text": spec["positive_answer_text"],
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(submission, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out} ({len(submission)} questions)")


if __name__ == "__main__":
    main()
