"""TEST_SUITE_SPEC §4 PPN dan PPh (§8 spec)."""

from datetime import date
from decimal import Decimal as D

from conftest import assert_ok, assert_status, money, rate

from pricing_engine.core import Status
from pricing_engine.pricing import PercentageFee, PricingMethod, calculate_price
from pricing_engine.tax import (
    AFFECTS_PROFIT_AND_LOSS,
    DppFactor,
    DppMethod,
    IncomeTaxRegime,
    TaxCategory,
    TaxRule,
    income_tax,
    select_tax_rule,
    vat_exclusive,
    vat_inclusive,
)

ELEVEN_TWELFTHS = DppFactor(11, 12)


def test_VAT_01_exclusive_other_value():
    r = vat_exclusive(net_price="100000", nominal_rate="0.12", dpp_method=DppMethod.OTHER_VALUE, dpp_factor=ELEVEN_TWELFTHS)
    assert_ok(r)
    assert money(r["dpp"]) == D("91666.67")
    assert r["vat"] == D("11000")  # eksak, tanpa pembulatan
    assert money(r["gross_price"]) == D("111000.00")
    assert rate(r["effective_rate"]) == D("0.110000")


def test_VAT_02_inclusive_other_value():
    r = vat_inclusive(gross_price="111000", nominal_rate="0.12", dpp_method=DppMethod.OTHER_VALUE, dpp_factor=ELEVEN_TWELFTHS)
    assert_ok(r)
    assert r["net_price"] == D("100000")
    assert r["vat"] == D("11000")


def test_VAT_03_full_dpp():
    r = vat_exclusive(net_price="100000", nominal_rate="0.12", dpp_method=DppMethod.FULL)
    assert money(r["vat"]) == D("12000.00")
    assert money(r["gross_price"]) == D("112000.00")


def test_VAT_04_vat_does_not_change_margin():
    priced = calculate_price(
        method=PricingMethod.TARGET_CONTRIBUTION_MARGIN,
        unit_cost="60000",
        target_margin="0.30",
        fees=[PercentageFee("marketplace", "0.10")],
    )
    vat = vat_exclusive(
        net_price=priced["net_price"], nominal_rate="0.12", dpp_method=DppMethod.OTHER_VALUE, dpp_factor=ELEVEN_TWELFTHS
    )
    assert money(vat["gross_price"]) == D("111000.00")
    assert rate(priced["contribution_margin"]) == D("0.300000")


RULES = [
    TaxRule("VAT-OLD", "VAT", "0.11", date(2022, 4, 1), date(2025, 1, 1)),
    TaxRule("VAT-12-DPP-11/12", "VAT", "0.12", date(2025, 1, 1), None, DppMethod.OTHER_VALUE, ELEVEN_TWELFTHS),
]


def test_VAT_05_no_rule_in_effect():
    r = select_tax_rule(rules=RULES, tax_type="VAT", as_of_date=date(2020, 1, 1))
    assert_status(r, Status.INVALID_INPUT)


def test_select_rule_by_date():
    assert select_tax_rule(rules=RULES, tax_type="VAT", as_of_date=date(2024, 12, 31))["rule"].code == "VAT-OLD"
    assert select_tax_rule(rules=RULES, tax_type="VAT", as_of_date=date(2026, 11, 22))["rule"].code == "VAT-12-DPP-11/12"


def test_income_tax_profit_based():
    r = income_tax(regime=IncomeTaxRegime.PROFIT_BASED, rate="0.22", profit_before_tax="50000000")
    assert money(r["income_tax"]) == D("11000000.00")
    assert money(r["net_profit"]) == D("39000000.00")


def test_income_tax_profit_based_loss_is_zero_tax():
    r = income_tax(regime=IncomeTaxRegime.PROFIT_BASED, rate="0.22", profit_before_tax="-1000000")
    assert r["income_tax"] == 0


def test_income_tax_turnover_with_exemption_and_threshold():
    # Angka ilustrasi; nilai regulasi berasal dari tax_rules yang sudah diverifikasi.
    r = income_tax(
        regime=IncomeTaxRegime.TURNOVER_FINAL,
        rate="0.005",
        gross_turnover="600000000",
        exempt_turnover="500000000",
        max_turnover_threshold="4800000000",
    )
    assert_ok(r)
    assert money(r["income_tax"]) == D("500000.00")
    over = income_tax(
        regime=IncomeTaxRegime.TURNOVER_FINAL, rate="0.005", gross_turnover="5000000000", max_turnover_threshold="4800000000"
    )
    assert_ok(over, Status.TAX_REGIME_THRESHOLD_EXCEEDED)


def test_withholding_is_not_expense():
    assert AFFECTS_PROFIT_AND_LOSS[TaxCategory.WITHHELD_BY_OTHERS] is False
    assert AFFECTS_PROFIT_AND_LOSS[TaxCategory.TAX_CREDIT] is False
    assert AFFECTS_PROFIT_AND_LOSS[TaxCategory.TAX_EXPENSE] is True
