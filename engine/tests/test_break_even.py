"""TEST_SUITE_SPEC §5 Break-even dan §6 Target laba."""

from decimal import Decimal as D

from conftest import assert_ok, assert_status, money, rate

from pricing_engine.break_even import (
    FixedCostTier,
    MixBasis,
    MixItem,
    TargetType,
    TaxRegime,
    break_even_multi,
    break_even_revenue,
    break_even_single,
    break_even_step,
    required_revenue,
)
from pricing_engine.core import Status

STEP_TIERS = [
    FixedCostTier(1, 1000, "10000000"),
    FixedCostTier(1001, 2000, "15000000"),
    FixedCostTier(2001, 3000, "22000000"),
]


def test_BEP_01_revenue():
    r = break_even_revenue(fixed_cost="50000000", cmr="0.40")
    assert money(r["bep_revenue"]) == D("125000000.00")


def test_BEP_02_units():
    r = break_even_single(fixed_cost="50000000", unit_price="100000", unit_variable_cost="60000")
    assert_ok(r)
    assert r["unit_contribution"] == D("40000")
    assert r["bep_units"] == D("1250")
    assert money(r["bep_revenue"]) == D("125000000.00")


def test_BEP_03_round_up_discrete():
    r = break_even_single(fixed_cost="50000000", unit_contribution="30000")
    assert r["bep_units"] == D("1667")


def test_BEP_04_negative_contribution():
    assert_status(break_even_single(fixed_cost="50000000", unit_price="50000", unit_variable_cost="60000"), Status.NO_BREAK_EVEN)


def test_BEP_05_zero_contribution():
    assert_status(break_even_single(fixed_cost="50000000", unit_price="60000", unit_variable_cost="60000"), Status.NO_BREAK_EVEN)


def test_BEP_06_zero_fixed_cost():
    r = break_even_single(fixed_cost="0", unit_contribution="40000")
    assert_ok(r)
    assert r["bep_units"] == 0


def test_BEP_07_step_fixed():
    r = break_even_step(unit_contribution="12000", tiers=STEP_TIERS)
    assert_ok(r)
    assert r["first_break_even_units"] == D("834")
    assert r["profitable_ranges"] == [(D("834"), D("1000")), (D("1250"), D("3000"))]
    assert r["tiers"][2]["profit_at_start"] == D("2012000")


def test_BEP_08_step_fixed_no_profitable_range():
    r = break_even_step(unit_contribution="5000", tiers=STEP_TIERS)
    assert_status(r, Status.NO_BREAK_EVEN_WITHIN_CAPACITY)
    assert [t["q_star"] for t in r["tiers"]] == [D("2000"), D("3000"), D("4400")]


def test_BEP_09_weighted_contribution():
    r = break_even_multi(
        fixed_cost="45000000",
        products=[MixItem("A", "100000", "60000", "0.6"), MixItem("B", "50000", "20000", "0.4")],
        mix_basis=MixBasis.UNITS,
    )
    assert_ok(r)
    assert r["r_mix"] == D("80000")
    assert r["cm_mix"] == D("36000")
    assert rate(r["wcmr"]) == D("0.450000")
    assert money(r["bep_revenue"]) == D("100000000.00")
    assert r["bep_mix_units"] == D("1250")
    assert r["bep_units"] == {"A": D("750"), "B": D("500")}


def test_weighted_mix_by_revenue_matches_units():
    # mix unit 0.6/0.4 ⇔ mix pendapatan 60000/80000 dan 20000/80000
    r = break_even_multi(
        fixed_cost="45000000",
        products=[MixItem("A", "100000", "60000", "0.75"), MixItem("B", "50000", "20000", "0.25")],
        mix_basis=MixBasis.REVENUE,
    )
    assert money(r["bep_revenue"]) == D("100000000.00")
    assert money(r["bep_units"]["A"]) == D("750.00")


def test_mix_must_sum_to_one():
    r = break_even_multi(fixed_cost="1", products=[MixItem("A", "10", "5", "0.5")])
    assert_status(r, Status.INVALID_INPUT)


def test_TGT_01_operating_profit():
    r = required_revenue(fixed_cost="50000000", cmr="0.40", target_amount="30000000")
    assert money(r["required_revenue"]) == D("200000000.00")


def test_TGT_02_net_profit_profit_based():
    r = required_revenue(
        fixed_cost="50000000",
        cmr="0.40",
        target_amount="39000000",
        target_type=TargetType.NET_PROFIT,
        tax_regime=TaxRegime.PROFIT_BASED,
        tax_rate="0.22",
    )
    assert money(r["required_pbt"]) == D("50000000.00")
    assert money(r["required_revenue"]) == D("250000000.00")


def test_TGT_03_net_profit_turnover_based():
    r = required_revenue(
        fixed_cost="50000000",
        cmr="0.40",
        target_amount="30000000",
        target_type=TargetType.NET_PROFIT,
        tax_regime=TaxRegime.TURNOVER_FINAL,
        tax_rate="0.005",
    )
    assert money(r["required_revenue"]) == D("202531645.57")


def test_TGT_04_cmr_below_turnover_rate():
    r = required_revenue(
        fixed_cost="50000000",
        cmr="0.004",
        target_amount="30000000",
        target_type=TargetType.NET_PROFIT,
        tax_regime=TaxRegime.TURNOVER_FINAL,
        tax_rate="0.005",
    )
    assert_status(r, Status.INFEASIBLE_MARGIN)
