"""Cross-check this dataset against an independently built one (the portfolio site's Pharma dataset).

The portfolio site's dataset was extracted by a different path (SEC XBRL company-facts tags); this one reads
the rendered statement pages. Where the two cover the same company, year and measure, they should agree.
Usage: python scripts/cross_check_parallel.py PATH_TO_OTHER_dataset.json
Writes docs/cross-check.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pharma_valuation.model import Dataset, gross_debt  # noqa: E402

PAIRS = {
    "operating_profit": "operating_income",
    "pretax_profit": "pretax_income",
    "income_tax": "income_tax",
    "profit_continuing": "net_income",
    "nci_profit": "nci_profit",
    "rnd": "r_and_d",
    "cfo": "cfo",
    "capex_ppe": "capex_ppe",
    "capex_intangibles": "capex_intangibles",
    "cash": "cash",
    "nci_book": "nci_book",
    "equity_total": "total_equity",
    "liquid_investments": "short_term_investments",
}


def main() -> int:
    other = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    mine = Dataset.load()
    lines = ["# Cross-check against an independently built dataset", ""]
    lines.append(
        "The portfolio site's Pharma dataset was extracted through SEC XBRL company-facts tags; this repository's dataset reads the rendered statement pages. "
        "Same companies (Novartis, GSK), same years (2023 to 2025). Values in millions of reporting currency."
    )
    lines.append("")
    lines.append("| Company | Year | Measure | This dataset | Other dataset | Result |")
    lines.append("| --- | --- | --- | ---: | ---: | --- |")
    compared = matched = 0
    differences: list[str] = []
    for key, company in (("novartis", "Novartis"), ("gsk", "GSK")):
        years = other["companies"][key]["years"]
        for year in ("2023", "2024", "2025"):
            row = years[year]
            for theirs, ours in PAIRS.items():
                if theirs not in row or not mine.has(company, int(year), ours):
                    continue
                a = float(mine.get(company, int(year), ours))
                b = float(row[theirs]["value"] if isinstance(row[theirs], dict) else row[theirs])
                ok = abs(a - b) <= 0.5
                compared += 1
                matched += ok
                if not ok:
                    differences.append(f"{company} {year} {theirs}: {a} vs {b}")
                lines.append(
                    f"| {company} | {year} | {ours} | {a:,.0f} | {b:,.0f} | {'match' if ok else 'DIFFERENT'} |"
                )
            if company == "GSK" and "debt_financial" in row:
                a = gross_debt(mine, company, int(year))
                b = float(row["debt_financial"]["value"])
                compared += 1
                matched += abs(a - b) <= 0.5
                lines.append(
                    f"| GSK | {year} | gross debt | {a:,.0f} | {b:,.0f} | {'match' if abs(a - b) <= 0.5 else 'DIFFERENT'} |"
                )
    lines.insert(3, f"**{matched} of {compared} compared values agree.**")
    lines.insert(4, "")
    if differences:
        lines += ["", "## Differences", *[f"- {d}" for d in differences]]
    (ROOT / "docs" / "cross-check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(matched, "of", compared)
    return 0 if matched == compared else 1


if __name__ == "__main__":
    raise SystemExit(main())
