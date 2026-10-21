# Document-Forensics Task Template

Use this template for closed-book tasks that require extracting facts from staged documents and
returning a structured JSON answer with exact citations.

## Layout to create

```
candidates/<id>/
  candidate.json
  task_card.json
  base/
    input/
      task_brief.md                 # scenario + questions + closed-book rule
      question_set.json             # structured questions
      output_contract.json          # output filename + field contract
      document_manifest.json        # doc_id -> citation aliases + filename
      source_documents/             # original files (docx/xlsx/pdf)
      extracted_text/               # UTF-8 text mirrors (preferred for agents)
    reference/
      answer_key.json               # canonical answers + anchors + positive evidence
      evaluator_documents.json      # doc_id -> full text used for quote verification
      verification_contract.json    # hard checks
    software/README.md
  scripts/
    evaluate.py                     # copy from this template
    make_gold_output.py             # copy from this template
  evidence/
    sources.jsonl
    evidence.jsonl
```

The factory-level `scripts/run_reference.py` drives `make_gold_output.py` and `evaluate.py`; the
candidate does not need its own `run_reference.py`.

## Authoring order

1. Collect sources and write `evidence/sources.jsonl`.
2. Write `base/reference/answer_key.json` and `base/reference/evaluator_documents.json`.
3. Write `base/input/*` and `base/input/extracted_text/*`.
4. Copy `evaluate.py` and `make_gold_output.py`; adapt the output filename if needed.
5. Write `task_card.json` from the template; derive the prompt from the gold and contract.
6. Write `evidence/evidence.jsonl` with one claim per question and the exact quote.
7. Run:
   ```bash
   python3 -I scripts/validate_task.py candidates/<id>
   python3 -I scripts/run_reference.py candidates/<id>
   python3 -I scripts/mutation_test.py candidates/<id>
   python3 -I scripts/evidence_check.py candidates/<id>
   ```

## Rules

- The answer key and evaluator documents are evaluator-controlled; never put them in `base/input`.
- Each accepted citation must be an alias in `document_manifest.json`.
- Each evidence snippet must be an exact excerpt from `evaluator_documents.json`.
- The answer text must be a short English explanation (this matches the seed family).
- Do not leak the answer in `task_brief.md` or `question_set.json`.
