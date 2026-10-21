#!/usr/bin/env python3
"""Prepare a blind solver workspace from a candidate.

Only agent-visible inputs are copied. The reference, evidence, verification,
review, scripts, and task card are never copied.

Usage:
  python3 -I scripts/blind_prepare.py <candidate-id> [--blind-root DIR] [--force]
  python3 -I scripts/blind_prepare.py --seed <seed-slug> [--seed-root DIR] [--blind-root DIR] [--force]

The seed form creates ``~/ale-blind/seed-<slug>`` and is used to establish the
baseline that synthetic candidates are compared against. ``--seed-root``
defaults to ``$SEED_ROOT`` or ``~/下载/business_finance_extracted/business_finance``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BLIND_ROOT = Path.home() / "ale-blind"
DEFAULT_SEED_ROOT = Path(
    os.environ.get(
        "SEED_ROOT",
        str(Path.home() / "下载" / "business_finance_extracted" / "business_finance"),
    )
).expanduser()
FORBIDDEN_NAMES = ("answer", "gold", "reference", "expected")

TASK_HEADER = """# Blind Solver Task

You are an independent solver. Work only inside the current workspace.

- Inputs: `base/input`
- Outputs: `base/output`
- Do not read outside the workspace.
- Do not use the web.
- Do not look for a reference answer or evaluation artifacts.

## Task

"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_id", nargs="?")
    parser.add_argument("--seed", help="Use a seed task slug instead of a candidate id")
    parser.add_argument("--seed-root", type=Path, default=DEFAULT_SEED_ROOT)
    parser.add_argument("--blind-root", type=Path, default=DEFAULT_BLIND_ROOT)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_text(path: Path) -> bool:
    return path.suffix.lower() in {
        ".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".py", ".toml",
    }


def main() -> None:
    args = parse_args()
    if args.seed:
        task_root = args.seed_root.expanduser() / args.seed
        blind_id = f"seed-{args.seed}"
    else:
        if not args.candidate_id:
            raise SystemExit("provide a candidate id or --seed <slug>")
        task_root = ROOT / "candidates" / args.candidate_id
        blind_id = args.candidate_id
    blind = args.blind_root.expanduser().resolve() / blind_id

    if not task_root.is_dir():
        raise SystemExit(f"unknown task: {task_root}")
    if not (task_root / "base" / "input").is_dir():
        if args.seed:
            raise SystemExit(
                f"SEED_NOT_BLIND_TESTABLE: missing base/input: {task_root}"
            )
        raise SystemExit(f"missing base/input: {task_root}")
    if blind.exists():
        if not args.force:
            raise SystemExit(f"blind workspace already exists: {blind} (pass --force)")
        shutil.rmtree(blind)

    (blind / "base" / "output").mkdir(parents=True)
    shutil.copytree(task_root / "base" / "input", blind / "base" / "input")
    software = task_root / "base" / "software"
    if software.is_dir():
        shutil.copytree(software, blind / "base" / "software")
    (blind / ".dsh-home").mkdir()
    (blind / "run").mkdir()
    (blind / "eval").mkdir()

    card = json.loads((task_root / "task_card.json").read_text(encoding="utf-8"))
    must_do = card.get("agentMustDo", [])
    task_text = TASK_HEADER + card.get("taskPrompt", "")
    if must_do:
        task_text += "\n## Must do\n\n" + "\n".join(f"- {item}" for item in must_do) + "\n"
    (blind / "TASK.md").write_text(task_text, encoding="utf-8")

    patch_source = ROOT / "docker" / "blind-dsh" / "blind.patch.yml"
    if patch_source.is_file():
        shutil.copy2(patch_source, blind / "blind.patch.yml")

    warnings: list[str] = []
    files = [path for path in blind.rglob("*") if path.is_file()]
    for path in files:
        relative = path.relative_to(blind)
        lowered = relative.name.lower()
        if any(marker in lowered for marker in FORBIDDEN_NAMES):
            warnings.append(f"forbidden-looking filename: {relative}")
        if is_text(path):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for marker in (
                "positive_evidence",
                "expected_conclusion",
                "expected_decision",
                "expected_total_qualifying",
                "answer_key",
            ):
                if marker in text:
                    warnings.append(f"sensitive marker {marker!r} in {relative}")

    manifest = {
        "candidate_id": blind_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blind_root": str(blind),
        "source_task": str(task_root),
        "files": [
            {"path": str(path.relative_to(blind)), "sha256": sha256(path), "size": path.stat().st_size}
            for path in files
        ],
        "excluded": [
            "base/reference",
            "base/output (pre-existing)",
            "evidence",
            "verify",
            "review",
            "scripts",
            "source_pack",
            "candidate.json",
            "task_card.json",
        ],
        "warnings": warnings,
    }
    (blind / "blind_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"blind workspace: {blind}")
    print(f"files: {len(files)}")
    print(f"TASK.md: {blind / 'TASK.md'}")
    print(f"input tree: {blind / 'base' / 'input'}")
    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("leakage scan: clean")


if __name__ == "__main__":
    main()
