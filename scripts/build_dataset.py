"""Assemble the traceable dataset from the parsed statement pages, note pages and XBRL facts.

Writes data/financials.csv (one row per company, fiscal year and field, with its source) and
data/dataset.json (the same facts plus FX rates and checksums), the two files the model and the site read.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pharma_valuation.extract import (  # noqa: E402
    COMPANIES,
    YEARS,
    build_facts,
    load_statements,
    parse_number,
    year_of,
)

FIELDS = [
    "company",
    "fiscal_year",
    "field",
    "value",
    "currency",
    "unit",
    "accession",
    "filed",
    "source_page",
    "source_url",
    "line_label",
    "note",
]


def first_nonempty_per_column(page: dict, label: str) -> dict[int, float]:
    """For a note page, the first non-empty value of each year column in rows with the given label."""

    out: dict[int, float] = {}
    for row in page["rows"]:
        if row["label"] != label:
            continue
        for header, text in zip(page["headers"], row["values"], strict=False):
            year = year_of(header)
            number = parse_number(text)
            if year in YEARS and year not in out and number is not None:
                out[year] = abs(number)
    return out


def main() -> int:
    statements = load_statements(ROOT / "data/extracted/statements.json")
    facts = build_facts(statements)
    notes = json.loads((ROOT / "data/extracted/notes.json").read_text(encoding="utf-8"))
    xbrl = json.loads((ROOT / "data/extracted/xbrl_facts.json").read_text(encoding="utf-8"))
    filings = {(f["company"], f["fiscal_year"]): f for f in statements}

    # Novartis depreciation and amortisation from the property and intangible notes (FY2025 filing).
    novartis_filing = filings[("Novartis", 2025)]
    for page in notes:
        if page["company"] != "Novartis" or page["page"] not in ("R90.htm", "R99.htm"):
            continue
        label, field, description = (
            (
                "Depreciation charge",
                "depreciation_ppe",
                "Depreciation of property, plant and equipment (excludes right-of-use assets and impairments)",
            )
            if page["page"] == "R90.htm"
            else (
                "Amortization charge",
                "amortisation_intangibles",
                "Amortisation of intangible assets other than goodwill (excludes impairments)",
            )
        )
        for year, value in first_nonempty_per_column(page, label).items():
            facts.append(
                {
                    "company": "Novartis",
                    "fiscal_year": year,
                    "field": field,
                    "value": value,
                    "currency": "USD",
                    "unit": "millions",
                    "accession": novartis_filing["accession"],
                    "filed": novartis_filing["filed"],
                    "source_page": page["page"],
                    "source_url": page["url"],
                    "line_label": label,
                    "note": description,
                }
            )
    # Novartis recognised post-employment liability from the filing's XBRL facts.
    for item in xbrl["novartis_pension_liability"]:
        facts.append(
            {
                "company": "Novartis",
                "fiscal_year": item["fiscal_year"],
                "field": "pension_liability",
                "value": item["value"] / 1e6,
                "currency": "USD",
                "unit": "millions",
                "accession": item["accession"],
                "filed": item["filed"],
                "source_page": "XBRL fact",
                "source_url": item["source_url"],
                "line_label": "ifrs-full:NoncurrentRecognisedLiabilitiesDefinedBenefitPlan",
                "note": "Recognised liability only; plan surpluses are not netted",
            }
        )
    # Shares outstanding as stated on each FY2025 filing's cover page.
    for page in notes:
        if page["purpose"] != "cover page" or page["fiscal_year"] != 2025:
            continue
        values = [
            parse_number(row["values"][0])
            for row in page["rows"]
            if row["label"] == "Entity Common Stock, Shares Outstanding" and row["values"]
        ]
        total = sum(v for v in values if v is not None)
        facts.append(
            {
                "company": page["company"],
                "fiscal_year": 2025,
                "field": "shares_outstanding_cover",
                "value": total / 1e6,
                "currency": COMPANIES[page["company"]]["currency"],
                "unit": "millions of shares",
                "accession": filings[(page["company"], 2025)]["accession"],
                "filed": filings[(page["company"], 2025)]["filed"],
                "source_page": page["page"],
                "source_url": page["url"],
                "line_label": "Entity Common Stock, Shares Outstanding",
                "note": "As stated on the cover page (cover date after fiscal year-end). Novo Nordisk: class A plus class B, includes treasury shares",
            }
        )

    facts.sort(key=lambda f: (f["company"], f["field"], f["fiscal_year"]))
    csv_path = ROOT / "data" / "financials.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(facts)
    fx = list(csv.DictReader((ROOT / "data" / "ecb-fx-rates.csv").open(encoding="utf-8")))
    payload = {
        "schema_version": 1,
        "companies": COMPANIES,
        "years": list(YEARS),
        "fx": fx,
        "facts": facts,
        "filings": [
            {k: f[k] for k in ("company", "fiscal_year", "accession", "filed", "filing_index")} for f in statements
        ],
        "sha256": {
            "financials.csv": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            "ecb-fx-rates.csv": hashlib.sha256((ROOT / "data" / "ecb-fx-rates.csv").read_bytes()).hexdigest(),
        },
    }
    (ROOT / "data" / "dataset.json").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(len(facts), "facts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
