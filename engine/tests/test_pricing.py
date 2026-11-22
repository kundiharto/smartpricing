"""TEST_SUITE_SPEC §1 Pricing, §2 Diskon, §3 Pembulatan."""

from decimal import Decimal as D

from conftest import assert_ok, assert_status, money, rate
from hypothesis import given
from hypothesis import strategies as st

from pricing_engine.core import Status
from pricing_engine.pricing import (
    TAX_LOAD_LABEL,
    MarginDefinition,
    PercentageFee,
    PriceBase,
    PricingMethod,
    calculate_price,
    evaluate_price,
    validate_publication,
)
from pricing_engine.rounding import RoundingMode, round_price

MP_FEE = PercentageFee("marketplace", "0.10", PriceBase.NET_PRICE)


# --- §1 Pricing ---------------------------------------------------------------


def test_PRC_01_markup():
    r = calculate_price(method=PricingMethod.MARKUP, unit_cost="60000", markup="0.25")
    assert_ok(r)
    assert money(r["net_price"]) == D("75000.00")


def test_PRC_02_target_gross_margin():
    r = calculate_price(method=PricingMethod.TARGET_GROSS_MARGIN, unit_cost="60000", target_margin="0.30")
    assert_ok(r)
    assert money(r["net_price"]) == D("85714.29")


def test_PRC_03_contribution_margin_with_fee():
    r = calculate_price(
        method=PricingMethod.TARGET_CONTRIBUTION_MARGIN, unit_cost="60000", target_margin="0.30", fees=[MP_FEE]
    )
    assert_ok(r)
    assert money(r["net_price"]) == D("100000.00")
    assert money(r["fee_total"]) == D("10000.00")
    assert money(r["contribution"]) == D("30000.00")
    assert rate(r["contribution_margin"]) == D("0.300000")


def test_PRC_04_discount_backwards():
    r = calculate_price(
        method=PricingMethod.TARGET_CONTRIBUTION_MARGIN, unit_cost="60000", target_margin="0.30", discount="0.20"
    )
    assert_ok(r)
    assert money(r["net_price"]) == D("85714.29")
    assert money(r["list_price"]) == D("107142.86")
    assert money(r["discount_amount"]) == D("21428.57")


def test_PRC_05_discount_and_fee_on_net():
    r = calculate_price(
        method=PricingMethod.TARGET_CONTRIBUTION_MARGIN,
        unit_cost="60000",
        target_margin="0.30",
        discount="0.20",
        fees=[MP_FEE],
    )
    assert_ok(r)
    assert money(r["net_price"]) == D("100000.00")
    assert money(r["list_price"]) == D("125000.00")


def test_PRC_06_fee_on_list_price():
    r = calculate_price(
        method=PricingMethod.TARGET_CONTRIBUTION_MARGIN,
        unit_cost="60000",
        target_margin="0.30",
        discount="0.20",
        fees=[PercentageFee("list fee", "0.05", PriceBase.LIST_PRICE)],
    )
    assert_ok(r)
    assert money(r["net_price"]) == D("94117.65")
    assert money(r["list_price"]) == D("117647.06")
    assert money(r["fee_total"]) == D("5882.35")
    assert money(r["contribution"]) == D("28235.29")
    assert rate(r["contribution_margin"]) == D("0.300000")
    assert any("0.0625" in line for line in r.trace)


def test_PRC_07_infeasible_margin():
    r = calculate_price(
        method=PricingMethod.TARGET_CONTRIBUTION_MARGIN,
        unit_cost="60000",
        target_margin="0.60",
        fees=[PercentageFee("fee", "0.45")],
    )
    assert_status(r, Status.INFEASIBLE_MARGIN)


def test_PRC_08_minimum_price():
    r = calculate_price(method=PricingMethod.MINIMUM_VIABLE, unit_cost="60000", fees=[MP_FEE])
    assert_ok(r)
    assert money(r["net_price"]) == D("66666.67")
    assert r["minimum_price"] == r["net_price"]


def test_PRC_09_break_even_price():
    r = calculate_price(method=PricingMethod.BREAK_EVEN, unit_cost="60000", fixed_cost="50000000", volume="2000")
    assert_ok(r)
    assert money(r["net_price"]) == D("85000.00")


def test_PRC_10_target_operating_profit_price():
    r = calculate_price(
        method=PricingMethod.TARGET_OPERATING_PROFIT,
        unit_cost="60000",
        fixed_cost="50000000",
        target_operating_profit="30000000",
        volume="2000",
    )
    assert_ok(r)
    assert money(r["net_price"]) == D("100000.00")


def test_PRC_11_turnover_tax_load():
    r = calculate_price(
        method=PricingMethod.TARGET_CONTRIBUTION_MARGIN,
        unit_cost="60000",
        target_margin="0.30",
        fees=[MP_FEE],
        turnover_tax_load="0.005",
    )
    assert_ok(r)
    assert money(r["net_price"]) == D("100840.34")
    assert r["tax_load_label"] == TAX_LOAD_LABEL
    assert rate(r["margin_after_tax_load"]) == D("0.300000")


def test_PRC_12_zero_volume_invalid():
    r = calculate_price(method=PricingMethod.BREAK_EVEN, unit_cost="60000", fixed_cost="50000000", volume="0")
    assert_status(r, Status.INVALID_INPUT)


def test_float_input_rejected():
    r = calculate_price(method=PricingMethod.MARKUP, unit_cost=60000.0, markup="0.25")
    assert_status(r, Status.INVALID_INPUT)
    assert "float" in r.message


def test_competitive_price_below_minimum_warns():
    r = calculate_price(
        method=PricingMethod.COMPETITIVE, unit_cost="60000", fees=[MP_FEE], reference_price="70000", adjustment="-0.10"
    )
    assert_ok(r, Status.BELOW_MIN_PRICE)
    assert money(r["net_price"]) == D("63000.00")


# --- §2 Diskon ----------------------------------------------------------------


def test_DSC_01_discount_impact():
    r = evaluate_price(
        list_price="125000", discount="0.25", unit_cost="60000", fees=[MP_FEE], target_margin="0.30"
    )
    assert_ok(r, Status.BELOW_TARGET_MARGIN)
    assert money(r["net_price"]) == D("93750.00")
    assert money(r["fee_total"]) == D("9375.00")
    assert money(r["contribution"]) == D("24375.00")
    assert rate(r["contribution_margin"]) == D("0.260000")
    assert money(r["minimum_price"]) == D("66666.67")


def test_DSC_02_discount_breaks_minimum():
    r = evaluate_price(list_price="125000", discount="0.50", unit_cost="60000", fees=[MP_FEE])
    assert_ok(r, Status.BELOW_MIN_PRICE)
    assert money(r["net_price"]) == D("62500.00")


def test_DSC_03_publication_without_override_rejected():
    r = validate_publication(net_price="62500", minimum_price="66666.67")
    assert_status(r, Status.INVALID_INPUT)
    ok = validate_publication(
        net_price="62500", minimum_price="66666.67", override_reason="Clearance stok lama", override_by="user-123"
    )
    assert_ok(ok, Status.BELOW_MIN_PRICE)
    assert ok["override_applied"] is True


# --- §3 Pembulatan ------------------------------------------------------------


def test_RND_01_round_up():
    r = round_price(target_price=D("85714.2857142857142857142857"), increment="500", mode=RoundingMode.UP)
    assert_ok(r)
    assert r["recommended_price"] == D("86000")


def test_RND_02_margin_guard():
    target = calculate_price(method=PricingMethod.TARGET_GROSS_MARGIN, unit_cost="60000", target_margin="0.30")["net_price"]
    r = round_price(target_price=target, increment="500", mode=RoundingMode.NEAREST)
    assert_ok(r)
    assert r["rounded_before_guard"] == D("85500")
    assert rate((D("85500") - 60000) / D("85500")) == D("0.298246")
    assert r["recommended_price"] == D("86000")
    assert r["guard_applied"] is True


def test_RND_03_review_example():
    r = round_price(target_price="10237", increment="500", mode=RoundingMode.NEAREST)
    assert r["rounded_before_guard"] == D("10000")
    assert r["recommended_price"] == D("10500")


def test_RND_04_full_precision_kept():
    target = D(60000) / (1 - D("0.30"))
    r = round_price(target_price=target, increment="500", mode=RoundingMode.UP)
    assert str(r["target_price"]) == "85714.28571428571428571428571"
    assert r["recommended_price"] == D("86000")


def test_rounding_respects_minimum_price():
    r = round_price(target_price="66000", increment="1000", mode=RoundingMode.DOWN, margin_guard=False, minimum_price="66666.67")
    assert r["recommended_price"] == D("67000")


# --- Property tests -----------------------------------------------------------

pct = st.decimals(min_value=D("0"), max_value=D("0.30"), places=4)


@given(
    cost=st.decimals(min_value=D("1"), max_value=D("10000000"), places=2),
    margin=pct,
    fee_net=pct,
    fee_list=st.decimals(min_value=D("0"), max_value=D("0.10"), places=4),
    discount=st.decimals(min_value=D("0"), max_value=D("0.50"), places=4),
)
def test_property_contribution_margin_round_trip(cost, margin, fee_net, fee_list, discount):
    fees = [PercentageFee("net", fee_net, PriceBase.NET_PRICE), PercentageFee("list", fee_list, PriceBase.LIST_PRICE)]
    priced = calculate_price(
        method=PricingMethod.TARGET_CONTRIBUTION_MARGIN,
        unit_cost=cost,
        target_margin=margin,
        discount=discount,
        fees=fees,
    )
    if priced.status is Status.INFEASIBLE_MARGIN:
        assert margin + fee_net + fee_list / (1 - discount) >= 1
        return
    assert_ok(priced)
    back = evaluate_price(
        list_price=priced["list_price"],
        discount=discount,
        unit_cost=cost,
        fees=fees,
        target_margin=margin,
        margin_definition=MarginDefinition.CONTRIBUTION,
    )
    assert abs(back["contribution_margin"] - margin) < D("1e-20")
    assert Status.BELOW_TARGET_MARGIN not in back.warning_codes
