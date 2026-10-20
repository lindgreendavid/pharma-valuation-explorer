import math

import pytest

from pharma_valuation.defaults import novartis_inputs
from pharma_valuation.model import (
    BridgeOptions,
    Dataset,
    DcfInputs,
    enterprise_value,
    equity_bridge,
    free_cash_flow,
    gross_debt,
    metrics,
    project,
    sensitivity_grid,
    to_eur,
    wacc_build_up,
)

DATA = Dataset.load()


def flat_inputs(**overrides: float) -> DcfInputs:
    base = {
        "base_revenue": 1000.0,
        "growth": [0.0] * 5,
        "operating_margin": [0.30] * 5,
        "tax_rate": 0.20,
        "da_pct_revenue": 0.05,
        "capex_pct_revenue": 0.05,
        "nwc_pct_revenue": 0.0,
        "base_nwc": 0.0,
        "wacc": 0.08,
        "terminal_growth": 0.0,
    }
    base.update(overrides)
    return DcfInputs(**base)  # type: ignore[arg-type]


def test_constant_cash_flow_is_a_perpetuity() -> None:
    """With no growth and D&A equal to capex, EV is NOPAT / WACC exactly."""

    result = enterprise_value(flat_inputs())
    nopat = 1000 * 0.30 * (1 - 0.20)
    assert result["enterprise_value"] == pytest.approx(nopat / 0.08, rel=1e-12)


def test_gordon_growth_closed_form() -> None:
    inputs = flat_inputs(growth=[0.02] * 5, terminal_growth=0.02, wacc=0.09)
    rows = project(inputs)
    explicit = sum(r["fcff"] / 1.09 ** r["year"] for r in rows)
    terminal_fcff = rows[-1]["nopat"] * 1.02 - 0.0  # nwc is zero and D&A equals capex
    expected = explicit + terminal_fcff / (0.09 - 0.02) / 1.09**5
    assert enterprise_value(inputs, rows)["enterprise_value"] == pytest.approx(expected, rel=1e-12)


def test_mid_year_convention_raises_value_by_half_a_year_of_discounting() -> None:
    end = enterprise_value(flat_inputs())["enterprise_value"]
    mid = enterprise_value(flat_inputs(mid_year=True))["enterprise_value"]
    assert mid == pytest.approx(end * 1.08**0.5, rel=1e-12)


def test_wacc_must_exceed_terminal_growth() -> None:
    with pytest.raises(ValueError):
        enterprise_value(flat_inputs(wacc=0.02, terminal_growth=0.03))


def test_growth_and_margin_lengths_must_match() -> None:
    with pytest.raises(ValueError):
        project(flat_inputs(growth=[0.0, 0.0]))


def test_working_capital_build_reduces_free_cash_flow() -> None:
    without = project(flat_inputs(growth=[0.1] * 5))
    with_nwc = project(flat_inputs(growth=[0.1] * 5, nwc_pct_revenue=0.2, base_nwc=200.0))
    assert all(a["fcff"] > b["fcff"] for a, b in zip(without, with_nwc, strict=True))
    assert with_nwc[0]["delta_nwc"] == pytest.approx(0.2 * 1100 - 200.0)


def test_value_moves_the_right_way_when_assumptions_change() -> None:
    inputs = novartis_inputs(DATA)
    base = enterprise_value(inputs)["enterprise_value"]
    higher_wacc = enterprise_value(novartis_inputs(DATA, wacc=inputs.wacc + 0.01))["enterprise_value"]
    higher_growth = enterprise_value(novartis_inputs(DATA, terminal_growth=inputs.terminal_growth + 0.005))[
        "enterprise_value"
    ]
    higher_margin = enterprise_value(novartis_inputs(DATA, margin_shift=0.02))["enterprise_value"]
    higher_tax = enterprise_value(novartis_inputs(DATA, tax_rate=inputs.tax_rate + 0.05))["enterprise_value"]
    assert higher_wacc < base < higher_growth
    assert higher_margin > base
    assert higher_tax < base


def test_terminal_value_is_a_large_but_not_total_share() -> None:
    share = enterprise_value(novartis_inputs(DATA))["terminal_share_of_value"]
    assert 0.5 < share < 0.95


def test_sensitivity_grid_matches_direct_valuation_and_is_monotone() -> None:
    inputs = novartis_inputs(DATA)
    waccs = [0.06, 0.07, 0.08]
    growths = [0.01, 0.02, 0.03]
    grid = sensitivity_grid(inputs, waccs, growths)
    direct = enterprise_value(novartis_inputs(DATA, wacc=0.07, terminal_growth=0.02))["enterprise_value"]
    assert grid[1][1] == pytest.approx(direct, rel=1e-12)
    for row in grid:
        assert row == sorted(row)
    for column in range(3):
        values = [grid[i][column] for i in range(3)]
        assert values == sorted(values, reverse=True)


def test_wacc_build_up() -> None:
    result = wacc_build_up(0.04, 1.0, 0.05, 0.05, 0.20, 0.25)
    assert result["cost_of_equity"] == pytest.approx(0.09)
    assert result["after_tax_cost_of_debt"] == pytest.approx(0.04)
    assert result["wacc"] == pytest.approx(0.75 * 0.09 + 0.25 * 0.04)


def test_bridge_adds_up_and_itemises_every_line() -> None:
    bridge = equity_bridge(DATA, "Novartis", 2025, 300_000.0)
    assert bridge["equity_value"] == pytest.approx(sum(i["amount"] for i in bridge["items"]))
    labels = " ".join(i["label"] for i in bridge["items"])
    for part in ("borrowings", "cash", "associates", "post-employment", "non-controlling"):
        assert part in labels


def test_bridge_identity_equity_plus_claims_less_assets_equals_enterprise_value() -> None:
    ev = 250_000.0
    bridge = equity_bridge(DATA, "Novartis", 2025, ev)
    claims = (
        gross_debt(DATA, "Novartis", 2025)
        + DATA.get("Novartis", 2025, "pension_liability")
        + DATA.get("Novartis", 2025, "nci_book")
    )
    non_operating = (
        DATA.get("Novartis", 2025, "cash")
        + DATA.get("Novartis", 2025, "short_term_investments")
        + DATA.get("Novartis", 2025, "equity_method_investments")
        + DATA.get("Novartis", 2025, "other_financial_assets")
    )
    assert bridge["equity_value"] + claims - non_operating == pytest.approx(ev)


def test_bridge_options_change_the_result_in_the_expected_direction() -> None:
    full = equity_bridge(DATA, "GSK", 2025, 100_000.0)["equity_value"]
    book = equity_bridge(DATA, "GSK", 2025, 100_000.0, BridgeOptions(nci_method="book"))["equity_value"]
    multiple = equity_bridge(DATA, "GSK", 2025, 100_000.0, BridgeOptions(nci_method="earnings_multiple"))[
        "equity_value"
    ]
    no_pension = equity_bridge(DATA, "GSK", 2025, 100_000.0, BridgeOptions(include_pension_liability=False))[
        "equity_value"
    ]
    assert full == book
    assert multiple < book  # GSK's book NCI is negative; an earnings multiple is a real claim
    assert no_pension > full
    labels = " ".join(i["label"] for i in equity_bridge(DATA, "GSK", 2025, 1.0)["items"])
    assert "contingent consideration" in labels  # debt-like and material for GSK


def test_free_cash_flow_classifies_interest_the_same_way() -> None:
    gsk = free_cash_flow(DATA, "GSK", 2025)
    raw = DATA.get("GSK", 2025, "cfo") - DATA.get("GSK", 2025, "capex_ppe") - DATA.get("GSK", 2025, "capex_intangibles")
    assert gsk == pytest.approx(
        raw
        - DATA.get("GSK", 2025, "interest_paid_outside_cfo")
        + DATA.get("GSK", 2025, "interest_received_outside_cfo")
    )
    novartis = free_cash_flow(DATA, "Novartis", 2025)
    assert novartis == pytest.approx(19144 - 1548 - 2352)


def test_metrics_are_internally_consistent() -> None:
    for company in ("Novartis", "GSK", "Novo Nordisk"):
        for year in (2023, 2024, 2025):
            m = metrics(DATA, company, year)
            assert m["operating_margin"] == pytest.approx(m["operating_income"] / m["revenue"])
            assert m["free_cash_flow"] == pytest.approx(m["fcf_margin"] * m["revenue"])
            assert 0.0 < m["effective_tax_rate"] < 0.4
            assert m["gross_debt"] > 0
        assert "revenue_growth" not in metrics(DATA, company, 2023)
        assert metrics(DATA, company, 2025)["revenue_growth"] == pytest.approx(
            DATA.get(company, 2025, "revenue") / DATA.get(company, 2024, "revenue") - 1
        )


def test_currency_conversion_uses_the_right_rate_and_round_trips() -> None:
    usd = DATA.get("Novartis", 2025, "revenue")
    eur_flow = to_eur(DATA, "Novartis", 2025, usd, "flow")
    eur_balance = to_eur(DATA, "Novartis", 2025, usd, "balance")
    assert eur_flow == pytest.approx(usd / DATA.eur_rate("USD", "annual_average", 2025))
    assert eur_balance == pytest.approx(usd / DATA.eur_rate("USD", "year_end", 2025))
    assert eur_flow != eur_balance
    assert math.isclose(eur_flow * DATA.eur_rate("USD", "annual_average", 2025), usd)


def test_default_inputs_are_documented_and_sane() -> None:
    inputs = novartis_inputs(DATA)
    assert inputs.wacc > inputs.terminal_growth
    assert 0.05 < inputs.wacc < 0.10
    assert len(inputs.growth) == len(inputs.operating_margin) == 5
    assert inputs.shares_outstanding > 1000
    assert "sources" in inputs.extra
