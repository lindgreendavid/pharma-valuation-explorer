"""Comparison metrics, the enterprise-to-equity bridge and the DCF, in plain Python.

Units: millions of the reporting currency unless stated. Percentages are fractions (0.05 = 5%).
The same formulas are implemented in site/engine.js; tests/test_parity.py checks both against shared vectors.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DATASET_PATH = Path(__file__).parents[2] / "data" / "dataset.json"


class Dataset:
    """Read access to the traceable facts and the ECB rates."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self._facts = {(f["company"], f["fiscal_year"], f["field"]): f for f in payload["facts"]}
        self._fx = {(r["currency"], r["kind"], r["period"][:4]): float(r["rate"]) for r in payload["fx"]}

    @classmethod
    def load(cls, path: Path = DATASET_PATH) -> Dataset:
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def has(self, company: str, year: int, name: str) -> bool:
        return (company, year, name) in self._facts

    def get(self, company: str, year: int, name: str, default: float | None = None) -> float:
        fact = self._facts.get((company, year, name))
        if fact is None:
            if default is None:
                raise KeyError(f"{company} {year} {name}")
            return default
        return float(fact["value"])

    def fact(self, company: str, year: int, name: str) -> dict[str, Any]:
        fact: dict[str, Any] = self._facts[(company, year, name)]
        return fact

    def currency(self, company: str) -> str:
        return str(self.payload["companies"][company]["currency"])

    def eur_rate(self, currency: str, kind: str, year: int) -> float:
        """Units of currency per 1 EUR; EUR itself is 1."""

        if currency == "EUR":
            return 1.0
        return self._fx[(currency, kind, str(year))]


# ---------------------------------------------------------------- comparison metrics


def gross_debt(data: Dataset, company: str, year: int) -> float:
    """Borrowings plus separately reported lease liabilities (some companies include leases in borrowings)."""

    total = data.get(company, year, "debt_current") + data.get(company, year, "debt_noncurrent")
    total += data.get(company, year, "lease_current", 0.0) + data.get(company, year, "lease_noncurrent", 0.0)
    return total


def debt_like_other(data: Dataset, company: str, year: int) -> float:
    """Contingent consideration owed on acquisitions (material for GSK)."""

    return data.get(company, year, "contingent_consideration_current", 0.0) + data.get(
        company, year, "contingent_consideration_noncurrent", 0.0
    )


def free_cash_flow(data: Dataset, company: str, year: int) -> float:
    """Operating cash flow less capex, with interest classified the same way for every company.

    Definition: cash flow after tax and after net interest paid, before lease principal, acquisitions,
    dividends and buybacks. Companies that report interest outside operating cash flow (GSK) are
    adjusted so that net interest paid is deducted for all.
    """

    cfo = data.get(company, year, "cfo")
    capex = data.get(company, year, "capex_ppe") + data.get(company, year, "capex_intangibles")
    adjustment = -data.get(company, year, "interest_paid_outside_cfo", 0.0) + data.get(
        company, year, "interest_received_outside_cfo", 0.0
    )
    return cfo - capex + adjustment


def metrics(data: Dataset, company: str, year: int) -> dict[str, float]:
    revenue = data.get(company, year, "revenue")
    operating = data.get(company, year, "operating_income")
    out = {
        "revenue": revenue,
        "operating_income": operating,
        "operating_margin": operating / revenue,
        "r_and_d_intensity": data.get(company, year, "r_and_d") / revenue,
        "net_income": data.get(company, year, "net_income"),
        "net_margin": data.get(company, year, "net_income") / revenue,
        "effective_tax_rate": data.get(company, year, "income_tax") / data.get(company, year, "pretax_income"),
        "operating_cash_flow": data.get(company, year, "cfo"),
        "capex": data.get(company, year, "capex_ppe") + data.get(company, year, "capex_intangibles"),
        "free_cash_flow": free_cash_flow(data, company, year),
    }
    out["fcf_margin"] = out["free_cash_flow"] / revenue
    out["fcf_to_net_income"] = out["free_cash_flow"] / out["net_income"]
    out["gross_debt"] = gross_debt(data, company, year)
    out["cash_and_investments"] = data.get(company, year, "cash") + data.get(
        company, year, "short_term_investments", 0.0
    )
    out["net_debt"] = out["gross_debt"] + debt_like_other(data, company, year) - out["cash_and_investments"]
    out["net_debt_to_operating_income"] = out["net_debt"] / operating
    if data.has(company, year - 1, "revenue"):
        out["revenue_growth"] = revenue / data.get(company, year - 1, "revenue") - 1.0
    return out


def to_eur(data: Dataset, company: str, year: int, value: float, kind: str) -> float:
    """Convert at the ECB annual average (flows) or year-end rate (balances); kind in {'flow','balance'}."""

    rate_kind = "annual_average" if kind == "flow" else "year_end"
    return value / data.eur_rate(data.currency(company), rate_kind, year)


# ---------------------------------------------------------------- enterprise value to equity value


@dataclass(frozen=True)
class BridgeOptions:
    include_equity_method_investments: bool = True
    include_other_financial_assets: bool = True
    include_pension_liability: bool = True
    nci_method: str = "book"  # 'book' or 'earnings_multiple'
    nci_earnings_multiple: float = 15.0


def equity_bridge(
    data: Dataset, company: str, year: int, enterprise_value: float, options: BridgeOptions | None = None
) -> dict[str, Any]:
    """Itemised bridge from enterprise value to equity value of the parent's shareholders.

    Not covered, by design and stated to the reader: litigation and tax provisions, off-balance-sheet
    commitments, operating-lease commitments outside IFRS 16 liabilities, deferred consideration other
    than recognised contingent consideration, and any pension surplus.
    """

    options = options or BridgeOptions()
    items: list[dict[str, Any]] = []

    def add(label: str, amount: float, source: str) -> None:
        items.append({"label": label, "amount": amount, "source": source})

    add("Enterprise value", enterprise_value, "model")
    add("Less: gross borrowings and lease liabilities", -gross_debt(data, company, year), "balance sheet")
    other = debt_like_other(data, company, year)
    if other:
        add("Less: contingent consideration liabilities (debt-like)", -other, "balance sheet")
    add("Plus: cash and cash equivalents", data.get(company, year, "cash"), "balance sheet")
    st = data.get(company, year, "short_term_investments", 0.0)
    if st:
        add("Plus: marketable securities and short-term investments", st, "balance sheet")
    if options.include_equity_method_investments:
        add(
            "Plus: investments in associates and joint ventures (book)",
            data.get(company, year, "equity_method_investments", 0.0),
            "balance sheet",
        )
    if options.include_other_financial_assets:
        add(
            "Plus: other non-current financial assets (book)",
            data.get(company, year, "other_financial_assets", 0.0),
            "balance sheet",
        )
    if options.include_pension_liability:
        add(
            "Less: recognised post-employment liabilities",
            -data.get(company, year, "pension_liability", 0.0),
            "balance sheet or note",
        )
    if options.nci_method == "earnings_multiple":
        nci = max(data.get(company, year, "nci_profit", 0.0), 0.0) * options.nci_earnings_multiple
        add(
            f"Less: non-controlling interests ({options.nci_earnings_multiple:g}x their profit)",
            -nci,
            "income statement, assumption",
        )
    else:
        add("Less: non-controlling interests (book value)", -data.get(company, year, "nci_book", 0.0), "balance sheet")
    equity = sum(item["amount"] for item in items)
    return {"items": items, "equity_value": equity}


# ---------------------------------------------------------------- DCF


@dataclass
class DcfInputs:
    base_revenue: float
    growth: list[float]  # explicit years, e.g. five values
    operating_margin: list[float]  # per explicit year, on net sales
    tax_rate: float
    da_pct_revenue: float
    capex_pct_revenue: float
    nwc_pct_revenue: float
    base_nwc: float
    wacc: float
    terminal_growth: float
    mid_year: bool = False
    normalise_terminal: bool = True  # terminal D&A equals capex, so growth is not funded by under-investment
    shares_outstanding: float = 1.0  # millions
    extra: dict[str, Any] = field(default_factory=dict)


def project(inputs: DcfInputs) -> list[dict[str, float]]:
    """Explicit-period free cash flow to the firm."""

    if len(inputs.growth) != len(inputs.operating_margin):
        raise ValueError("growth and operating_margin must have the same length")
    rows: list[dict[str, float]] = []
    revenue = inputs.base_revenue
    nwc = inputs.base_nwc
    for index, (growth, margin) in enumerate(zip(inputs.growth, inputs.operating_margin, strict=True), start=1):
        revenue = revenue * (1.0 + growth)
        ebit = revenue * margin
        nopat = ebit * (1.0 - inputs.tax_rate)
        da = revenue * inputs.da_pct_revenue
        capex = revenue * inputs.capex_pct_revenue
        new_nwc = revenue * inputs.nwc_pct_revenue
        delta_nwc = new_nwc - nwc
        nwc = new_nwc
        fcff = nopat + da - capex - delta_nwc
        rows.append(
            {
                "year": index,
                "revenue": revenue,
                "ebit": ebit,
                "nopat": nopat,
                "da": da,
                "capex": capex,
                "delta_nwc": delta_nwc,
                "fcff": fcff,
            }
        )
    return rows


def terminal_free_cash_flow(inputs: DcfInputs, last: dict[str, float]) -> float:
    """First post-forecast-year free cash flow: last NOPAT grown, working-capital build and, if normalised, D&A equal to capex."""

    growth = inputs.terminal_growth
    nopat = last["nopat"] * (1.0 + growth)
    delta_nwc = inputs.nwc_pct_revenue * last["revenue"] * growth
    net_capex = 0.0 if inputs.normalise_terminal else (last["capex"] - last["da"]) * (1.0 + growth)
    return nopat - net_capex - delta_nwc


def enterprise_value(inputs: DcfInputs, rows: list[dict[str, float]] | None = None) -> dict[str, float]:
    """Present value of explicit cash flows plus Gordon-growth terminal value."""

    if inputs.wacc <= inputs.terminal_growth:
        raise ValueError("WACC must exceed terminal growth")
    rows = rows if rows is not None else project(inputs)
    shift = 0.5 if inputs.mid_year else 0.0
    pv_explicit = sum(row["fcff"] / (1.0 + inputs.wacc) ** (row["year"] - shift) for row in rows)
    last = rows[-1]
    terminal_fcff = terminal_free_cash_flow(inputs, last)
    terminal_value = terminal_fcff / (inputs.wacc - inputs.terminal_growth)
    pv_terminal = terminal_value / (1.0 + inputs.wacc) ** (last["year"] - shift)
    return {
        "pv_explicit": pv_explicit,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "enterprise_value": pv_explicit + pv_terminal,
        "terminal_share_of_value": pv_terminal / (pv_explicit + pv_terminal),
    }


def wacc_build_up(
    risk_free: float,
    beta: float,
    equity_risk_premium: float,
    pre_tax_cost_of_debt: float,
    tax_rate: float,
    debt_weight: float,
) -> dict[str, float]:
    cost_of_equity = risk_free + beta * equity_risk_premium
    cost_of_debt = pre_tax_cost_of_debt * (1.0 - tax_rate)
    wacc = (1.0 - debt_weight) * cost_of_equity + debt_weight * cost_of_debt
    return {"cost_of_equity": cost_of_equity, "after_tax_cost_of_debt": cost_of_debt, "wacc": wacc}


def sensitivity_grid(
    inputs: DcfInputs, waccs: list[float], terminal_growths: list[float], equity_per_ev: float | None = None
) -> list[list[float]]:
    """Enterprise value for every (WACC, terminal growth) pair; cash flows do not depend on either."""

    rows = project(inputs)
    grid = []
    for wacc in waccs:
        line = []
        for growth in terminal_growths:
            variant = DcfInputs(**{**inputs.__dict__, "wacc": wacc, "terminal_growth": growth})
            line.append(enterprise_value(variant, rows)["enterprise_value"])
        grid.append(line)
    return grid
