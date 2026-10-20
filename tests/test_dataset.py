import csv
import hashlib
from pathlib import Path

import pytest

from pharma_valuation.extract import MAPPING, YEARS, parse_number, year_of
from pharma_valuation.model import Dataset
from pharma_valuation.reconcile import run

ROOT = Path(__file__).parents[1]
DATA = Dataset.load()
COMPANIES = list(MAPPING)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(1,548)", -1548.0),
        ("kr 102,434", 102434.0),
        ("$ (17)", -17.0),
        ("  ", None),
        ("1,219,427,096", 1219427096.0),
        ("£ 1.411", 1.411),
    ],
)
def test_number_parsing(text: str, expected: float | None) -> None:
    assert parse_number(text) == expected


def test_year_of_header() -> None:
    assert year_of("Dec. 31, 2025") == 2025
    assert year_of("Dec. 31, 2025 GBP (£)") == 2025
    assert year_of("12 Months Ended") is None


@pytest.mark.parametrize("company", COMPANIES)
def test_every_mapped_field_has_all_three_years(company: str) -> None:
    for field in MAPPING[company]:
        for year in YEARS:
            assert DATA.has(company, year, field), (company, year, field)


@pytest.mark.parametrize("company", COMPANIES)
def test_balance_sheet_identity_holds_for_every_date(company: str) -> None:
    for year in YEARS:
        assets = DATA.get(company, year, "total_assets")
        equity_and_liabilities = DATA.get(company, year, "total_equity") + DATA.get(company, year, "total_liabilities")
        assert abs(assets - equity_and_liabilities) <= 1.0, (company, year)


@pytest.mark.parametrize("company", COMPANIES)
def test_every_fact_is_traceable(company: str) -> None:
    for fact in DATA.payload["facts"]:
        if fact["company"] != company:
            continue
        assert fact["accession"].count("-") == 2
        assert fact["source_url"].startswith("https://")
        assert fact["line_label"]
        assert fact["currency"] == DATA.currency(company)


def test_company_currencies_and_fiscal_years() -> None:
    assert {c: DATA.currency(c) for c in COMPANIES} == {"Novartis": "USD", "GSK": "GBP", "Novo Nordisk": "DKK"}
    assert DATA.payload["years"] == [2023, 2024, 2025]


def test_csv_and_fx_checksums_match_the_dataset() -> None:
    for name, digest in DATA.payload["sha256"].items():
        assert hashlib.sha256((ROOT / "data" / name).read_bytes()).hexdigest() == digest


def test_csv_has_the_same_rows_as_the_json() -> None:
    with (ROOT / "data" / "financials.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(DATA.payload["facts"])


def test_fx_rates_are_plausible_and_eur_is_identity() -> None:
    assert DATA.eur_rate("EUR", "year_end", 2025) == 1.0
    assert 0.9 < DATA.eur_rate("USD", "annual_average", 2025) < 1.4
    assert 0.7 < DATA.eur_rate("GBP", "year_end", 2025) < 1.0
    assert 7.3 < DATA.eur_rate("DKK", "year_end", 2025) < 7.6


def test_every_reconciliation_against_the_xbrl_facts_matches() -> None:
    results = run()
    assert len(results) >= 36
    assert [r for r in results if r["status"] != "match"] == []


def test_discontinued_operations_explain_the_novartis_2023_difference() -> None:
    results = {(r["field"], r["fiscal_year"]): r for r in run() if r["company"] == "Novartis"}
    assert results[("net_income", 2023)]["dataset_value"] == 8572.0
    assert results[("net_income", 2023)]["xbrl_value"] == 14854.0
    assert results[("net_income", 2024)]["dataset_value"] == results[("net_income", 2024)]["xbrl_value"]


def test_selected_figures_equal_the_filings() -> None:
    """Hand-checked against the filed statements (see docs/reconciliation.md)."""

    expected = {
        ("Novartis", 2025, "revenue"): 54532.0,
        ("Novartis", 2025, "operating_income"): 17644.0,
        ("Novartis", 2025, "cfo"): 19144.0,
        ("GSK", 2025, "revenue"): 32667.0,
        ("GSK", 2025, "operating_income"): 7932.0,
        ("GSK", 2025, "cfo"): 7741.0,
        ("Novo Nordisk", 2025, "revenue"): 309064.0,
        ("Novo Nordisk", 2025, "operating_income"): 127658.0,
        ("Novo Nordisk", 2025, "cfo"): 119102.0,
    }
    for (company, year, field), value in expected.items():
        assert DATA.get(company, year, field) == value


def test_rebuilding_the_facts_from_the_saved_statements_reproduces_the_dataset() -> None:
    from pharma_valuation.extract import Rule, build_facts, find_row, load_statements

    statements = load_statements(ROOT / "data" / "extracted" / "statements.json")
    rebuilt = {(f["company"], f["fiscal_year"], f["field"]): f["value"] for f in build_facts(statements)}
    stored = {(f["company"], f["fiscal_year"], f["field"]): f["value"] for f in DATA.payload["facts"]}
    assert rebuilt
    assert all(stored[key] == value for key, value in rebuilt.items())
    with pytest.raises(KeyError):
        find_row(statements[0]["statements"]["income_statement"], Rule("income_statement", r"^No such line$"))


def test_a_true_minus_sign_is_parsed_and_digits_are_untouched() -> None:
    assert parse_number("\u22121,234") == -1234.0
    assert parse_number("52,212") == 52212.0
