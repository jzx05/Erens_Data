# Huachen Bank — Operational Risk Event Classification and BIA Capital

## Role and objective

You are an operational-risk analyst at Huachen Bank (synthetic). The corporate loss-event ledger
contains 60 operational-risk events. Classify every event into exactly one Basel loss-event category
(`EL1`–`EL7`) and exactly one Basel business line (`BL1`–`BL8`), preserve every loss amount, and
calculate operational-risk regulatory capital under the Basic Indicator Approach (BIA).

This brief is the solve-time contract. The binding taxonomy rules are repeated in full in
`base/input/risk_taxonomy_policy.md`; where this brief and the policy agree, both apply.

## Inputs

| File | Contents |
|---|---|
| `base/input/operational_risk_events.csv` | 60 loss events: `Event_ID`, `Event_Description_CN`, `Loss_Amount_CNY`, `Event_Date`, `Involved_Department` |
| `base/input/risk_taxonomy_policy.md` | Binding EL1–EL7 and BL1–BL8 definitions and classification rules |
| `base/input/business_line_guide.csv` | Quick-reference business-line scope and typical products |
| `base/input/gross_income.csv` | Six fiscal years: `year`, `gross_income_cny`, `notes` |
| `base/input/output_contract.json` | Exact output files, keys, columns and formats |
| `base/input/output_schema.txt` | Layout examples for the three output files |
| `base/input/runtime_env/pyproject.toml` | Runtime declaration |

The task is closed-book: use only these files and the Python 3.12 standard library.

## Loss-event categories (EL1–EL7)

- **EL1 Internal Fraud** — an internal employee or officer acts intentionally to defraud,
  misappropriate, circumvent policy or gain a personal benefit. Includes unauthorized trading,
  falsified records, embezzlement, bribery, insider dealing, front-running and diversion of funds.
- **EL2 External Fraud** — a third party defrauds the bank, or uses the bank to defraud others,
  through deception, forgery, theft, hacking or intrusion, with no internal intent. Includes
  phishing, forged identity or corporate documents, counterfeit cards, ATM skimming, fake financial
  statements and fraudulent trade documents.
- **EL3 Employment Practices and Workplace Safety** — loss from an employment relationship, labour
  law, occupational health and safety, or workplace conditions. Includes wrongful termination,
  discrimination, harassment, workplace injury or illness, and unsafe premises.
- **EL4 Clients, Products and Business Practices** — failure of a professional obligation to
  clients, or loss from product design. Includes unsuitable sales, misleading marketing, missing
  risk disclosure, fiduciary breach, privacy breach, KYC/AML screening failure, and undisclosed
  conflicts of interest.
- **EL5 Damage to Physical Assets** — damage to or destruction of physical assets by a natural
  disaster, accident, vandalism, terrorism or another external physical event. Loss of service
  without physical damage is not EL5.
- **EL6 Business Disruption and System Failures** — interruption of business or systems with no
  theft and no physical damage. Includes hardware, software, network, power, capacity, certificate
  and third-party service-provider outages.
- **EL7 Execution, Delivery and Process Management** — failed processing, settlement, documentation,
  data entry, reconciliation, model or parameter, collateral management or deadline. Includes
  wrong-side trades, data-entry errors, valuation parameter errors, missed deadlines and unverified
  counterparty documents.

### Loss-event precedence rules

1. Intentional insider act for personal gain or concealment → **EL1**, even if it looks like a
   processing or reporting error.
2. Third party obtains the benefit by deception, forgery, theft or intrusion → **EL2**, even if bank
   staff were negligent; an intrusion that causes only an outage and no theft is **EL6**.
3. Employment relationship or workplace safety → **EL3**.
4. Client-facing suitability, disclosure, marketing, fiduciary, privacy, KYC or AML screening →
   **EL4**.
5. Physical damage or destruction by an external physical event → **EL5**, even if business is also
   interrupted.
6. System, network, certificate, capacity or third-party service outage without theft or physical
   damage → **EL6**.
7. Otherwise, a processing, settlement, documentation, data-entry, reconciliation, model or
   parameter, collateral or deadline failure → **EL7**.

## Business lines (BL1–BL8)

- **BL1 Corporate Finance** — M&A advisory, equity and debt underwriting, IPO, syndicated loans and
  acquisition financing for large corporates.
- **BL2 Trading and Sales** — proprietary trading, market making, fixed income, FX, commodities and
  derivatives, and institutional sales.
- **BL3 Retail Banking** — deposits, personal loans, mortgages, credit cards, consumer finance,
  branch services, and branch distribution of investment and wealth products to individuals.
- **BL4 Commercial Banking** — SME and mid-market lending, working-capital loans, trade finance,
  letters of credit, factoring and supply-chain finance.
- **BL5 Payment and Settlement** — payment processing, remittances, clearing, settlement, fund
  transfers, cash management, cross-border payments and payment-related AML monitoring.
- **BL6 Agency Services** — custody, escrow, corporate trust, registrar, securities lending and
  custody valuation.
- **BL7 Asset Management** — discretionary portfolio management, fund management, fund accounting
  and valuation, and pension mandates.
- **BL8 Retail Brokerage** — securities and futures execution for retail clients, online brokerage,
  margin financing and retail investment research.

### Business-line attribution rules

1. The `Involved_Department` column is corroborating evidence only; it never determines the business
   line by itself.
2. Support functions own no business line: 信息技术部, 人力资源部, 合规部, 风险管理部, 内审部,
   财务部, 行政部 and the central 运营管理部. For events recorded against them, read the business
   line from the activity, system, customer or staff group described in the narrative.
3. Multi-line departments are attributed by activity: 国际结算部 trade finance is BL4 but
   cross-border remittance is BL5; 财富管理部 discretionary mandates are BL7 but branch product
   distribution is BL3; 运营管理部 central payment operations are BL5 but branch premises and
   service issues are BL3.
4. Corporate account opening and onboarding, including KYC on the corporate entity, are BL4; payment
   processing and settlement on those accounts are BL5.
5. Employment-practices and workplace-safety events take the business line of the unit whose staff
   or premises are affected.
5. Physical-damage events take the business line of the activity at the damaged site. For a shared
   data centre or disaster-recovery centre, use the business system named as interrupted.
   A system described as "托管在机房内" or "托管系统" that performs asset valuation is a
   custody/agency valuation system (BL6), not a discretionary asset-management system (BL7),
   unless the narrative explicitly identifies a fund-accounting or discretionary
   portfolio-management system.
6. System-failure events take the business line of the business process or system interrupted.

## Loss amounts

Copy `Loss_Amount_CNY` from the ledger exactly for all 60 events. Do not adjust for recoveries,
insurance, provisions or materiality.

## BIA capital

- `alpha = 0.15`.
- The averaging set is every fiscal year in `gross_income.csv`; do not use a three-year window.
- A year is included in the positive-year average if and only if its gross income is strictly
  greater than zero. Zero and negative years are excluded from both the numerator and the
  denominator.
- `positive_year_count` = number of strictly positive years.
- `positive_gi_sum_cny` = sum of the gross income of the included years.
- `average_positive_gi_cny` = `positive_gi_sum_cny` / `positive_year_count`.
- `or_capital_cny` = `0.15` × `average_positive_gi_cny`.
- If `positive_year_count == 0`, report both the average and the capital as `0.00`.
- Round `average_positive_gi_cny` and `or_capital_cny` to two decimal places using round-half-up
  (ties away from zero). Compute from unrounded inputs and round only the reported values.

## Outputs

Write exactly three files under `base/output`. Do not add extra files.

### 1. `classified_events.csv`

UTF-8 CSV with exactly these columns in this order (comma-separated):
`Event_ID`, `Loss_Event_Category`, `Business_Line`, `Loss_Amount_CNY`

One data row for each of the 60 ledger events, in any order, with the exact `Event_ID` and the exact
loss amount. `Loss_Event_Category` must be one of `EL1`–`EL7`; `Business_Line` must be one of
`BL1`–`BL8`.

### 2. `capital_calculation.json`

A single JSON object with exactly these six keys:

- `alpha` — number, `0.15`.
- `gross_income_years` — object mapping each four-digit year from `gross_income.csv` (as a string)
  to its numeric gross income in CNY.
- `positive_year_count` — integer.
- `positive_gi_sum_cny` — number, the sum of the included years.
- `average_positive_gi_cny` — number, rounded to two decimal places.
- `or_capital_cny` — number, rounded to two decimal places.

### 3. `execution_log.txt`

Plain text, non-empty. Briefly state the classification method and the BIA capital steps.

## Pass criteria

The task returns `1.0` only when all of the following hold; otherwise it returns `0.0`:

- all three output files exist and parse;
- `classified_events.csv` contains each of the 60 ledger `Event_ID`s exactly once and no others;
- every loss-event category is a valid `EL1`–`EL7` code and every business line is a valid
  `BL1`–`BL8` code;
- loss-event category accuracy is at least **90%** (at least 54 of 60 events correct);
- business-line accuracy is at least **90%** (at least 54 of 60 events correct);
- loss amounts match the ledger exactly for **all 60** events;
- `capital_calculation.json` matches the gold BIA values, with monetary values compared with an
  absolute tolerance of 0.01 CNY.

A partial answer scores `0.0`. The evaluator reports per-event correctness details for diagnosis.
