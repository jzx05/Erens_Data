#!/usr/bin/env python3
"""Compare a candidate's difficulty features with its anchor seed and the corpus.

Usage:
  python3 -I scripts/difficulty.py candidates/<id> [--max-distance 2.0]

The distance is Euclidean over z-scored seed features. A threshold of 2.0 is a
starting point; calibrate it on the two pilot candidates before scaling.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "profiles" / "seed_profile.json"

MODALITY_EXTENSIONS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".jsonl": "jsonl",
    ".md": "markdown",
    ".txt": "text",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".pdf": "pdf",
    ".py": "python",
    ".toml": "toml",
    ".lock": "lock",
    ".html": "html",
    ".xml": "xml",
    ".parquet": "parquet",
    ".arrow": "arrow",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".zip": "archive",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--max-distance", type=float, default=2.0)
    return parser.parse_args()


def iter_files(path: Path) -> list[Path]:
    return sorted(item for item in path.rglob("*") if item.is_file()) if path.is_dir() else []


def features_for(task_dir: Path, card: dict) -> dict:
    inputs = iter_files(task_dir / "base" / "input")
    references = iter_files(task_dir / "base" / "reference")
    modalities = Counter(
        MODALITY_EXTENSIONS.get(path.suffix.lower(), path.suffix.lower() or "other")
        for path in inputs
    )
    byte_count = sum(path.stat().st_size for path in inputs if path.exists())
    return {
        "software_count": len(card.get("software", [])),
        "input_file_count": len(card.get("inputFiles", [])),
        "base_input_file_count": len(inputs),
        "log_input_bytes": math.log1p(byte_count),
        "reference_file_count": len(references),
        "prompt_kchars": len(card.get("taskPrompt", "")) / 1000.0,
        "must_do_count": len(card.get("agentMustDo", [])),
        "evaluation_kchars": len(card.get("evaluation", "")) / 1000.0,
        "timeout_units": int(card.get("vm", {}).get("timeout", 0) or 0) / 7200.0,
        "modality_count": len(modalities),
    }


def distance(a: dict[str, float], b: dict[str, float], keys: list[str]) -> float:
    return math.sqrt(sum((a[key] - b[key]) ** 2 for key in keys))


def main() -> int:
    args = parse_args()
    root = args.candidate.expanduser().resolve()
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    keys = profile["vector_keys"]
    seeds = profile["tasks"]

    means = {key: sum(task["features"][key] for task in seeds) / len(seeds) for key in keys}
    stds = {}
    for key in keys:
        variance = sum((task["features"][key] - means[key]) ** 2 for task in seeds) / len(seeds)
        stds[key] = math.sqrt(variance) or 1.0

    def z(values: dict[str, float]) -> dict[str, float]:
        return {key: (values[key] - means[key]) / stds[key] for key in keys}

    card = json.loads((root / "task_card.json").read_text(encoding="utf-8"))
    candidate_obj = {}
    candidate_path = root / "candidate.json"
    if candidate_path.is_file():
        candidate_obj = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate_features = features_for(root, card)
    candidate_z = z(candidate_features)

    seed_vectors = {task["slug"]: z(task["features"]) for task in seeds}
    anchor_slug = candidate_obj.get("seed_anchor")
    if not anchor_slug or anchor_slug not in seed_vectors:
        same_stratum = [
            task
            for task in seeds
            if task["subdomain_code"] == candidate_obj.get("stratum")
        ]
        pool = same_stratum or seeds
        anchor = min(
            pool,
            key=lambda task: distance(candidate_z, seed_vectors[task["slug"]], keys),
        )
        anchor_slug = anchor["slug"]

    anchor_z = seed_vectors[anchor_slug]
    anchor_distance = distance(candidate_z, anchor_z, keys)
    nearest = sorted(
        (
            {"slug": slug, "distance": round(distance(candidate_z, vector, keys), 4)}
            for slug, vector in seed_vectors.items()
        ),
        key=lambda item: item["distance"],
    )[:3]

    anchor_task = next(task for task in seeds if task["slug"] == anchor_slug)
    stratum_ok = candidate_obj.get("stratum") == anchor_task["subdomain_code"]
    passed = anchor_distance <= args.max_distance and stratum_ok

    report = {
        "candidate": str(root),
        "anchor": anchor_slug,
        "anchor_subdomain": anchor_task["subdomain_code"],
        "candidate_stratum": candidate_obj.get("stratum"),
        "stratum_ok": stratum_ok,
        "anchor_distance": round(anchor_distance, 4),
        "max_distance": args.max_distance,
        "nearest_seeds": nearest,
        "candidate_features": {key: round(value, 4) for key, value in candidate_features.items()},
        "seed_means": {key: round(value, 4) for key, value in means.items()},
        "seed_stds": {key: round(value, 4) for key, value in stds.items()},
        "passed": passed,
    }
    (root / "verify").mkdir(exist_ok=True)
    (root / "verify" / "difficulty.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
