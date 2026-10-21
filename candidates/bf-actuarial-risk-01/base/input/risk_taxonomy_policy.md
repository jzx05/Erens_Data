# Huachen Bank — Operational Risk Taxonomy and Classification Policy

Document owner: Group Operational Risk Committee (synthetic)
Version: 4.2
Applies to: all operational-risk loss events recorded in the corporate loss-event ledger

This policy defines the seven Basel loss-event categories (EL1–EL7) and the eight Basel business
lines (BL1–BL8) used by Huachen Bank (synthetic), states the rules for assigning both codes to a
loss event, and fixes the Basic Indicator Approach (BIA) capital calculation.

## 1. Scope

Every loss event is assigned exactly one loss-event category and exactly one business line. The
assignment is made from the event narrative as a whole, not from the department label alone.

## 2. Loss-event categories (EL1–EL7)

### EL1 — Internal Fraud (内部欺诈)

Definition: loss caused by an act by an internal employee or officer that is intended to defraud,
misappropriate property, circumvent internal policy or the law, or obtain a personal benefit.
The act may involve collusion with an external party; the involvement of an insider is decisive.

Key indicators: unauthorized trading, deliberate limit breach, falsified records or reports,
embezzlement, theft of customer or bank assets by staff, bribery or kickbacks, insider dealing,
front-running, diversion of funds to an account controlled by an employee.

### EL2 — External Fraud (外部欺诈)

Definition: loss caused by a third party who defrauds the bank, or who uses the bank to defraud
others, through deception, theft, forgery, hacking or other dishonest means. No internal employee
intends to participate in the loss.

Key indicators: phishing or social engineering, forged identity or corporate documents, counterfeit
cards, ATM skimming, card-not-present fraud, fake collateral or financial statements submitted by a
customer, hacking that steals funds, fraudulent letters of credit or trade documents.

### EL3 — Employment Practices and Workplace Safety (就业实践和工作场所安全)

Definition: loss arising from an employment relationship, from a breach of labour or occupational
health and safety obligations, or from workplace conditions.

Key indicators: wrongful termination, discrimination in hiring or promotion, harassment, workplace
injury or occupational illness, failure to provide a safe workplace, unpaid social insurance or
benefits, labour-arbitration awards.

### EL4 — Clients, Products and Business Practices (客户、产品和业务实践)

Definition: loss arising from a failure to meet professional obligations to clients, or from the
nature or design of a product or service, including suitability, disclosure, marketing, fiduciary,
market-conduct and anti-money-laundering negligence failures.

Key indicators: unsuitable product sold to a client, misleading advertising or expected-return
claims, missing risk disclosure, fiduciary breach, unauthorized deviation from an agreed mandate,
privacy breach affecting clients, KYC or anti-money-laundering screening failure, conflicts of
interest not disclosed, improper market conduct.

### EL5 — Damage to Physical Assets (实物资产损坏)

Definition: loss arising from the damage to or destruction of physical assets by a natural disaster,
an accident, vandalism, terrorism or another external event. Loss of service alone is not EL5; the
physical damage or destruction is required.

Key indicators: fire, flood, typhoon, earthquake, explosion, structural damage, vandalism,
destruction of premises, vaults, data-centre equipment or self-service terminals by a physical event.

### EL6 — Business Disruption and System Failures (业务中断和系统故障)

Definition: loss arising from the interruption of business or of a system, without theft and without
physical damage. This includes hardware failure, software failure, telecommunications or network
outage, power failure, capacity exhaustion, expired certificates, and outages of third-party service
providers.

Key indicators: system downtime, server or storage failure, database contention, network or leased
line outage, cloud or outsourced service outage, capacity crash, certificate expiry, ATM network
interruption.

### EL7 — Execution, Delivery and Process Management (执行、交割和流程管理)

Definition: loss arising from failed transaction processing, failed settlement or delivery, errors in
documentation or data entry, reconciliation failures, model or parameter errors, missed deadlines,
or mismanagement of counterparties and collateral.

Key indicators: wrong-side trade capture, settlement error, reconciliation break, data-entry error,
wrong parameter in a valuation or monitoring model, collateral or margin management failure,
documentation error, missed regulatory deadline, incorrect fee or payment computation, unverified
counterparty documents, vendor management failure.

## 3. Business lines (BL1–BL8)

### BL1 — Corporate Finance (公司金融)

Scope: advisory and capital-raising services for large corporates, including mergers and
acquisitions, equity and debt underwriting, initial public offerings, syndicated loans and
acquisition financing arranged for large corporates.

### BL2 — Trading and Sales (交易和销售)

Scope: proprietary trading, market making, dealing in fixed income, foreign exchange, commodities
and derivatives, and sales of these instruments to institutional clients. Trading-system and
trading-settlement losses belong here.

### BL3 — Retail Banking (零售银行)

Scope: deposits, personal loans, mortgages, credit cards, consumer finance and branch services for
individuals, including the sale and distribution of investment, insurance and wealth-management
products to individual clients through branches or direct channels.

### BL4 — Commercial Banking (商业银行)

Scope: lending, deposits and related services to small and medium-sized enterprises and mid-market
corporates, including working-capital loans, trade finance, letters of credit, factoring and
supply-chain finance. Acquisition or syndicated financing for large corporates is BL1, not BL4.

### BL5 — Payment and Settlement (支付和结算)

Scope: payment processing, remittances, clearing, settlement, fund transfers, cash management,
cross-border payment and bank-securities transfer services. Anti-money-laundering monitoring of
payment and remittance flows belongs here.

### BL6 — Agency Services (代理服务)

Scope: custody, escrow, corporate trust, registrar and transfer agency, securities lending and
related asset-servicing activities, including custody valuation and corporate-action processing.

### BL7 — Asset Management (资产管理)

Scope: discretionary portfolio management, fund management, fund accounting and valuation, pension
and wealth mandates managed on behalf of clients. Distribution of third-party products to retail
clients through branches is BL3, not BL7.

### BL8 — Retail Brokerage (零售经纪)

Scope: execution and clearing of securities, futures and margin-financing orders for retail clients,
including online brokerage, investment research distributed to retail clients, and suitability
assessment for trading permissions.

## 4. Classification rules

### 4.1 Assigning the loss-event category

Read the whole narrative, identify the proximate cause of the loss, then apply the following
precedence rules in order:

1. If an employee or officer acted intentionally for personal gain or to conceal a breach, assign
   **EL1**, even if the mechanism looks like a processing or reporting error.
2. If a third party obtained the benefit through deception, forgery, theft or intrusion, assign
   **EL2**, even if bank staff were negligent. If the intrusion caused only an outage and no theft,
   assign EL6 instead.
3. If the loss arises from the employment relationship or from workplace safety, assign **EL3**.
4. If the loss arises from a client-facing obligation — suitability, disclosure, marketing,
   fiduciary duty, privacy, KYC or anti-money-laundering screening — assign **EL4**.
5. If physical assets were damaged or destroyed by an external physical event, assign **EL5**, even
   if business was also interrupted.
6. If a system, network, certificate, capacity limit or third-party service provider failed and
   there was neither theft nor physical damage, assign **EL6**.
7. Otherwise, if the loss arises from transaction processing, settlement, documentation, data entry,
   reconciliation, a model or parameter, collateral management or a missed deadline, assign **EL7**.

Two consequences of the precedence order matter in practice:

- A natural disaster that destroys equipment is EL5 even when the destruction causes a system outage.
- A configuration or parameter error in a monitoring or valuation model is EL7 even when it is
  discovered through a system report; a pure availability failure of that system is EL6.

### 4.2 Assigning the business line

Determine the business line from the product, customer relationship or business activity that gave
rise to the loss:

1. The organisational department recorded in the ledger is corroborating evidence only. It never
   determines the business line by itself.
2. Support and control functions do not own any business line. The following departments are support
   functions: 信息技术部, 人力资源部, 合规部, 风险管理部, 内审部, 财务部, 行政部 and the central
   运营管理部. For an event recorded against one of these departments, the business line must be
   read from the business activity, system, customer or staff group described in the narrative.
3. Multi-line departments are attributed by activity, not by department name:
   - 国际结算部: trade finance, letters of credit and documentary collections are BL4; cross-border
     remittance, clearing and payment flows are BL5.
   - 财富管理部: discretionary or advisory portfolio mandates are BL7; branch distribution of
     products to individual clients is BL3.
   - 运营管理部: central payment, clearing and account-servicing operations are BL5; branch
     premises and branch service issues are BL3.
4. Specific attributions that override a first impression:
   - Acquisition financing, syndicated loans to large corporates, underwriting and M&A advisory
     are BL1.
   - Proprietary trading, FX, derivatives and trading settlement are BL2.
   - Personal deposits, personal loans, mortgages, credit cards and branch product distribution are
     BL3.
   - SME and mid-market lending, trade finance and supply-chain finance are BL4.
   - Payments, remittances, clearing, settlement and payment-related AML monitoring are BL5.
   - Custody, escrow, trust, registrar and custody valuation are BL6.
   - Discretionary portfolio management, fund management and fund accounting are BL7.
   - Retail securities execution, margin financing and retail research are BL8.
   - Corporate account opening and onboarding, including KYC on the corporate entity, are BL4;
     payment processing and settlement on those accounts are BL5.
5. Employment-practices and workplace-safety events take the business line of the organisational
   unit whose staff or premises are affected.
6. Physical-damage events take the business line of the activity carried on at the damaged site. If
   the site is a shared data centre or disaster-recovery centre, use the business system named in
   the narrative as the one that was interrupted.
   A system described as "托管在机房内" or "托管系统" that performs asset valuation is a
   custody/agency valuation system (BL6), not a discretionary asset-management system (BL7),
   unless the narrative explicitly identifies a fund-accounting or discretionary
   portfolio-management system.
7. System-failure events take the business line of the business process or system that was
   interrupted.

### 4.3 Loss amount

Copy `Loss_Amount_CNY` from the ledger exactly. Do not adjust it for recoveries, insurance,
provisions or materiality.

## 5. Basic Indicator Approach (BIA) capital

### 5.1 Averaging set

The averaging set is every fiscal year listed in `gross_income.csv`. Do not restrict the calculation
to a three-year window and do not drop any row from the data set.

### 5.2 Inclusion rule

A year is included in the positive-year average if and only if its gross income is strictly greater
than zero. Years with zero gross income and years with negative gross income are excluded from both
the numerator and the denominator.

### 5.3 Formula

- `positive_year_count` = the number of years whose gross income is strictly greater than zero.
- `positive_gi_sum_cny` = the sum of the gross income of the included years.
- `average_positive_gi_cny` = `positive_gi_sum_cny` / `positive_year_count`.
- `or_capital_cny` = `alpha` × `average_positive_gi_cny`, with `alpha = 0.15`.
- If `positive_year_count` is zero, set both `average_positive_gi_cny` and `or_capital_cny` to
  `0.00`.

### 5.4 Rounding

Round both `average_positive_gi_cny` and `or_capital_cny` to two decimal places using round-half-up
(ties away from zero). Do not round intermediate values: compute the average and the capital charge
from the unrounded inputs, then round only the reported values.
