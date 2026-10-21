# HR Attrition and Headcount Policy

## Analysis period

Calendar year 2025: 2025-01-01 through 2025-12-31 inclusive.

## Headcount definitions

- `start_headcount`: employees with `hire_date <= 2025-01-01` and (`termination_date` empty or `termination_date >= 2025-01-01`).
- `end_headcount`: employees with `hire_date <= 2025-12-31` and (`termination_date` empty or `termination_date > 2025-12-31`).
- `average_headcount = (start_headcount + end_headcount) / 2`.

## Terminations

A termination in 2025 is an employee whose `termination_date` falls in the range 2025-01-01 to 2025-12-31 inclusive. Terminations dated before 2025-01-01 or after 2025-12-31 are excluded from every 2025 metric.

## Metric definitions

- `attrition_pct = terminations in 2025 / average_headcount * 100`. If `average_headcount == 0`, report `0.00`.
- A regrettable termination is a 2025 termination with `performance_rating >= 4`.
- `replacement_cost_usd = annual_salary_usd * 1.5`, charged for every 2025 termination (regrettable or not).
- Engagement risk: an employee counted in `end_headcount` whose `engagement_score < 0.4`.

## Reporting conventions

- `department_attrition.csv` has one row per department present in `employees.csv`, sorted by `department` ascending.
- `attrition_report.json` reports `overall_attrition_pct = total 2025 terminations / overall average headcount * 100`, where the overall average headcount is `(sum of department start_headcount + sum of department end_headcount) / 2`.
- `departments` in the JSON is a list of objects `{"department": ..., "attrition_pct": ...}` sorted by `attrition_pct` descending, with ties broken by `department` ascending.
- `highest_attrition_department` is the department with the highest rounded `attrition_pct`; break ties with the lexicographically smallest department name.
- Round every percentage and every USD amount to 2 decimals with ROUND_HALF_UP. Headcounts are integers. Compute from unrounded values.
