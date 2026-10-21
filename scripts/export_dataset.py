#!/usr/bin/env python3
"""Export accepted candidates as an AgentHLE-compatible dataset.

Usage:
  python3 -I scripts/export_dataset.py --out exports/business_finance_20
  python3 -I scripts/export_dataset.py --out exports/pilot --allow-partial
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "state" / "candidates.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "exports" / "business_finance_20")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--target", type=int, default=20)
    return parser.parse_args()


def load_queue() -> list[dict]:
    items = []
    if not QUEUE.is_file():
        return items
    for line in QUEUE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_tree(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)


def copy_file(source: Path, target: Path) -> None:
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main() -> int:
    args = parse_args()
    out = args.out.expanduser().resolve()
    accepted = [item for item in load_queue() if item.get("status") == "ACCEPTED"]
    if not accepted:
        raise SystemExit("no ACCEPTED candidates")
    if len(accepted) < args.target and not args.allow_partial:
        raise SystemExit(
            f"only {len(accepted)}/{args.target} accepted; pass --allow-partial to export anyway"
        )

    out.mkdir(parents=True, exist_ok=True)
    manifest_tasks = []
    for item in accepted:
        candidate_id = item["id"]
        source = ROOT / "candidates" / candidate_id
        if not source.is_dir():
            raise SystemExit(f"accepted candidate directory missing: {source}")
        target = out / candidate_id
        target.mkdir(parents=True, exist_ok=True)

        copy_file(source / "candidate.json", target / "candidate.json")
        copy_file(source / "task_card.json", target / "task_card.json")
        copy_file(source / "main.py", target / "main.py")
        copy_tree(source / "base" / "input", target / "base" / "input")
        copy_tree(source / "base" / "reference", target / "base" / "reference")
        copy_tree(source / "base" / "software", target / "base" / "software")
        copy_file(source / "scripts" / "evaluate.py", target / "scripts" / "evaluate.py")
        copy_file(
            source / "scripts" / "make_gold_output.py",
            target / "scripts" / "make_gold_output.py",
        )
        copy_file(source / "evidence" / "sources.jsonl", target / "evidence" / "sources.jsonl")
        copy_file(source / "evidence" / "evidence.jsonl", target / "evidence" / "evidence.jsonl")

        candidate_meta = {}
        candidate_path = source / "candidate.json"
        if candidate_path.is_file():
            candidate_meta = json.loads(candidate_path.read_text(encoding="utf-8"))
        source_policy = candidate_meta.get("source_policy", "unknown")
        if source_policy == "public":
            copy_tree(source / "source_pack", target / "source_pack")
        else:
            source_pack = source / "source_pack"
            if source_pack.is_dir() and any(source_pack.rglob("*")):
                (target / "INTERNAL_ONLY_SOURCES.txt").write_text(
                    "source_pack omitted from export because at least one source is not "
                    "redistributable; see evidence/sources.jsonl.\n",
                    encoding="utf-8",
                )

        copy_tree(source / "verify", target / "verify")
        copy_file(source / "review" / "review.json", target / "review" / "review.json")

        task_card = target / "task_card.json"
        manifest_tasks.append(
            {
                "id": candidate_id,
                "stratum": item.get("stratum"),
                "seed_refs": item.get("seed_refs", []),
                "task_family": candidate_meta.get("task_family"),
                "difficulty_target": item.get("difficulty_target"),
                "source_policy": source_policy,
                "task_card_sha256": sha256(task_card) if task_card.is_file() else None,
            }
        )

    manifest = {
        "dataset": out.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "accepted": len(accepted),
        "partial": len(accepted) < args.target,
        "tasks": manifest_tasks,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
