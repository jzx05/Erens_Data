#!/usr/bin/env python3
"""Verify the source and evidence ledgers.

Checks:
  - required source fields and license/redistribution metadata
  - local file existence and optional sha256
  - every evidence quote is present in the cited source text
  - every used_in path exists

Usage:
  python3 -I scripts/evidence_check.py candidates/<id>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".xml", ".html"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return records


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_text(root: Path, source: dict) -> tuple[Path | None, str]:
    for key in ("text_path", "local_path"):
        value = source.get(key)
        if not isinstance(value, str) or not value:
            continue
        path = (root / value).resolve()
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            return path, path.read_text(encoding="utf-8", errors="replace")
    source_id = source.get("source_id", "")
    for candidate in (
        root / "source_pack" / f"{source_id}.txt",
        root / "source_pack" / f"{source_id}.md",
    ):
        if candidate.is_file():
            return candidate, candidate.read_text(encoding="utf-8", errors="replace")
    return None, ""


def main() -> int:
    args = parse_args()
    root = args.candidate.expanduser().resolve()
    sources_path = root / "evidence" / "sources.jsonl"
    evidence_path = root / "evidence" / "evidence.jsonl"
    errors: list[str] = []
    warnings: list[str] = []

    try:
        sources = read_jsonl(sources_path)
        evidence = read_jsonl(evidence_path)
    except ValueError as exc:
        raise SystemExit(str(exc))

    if not sources:
        errors.append("no sources recorded")
    if not evidence:
        errors.append("no evidence recorded")

    source_map: dict[str, dict] = {}
    for index, source in enumerate(sources, 1):
        source_id = source.get("source_id")
        if not source_id:
            errors.append(f"source #{index}: missing source_id")
            continue
        source_map[source_id] = source
        for field in ("title", "license"):
            if not source.get(field):
                errors.append(f"source {source_id}: missing {field}")
        if "redistributable" not in source:
            errors.append(f"source {source_id}: missing redistributable")
        if not any(source.get(key) for key in ("url", "local_path", "text_path")):
            errors.append(f"source {source_id}: need url, local_path, or text_path")
        local_path = source.get("local_path")
        if local_path:
            path = (root / local_path).resolve()
            if not path.is_file():
                errors.append(f"source {source_id}: local_path missing: {local_path}")
            elif source.get("sha256") and sha256(path) != source["sha256"]:
                errors.append(f"source {source_id}: sha256 mismatch")
        if (
            source.get("redistributable") is False
            and isinstance(local_path, str)
            and local_path.startswith("source_pack/")
        ):
            warnings.append(
                f"source {source_id}: non-redistributable source is copied into source_pack"
            )

    for index, item in enumerate(evidence, 1):
        claim_id = item.get("claim_id") or f"evidence #{index}"
        source_id = item.get("source_id")
        quote = item.get("exact_quote")
        locator = item.get("locator")
        if not source_id:
            errors.append(f"{claim_id}: missing source_id")
            continue
        source = source_map.get(source_id)
        if source is None:
            errors.append(f"{claim_id}: unknown source_id {source_id}")
            continue
        if not quote or not isinstance(quote, str):
            errors.append(f"{claim_id}: missing exact_quote")
            continue
        if not locator:
            errors.append(f"{claim_id}: missing locator")
        text_path, text = source_text(root, source)
        if not text:
            warnings.append(
                f"{claim_id}: source {source_id} has no text mirror; quote not machine-checked"
            )
        else:
            if quote not in text and normalize(quote) not in normalize(text):
                errors.append(
                    f"{claim_id}: quote not found in {text_path.relative_to(root)} "
                    f"(source {source_id})"
                )
        used_in = item.get("used_in", [])
        if not isinstance(used_in, list) or not used_in:
            warnings.append(f"{claim_id}: no used_in paths")
        else:
            for rel in used_in:
                if not (root / rel).exists():
                    errors.append(f"{claim_id}: used_in path does not exist: {rel}")

    report = {
        "candidate": str(root),
        "sources": len(sources),
        "evidence": len(evidence),
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    (root / "verify").mkdir(exist_ok=True)
    (root / "verify" / "evidence.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
