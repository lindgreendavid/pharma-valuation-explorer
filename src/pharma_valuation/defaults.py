"""Default DCF inputs for the valued company (Novartis, USD millions), with the reason for each.

Observed values come from the dataset (traceable to filings). Assumptions are the author's choices for
exploring a range; they are not forecasts, guidance or a recommendation, and the site lets a reader change all of them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pharma_valuation.model import Dataset, DcfInputs, gross_debt, wacc_build_up

COMPANY = "Novartis"
BASE_YEAR = 2025
PARAMETERS_PATH = Path(__file__).parents[2] / "data" / "market-parameters.json"

# Assumptions (not observed): explained in docs/methodology.md.
GROWTH = [0.05, 0.045, 0.04, 0.035, 0.03]
OPERATING_MARGIN = [0.32, 0.315, 0.31, 0.305, 0.30]
TAX_RATE = 0.16
TERMINAL_GROWTH = 0.02
BETA = 0.75
DEBT_WEIGHT = 0.15


def market_parameters() -> dict[str, Any]:
    parameters: dict[str, Any] = json.loads(PARAMETERS_PATH.read_text(encoding="utf-8"))
    return parameters


def novartis_inputs(
    data: Dataset,
    wacc: float | None = None,
    terminal_growth: float | None = None,
    tax_rate: float | None = None,
    margin_shift: float = 0.0,
) -> DcfInputs:
    revenue = data.get(COMPANY, BASE_YEAR, "revenue")
    nwc = (
        data.get(COMPANY, BASE_YEAR, "inventories")
        + data.get(COMPANY, BASE_YEAR, "receivables")
        - data.get(COMPANY, BASE_YEAR, "payables")
    )
    da = (
        data.get(COMPANY, BASE_YEAR, "depreciation_ppe") + data.get(COMPANY, BASE_YEAR, "amortisation_intangibles")
    ) / revenue
    capex = (data.get(COMPANY, BASE_YEAR, "capex_ppe") + data.get(COMPANY, BASE_YEAR, "capex_intangibles")) / revenue
    params = market_parameters()
    average_debt = (gross_debt(data, COMPANY, BASE_YEAR) + gross_debt(data, COMPANY, BASE_YEAR - 1)) / 2
    pre_tax_cost_of_debt = data.get(COMPANY, BASE_YEAR, "interest_expense") / average_debt
    tax = TAX_RATE if tax_rate is None else tax_rate
    build = wacc_build_up(
        params["risk_free_rate"]["value"],
        BETA,
        params["equity_risk_premium"]["value"],
        pre_tax_cost_of_debt,
        tax,
        DEBT_WEIGHT,
    )
    return DcfInputs(
        base_revenue=revenue,
        growth=list(GROWTH),
        operating_margin=[m + margin_shift for m in OPERATING_MARGIN],
        tax_rate=tax,
        da_pct_revenue=da,
        capex_pct_revenue=capex,
        nwc_pct_revenue=nwc / revenue,
        base_nwc=nwc,
        wacc=build["wacc"] if wacc is None else wacc,
        terminal_growth=TERMINAL_GROWTH if terminal_growth is None else terminal_growth,
        shares_outstanding=data.get(COMPANY, BASE_YEAR, "shares_outstanding_cover"),
        extra={
            "wacc_build_up": build,
            "pre_tax_cost_of_debt": pre_tax_cost_of_debt,
            "sources": {
                "observed": "FY2025 20-F: net sales, inventories, receivables, payables, capex, interest expense, borrowings; Novartis notes for depreciation and amortisation",
                "market": "risk-free rate (FRED DGS10, 2025-12-31) and equity risk premium (Damodaran, 2026-01-01)",
                "assumed": "growth path, margin path, tax rate, beta, debt weight, terminal growth",
            },
        },
    )
