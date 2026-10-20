# Pharma Valuation Explorer

**Part of [Lab Notes](https://notes.lindgreendavid.com/), Project 1 of three.** Status: **working release 0.1.0, unpublished, not investment advice.**

An analyst comparing pharmaceutical companies has to read long filings, and comparisons go wrong when currencies, definitions and reporting treatments are mixed without saying so. This project gives a like-for-like comparison of Novartis (USD), GSK (GBP) and Novo Nordisk (DKK) for fiscal years 2023 to 2025, every figure traced to its filing, and a DCF of Novartis whose assumptions, enterprise-to-equity bridge and sensitivities can be inspected and changed.

## What you get

- A comparable-company dashboard: revenue, margins, R&D intensity, cash generation, leverage, with consistent definitions and a plain list of comparability problems.
- A DCF with understandable operating assumptions, an itemised bridge from enterprise value to equity value, and two sensitivity heatmaps.
- Sources beside the figures, a searchable dataset of 276 facts, an Excel model with live formulas, and the validation results.
- No share prices: no public price source with a clear reuse licence was available programmatically. Enter a price to see multiples and the comparison with market value.

## Limits first

Three companies, three years; reported IFRS figures, not adjusted; a simplified bridge that is not a complete claims analysis; DCF defaults are the author's assumptions; terminal value is about four fifths of enterprise value. Full list: [`docs/methodology.md`](docs/methodology.md) and the site's Limits section.

## Run and reproduce

```bash
python -m venv .venv && .venv/Scripts/pip install -e '.[dev]'   # use bin/pip on macOS and Linux
pytest
node --test site/tests/*.test.mjs
python scripts/build_site_data.py        # regenerate site/data from the dataset
python scripts/build_workbook.py         # regenerate the Excel model
cd site && python -m http.server 8000    # open http://localhost:8000
```

The fetch scripts (`scripts/fetch_*.py`) re-download everything from SEC EDGAR, the ECB, FRED and Damodaran's site. They use `curl` and identify the requester as SEC fair-access rules require.

## Layout

| Path | What |
| --- | --- |
| `src/pharma_valuation/` | Extraction rules, model (metrics, bridge, DCF), defaults, reconciliation |
| `data/` | Parsed statements, the dataset (CSV and JSON), ECB rates, market parameters, checksums |
| `scripts/` | Fetchers, dataset and workbook builders |
| `site/` | Static web app (engine, UI, data, downloads) |
| `tests/`, `site/tests/` | Python and JavaScript tests |
| `docs/` | Methodology and evidence log |

## Data and licences

Code MIT. Filings: SEC EDGAR (public). FX: European Central Bank. Risk-free rate: FRED (US Treasury). Equity risk premium: Aswath Damodaran. Geist typeface: SIL Open Font License.

## How it was built

Designed and directed by David Lindgreen. Code, tests and text were written with substantial assistance from an AI system (Claude, Anthropic). See [`docs/evidence-log.md`](docs/evidence-log.md).
