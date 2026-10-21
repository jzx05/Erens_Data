# SSE Programmatic Trading Compliance Review

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

1. A client's single account reached exactly 20,000 order submissions and cancellations in one trading day, but never reached 300 in any single second. Under the staged rules, does the account meet the high-frequency trading definition?
2. A public fund manager uses a pre-set order-splitting algorithm solely to reduce the market impact of large orders and to ensure fair execution across portfolios. It has already submitted the report required by Article 9. Must it also report the additional high-frequency information listed in Article 34 (server location, test report, emergency plan)?
3. A client asks for the specific numerical threshold for "频繁瞬时撤单" (frequent instant cancellation) — a specific cancellation ratio or count. Do the staged rules provide that number?

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
