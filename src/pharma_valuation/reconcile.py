"""Reconcile extracted figures to a second, independent path through the same public filings.

Path A (the dataset) reads the rendered statement pages. Path B reads the SEC XBRL JSON facts API.
A mapping or parsing error in A shows up as a difference against B. Known, explained differences
(Novartis reports discontinued operations: the XBRL totals include them, the dataset uses continuing
operations) are checked against the statements' own totals rather than waved through.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pharma_valuation.extract import parse_number, year_of

ROOT = Path(__file__).parents[2]
TOLERANCE = 0.5  # millions: both paths report whole millions


def load_json(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def statement_total(statements: list[dict[str, Any]], company: str, kind: str, pattern: str, year: int) -> float | None:
    """Value of a labelled row from the most recent filing that contains the year."""

    for filing in sorted((f for f in statements if f["company"] == company), key=lambda f: -f["fiscal_year"]):
        statement = filing["statements"][kind]
        for row in statement["rows"]:
            if re.search(pattern, row["label"]) and any(row["values"]):
                for header, text in zip(statement["headers"], row["values"], strict=False):
                    if year_of(header) == year and parse_number(text) is not None:
                        return parse_number(text)
    return None


def run() -> list[dict[str, Any]]:
    dataset = load_json("data/dataset.json")
    statements = load_json("data/extracted/statements.json")
    facts = {(f["company"], f["fiscal_year"], f["field"]): f["value"] for f in dataset["facts"]}
    xbrl = load_json("data/extracted/xbrl_facts.json")["reconcile"]
    results: list[dict[str, Any]] = []
    for item in xbrl:
        company, year, field = item["company"], item["fiscal_year"], item["field"]
        other = item["value"] / 1e6
        mine = facts.get((company, year, field))
        status, explanation = "match", ""
        expected = mine
        if company == "Novartis" and field in ("net_income", "cfo"):
            # XBRL ProfitLoss and CashFlowsFromUsedInOperatingActivities include discontinued operations.
            pattern = r"^Net income$" if field == "net_income" else r"^Total net cash flows from operating activities"
            kind = "income_statement" if field == "net_income" else "cash_flow"
            expected = statement_total(statements, company, kind, pattern, year)
            explanation = "XBRL concept is the total including discontinued operations; compared with the statement's own total row"
        if expected is None:
            status = "not_compared"
        elif abs(expected - other) > TOLERANCE:
            status = "difference"
        results.append(
            {
                "company": company,
                "fiscal_year": year,
                "field": field,
                "dataset_value": mine,
                "compared_with": expected,
                "xbrl_value": other,
                "xbrl_concept": item["concept"],
                "accession": item["accession"],
                "status": status,
                "explanation": explanation,
            }
        )
    return results
