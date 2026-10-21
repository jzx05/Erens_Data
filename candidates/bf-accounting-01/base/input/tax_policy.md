# Tax Policy

Formulas:
- current_tax_usd = (pretax_income_usd + permanent_differences_usd) * statutory_tax_rate
- deferred_tax_expense_usd = temporary_differences_usd * statutory_tax_rate
- total_tax_expense_usd = current_tax_usd + deferred_tax_expense_usd
- effective_tax_rate_pct = total_tax_expense_usd / pretax_income_usd * 100
- deferred_tax_balance_usd = prior_deferred_tax_balance_usd + deferred_tax_expense_usd

Signs: positive permanent differences raise taxable income. Positive temporary differences are taxable and raise the deferred tax liability; negative ones create a deferred tax asset. Entry: Dr Current tax expense / Cr Current tax payable = current_tax_usd; Dr Deferred tax expense / Cr Deferred tax liability = deferred_tax_expense_usd (swap if negative).

Outputs: `tax_computation.csv` columns: entity, current_tax_usd, deferred_tax_expense_usd, total_tax_expense_usd, effective_tax_rate_pct, deferred_tax_balance_usd; sorted by entity ascending. `tax_summary.json` keys: total_current_tax_usd, total_deferred_tax_expense_usd, total_tax_expense_usd, weighted_effective_tax_rate_pct, entity_with_largest_deferred_tax_expense.

Conventions: compute unrounded; round every output to 2 decimals with ROUND_HALF_UP. Totals sum rounded per-entity values. weighted_effective_tax_rate_pct = total_tax_expense_usd / sum(pretax_income_usd) * 100. Break ties by smallest entity name.
