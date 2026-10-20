"""Write the default DCF inputs and parity vectors that the site and its tests use.

site/data/defaults.json: the Novartis DCF defaults (observed values and assumptions, each with its source).
site/data/vectors.json: outputs of the Python model for fixed scenarios, so the JavaScript engine is checked against it.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pharma_valuation.defaults import BETA, COMPANY, DEBT_WEIGHT, market_parameters, novartis_inputs  # noqa: E402
from pharma_valuation.model import (  # noqa: E402
    BridgeOptions,
    Dataset,
    enterprise_value,
    equity_bridge,
    metrics,
    sensitivity_grid,
    to_eur,
)

SITE = ROOT / "site" / "data"


def write_validation(data: Dataset, vectors: dict[str, object]) -> None:
    from pharma_valuation.extract import MAPPING, YEARS
    from pharma_valuation.reconcile import run

    results = run()
    identities = [
        abs(data.get(c, y, "total_assets") - data.get(c, y, "total_equity") - data.get(c, y, "total_liabilities"))
        <= 1.0
        for c in MAPPING
        for y in YEARS
    ]
    grid = vectors["grid"]["values"]  # type: ignore[index]
    parity = (
        len(vectors["metrics"]) + len(vectors["scenarios"]) + sum(len(r) for r in grid) + 2 * len(vectors["bridges"])
    )  # type: ignore[arg-type]
    payload = {
        "reconciliation": {"compared": len(results), "matched": sum(r["status"] == "match" for r in results)},
        "identities": {"total": len(identities), "passed": sum(identities)},
        "facts": len(data.payload["facts"]),
        "parity": {"vectors": parity},
        "workbook": {"cells_compared": WORKBOOK_CELLS_COMPARED},
        "checked": [
            "Every extracted figure is mapped by an explicit rule (statement, line label, occurrence) and carries its accession number, page and line label.",
            "39 headline figures (revenue, operating income, net income, operating cash flow, cash) equal the values read through the SEC XBRL facts API, a second path through the same filings. The one known difference, Novartis 2023, is explained by discontinued operations and checked against the statements' own totals.",
            "Assets equal equity plus liabilities for every company and date.",
            "The DCF satisfies closed-form identities (a flat business is worth NOPAT over WACC; Gordon growth), the bridge sums to equity value, and value moves the right way when WACC, growth, margin or tax change.",
            "The JavaScript engine that runs in your browser reproduces the Python model on fixed scenarios.",
            "The Excel workbook, recalculated by an independent evaluator, reproduces the Python model, including all 25 sensitivity cells.",
        ],
        "not_checked": [
            "No one else has audited the mapping or the dataset. The figures were not compared with the companies' printed annual reports or with a data vendor.",
            "Share counts are cover-page figures, not weighted or diluted averages, and no share price is included, so no claim is made about whether any company is cheap or expensive.",
            "Pension, contingent-consideration and non-controlling-interest treatments are simplified and documented; litigation and tax provisions are not modelled.",
            "The DCF defaults are assumptions. Their reasonableness was checked for internal consistency, not against analyst forecasts or company guidance.",
            "Other companies, other years, and adjusted (non-IFRS) measures.",
        ],
    }
    (SITE / "validation.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


# five DCF outputs, 25 sensitivity cells, 16 comparison cells and 11 check cells (see tests/test_workbook.py)
WORKBOOK_CELLS_COMPARED = 57


def main() -> int:
    SITE.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "data" / "dataset.json", SITE / "dataset.json")
    data = Dataset.load()
    inputs = novartis_inputs(data)
    params = market_parameters()
    defaults = asdict(inputs)
    defaults["company"] = COMPANY
    defaults["beta"] = BETA
    defaults["debt_weight"] = DEBT_WEIGHT
    defaults["risk_free_rate"] = params["risk_free_rate"]
    defaults["equity_risk_premium"] = params["equity_risk_premium"]
    (SITE / "defaults.json").write_text(json.dumps(defaults, indent=1) + "\n", encoding="utf-8")

    scenarios = {
        "base": {},
        "wacc_up": {"wacc": inputs.wacc + 0.01},
        "growth_up": {"terminal_growth": inputs.terminal_growth + 0.005},
        "margin_down": {"margin_shift": -0.03},
        "tax_up": {"tax_rate": inputs.tax_rate + 0.05},
    }
    vectors: dict[str, object] = {"scenarios": {}, "metrics": {}, "eur": {}, "bridges": {}}
    for name, overrides in scenarios.items():
        scenario = novartis_inputs(data, **overrides)
        result = enterprise_value(scenario)
        vectors["scenarios"][name] = {  # type: ignore[index]
            "inputs": asdict(scenario),
            "enterprise_value": result,
            "bridge": equity_bridge(data, COMPANY, 2025, result["enterprise_value"]),
        }
    waccs = [inputs.wacc + s for s in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    growths = [0.01, 0.015, 0.02, 0.025, 0.03]
    vectors["grid"] = {"waccs": waccs, "growths": growths, "values": sensitivity_grid(inputs, waccs, growths)}
    for company in ("Novartis", "GSK", "Novo Nordisk"):
        for year in (2023, 2024, 2025):
            vectors["metrics"][f"{company}|{year}"] = metrics(data, company, year)  # type: ignore[index]
            vectors["eur"][f"{company}|{year}"] = {  # type: ignore[index]
                "revenue_flow": to_eur(data, company, year, data.get(company, year, "revenue"), "flow"),
                "cash_balance": to_eur(data, company, year, data.get(company, year, "cash"), "balance"),
            }
        vectors["bridges"][company] = {  # type: ignore[index]
            "book": equity_bridge(data, company, 2025, 100_000.0),
            "multiple": equity_bridge(data, company, 2025, 100_000.0, BridgeOptions(nci_method="earnings_multiple")),
        }
    (SITE / "vectors.json").write_text(json.dumps(vectors, indent=1) + "\n", encoding="utf-8")
    write_validation(data, vectors)
    print("site data written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
