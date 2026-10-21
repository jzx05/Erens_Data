# American Option Pricing with a Cox-Ross-Rubinstein Binomial Tree

## Role and objective

You are a quantitative analyst on a derivatives desk. Price a physically settled American put
option with a recombining Cox-Ross-Rubinstein (CRR) binomial tree for one base case and a grid of
eight stress scenarios. Report the price, Delta, Gamma, intrinsic value, and early-exercise
premium for every scenario, plus a base-case summary.

## Inputs

| File | Contents |
|---|---|
| `base/input/option_terms.json` | Base-case option terms (one JSON object). |
| `base/input/scenario_grid.csv` | Scenario overrides with columns `scenario_id,spot,volatility,steps`. |
| `base/input/output_contract.json` | Exact output file names, columns, keys, and formats. |
| `base/input/runtime_env/pyproject.toml` | Runtime declaration. |

All inputs are UTF-8. The task is closed-book: use only the staged files and the Python 3.12
standard library (`math`, `csv`, `json`, `decimal`). Do not use external market data, financial
libraries, or any reference output from another task.

## Base-case terms

`option_terms.json` is a single JSON object with exactly these fields:

- `underlying` (string) — synthetic instrument identifier.
- `option_type` (string) — the value is `"put"`.
- `spot` (number) — base-case spot price S0.
- `strike` (number) — strike price K.
- `risk_free_rate` (number) — continuously compounded annual rate r, expressed as a decimal
  (0.045 means 4.5% per year).
- `volatility` (number) — annualised volatility sigma, expressed as a decimal.
- `maturity_years` (number) — time to expiry T in years.
- `steps` (number) — number of CRR time steps N; integer-valued and at least 2.
- `dividend_yield` (number) — continuously compounded annual dividend yield q, expressed as a
  decimal.

## Scenario grid

`scenario_grid.csv` has exactly the header `scenario_id,spot,volatility,steps` followed by eight
data rows. Each data row overrides `spot`, `volatility`, and `steps` for that scenario. Every
other term — `strike`, `risk_free_rate`, `maturity_years`, `dividend_yield`, and `option_type` —
is inherited unchanged from `option_terms.json`.

## CRR model specification (exact)

For a valuation with spot S0, strike K, annual rate r, volatility sigma, maturity T, integer step
count N, and continuous dividend yield q, define:

- `dt = T / N`
- `u = exp(sigma * sqrt(dt))`
- `d = 1 / u`
- `p = (exp((r - q) * dt) - d) / (u - d)`
- `df = exp(-r * dt)`

Node `(n, j)` for `0 <= j <= n <= N` has spot `S(n, j) = S0 * u^j * d^(n - j)`.

### American tree

Terminal values at `n = N`:

- `V(N, j) = max(K - S(N, j), 0)`

Backward induction for `n = N-1, N-2, ..., 0` and `0 <= j <= n`:

- continuation `C(n, j) = df * (p * V(n+1, j+1) + (1 - p) * V(n+1, j))`
- exercise `E(n, j) = max(K - S(n, j), 0)`
- `V(n, j) = max(C(n, j), E(n, j))`

The American price is `V(0, 0)`. Early exercise is allowed at every node, including the root.

### European benchmark and early-exercise premium

Compute a second tree with the same `dt`, `u`, `d`, `p`, and `df`, and the same terminal payoff
`E(N, j) = max(K - S(N, j), 0)`, but with no early-exercise max at intermediate nodes:

- `B(n, j) = df * (p * B(n+1, j+1) + (1 - p) * B(n+1, j))` for `n = N-1, ..., 0`

The European price is `B(0, 0)`. Define `early_exercise_premium = V(0, 0) - B(0, 0)`.

### Delta and Gamma

Using the American-tree node values (not the European tree):

- `Delta = (V(1, 1) - V(1, 0)) / (S(1, 1) - S(1, 0))`
- `Gamma = [ (V(2, 2) - V(2, 1)) / (S(2, 2) - S(2, 1)) - (V(2, 1) - V(2, 0)) / (S(2, 1) - S(2, 0)) ] / (0.5 * (S(2, 2) - S(2, 0)))`

Because `d = 1 / u`, `S(2, 1) = S0`.

## Outputs

Write exactly two files in the output directory (`base/output`). Do not add extra files.

### 1. `pricing_results.csv`

The header must contain exactly these six column names, in this order:
`scenario_id`, `price`, `delta`, `gamma`, `intrinsic_value`, `early_exercise_premium`.

One data row per scenario, in the same order as `scenario_grid.csv`.

- `scenario_id` — copied verbatim from the grid.
- `price` — American CRR price `V(0, 0)`.
- `delta` — Delta as defined above.
- `gamma` — Gamma as defined above.
- `intrinsic_value` — `max(K - spot, 0)`, using the scenario spot and the base-case strike.
- `early_exercise_premium` — American price minus the European price from the same tree.

### 2. `summary.json`

A single JSON object with exactly these five keys:

```json
{
  "base_case_price": <number>,
  "base_case_delta": <number>,
  "base_case_gamma": <number>,
  "scenario_count": <integer>,
  "highest_price_scenario": "<scenario_id>"
}
```

- The three `base_case_*` values use the parameters in `option_terms.json` exactly; they are not
  taken from any scenario row.
- `scenario_count` is the number of data rows in `scenario_grid.csv`.
- `highest_price_scenario` is the `scenario_id` with the largest price after rounding to 4 decimal
  places. If two or more scenarios tie on the rounded price, choose the one that appears first in
  `scenario_grid.csv`.

## Rounding and formatting

Round every numeric output value — price, delta, gamma, intrinsic value, early-exercise premium,
and the three base-case summary values — to exactly 4 decimal places using round-half-up (ties
away from zero). Do not round intermediate computations; round only the final reported values.

- In `pricing_results.csv`, write each numeric cell with exactly four digits after the decimal
  point (for example `123.4567`, `-0.1234`, `0.0000`).
- In `summary.json`, write numbers as JSON numbers rounded to 4 decimal places.
- `scenario_count` is an integer and is not rounded.
