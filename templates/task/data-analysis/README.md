# Data-Analysis Task Template

Use this template for tasks where the solver must compute metrics from a small dataset and write
exact output files (CSV/TSV/JSON/Markdown).

## Layout to create

```
candidates/<id>/
  candidate.json
  task_card.json
  base/
    input/
      task_brief.md
      output_contract.json
      <dataset files>.csv
      runtime_env/            # optional: pyproject.toml, uv.lock
    reference/
      verification_contract.json
      gold/                   # exact gold output files
    software/README.md
  scripts/
    evaluate.py               # copy from this template
    make_gold_output.py       # copy from this template
  evidence/
    sources.jsonl
    evidence.jsonl
```

The factory-level `scripts/run_reference.py` drives `make_gold_output.py` and `evaluate.py`.

## verification_contract.json

```json
{
  "required_outputs": ["randomization_assignment.csv", "experiment_results.tsv", "experiment_report.md"],
  "tolerance": 1e-6,
  "table_outputs": [{"file": "experiment_results.tsv", "delimiter": "\t"}],
  "text_outputs": ["experiment_report.md"]
}
```

## Authoring order

1. Write the dataset and the exact output contract.
2. Write a reference solution that produces `base/reference/gold/`.
3. Run the reference solution and confirm it reproduces the gold exactly.
4. Write the evaluator contract and copy the template scripts.
5. Write `task_card.json` and `evidence/evidence.jsonl`.
6. Run the factory gates.

## Rules

- The gold files must be produced by an actual reference solution, not hand-written.
- State tolerances explicitly; do not hide floating-point matching rules.
- If a metric is undefined (for example a zero denominator), define the expected behavior in the
  contract and encode it in the evaluator.
- Do not leak the gold files or the reference solution into `base/input`.
