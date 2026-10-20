"""Fetch SEC XBRL company facts and keep the few facts used as a second, independent path.

Two uses: (1) the Novartis recognised post-employment liability, which is not a line on its balance
sheet; (2) a reconciliation set (revenue, operating income, net income, operating cash flow, cash)
read from the JSON facts API instead of the rendered statement pages, so extraction errors show up as differences.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "extracted" / "xbrl_facts.json"
USER_AGENT = "David Lindgreen lindgreendavid@gmail.com portfolio research"
CIKS = {"Novartis": 1114448, "GSK": 1131399, "Novo Nordisk": 353278}
# FY2025 filing accession per company, and the FY2024 filing for 2023 balance-sheet dates
ACCESSIONS = {
    "Novartis": {2025: "0001114448-26-000004", 2024: "0001370368-25-000004"},
    "GSK": {2025: "0001131399-26-000004", 2024: "0001131399-25-000007"},
    "Novo Nordisk": {2025: "0000353278-26-000012", 2024: "0001628280-25-003920"},
}
# company -> field -> (concept, duration or instant)
RECONCILE = {
    "Novartis": {"operating_income": "OperatingIncomeLoss", "cash": "CashAndCashEquivalents"},
    "GSK": {
        "revenue": "Revenue",
        "operating_income": "ProfitLossFromOperatingActivities",
        "net_income": "ProfitLoss",
        "cfo": "CashFlowsFromUsedInOperatingActivities",
        "cash": "CashAndCashEquivalents",
    },
    "Novo Nordisk": {
        "revenue": "Revenue",
        "operating_income": "ProfitLossFromOperatingActivities",
        "net_income": "ProfitLoss",
        "cfo": "CashFlowsFromUsedInOperatingActivities",
        "cash": "CashAndCashEquivalents",
    },
}
RECONCILE_NOVARTIS_EXTRA = {"net_income": "ProfitLoss", "cfo": "CashFlowsFromUsedInOperatingActivities"}


def get_json(url: str) -> dict:
    raw = subprocess.run(
        ["curl", "-sS", "-m", "120", "-H", f"User-Agent: {USER_AGENT}", url], capture_output=True, check=True
    ).stdout
    time.sleep(0.5)
    return json.loads(raw)


def pick(facts: dict, concept: str, end: str, accession: str) -> dict | None:
    unit_map = facts["facts"]["ifrs-full"].get(concept, {}).get("units", {})
    for unit, items in unit_map.items():
        for item in items:
            if item["end"] == end and item["accn"] == accession and item.get("form") == "20-F":
                # annual flows only (period of roughly a year); balances have no start date
                start = item.get("start")
                if start is None or start.endswith("-01-01"):
                    return {
                        "unit": unit,
                        "value": item["val"],
                        "accession": accession,
                        "filed": item["filed"],
                        "concept": concept,
                        "end": end,
                    }
    return None


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    out: dict[str, object] = {"novartis_pension_liability": [], "reconcile": []}
    for company, cik in CIKS.items():
        facts = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
        (RAW / f"companyfacts-{company.lower().replace(' ', '-')}.json").write_text(json.dumps(facts), encoding="utf-8")
        mapping = dict(RECONCILE[company])
        if company == "Novartis":
            mapping.update(RECONCILE_NOVARTIS_EXTRA)
        for year in (2023, 2024, 2025):
            accession = ACCESSIONS[company][2025 if year >= 2024 else 2024]
            if year == 2023 and company != "GSK":
                accession = ACCESSIONS[company][2025]
            for field, concept in mapping.items():
                found = pick(facts, concept, f"{year}-12-31", accession) or pick(
                    facts, concept, f"{year}-12-31", ACCESSIONS[company][2024]
                )
                if found:
                    found.update(company=company, fiscal_year=year, field=field)
                    out["reconcile"].append(found)  # type: ignore[union-attr]
        if company == "Novartis":
            for year, accession in (
                (2025, ACCESSIONS[company][2025]),
                (2024, ACCESSIONS[company][2025]),
                (2023, ACCESSIONS[company][2024]),
            ):
                item = pick(facts, "NoncurrentRecognisedLiabilitiesDefinedBenefitPlan", f"{year}-12-31", accession)
                if item:
                    out["novartis_pension_liability"].append(  # type: ignore[union-attr]
                        {
                            "fiscal_year": year,
                            "value": item["value"],
                            "accession": accession,
                            "filed": item["filed"],
                            "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json (ifrs-full:NoncurrentRecognisedLiabilitiesDefinedBenefitPlan, accn {accession})",
                        }
                    )
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(len(out["reconcile"]), "reconciliation facts;", len(out["novartis_pension_liability"]), "pension facts")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
