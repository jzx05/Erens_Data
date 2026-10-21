#!/usr/bin/env python3
"""Generic closed-book document-forensics evaluator.

Expected files:
  base/input/output_contract.json       # {"output_file": "research_answers.json", ...}
  base/input/document_manifest.json     # [{"doc_id": "...", "citation_aliases": [...]}]
  base/reference/answer_key.json        # {question_key: spec}
  base/reference/evaluator_documents.json  # {doc_id: full_text}
  <output_dir>/<output_file>            # submission

Each answer-key spec:
  expected_conclusion: "Yes" | "No" | "Unknown"
  accepted_citations: [alias, ...]
  accepted_doc_ids: [doc_id, ...]        # optional
  evidence_anchors: [exact substring, ...]
  positive_evidence: exact quote         # used by make_gold_output.py
  positive_answer_text: short English explanation

Prints one JSON object with a `score` in [0, 1].
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ALLOWED_CONCLUSIONS = {"yes", "no", "unknown"}
ASCII_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def default_root() -> Path:
    return Path(__file__).resolve().parent.parent


def normalize(text: str) -> str:
    normalized = text.strip().lower().replace("　", " ")
    for source, target in {
        "：": ":",
        "（": "(",
        "）": ")",
        "《": "",
        "》": "",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
    }.items():
        normalized = normalized.replace(source, target)
    return re.sub(r"\s+", "", normalized)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_citation_map(manifest: list[dict]) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for entry in manifest:
        doc_id = entry.get("doc_id")
        if not isinstance(doc_id, str):
            continue
        for alias in entry.get("citation_aliases", []):
            if isinstance(alias, str):
                mapping.setdefault(normalize(alias), set()).add(doc_id)
    return mapping


def looks_like_english_explanation(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return len(stripped) >= 20 and len(ASCII_WORD_RE.findall(stripped)) >= 3


def score_question(
    response: Any,
    spec: dict,
    citation_map: dict[str, set[str]],
    documents: dict[str, str],
) -> dict:
    breakdown = {
        "score": 0.0,
        "conclusion_correct": False,
        "citation_valid": False,
        "evidence_valid": False,
        "answer_text_valid": False,
        "notes": [],
    }
    if not isinstance(response, dict):
        breakdown["notes"].append("question payload is not an object")
        return breakdown

    conclusion = response.get("conclusion")
    if not isinstance(conclusion, str) or conclusion.strip().lower() not in ALLOWED_CONCLUSIONS:
        breakdown["notes"].append("conclusion is missing or invalid")
        return breakdown
    if conclusion.strip().lower() != str(spec["expected_conclusion"]).lower():
        breakdown["notes"].append("conclusion does not match the canonical answer")
        return breakdown
    breakdown["conclusion_correct"] = True

    citation = response.get("citation_document")
    if not isinstance(citation, str) or not citation.strip():
        breakdown["notes"].append("citation_document is missing")
        return breakdown
    normalized_citation = normalize(citation)
    accepted_aliases = {normalize(item) for item in spec.get("accepted_citations", [])}
    if normalized_citation not in accepted_aliases:
        breakdown["notes"].append("citation_document is not an accepted alias")
        return breakdown
    cited_doc_ids = citation_map.get(normalized_citation, set())
    accepted_doc_ids = set(spec.get("accepted_doc_ids", []))
    if not accepted_doc_ids:
        accepted_doc_ids = set(cited_doc_ids)
    doc_ids_to_check = cited_doc_ids & accepted_doc_ids if cited_doc_ids else accepted_doc_ids
    if not doc_ids_to_check:
        doc_ids_to_check = accepted_doc_ids
    breakdown["citation_valid"] = True

    evidence = response.get("evidence_snippet")
    if not isinstance(evidence, str) or not evidence.strip():
        breakdown["notes"].append("evidence_snippet is missing")
        return breakdown
    normalized_evidence = normalize(evidence)
    anchors = spec.get("evidence_anchors", [])
    if not all(normalize(anchor) in normalized_evidence for anchor in anchors if anchor):
        breakdown["notes"].append("evidence_snippet does not contain the required anchor text")
        return breakdown
    found = any(
        normalized_evidence in normalize(documents.get(doc_id, ""))
        for doc_id in doc_ids_to_check
        if documents.get(doc_id)
    )
    if not found:
        breakdown["notes"].append(
            "evidence_snippet is not an exact excerpt from the cited visible source"
        )
        return breakdown
    breakdown["evidence_valid"] = True

    answer_text = response.get("answer_text")
    if not looks_like_english_explanation(answer_text):
        breakdown["notes"].append("answer_text is missing or not a short English explanation")
        return breakdown
    breakdown["answer_text_valid"] = True
    breakdown["score"] = 1.0
    breakdown["notes"].append("accepted")
    return breakdown


def main() -> None:
    args = parse_args()
    root = (args.candidate_root or default_root()).resolve()
    output_dir = (args.output_dir or root / "base" / "output").resolve()
    input_dir = root / "base" / "input"
    reference_dir = root / "base" / "reference"

    contract = load_json(input_dir / "output_contract.json")
    output_file = contract.get("output_file", "research_answers.json")
    answer_key = load_json(reference_dir / "answer_key.json")
    documents = load_json(reference_dir / "evaluator_documents.json")
    manifest = load_json(input_dir / "document_manifest.json")

    submission_path = output_dir / output_file
    if not submission_path.is_file():
        print(json.dumps({"score": 0.0, "error": f"missing output file: {output_file}"}))
        return
    try:
        submission = load_json(submission_path)
    except json.JSONDecodeError as exc:
        print(json.dumps({"score": 0.0, "error": f"invalid JSON: {exc}"}))
        return
    if not isinstance(submission, dict):
        print(json.dumps({"score": 0.0, "error": "submission root is not an object"}))
        return

    required = list(answer_key.keys())
    missing = [key for key in required if key not in submission]
    if missing:
        print(json.dumps({"score": 0.0, "error": f"missing keys: {', '.join(missing)}"}))
        return

    citation_map = build_citation_map(manifest)
    per_question = {
        key: score_question(submission[key], spec, citation_map, documents)
        for key, spec in answer_key.items()
    }
    score = sum(item["score"] for item in per_question.values()) / len(answer_key)
    print(
        json.dumps(
            {
                "score": score,
                "question_scores": per_question,
                "all_required_keys_present": True,
                "unexpected_keys": sorted(set(submission) - set(required)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
