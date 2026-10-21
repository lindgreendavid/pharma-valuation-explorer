# Methodology

Version 0.1.0. Public data only. Educational and analytical; not investment advice.

## Scope

Three pharmaceutical companies, selected after reviewing which large IFRS reporters have complete, comparable filings on SEC EDGAR for fiscal years 2023 to 2025:

| Company | Reporting currency | Filing | Why chosen |
| --- | --- | --- | --- |
| Novartis | USD | Form 20-F, IFRS | Complete statements; continuing-operations presentation after the Sandoz spin-off; subject of the DCF |
| GSK | GBP | Form 20-F, IFRS | Different currency; interest classified differently; large debt-like contingent consideration and a negative book non-controlling interest, which make the bridge instructive |
| Novo Nordisk | DKK | Form 20-F, IFRS | Third currency; clean statements; very different growth and margin profile |

All three have a 31 December year end. **Sanofi** was reviewed and left out of this release: its FY2025 statements carry a major discontinued operation (Opella) and re-presented comparatives that need their own careful treatment. It is a candidate for the next release. Sanofi is also the author's employer, which is a second reason to value a different company first.

## Data lineage

1. `scripts/fetch_statements.py` downloads the XBRL "R" pages (the rendered primary statements) of the FY2025 and FY2024 20-F for each company from SEC EDGAR and parses them. `scripts/fetch_notes.py` adds cover pages (shares outstanding) and the Novartis notes that give depreciation and amortisation.
2. `src/pharma_valuation/extract.py` holds `MAPPING`: for each company and field, the statement, a line-label pattern and which match to take. Nothing is estimated. Values are millions of the reporting currency as filed. Liabilities presented as negatives are stored as positive magnitudes.
3. `scripts/fetch_xbrl_facts.py` reads the SEC XBRL facts API. It supplies the Novartis recognised post-employment liability (not a line on its balance sheet) and a second, independent path used for reconciliation.
4. `scripts/fetch_fx.py` fetches ECB euro reference rates for USD, GBP and DKK: annual averages for flows and year-end rates for balances. `scripts/fetch_market_parameters.py` fetches the risk-free rate (FRED DGS10 on 2025-12-31) and the equity risk premium (Damodaran implied ERP, 2026-01-01).
5. `scripts/build_dataset.py` writes `data/financials.csv` and `data/dataset.json` (276 facts), each with accession number, filing date, source page URL and line label.

FY2025 filings supply income statements and cash flow statements for 2023 to 2025. Balance sheets for 2023 come from the FY2024 filings where the FY2025 filing shows only two years.

## Treatment of fiscal years, currencies and reported versus adjusted measures

- **Fiscal years.** All three end on 31 December. No calendarisation is needed.
- **Currencies.** Ratios are computed in the reporting currency. For levels, flows are converted at the ECB annual-average rate and balances at the year-end rate. The site shows either EUR or the reporting currency.
- **Reported, not adjusted.** IFRS figures as filed. Company "core", "adjusted" or "underlying" measures are not used. Impairments, restructuring and acquisition effects therefore remain inside reported operating income.
- **Continuing operations.** Novartis revenue, operating income, net income and operating cash flow are continuing operations (2023 excludes the Sandoz spin-off). Using totals would give a 2023 net income of 14,854 instead of 8,572 USD million.

## Definitions

- **Revenue**: net product sales (Novartis "net sales from continuing operations", GSK "turnover", Novo Nordisk "net sales"). Novartis other revenues and GSK royalty income are excluded from revenue but included in operating income.
- **Operating margin**: reported operating income / revenue.
- **Free cash flow**: operating cash flow less purchases of property, plant and equipment and of intangible assets, with interest classified consistently: Novartis and Novo Nordisk include interest paid and received in operating cash flow; GSK reports interest paid in financing and interest received in investing, so net interest is deducted for GSK to match. It is before lease principal, acquisitions, dividends and buybacks.
- **Gross debt**: borrowings plus lease liabilities. GSK and Novo Nordisk include leases in borrowings; Novartis reports them separately.
- **Net debt**: gross debt plus debt-like contingent consideration (GSK) less cash and short-term investments.
- **Not shown: EV/EBITDA.** Depreciation and amortisation are not presented on the face of all three statements and include impairments in different ways. Adding them needs note-level extraction for every company.

## Enterprise value to equity value

Itemised on the site and in the workbook: less gross borrowings and leases; less contingent consideration (GSK); plus cash and short-term investments; plus associates and joint ventures at book value; plus other non-current financial assets at book value; less recognised post-employment liabilities; less non-controlling interests (book value, or a multiple of their profit). Each item is a filed balance-sheet figure. **Not covered**: litigation and tax provisions, off-balance-sheet commitments, pension surpluses, operating-lease commitments outside IFRS 16. The bridge is therefore not a complete claims analysis and is described that way wherever it appears.

## The DCF

Five explicit years (FY2026 to FY2030) on FY2025 actuals, free cash flow to the firm = NOPAT + D&A - capex - increase in working capital. Terminal value uses Gordon growth with D&A set equal to capex in the terminal year, so growth is not funded by under-investment. End-of-year discounting by default, mid-year optional.

Observed inputs (from the filing): base revenue, working capital as a share of revenue, D&A and capex as shares of revenue, pre-tax cost of debt (interest expense over average gross debt). Market inputs (sourced and dated): risk-free rate 4.18% and equity risk premium 4.23%. **Assumptions** (the author's, labelled as such): revenue growth path 5.0% fading to 3.0%, operating margin path 32.0% fading to 30.0%, tax rate 16%, equity beta 0.75, debt weight 15%, terminal growth 2.0%. They are chosen to explore a range, not to forecast. Terminal value is about 79% of enterprise value at the defaults, which is why the value is sensitive to the discount rate and terminal growth.

**No share prices are used or shipped.** No public price source with a clear reuse licence was available programmatically (Stooq blocks automated access and other sources restrict redistribution). Multiples and the comparison with a market value appear only if a user enters a price.

## Validation

Run `pytest` (Python) and `node --test site/tests/*.test.mjs` (JavaScript).

- **Second extraction path.** 39 headline figures equal the values read through the XBRL facts API. The only known difference (Novartis 2023 net income and operating cash flow) is explained by discontinued operations and checked against the statements' own total rows.
- **Independent dataset.** 78 values for Novartis and GSK equal a separately built dataset (the portfolio site's, extracted through XBRL company-facts tags): `docs/cross-check.md`.
- **Identities.** Assets = equity + liabilities for all nine company-dates.
- **Model.** A flat business is worth NOPAT / WACC; Gordon growth closed form; mid-year convention; the bridge sums; the bridge identity (equity + claims - non-operating assets = enterprise value); value falls with WACC and tax and rises with growth and margin; the sensitivity grid equals direct valuation and is monotone.
- **Implementations agree.** The browser JavaScript engine reproduces the Python model on fixed scenarios (45 vectors). The Excel workbook, recalculated by an independent evaluator, reproduces the Python model including all 25 sensitivity cells.
- **Hand check.** Nine headline figures were compared by hand with the filed statements (`tests/test_dataset.py::test_selected_figures_equal_the_filings`).

**Not validated:** no external audit; no comparison with printed annual reports or a data vendor; the DCF assumptions are not checked against analyst forecasts or guidance; share counts are cover-page figures at the filing date.
