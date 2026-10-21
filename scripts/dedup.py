#!/usr/bin/env python3
"""Detect near-duplicate candidates against seeds and accepted candidates.

Usage:
  python3 -I scripts/dedup.py candidates/<id> [--threshold 0.85]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_ROOT = Path.home() / "下载" / "business_finance_extracted" / "business_finance"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--threshold", type=float, default=0.85)
    return parser.parse_args()


def normalize(text: str) -> str:
    lowered = text.lower()
    return re.sub(r"[\s\W_]+", "", lowered, flags=re.UNICODE)


def ngrams(text: str, size: int = 3) -> set[str]:
    normalized = normalize(text)
    if len(normalized) <= size:
        return {normalized}
    return {normalized[index : index + size] for index in range(len(normalized) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def file_hashes(path: Path) -> dict[str, str]:
    hashes = {}
    if not path.is_dir():
        return hashes
    for item in path.rglob("*"):
        if item.is_file():
            hashes[hashlib.sha256(item.read_bytes()).hexdigest()] = str(item)
    return hashes


def task_text(card: dict) -> str:
    return "\n".join(
        [
            str(card.get("title", "")),
            str(card.get("summary", "")),
            str(card.get("taskPrompt", "")),
        ]
    )


def main() -> int:
    args = parse_args()
    root = args.candidate.expanduser().resolve()
    card = json.loads((root / "task_card.json").read_text(encoding="utf-8"))
    candidate_meta = {}
    candidate_path = root / "candidate.json"
    if candidate_path.is_file():
        candidate_meta = json.loads(candidate_path.read_text(encoding="utf-8"))
    internal_variant = bool(
        candidate_meta.get("variant_of")
        or candidate_meta.get("source_policy") == "internal_only"
        or candidate_meta.get("internal_only")
    )
    candidate_grams = ngrams(task_text(card))
    candidate_hashes = set(file_hashes(root / "base" / "input"))

    comparisons = []
    seed_cards = list(SEED_ROOT.glob("*/task_card.json"))
    for seed_card_path in seed_cards:
        seed_card = json.loads(seed_card_path.read_text(encoding="utf-8"))
        similarity = jaccard(candidate_grams, ngrams(task_text(seed_card)))
        seed_hashes = set(file_hashes(seed_card_path.parent / "base" / "input"))
        overlap = (
            len(candidate_hashes & seed_hashes) / len(candidate_hashes)
            if candidate_hashes
            else 0.0
        )
        comparisons.append(
            {
                "kind": "seed",
                "name": seed_card_path.parent.name,
                "text_similarity": round(similarity, 4),
                "file_hash_overlap": round(overlap, 4),
            }
        )

    for other in sorted((ROOT / "candidates").glob("*/task_card.json")):
        if other.parent.resolve() == root:
            continue
        other_candidate = other.parent / "candidate.json"
        status = ""
        if other_candidate.is_file():
            try:
                status = json.loads(other_candidate.read_text(encoding="utf-8")).get("status", "")
            except json.JSONDecodeError:
                status = ""
        if status not in {"ACCEPTED", "REVIEWED"}:
            continue
        other_card = json.loads(other.read_text(encoding="utf-8"))
        comparisons.append(
            {
                "kind": "candidate",
                "name": other.parent.name,
                "status": status,
                "text_similarity": round(jaccard(candidate_grams, ngrams(task_text(other_card))), 4),
                "file_hash_overlap": 0.0,
            }
        )

    matches = [
        item
        for item in comparisons
        if item["text_similarity"] >= args.threshold
        or (not internal_variant and item["file_hash_overlap"] >= 0.5)
    ]
    warnings = [
        item
        for item in comparisons
        if internal_variant and item["file_hash_overlap"] >= 0.5
    ]
    report = {
        "candidate": str(root),
        "threshold": args.threshold,
        "internal_variant": internal_variant,
        "matches": matches,
        "warnings": warnings,
        "passed": not matches,
        "top_similar": sorted(
            comparisons, key=lambda item: item["text_similarity"], reverse=True
        )[:5],
    }
    (root / "verify").mkdir(exist_ok=True)
    (root / "verify" / "dedup.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
