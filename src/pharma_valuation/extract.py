"""Turn the parsed SEC statement pages into the traceable dataset.

Every datum is a (company, fiscal year, field) with the value as filed (millions of the reporting
currency), the accession number, the R page it came from and the line label. Nothing is estimated,
adjusted or converted here. The declarative MAPPING below is the whole definition of the dataset.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMPANIES = {
    "Novartis": {"currency": "USD", "ticker_note": "NOVN (SIX), NVS (NYSE ADS, 1 share)"},
    "GSK": {"currency": "GBP", "ticker_note": "GSK (LSE), GSK (NYSE ADS, 2 shares)"},
    "Novo Nordisk": {"currency": "DKK", "ticker_note": "NOVO B (Nasdaq Copenhagen), NVO (NYSE ADS, 1 share)"},
}
YEARS = (2023, 2024, 2025)


@dataclass(frozen=True)
class Rule:
    """Where one field comes from: a statement, a label pattern and which match to take."""

    statement: str
    pattern: str
    occurrence: int = 0
    absolute: bool = False  # liabilities shown as negatives are stored as positive magnitudes
    note: str = ""


# The mapping is explicit so each choice is reviewable. "income_statement", "cash_flow" and
# "balance_sheet" refer to the FY2025 filing; balance-sheet dates not in it come from the FY2024 filing.
MAPPING: dict[str, dict[str, Rule]] = {
    "Novartis": {
        "revenue": Rule(
            "income_statement",
            r"^Net sales from continuing operations",
            note="Net sales; 'other revenues' are excluded",
        ),
        "operating_income": Rule("income_statement", r"^Operating income from continuing operations"),
        "r_and_d": Rule("income_statement", r"^Research and development$", absolute=True),
        "pretax_income": Rule("income_statement", r"^Income before taxes from continuing operations"),
        "income_tax": Rule("income_statement", r"^Income taxes$", absolute=True),
        "interest_expense": Rule("income_statement", r"^Interest expense", absolute=True),
        "net_income": Rule(
            "income_statement",
            r"^Net income from continuing operations",
            note="Continuing operations; 2023 excludes the Sandoz spin-off",
        ),
        "nci_profit": Rule("income_statement", r"^Non-controlling interests$"),
        "cfo": Rule("cash_flow", r"^Net cash flows from operating activities from continuing operations$"),
        "capex_ppe": Rule("cash_flow", r"^Purchases of property, plant and equipment", absolute=True),
        "capex_intangibles": Rule("cash_flow", r"^Purchases of intangible assets", absolute=True),
        "interest_paid_in_cfo": Rule(
            "cash_flow", r"^Interest paid", absolute=True, note="Interest paid is inside operating cash flow"
        ),
        "interest_received_in_cfo": Rule(
            "cash_flow", r"^Interest received", note="Interest received is inside operating cash flow"
        ),
        "lease_principal": Rule("cash_flow", r"^Payments of lease liabilities", absolute=True),
        "dividends_paid": Rule("cash_flow", r"^Dividends paid to shareholders", absolute=True),
        "buybacks": Rule("cash_flow", r"^Purchases of treasury shares", absolute=True),
        "cash": Rule("balance_sheet", r"^Cash and cash equivalents$"),
        "short_term_investments": Rule(
            "balance_sheet",
            r"^Marketable securities(, commodities)?, time deposits and derivative",
            note="Includes derivative financial instruments",
        ),
        "debt_current": Rule(
            "balance_sheet",
            r"^Financial debts and derivative financial instruments",
            note="Includes derivative financial instruments",
        ),
        "debt_noncurrent": Rule("balance_sheet", r"^Financial debts$"),
        "lease_noncurrent": Rule("balance_sheet", r"^Lease liabilities", 0),
        "lease_current": Rule("balance_sheet", r"^Lease liabilities", 1),
        "nci_book": Rule("balance_sheet", r"^Non-controlling interests$"),
        "equity_method_investments": Rule("balance_sheet", r"^Investments in associated companies"),
        "other_financial_assets": Rule(
            "balance_sheet", r"^Financial assets$", note="Non-current financial assets, book value"
        ),
        "total_equity": Rule("balance_sheet", r"^Total equity$"),
        "total_assets": Rule("balance_sheet", r"^Total assets$"),
        "total_liabilities": Rule("balance_sheet", r"^Total liabilities$"),
        "inventories": Rule("balance_sheet", r"^Inventories$"),
        "receivables": Rule("balance_sheet", r"^Trade receivables$"),
        "payables": Rule("balance_sheet", r"^Trade payables$"),
    },
    "GSK": {
        "revenue": Rule("income_statement", r"^Turnover$", note="Turnover; royalty income is excluded"),
        "operating_income": Rule("income_statement", r"^Operating profit$"),
        "r_and_d": Rule("income_statement", r"^Research and development$", absolute=True),
        "pretax_income": Rule("income_statement", r"^Profit before taxation"),
        "income_tax": Rule("income_statement", r"^Taxation$", absolute=True),
        "net_income": Rule("income_statement", r"^Profit after taxation"),
        "nci_profit": Rule("income_statement", r"^Profit attributable to non-controlling interests"),
        "cfo": Rule("cash_flow", r"^Total net cash inflow/\(outflow\) from operating activities"),
        "capex_ppe": Rule("cash_flow", r"^Purchase of property, plant and equipment", absolute=True),
        "capex_intangibles": Rule("cash_flow", r"^Purchase of intangible assets", absolute=True),
        "interest_paid_outside_cfo": Rule(
            "cash_flow", r"^Interest paid", absolute=True, note="GSK reports interest paid in financing activities"
        ),
        "interest_received_outside_cfo": Rule(
            "cash_flow", r"^Interest received", note="GSK reports interest received in investing activities"
        ),
        "lease_principal": Rule("cash_flow", r"^Repayment of lease liabilities", absolute=True),
        "dividends_paid": Rule("cash_flow", r"^Dividends paid to shareholders", absolute=True),
        "buybacks": Rule("cash_flow", r"^Purchase of treasury shares", absolute=True),
        "cash": Rule("balance_sheet", r"^Cash and cash equivalents$"),
        "short_term_investments": Rule("balance_sheet", r"^Liquid investments"),
        "debt_current": Rule(
            "balance_sheet", r"^Short-term borrowings", absolute=True, note="Borrowings include lease liabilities"
        ),
        "debt_noncurrent": Rule(
            "balance_sheet", r"^Long-term borrowings", absolute=True, note="Borrowings include lease liabilities"
        ),
        "pension_liability": Rule("balance_sheet", r"^Pensions and other post-employment benefits", absolute=True),
        "contingent_consideration_current": Rule(
            "balance_sheet", r"^Contingent consideration liabilities", 0, absolute=True
        ),
        "contingent_consideration_noncurrent": Rule(
            "balance_sheet", r"^Contingent consideration liabilities", 1, absolute=True
        ),
        "nci_book": Rule(
            "balance_sheet", r"^Non-controlling interests$", note="Negative book value; see the bridge notes"
        ),
        "equity_method_investments": Rule("balance_sheet", r"^Investments in associates and joint ventures"),
        "other_financial_assets": Rule(
            "balance_sheet", r"^Other investments", note="Non-current investments, book value"
        ),
        "total_equity": Rule("balance_sheet", r"^Total equity$"),
        "total_assets": Rule("balance_sheet", r"^Total assets$"),
        "total_liabilities": Rule("balance_sheet", r"^Total liabilities$", absolute=True),
        "inventories": Rule("balance_sheet", r"^Inventories$"),
        "receivables": Rule("balance_sheet", r"^Trade and other receivables"),
        "payables": Rule("balance_sheet", r"^Trade and other payables", absolute=True),
    },
    "Novo Nordisk": {
        "revenue": Rule("income_statement", r"^Net sales$"),
        "operating_income": Rule("income_statement", r"^Operating profit$"),
        "r_and_d": Rule("income_statement", r"^Research and development costs", absolute=True),
        "pretax_income": Rule("income_statement", r"^Profit before income taxes"),
        "income_tax": Rule("income_statement", r"^Income taxes$", absolute=True),
        "net_income": Rule("income_statement", r"^Net profit$"),
        "cfo": Rule("cash_flow", r"^Net cash flows from operating activities"),
        "capex_ppe": Rule("cash_flow", r"^Purchase of property, plant and equipment", absolute=True),
        "capex_intangibles": Rule("cash_flow", r"^Purchase of intangible assets", absolute=True),
        "interest_paid_in_cfo": Rule(
            "cash_flow", r"^Interest paid", absolute=True, note="Interest paid is inside operating cash flow"
        ),
        "interest_received_in_cfo": Rule(
            "cash_flow", r"^Interest received", note="Interest received is inside operating cash flow"
        ),
        "dividends_paid": Rule("cash_flow", r"^Dividends paid", absolute=True),
        "buybacks": Rule("cash_flow", r"^Purchase of treasury shares", absolute=True),
        "cash": Rule("balance_sheet", r"^Cash at bank"),
        "short_term_investments": Rule("balance_sheet", r"^Marketable securities"),
        "debt_noncurrent": Rule("balance_sheet", r"^Borrowings$", 0, note="Borrowings include lease liabilities"),
        "debt_current": Rule("balance_sheet", r"^Borrowings$", 1, note="Borrowings include lease liabilities"),
        "pension_liability": Rule("balance_sheet", r"^Retirement benefit obligations"),
        "equity_method_investments": Rule("balance_sheet", r"^Investments in associated companies"),
        "other_financial_assets": Rule(
            "balance_sheet", r"^Other financial assets", note="Non-current financial assets, book value"
        ),
        "total_equity": Rule("balance_sheet", r"^Total equity$"),
        "total_assets": Rule("balance_sheet", r"^Total assets$"),
        "total_liabilities": Rule("balance_sheet", r"^Total liabilities$"),
        "inventories": Rule("balance_sheet", r"^Inventories$"),
        "receivables": Rule("balance_sheet", r"^Trade receivables$"),
        "payables": Rule("balance_sheet", r"^Trade payables$"),
    },
}

NUMBER = re.compile(r"-?[\d,]+(?:\.\d+)?")


def parse_number(text: str) -> float | None:
    """'(1,548)' -> -1548.0; 'kr 102,434' -> 102434.0; '' -> None."""

    cleaned = text.strip()
    if not cleaned:
        return None
    negative = cleaned.startswith("(") or cleaned.startswith("-") or "(" in cleaned
    match = NUMBER.search(cleaned.replace("\u2212", "-"))
    if not match:
        return None
    value = float(match.group(0).replace(",", ""))
    return -abs(value) if negative else value


def year_of(header: str) -> int | None:
    match = re.search(r"(20\d\d)", header)
    return int(match.group(1)) if match else None


def find_row(statement: dict[str, Any], rule: Rule) -> dict[str, Any]:
    pattern = re.compile(rule.pattern)
    matches = [row for row in statement["rows"] if pattern.search(row["label"]) and any(row["values"])]
    if len(matches) <= rule.occurrence:
        raise KeyError(f"no match {rule.occurrence} for {rule.pattern!r} in {statement['title']}")
    row: dict[str, Any] = matches[rule.occurrence]
    return row


def build_facts(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per (company, fiscal year, field). Later filings win only where an earlier one lacks the year."""

    by_company: dict[str, dict[int, dict[str, Any]]] = {}
    for filing in statements:
        by_company.setdefault(filing["company"], {})[filing["fiscal_year"]] = filing
    facts: list[dict[str, Any]] = []
    for company, mapping in MAPPING.items():
        filings = by_company[company]
        for field, rule in mapping.items():
            seen: set[int] = set()
            # prefer the most recent filing; fall back to the earlier filing for older balance-sheet dates
            for fiscal_year in sorted(filings, reverse=True):
                filing = filings[fiscal_year]
                statement = filing["statements"][rule.statement]
                try:
                    row = find_row(statement, rule)
                except KeyError:
                    continue
                for header, text in zip(statement["headers"], row["values"], strict=False):
                    year = year_of(header)
                    value = parse_number(text)
                    if year not in YEARS or year in seen or value is None:
                        continue
                    seen.add(year)
                    facts.append(
                        {
                            "company": company,
                            "fiscal_year": year,
                            "field": field,
                            "value": abs(value) if rule.absolute else value,
                            "currency": COMPANIES[company]["currency"],
                            "unit": "millions",
                            "accession": filing["accession"],
                            "filed": filing["filed"],
                            "source_page": f"{statement['page']}",
                            "source_url": statement["url"],
                            "line_label": row["label"],
                            "note": rule.note,
                        }
                    )
    return facts


def load_statements(path: Path) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return data
