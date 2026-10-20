# Evidence log (for CV and interview use)

This file records what can be demonstrated about this project. It is written by the AI system that implemented most of the code, and it deliberately separates what is established from what only David can attest to.

## Data coverage

Three companies, fiscal years 2023 to 2025, 276 facts, each with accession number, statement page and line label. Sanofi was reviewed and excluded from this release (reasons in `methodology.md`).

## Technical and financial checks (reproducible)

- 39 of 39 headline figures equal a second extraction path (SEC XBRL facts API); one difference explained and verified (Novartis 2023, discontinued operations).
- 9 of 9 balance sheet identities hold.
- DCF closed-form identities, bridge identity and scenario monotonicity are tested.
- The JavaScript engine and the Excel workbook reproduce the Python model; the workbook was recalculated by an independent evaluator.

## Important trade-offs

- Reported IFRS figures rather than company-adjusted measures, so comparisons are transparent but include impairments and restructuring.
- No EV/EBITDA, because D&A is not comparable across the three statements without note-level work.
- No share prices (no licensed source), so there is no claim about relative valuation.
- A simplified, labelled enterprise-to-equity bridge rather than a complete claims analysis.

## AI assistance

Most of the extraction code, model code, workbook builder, tests, site and documentation were written by an AI system (Claude, Anthropic) directed by David. The AI also made the design decisions above (company selection, definitions, defaults). Every number was checked by tests rather than by inspection alone.

## What David should be able to explain (to be completed by him)

Before using this project on a CV or in an interview, David should be able to answer, in his own words, and add notes here:

1. Why net income differs from operating cash flow for each company, and what drives GSK's low cash conversion.
2. The difference between enterprise value and equity value, and each line of the bridge, including why GSK's non-controlling interest and contingent consideration matter.
3. Why raising WACC lowers the value, why terminal value is about four fifths of the total, and what the terminal growth and margin assumptions imply.
4. What the three comparability problems are (currency, interest classification, continuing operations) and how each is handled.
5. What was not checked and why that matters.

Author's notes: (not yet written)

## Remaining limitations and next steps

See the Limits section of the site. Next: add Sanofi, add note-level D&A for EV/EBITDA, add a licensed or user-supplied price series, add a second DCF company.

## Claims this project does not support

No hours saved, users, adoption, commercial impact or market-beating results. A reproducible dataset, a transparent model and documented validation are the results.
