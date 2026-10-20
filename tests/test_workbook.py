"""Recalculate the downloadable workbook with an independent evaluator and compare it with the Python model."""

from pathlib import Path

import pytest

formulas = pytest.importorskip("formulas")

from pharma_valuation.defaults import novartis_inputs  # noqa: E402
from pharma_valuation.model import Dataset, enterprise_value, equity_bridge, metrics, sensitivity_grid  # noqa: E402

ROOT = Path(__file__).parents[1]
DATA = Dataset.load()


@pytest.fixture(scope="module")
def solved() -> dict[str, float]:
    model = formulas.ExcelModel().loads(str(ROOT / "site" / "downloads" / "pharma-valuation-model.xlsx")).finish()
    solution = model.calculate()
    out: dict[str, float] = {}
    for key, value in solution.items():
        text = key.upper()
        if "]" in text and "!" in text:
            sheet, cell = text.split("]", 1)[1].split("!", 1)
            if ":" not in cell:
                out[f"{sheet.strip(chr(39))}!{cell}"] = value.value[0, 0]
    return out


def test_enterprise_value_and_per_share_match_the_python_model(solved: dict[str, float]) -> None:
    inputs = novartis_inputs(DATA)
    ev = enterprise_value(inputs)
    assert solved["DCF!B17"] == pytest.approx(inputs.wacc, rel=1e-12)
    assert solved["DCF!B41"] == pytest.approx(ev["enterprise_value"], rel=1e-9)
    assert solved["DCF!B42"] == pytest.approx(ev["terminal_share_of_value"], rel=1e-9)
    bridge = equity_bridge(DATA, "Novartis", 2025, ev["enterprise_value"])
    assert solved["DCF!B53"] == pytest.approx(bridge["equity_value"], rel=1e-9)
    assert solved["DCF!B55"] == pytest.approx(bridge["equity_value"] / inputs.shares_outstanding, rel=1e-9)


def test_sensitivity_grid_matches_the_python_grid(solved: dict[str, float]) -> None:
    inputs = novartis_inputs(DATA)
    waccs = [inputs.wacc + shift for shift in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    growths = [0.01, 0.015, 0.02, 0.025, 0.03]
    grid = sensitivity_grid(inputs, waccs, growths)
    adjustment = equity_bridge(DATA, "Novartis", 2025, 0.0)["equity_value"]
    for i, row in enumerate(grid):
        for j, ev in enumerate(row):
            cell = solved[f"SENSITIVITY!{'BCDEF'[j]}{4 + i}"]
            assert cell == pytest.approx((ev + adjustment) / inputs.shares_outstanding, rel=1e-9)


def test_comparison_sheet_matches_the_python_metrics(solved: dict[str, float]) -> None:
    columns = {("Novartis", 2025): "D", ("GSK", 2025): "G", ("Novo Nordisk", 2025): "J", ("GSK", 2024): "F"}
    rows = {}
    for key, letter in columns.items():
        company, year = key
        m = metrics(DATA, company, year)
        # locate rows by label order: revenue is the first data row (row 4); derived rows follow the 19 base rows plus a gap
        assert solved[f"COMPARISON!{letter}4"] == pytest.approx(m["revenue"])
        rows[key] = m
    # derived rows start after 19 base rows (rows 4-22) and one blank row: growth is row 24
    for key, letter in columns.items():
        m = rows[key]
        assert solved[f"COMPARISON!{letter}25"] == pytest.approx(m["operating_margin"])
        assert solved[f"COMPARISON!{letter}29"] == pytest.approx(m["free_cash_flow"])
        assert solved[f"COMPARISON!{letter}33"] == pytest.approx(m["net_debt"])


def test_workbook_checks_all_pass(solved: dict[str, float]) -> None:
    for row in range(3, 12):
        assert abs(float(solved[f"CHECKS!B{row}"])) <= 1.0
    assert solved["CHECKS!B12"] in (True, 1)
    assert solved["CHECKS!B13"] in (True, 1)
