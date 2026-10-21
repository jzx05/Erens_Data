#!/usr/bin/env python3
"""Build candidate bf-compliance-02 from the SSE seed source pack.

This is an internal-only variant: it reuses the staged SSE documents but asks a
new set of questions. It never modifies the seed task.

Usage:
  python3 -I scripts/build_bf_compliance_02.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = (
    Path.home()
    / "下载"
    / "business_finance_extracted"
    / "business_finance"
    / "sse_northbound_programmatic_trading_01"
)
CANDIDATE_ID = "bf-compliance-02"
CAND = ROOT / "candidates" / CANDIDATE_ID
TEMPLATE = ROOT / "templates" / "task" / "document-forensics"

Q1 = (
    "A client's single account reached exactly 20,000 order submissions and cancellations in one "
    "trading day, but never reached 300 in any single second. Under the staged rules, does the "
    "account meet the high-frequency trading definition?"
)
Q2 = (
    "A public fund manager uses a pre-set order-splitting algorithm solely to reduce the market "
    "impact of large orders and to ensure fair execution across portfolios. It has already "
    "submitted the report required by Article 9. Must it also report the additional high-frequency "
    "information listed in Article 34 (server location, test report, emergency plan)?"
)
Q3 = (
    "A client asks for the specific numerical threshold for \"频繁瞬时撤单\" (frequent instant "
    "cancellation) — a specific cancellation ratio or count. Do the staged rules provide that "
    "number?"
)

Q1_EVIDENCE = (
    "第三十三条 投资者交易行为存在下列情形之一的，属于高频交易：\n"
    "（一）单个账户每秒申报、撤单的最高笔数达到300笔以上；\n"
    "（二）单个账户单日申报、撤单的最高笔数达到20000笔以上；\n"
    "（三）本所认定的其他情形。"
)
Q1_INCLUSIVE_EVIDENCE = "第四十六条 本细则所称“以上”包含本数。"
Q2_EVIDENCE = (
    "投资者以减少大额订单对市场冲击或者保障不同投资组合交易公平性为目的,在交易环节按照设定的"
    "拆单算法自动执行交易指令，且已按照本细则第九条规定履行报告义务的，不适用前款要求。前述"
    "投资者包括公募基金管理人及其子公司、从事资产管理业务的会员、合格境外投资者及本所认定的"
    "其他投资者。"
)
Q3_EVIDENCE = (
    "（二）频繁瞬时撤单，是指日内频繁出现申报后迅速撤单、全日撤单比例较高，即全日发生多次"
    "1秒钟内申报又撤单的情形，且全日撤单比例达到一定标准；"
)

ANSWER_KEY = {
    "q1_daily_order_threshold": {
        "question": Q1,
        "expected_conclusion": "Yes",
        "accepted_citations": ["上海证券交易所程序化交易管理实施细则"],
        "accepted_doc_ids": ["doc_08"],
        "evidence_anchors": ["单个账户单日申报、撤单的最高笔数达到20000笔以上"],
        "positive_evidence": Q1_EVIDENCE,
        "positive_answer_text": (
            "Yes. Article 33(2) defines high-frequency trading as a single account reaching 20,000 "
            "or more daily order submissions and cancellations; Article 46 provides that “以上” "
            "includes the stated number."
        ),
    },
    "q2_order_splitting_exemption": {
        "question": Q2,
        "expected_conclusion": "No",
        "accepted_citations": ["上海证券交易所程序化交易管理实施细则"],
        "accepted_doc_ids": ["doc_08"],
        "evidence_anchors": ["不适用前款要求"],
        "positive_evidence": Q2_EVIDENCE,
        "positive_answer_text": (
            "No. Article 34(2) exempts investors, including public fund managers, that use an "
            "order-splitting algorithm for those purposes and have already reported under Article "
            "9 from the additional high-frequency reporting."
        ),
    },
    "q3_cancellation_ratio_standard": {
        "question": Q3,
        "expected_conclusion": "Unknown",
        "accepted_citations": ["上海证券交易所程序化交易管理实施细则"],
        "accepted_doc_ids": ["doc_08"],
        "evidence_anchors": ["全日撤单比例达到一定标准"],
        "positive_evidence": Q3_EVIDENCE,
        "positive_answer_text": (
            "Unknown. Article 18(2) describes the behavior and refers to “达到一定标准” but does "
            "not state a specific cancellation ratio or count."
        ),
    },
}

TASK_PROMPT = f"""You are a compliance analyst at a mainland securities firm's programmatic trading
desk. A client relationship manager has forwarded three questions from clients. Answer them using
only the staged Shanghai Stock Exchange materials.

## Closed-Book Rule

- Use only the staged materials under `base/input`.
- Do not use outside web search or external regulatory knowledge.

## Inputs

- Task brief: `base/input/task_brief.md`
- Question set: `base/input/question_set.json`
- Output contract: `base/input/output_contract.json`
- Document manifest: `base/input/document_manifest.json`
- Original source files: `base/input/source_documents`
- Extracted UTF-8 text mirrors: `base/input/extracted_text`

## Questions

1. {Q1}
2. {Q2}
3. {Q3}

## Deliverable

Write exactly one JSON file here:

- `base/output/research_answers.json`

Each top-level question key must contain:

- `conclusion`: exactly `Yes`, `No`, or `Unknown`
- `citation_document`: the accepted Simplified Chinese source document name
- `evidence_snippet`: an exact Chinese excerpt copied from the staged source
- `answer_text`: a short English explanation

## Evidence Rule

- `evidence_snippet` must be a single contiguous excerpt copied from one cited source.
- Do not concatenate non-adjacent clauses, sections, or articles. Put additional legal reasoning in
  `answer_text`.

## Label Semantics

- `Yes`: the staged source explicitly supports the proposition.
- `No`: the staged source explicitly negates the proposition, or explicitly states that the
  requested permission/requirement does not apply.
- `Unknown`: the staged source does not provide the requested information, or says the value/rule
  will be specified elsewhere. Do not use `No` merely because a number or detail is absent.
"""

TASK_BRIEF = f"""# SSE Programmatic Trading Compliance Review

You are a compliance analyst at a mainland securities firm's programmatic trading desk. The client
relationship manager has forwarded three questions from clients. Answer them using only the staged
Shanghai Stock Exchange materials.

## Closed-Book Rule

- Use only the staged materials under `base/input`.
- Do not use outside web search or external regulatory knowledge.

## Inputs

- Question set: `base/input/question_set.json`
- Output contract: `base/input/output_contract.json`
- Document manifest: `base/input/document_manifest.json`
- Original source files: `base/input/source_documents`
- Extracted UTF-8 text mirrors: `base/input/extracted_text`

## Questions

1. {Q1}
2. {Q2}
3. {Q3}

## Deliverable

Write exactly one JSON file to `base/output/research_answers.json`.

Each top-level question key must contain:

- `conclusion`: exactly `Yes`, `No`, or `Unknown`
- `citation_document`: the accepted Simplified Chinese source document name
- `evidence_snippet`: an exact Chinese excerpt copied from the staged source
- `answer_text`: a short English explanation

## Evidence Rule

- `evidence_snippet` must be a single contiguous excerpt copied from one cited source.
- Do not concatenate non-adjacent clauses, sections, or articles. Put additional legal reasoning in
  `answer_text`.

## Label Semantics

- `Yes`: the staged source explicitly supports the proposition.
- `No`: the staged source explicitly negates the proposition, or explicitly states that the
  requested permission/requirement does not apply.
- `Unknown`: the staged source does not provide the requested information, or says the value/rule
  will be specified elsewhere. Do not use `No` merely because a number or detail is absent.
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if CAND.exists():
        if not args.force:
            raise SystemExit(f"candidate already exists: {CAND} (pass --force to rebuild)")
        shutil.rmtree(CAND)
    for relative in ("base/input", "base/reference", "base/software", "scripts", "evidence"):
        (CAND / relative).mkdir(parents=True, exist_ok=True)

    shutil.copytree(SEED / "base/input/source_documents", CAND / "base/input/source_documents")
    shutil.copytree(SEED / "base/input/extracted_text", CAND / "base/input/extracted_text")
    shutil.copy2(
        SEED / "base/input/document_manifest.json",
        CAND / "base/input/document_manifest.json",
    )
    shutil.copy2(
        SEED / "base/reference/evaluator_documents.json",
        CAND / "base/reference/evaluator_documents.json",
    )
    software = SEED / "base/software"
    if software.is_dir():
        shutil.copytree(software, CAND / "base/software", dirs_exist_ok=True)
    shutil.copy2(TEMPLATE / "scripts/evaluate.py", CAND / "scripts/evaluate.py")
    shutil.copy2(TEMPLATE / "scripts/make_gold_output.py", CAND / "scripts/make_gold_output.py")

    write_json(
        CAND / "candidate.json",
        {
            "id": CANDIDATE_ID,
            "status": "AUTHORED",
            "stratum": "compliance",
            "seed_anchor": "sse_northbound_programmatic_trading_01",
            "seed_refs": [
                "sse_northbound_programmatic_trading_01",
                "legal_ma_consistency_audit_01",
            ],
            "difficulty_target": 100.0,
            "task_family": "document-forensics",
            "source_policy": "internal_only",
            "internal_only": True,
            "variant_of": "sse_northbound_programmatic_trading_01",
            "attempts": 0,
            "reason_codes": [],
            "paths": {},
        },
    )

    task_id = "business_finance/sse_programmatic_trading_compliance_02"
    write_json(
        CAND / "task_card.json",
        {
            "taskId": task_id,
            "title": "SSE Programmatic Trading Compliance Review",
            "summary": (
                "Answer three closed-book questions about the high-frequency trading threshold, "
                "the order-splitting exemption, and the undefined frequent-cancellation standard "
                "using staged Shanghai Stock Exchange rules."
            ),
            "category": "business_finance",
            "software": ["Python"],
            "taskPrompt": TASK_PROMPT,
            "agentMustDo": [
                "Read the staged task brief, question set, output contract, document manifest, and extracted-text mirrors.",
                "Answer all three questions using only the staged SSE materials.",
                "Write exactly one JSON file to `base/output/research_answers.json`.",
                "For each question, provide a Yes/No/Unknown conclusion, an accepted Chinese citation, an exact Chinese evidence excerpt, and a short English explanation.",
                "Apply the stated label semantics, especially for Unknown.",
            ],
            "inputFiles": [
                {
                    "name": "task_brief.md",
                    "format": "Markdown",
                    "path": "input/task_brief.md",
                    "description": "Scenario, questions, closed-book rule, and label semantics.",
                },
                {
                    "name": "question_set.json",
                    "format": "JSON",
                    "path": "input/question_set.json",
                    "description": "Structured questions and allowed conclusion labels.",
                },
                {
                    "name": "output_contract.json",
                    "format": "JSON",
                    "path": "input/output_contract.json",
                    "description": "Required output filename and per-question fields.",
                },
                {
                    "name": "document_manifest.json",
                    "format": "JSON",
                    "path": "input/document_manifest.json",
                    "description": "Maps staged Chinese source files to citation aliases.",
                },
                {
                    "name": "source_documents",
                    "format": "DOCX/XLSX directory",
                    "path": "input/source_documents",
                    "description": "The ten original staged Shanghai Stock Exchange source files.",
                },
                {
                    "name": "extracted_text",
                    "format": "UTF-8 text directory",
                    "path": "input/extracted_text",
                    "description": "Search-friendly text mirrors of the staged Chinese source files.",
                },
            ],
            "referenceFiles": [
                {
                    "name": "research_answers.json",
                    "format": "JSON",
                    "path": "output/research_answers.json",
                    "description": "Required structured answer file containing all three responses.",
                }
            ],
            "evaluation": (
                "Hard gates: missing output file, invalid JSON root, missing required question "
                "keys, or missing per-question fields. For each question, check the conclusion "
                "against the canonical answer, the citation against accepted Chinese aliases, the "
                "evidence snippet against the cited visible source and its required anchors, and "
                "the presence of a short English explanation. Give 1.0 only when all checks pass, "
                "then average the three question scores."
            ),
            "vm": {
                "machineType": "c4-standard-4",
                "snapshot": "cpu-free-ubuntu",
                "timeout": 7200,
            },
            "taxonomy": {
                "domain_id": "6",
                "domain_code": "business_finance",
                "subdomain_id": "6.4",
                "subdomain_code": "compliance",
                "subdomain_name": "Compliance & Regulatory",
                "classifier": {
                    "model": "manual",
                    "classified_at": "2026-10-21T00:00:00Z",
                    "source": {
                        "submission_id": "factory",
                        "fields": ["taskPrompt", "title", "summary", "software"],
                        "mode": "manual",
                    },
                    "rationale": "The task applies Shanghai Stock Exchange programmatic-trading rules to client compliance questions.",
                },
            },
            "requiredSystemPackages": [],
        },
    )

    write_json(
        CAND / "base/input/question_set.json",
        {
            "questions": [
                {
                    "key": "q1_daily_order_threshold",
                    "question": Q1,
                    "allowed_conclusions": ["Yes", "No", "Unknown"],
                },
                {
                    "key": "q2_order_splitting_exemption",
                    "question": Q2,
                    "allowed_conclusions": ["Yes", "No", "Unknown"],
                },
                {
                    "key": "q3_cancellation_ratio_standard",
                    "question": Q3,
                    "allowed_conclusions": ["Yes", "No", "Unknown"],
                },
            ]
        },
    )

    write_json(
        CAND / "base/input/output_contract.json",
        {
            "output_file": "research_answers.json",
            "output_dir": "base/output",
            "top_level_keys": [
                "q1_daily_order_threshold",
                "q2_order_splitting_exemption",
                "q3_cancellation_ratio_standard",
            ],
            "per_question_fields": {
                "conclusion": "exactly one of Yes, No, Unknown",
                "citation_document": "accepted Chinese citation alias from document_manifest.json",
                "evidence_snippet": "exact Chinese excerpt copied from the staged source",
                "answer_text": "short English explanation",
            },
        },
    )

    (CAND / "base/input/task_brief.md").write_text(TASK_BRIEF, encoding="utf-8")
    write_json(CAND / "base/reference/answer_key.json", ANSWER_KEY)
    write_json(
        CAND / "base/reference/verification_contract.json",
        {
            "task_id": task_id,
            "variant_name": "base",
            "required_outputs": ["research_answers.json"],
            "hard_checks": [
                "all required question keys present",
                "each conclusion matches the canonical answer",
                "each citation is an accepted alias in the document manifest",
                "each evidence snippet is an exact excerpt from the cited source",
                "each evidence snippet contains its required anchor text",
                "each answer_text is a short English explanation",
                "score is 1.0 only when every question passes all checks",
            ],
        },
    )

    manifest = json.loads((CAND / "base/input/document_manifest.json").read_text(encoding="utf-8"))
    with (CAND / "evidence/sources.jsonl").open("w", encoding="utf-8") as handle:
        for entry in manifest:
            source_path = CAND / "base/input" / entry["staged_source_path"]
            record = {
                "source_id": entry["doc_id"],
                "title": entry.get("original_filename", entry["doc_id"]),
                "publisher": "Shanghai Stock Exchange (seed task source)",
                "local_path": "base/input/" + entry["staged_source_path"],
                "text_path": "base/input/" + entry["staged_extract_path"],
                "retrieved_at": "2026-10-21T00:00:00Z",
                "license": "seed task source document, internal use only",
                "redistributable": False,
                "sha256": sha256(source_path) if source_path.is_file() else None,
                "locators": [entry["staged_extract_path"]],
                "notes": "Internal variant of the SSE seed source pack.",
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    evidence = [
        (
            "q1_daily_order_threshold",
            Q1_EVIDENCE,
            "third article 33",
        ),
        (
            "q1_threshold_inclusive",
            Q1_INCLUSIVE_EVIDENCE,
            "article 46",
        ),
        (
            "q2_order_splitting_exemption",
            Q2_EVIDENCE,
            "article 34 paragraph 2",
        ),
        (
            "q3_cancellation_ratio_standard",
            Q3_EVIDENCE,
            "article 18 item 2",
        ),
    ]
    with (CAND / "evidence/evidence.jsonl").open("w", encoding="utf-8") as handle:
        for claim_id, quote, locator in evidence:
            record = {
                "claim_id": claim_id,
                "source_id": "doc_08",
                "locator": f"base/input/extracted_text/程序化交易管理实施细则.txt ({locator})",
                "exact_quote": quote,
                "used_in": ["task_card.json", "base/reference/answer_key.json"],
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"built {CAND}")
    print(f"  task_card: {CAND / 'task_card.json'}")
    print(f"  answer_key: {CAND / 'base/reference/answer_key.json'}")
    print(f"  source docs: {len(list((CAND / 'base/input/source_documents').iterdir()))}")
    print(f"  evidence claims: {len(evidence)}")


if __name__ == "__main__":
    main()
