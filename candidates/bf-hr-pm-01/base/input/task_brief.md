# Employee Attrition and Headcount Analysis

Read `employees.csv`, `hr_policy.md`, and `output_contract.json`. Analyze calendar year 2025 and write `department_attrition.csv` and `attrition_report.json` under `base/output`.

Formulas and denominators:

- Department `attrition_pct = terminations in 2025 / average_headcount * 100`, where `average_headcount = (start_headcount + end_headcount) / 2` for that department.
- Overall `overall_attrition_pct = total 2025 terminations / overall average headcount * 100`, where the overall average headcount is `(sum of department start_headcount + sum of department end_headcount) / 2`.
- `replacement_cost_usd = annual_salary_usd * 1.5` for every 2025 termination.
- A regrettable termination has `performance_rating >= 4`.
- Engagement risk is an employee active on 2025-12-31 with `engagement_score < 0.4`.

A termination counts only when `termination_date` is within 2025-01-01..2025-12-31 inclusive. Round every percentage and USD amount to 2 decimals with ROUND_HALF_UP. Exact columns, keys, and sorting are in `hr_policy.md` and `output_contract.json`.
