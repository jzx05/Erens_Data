# Pilot: bf-compliance-02 (2026-10-21)

Internal variant of `sse_northbound_programmatic_trading_01`. Same staged SSE source pack,
three new questions:

1. Exactly 20,000 daily order submissions/cancellations -> high-frequency? (Yes)
2. Public fund order-splitting exemption from Article 34 additional reporting? (No)
3. Numerical standard for "频繁瞬时撤单"? (Unknown)

## First independent solve

The solver answered all three conclusions correctly, but q1 scored 0 because its
`evidence_snippet` concatenated Article 33 and Article 46, which are not contiguous in the source.
The evaluator correctly rejected it as "not an exact excerpt from the cited visible source".

## Fix

- Task brief and task prompt now include an **Evidence Rule**:
  `evidence_snippet` must be one contiguous excerpt from one cited source; additional legal
  reasoning belongs in `answer_text`.
- The document-forensics template and `ale-task-author` skill require the same rule.
- The answer key keeps Article 33 as the positive evidence and records Article 46 as a separate
  evidence-ledger claim, so the human reviewer can see the full support chain.

## Deterministic gates after the fix

| Gate | Result |
|---|---|
| Schema | pass |
| Gold run | 1.0 |
| Mutation | 3/3 rejected |
| Evidence | 0 errors, 0 warnings |
| Difficulty | distance 1.6124 <= 2.0 |
| Dedup | text similarity 0.4786; internal source-hash overlap is a warning |

## Second independent solve

With the Evidence Rule in the prompt, a fresh solver scored **1.0**: all three conclusions,
citations, evidence excerpts, and English explanations passed. Review total: **100/100**;
recommendation **ACCEPT**; `human_signoff` is still `null` pending the user's decision.
