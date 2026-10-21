#!/usr/bin/env python3
"""Validate a candidate task's structure, task card, and basic leakage checks.

Usage:
  python3 -I scripts/validate_task.py candidates/<id> [--json]

Exit code 0 when there are no errors, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_CARD_FIELDS = [
    "taskId",
    "title",
    "summary",
    "category",
    "software",
    "taskPrompt",
    "inputFiles",
    "referenceFiles",
    "evaluation",
    "vm",
    "taxonomy",
]

REQUIRED_DIRS = ["base/input", "base/reference"]
REQUIRED_FILES = ["candidate.json", "task_card.json", "scripts/evaluate.py"]
EVIDENCE_FILES = ["evidence/sources.jsonl", "evidence/evidence.jsonl"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.is_file():
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return records


def resolve_declared_path(root: Path, declared: str) -> Path | None:
    candidates = [
        root / declared,
        root / "base" / declared,
        root / "base" / "input" / declared,
        root / "base" / "reference" / declared,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def text_files_under(root: Path) -> list[Path]:
    suffixes = {".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".py"}
    if not root.is_dir():
        return []
    return [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes]


def is_source_material(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool(parts & {"source_documents", "extracted_text", "source_pack", "sources"})


def sensitive_strings(value, key: str = "") -> list[str]:
    """Collect answer-like strings, excluding question/prompt/citation text."""
    lowered = key.lower()
    if any(marker in lowered for marker in ("question", "prompt", "citation", "alias")):
        return []
    sensitive_key = any(
        marker in lowered
        for marker in ("answer", "conclusion", "evidence", "positive", "solution", "gold", "correct", "expected")
    )
    found: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            found.extend(sensitive_strings(child, str(child_key)))
    elif isinstance(value, list):
        for child in value:
            found.extend(sensitive_strings(child, key))
    elif isinstance(value, str) and sensitive_key and len(value.strip()) >= 20:
        found.append(value.strip())
    return found


def leakage_warnings(root: Path) -> list[str]:
    warnings: list[str] = []
    reference = root / "base" / "reference"
    input_dir = root / "base" / "input"
    input_paths = [path for path in text_files_under(input_dir) if not is_source_material(path)]
    for ref_path in text_files_under(reference):
        try:
            ref_text = ref_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        snippets: list[str] = []
        if ref_path.suffix.lower() == ".json":
            try:
                snippets = sensitive_strings(json.loads(ref_text))
            except json.JSONDecodeError:
                snippets = []
        if not snippets:
            snippets = [line.strip() for line in ref_text.splitlines() if len(line.strip()) >= 40]
        snippets = list(dict.fromkeys(snippets))
        for input_path in input_paths:
            try:
                input_text = input_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hits = [snippet for snippet in snippets if snippet in input_text]
            if hits:
                warnings.append(
                    f"possible leakage: {ref_path.relative_to(root)} answer-like content appears in "
                    f"{input_path.relative_to(root)} ({len(hits)} item(s))"
                )
                break
    for input_path in input_paths:
        name = input_path.name.lower()
        if "answer" in name or "gold" in name or "reference" in name:
            warnings.append(f"suspicious input filename: {input_path.relative_to(root)}")
    return warnings


def main() -> int:
    args = parse_args()
    root = args.candidate.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not root.is_dir():
        errors.append(f"candidate directory does not exist: {root}")
    for rel in REQUIRED_DIRS:
        if not (root / rel).is_dir():
            errors.append(f"missing directory: {rel}")
    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            errors.append(f"missing file: {rel}")
    for rel in EVIDENCE_FILES:
        if not (root / rel).is_file():
            warnings.append(f"missing evidence file: {rel} (required before REVIEWED)")

    card = None
    card_path = root / "task_card.json"
    if card_path.is_file():
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"task_card.json is invalid JSON: {exc}")
    if isinstance(card, dict):
        for field in REQUIRED_CARD_FIELDS:
            if field not in card:
                errors.append(f"task_card.json missing field: {field}")
        for field in ("inputFiles", "referenceFiles"):
            entries = card.get(field, [])
            if not isinstance(entries, list):
                errors.append(f"task_card.json field {field} must be a list")
                continue
            for entry in entries:
                declared = entry.get("path") if isinstance(entry, dict) else None
                if not declared:
                    errors.append(f"task_card.json {field} entry missing path")
                    continue
                if resolve_declared_path(root, declared) is None:
                    if field == "referenceFiles":
                        warnings.append(
                            f"declared reference output does not exist yet: {declared}"
                        )
                    else:
                        errors.append(f"declared {field} path does not exist: {declared}")
        prompt = card.get("taskPrompt", "")
        if isinstance(prompt, str) and len(prompt) < 80:
            errors.append("task_card.json taskPrompt is suspiciously short")
    elif card is not None:
        errors.append("task_card.json root must be an object")

    candidate_path = root / "candidate.json"
    if candidate_path.is_file():
        try:
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            for field in ("id", "status", "stratum", "seed_refs"):
                if field not in candidate:
                    errors.append(f"candidate.json missing field: {field}")
        except json.JSONDecodeError as exc:
            errors.append(f"candidate.json is invalid JSON: {exc}")

    input_dir = root / "base" / "input"
    reference_dir = root / "base" / "reference"
    if input_dir.is_dir() and not any(input_dir.rglob("*")):
        errors.append("base/input is empty")
    if reference_dir.is_dir() and not any(reference_dir.rglob("*")):
        errors.append("base/reference is empty")

    try:
        for rel in EVIDENCE_FILES:
            if (root / rel).is_file():
                read_jsonl(root / rel)
    except ValueError as exc:
        errors.append(str(exc))

    warnings.extend(leakage_warnings(root))

    report = {
        "candidate": str(root),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }
    if (root / "candidate.json").is_file():
        (root / "verify").mkdir(exist_ok=True)
        (root / "verify" / "schema.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{'PASS' if report['ok'] else 'FAIL'} {root}")
        for error in errors:
            print(f"  ERROR {error}")
        for warning in warnings:
            print(f"  WARN  {warning}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
