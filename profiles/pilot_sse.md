# Pilot: SSE seed task (2026-10-21)

Seed: `sse_northbound_programmatic_trading_01` (compliance, closed-book document forensics).

## Results

| Check | Result |
|---|---|
| Gold submission built from `answer_key.json` | score 1.0 |
| Mutated conclusion (`q1` No -> Yes) | score 0.667, rejected |
| Independent solver (fresh context, only `base/input`) | score 0.667 |
| Independent solver q1 | 1.0 |
| Independent solver q2 | 0.0 |
| Independent solver q3 | 1.0 |
| Generic factory evaluator on a replay of the seed | 1.0 |
| Factory mutation test (drop / scalar / structure) | 3/3 rejected |
| Factory evidence check | 0 errors |
| Factory difficulty check | distance 0.0 to anchor |

## Finding

The independent solver answered q2 with `No`, while the answer key expects `Unknown`:

> Question: "what are the specific numerical amounts of the flow fee and cancellation fee?"
> Solver: "No. ... The staged rules give no numerical amounts."
> Key: "Unknown. ... the rules ... do not provide specific numerical amounts."

The solver's reasoning is correct; the label is ambiguous because the task brief defines the
allowed labels but not their semantics. This is a real clarity defect in the seed task, not a model
failure.

## Fix applied to the factory

- `templates/task/document-forensics/base/input/task_brief.md.template` now defines:
  - `Yes` = source explicitly supports the proposition
  - `No` = source explicitly negates it or says the requirement does not apply
  - `Unknown` = source does not provide the requested value, or says it will be specified elsewhere
- `skills/ale-task-author/SKILL.md` requires label semantics for every closed-book label question.

## Conclusion

The evaluator, mutation gate, evidence gate, difficulty gate, and independent-solver gate all work.
The independent-solver gate is valuable: it surfaced a task-design ambiguity that the gold run and
mutation test could not detect. Keep it as a hard gate for every candidate.
