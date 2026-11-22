"""TEST_SUITE_SPEC §14 Rencana laba, BEP bertingkat, target, skenario, alokasi.

Angka harapan dihitung manual (lihat komentar), bukan dari engine.
"""

from datetime import date
from decimal import Decimal as D

from conftest import assert_ok, assert_status, money, rate

from pricing_engine.core import Status
from pricing_engine.planning import (
    Adjustments,
    AllocationBasis,
    AllocationRuleSpec,
    Behavior,
    CostItemSpec,
    DriverType,
    SalesLine,
    Scope,
    TargetKind,
    TaxRegime,
    Tier,
    preview_costs,
    profit_plan,
)

AS_OF = date(2026, 6, 1)
LINES = [SalesLine("A", "100000", "60000", "1000"), SalesLine("B", "50000", "20000", "1000")]

SEWA = CostItemSpec("SEWA", "Sewa gedung", Behavior.FIXED, base_amount="20000000", category="FIXED_OPERATING")
KOMISI = CostItemSpec("KOMISI", "Komisi sales", Behavior.PERCENTAGE, percentage="0.05", percentage_base="REVENUE", category="SELLING")
ONGKIR = CostItemSpec("ONGKIR", "Ongkir", Behavior.VARIABLE, driver_code="UNIT", driver_type=DriverType.SALES_UNITS, rate="2000", category="DISTRIBUTION")
OPERATOR = CostItemSpec(
    "OPERATOR", "Operator produksi", Behavior.STEP_FIXED, driver_code="PROD", driver_type=DriverType.PRODUCTION_UNITS,
    step_mode="TABLE", tiers=(Tier(0, 2000, "10000000"), Tier(2001, 3000, "15000000")), category="DIRECT_LABOR",
)
OH = CostItemSpec("OH", "Overhead pabrik", Behavior.FIXED, scope=Scope.ALLOCATION_POOL, base_amount="6000000", category="PRODUCTION_OVERHEAD")
PENOLONG = CostItemSpec("PENOLONG", "Bahan penolong", Behavior.VARIABLE, scope=Scope.PRODUCT, driver_code="UNIT",
                        driver_type=DriverType.PRODUCTION_UNITS, rate="500")
ITEMS = [SEWA, KOMISI, ONGKIR, OPERATOR, OH, PENOLONG]
RULES = [AllocationRuleSpec("OH", AllocationBasis.DRIVER, (("A", "2"), ("B", "1")))]


def plan(**kw):
    base = dict(lines=LINES, items=ITEMS, as_of_date=AS_OF, allocation_rules=RULES)
    return profit_plan(**{**base, **kw})


def test_PLN_01_profit_and_loss():
    r = plan(tax_regime=TaxRegime.PROFIT_BASED, tax_rate="0.22")
    assert_ok(r)
    p = r["pnl"]
    # R = 100.000×1.000 + 50.000×1.000 ; HPP = 60.000×1.000 + 20.000×1.000
    assert money(p["revenue"]) == D("150000000.00")
    assert money(p["cogs"]) == D("80000000.00")
    assert money(p["gross_profit"]) == D("70000000.00")
    # variabel = 5% × 150 jt + 2.000 × 2.000 unit
    assert money(p["variable_costs"]) == D("11500000.00")
    assert money(p["contribution"]) == D("58500000.00")
    # tetap = sewa 20 jt + operator tier 1 10 jt + overhead 6 jt (bahan penolong scope PRODUCT tidak dihitung ulang)
    assert money(p["fixed_costs"]) == D("36000000.00")
    assert money(p["operating_profit"]) == D("22500000.00")
    assert money(p["income_tax"]) == D("4950000.00")
    assert money(p["net_profit"]) == D("17550000.00")
    assert r["excluded_product_scope"] == ["PENOLONG"]


def test_PLN_02_break_even_with_step_costs():
    r = plan()
    b = r["break_even"]
    # UCM = 75.000 − 40.000 − 2.000 − 5%×75.000 = 29.250 ; BEP = ceil(36 jt / 29.250) = 1.231
    assert b["unit_contribution"] == D("29250")
    assert b["units"] == D("1231")
    assert money(b["revenue"]) == D("92325000.00")
    assert rate(b["margin_of_safety"]) == D("0.384500")
    assert b["profitable_ranges"][0][0] == D("1231")


def test_PLN_03_target_crosses_step_threshold():
    r = plan(target_kind=TargetKind.OPERATING_PROFIT, target_amount="50000000")
    t = r["target"]
    # tier1: ceil(86 jt/29.250)=2.941 > 2.000 ; tier2 (41 jt): ceil(91 jt/29.250)=3.112 > 3.000 ;
    # di atas 3.000 (kapasitas tier tertinggi, 41 jt) → 3.112
    assert t["units"] == D("3112")
    assert money(t["revenue"]) == D("233400000.00")
    assert t["achieved"] is False


def test_PLN_04_net_profit_target_profit_tax():
    r = plan(tax_regime=TaxRegime.PROFIT_BASED, tax_rate="0.22", target_kind=TargetKind.NET_PROFIT, target_amount="39000000")
    # NP 39 jt ⇔ OP 50 jt → sama dengan PLN-03
    assert r["target"]["units"] == D("3112")


def test_PLN_05_turnover_tax():
    r = plan(tax_regime=TaxRegime.TURNOVER_FINAL, tax_rate="0.005")
    assert money(r["pnl"]["income_tax"]) == D("750000.00")
    assert money(r["pnl"]["net_profit"]) == D("21750000.00")


def test_PLN_06_product_profitability_and_allocation():
    r = plan()
    rows = {l["product"]: l for l in r["lines"]}
    # A: 100 − 60 − (5 + 2) = 33 jt ; alokasi 2/3 × 6 jt = 4 jt
    assert money(rows["A"]["contribution"]) == D("33000000.00")
    assert money(rows["A"]["allocated_costs"]) == D("4000000.00")
    assert money(rows["A"]["profit_after_allocation"]) == D("29000000.00")
    assert money(rows["B"]["contribution"]) == D("25500000.00")
    assert money(rows["B"]["profit_after_allocation"]) == D("23500000.00")
    # Σ laba produk − biaya level perusahaan = laba operasional
    assert money(r["company_level_costs"]) == D("30000000.00")
    total = sum(l["profit_after_allocation"] for l in r["lines"]) - r["company_level_costs"]
    assert money(total) == money(r["pnl"]["operating_profit"])


def test_PLN_07_allocation_by_revenue():
    r = plan(allocation_rules=[AllocationRuleSpec("OH", AllocationBasis.REVENUE)])
    rows = {l["product"]: l for l in r["lines"]}
    assert rows["A"]["allocated_costs"] == D("4000000")
    assert rows["B"]["allocated_costs"] == D("2000000")


def test_PLN_08_allocation_percentage_must_be_full():
    r = plan(allocation_rules=[AllocationRuleSpec("OH", AllocationBasis.PERCENTAGE, (("A", "0.5"), ("B", "0.4")))])
    assert_status(r, Status.INVALID_INPUT)


def test_SCN_01_volume_increase_triggers_step():
    r = plan(adjustments=Adjustments(volume_change="0.10"))
    p = r["pnl"]
    # U = 2.200 → operator tier 2 (15 jt). R = 165 jt, HPP 88 jt, var = 8,25 + 4,4 = 12,65 jt
    assert money(p["revenue"]) == D("165000000.00")
    assert money(p["fixed_costs"]) == D("41000000.00")
    assert money(p["operating_profit"]) == D("23350000.00")
    op = next(c for c in r["costs"] if c["code"] == "OPERATOR")
    assert op["tier"] == [D("2001"), D("3000")]


def test_SCN_02_capacity_exceeded_warning():
    r = plan(adjustments=Adjustments(volume_change="0.60"))
    assert_ok(r, Status.CAPACITY_EXCEEDED)


def test_SCN_03_cost_inflation_and_item_override():
    r = plan(adjustments=Adjustments(unit_cost_change="0.08", fixed_cost_change="0.05", item_changes=(("KOMISI", "0.20"),)))
    p = r["pnl"]
    # HPP 80 jt × 1,08 = 86,4 jt ; komisi 6% = 9 jt + ongkir 4 jt ; tetap 36 jt × 1,05 = 37,8 jt
    assert money(p["cogs"]) == D("86400000.00")
    assert money(p["variable_costs"]) == D("13000000.00")
    assert money(p["fixed_costs"]) == D("37800000.00")
    assert money(p["operating_profit"]) == D("12800000.00")


def test_SCN_04_price_change():
    r = plan(adjustments=Adjustments(price_change="0.04"))
    # R = 156 jt ; komisi 7,8 jt
    assert money(r["pnl"]["revenue"]) == D("156000000.00")
    assert money(r["pnl"]["variable_costs"]) == D("11800000.00")


def test_PER_01_annual_scenario_scales_monthly_costs():
    r = plan(period_months=12)
    # volume 2.000/tahun → ±167/bulan → operator tier 1 ; tetap = (20 + 10 + 6) jt × 12
    assert money(r["pnl"]["fixed_costs"]) == D("432000000.00")


def test_ESC_07_escalation_in_plan():
    sewa = CostItemSpec("SEWA", "Sewa", Behavior.FIXED, base_amount="20000000", escalation_type="COMPOUND_PCT",
                        escalation_rate="0.10", escalation_frequency="ANNUAL", effective_from=date(2025, 1, 1))
    r = profit_plan(lines=LINES, items=[sewa], as_of_date=AS_OF)
    assert money(r["pnl"]["fixed_costs"]) == D("22000000.00")


def test_STP_01_ceiling_step_costs():
    ops = CostItemSpec("OPS", "Operator", Behavior.STEP_FIXED, driver_code="PROD", driver_type=DriverType.PRODUCTION_UNITS,
                       step_mode="CEILING", capacity_per_resource="400", cost_per_resource="5000000")
    r = profit_plan(lines=LINES, items=[ops], as_of_date=AS_OF)
    row = r["costs"][0]
    assert row["resource_count"] == 5
    assert money(r["pnl"]["fixed_costs"]) == D("25000000.00")
    # UCM = 75.000 − 40.000 = 35.000 ; segmen ≤400 unit: 1 operator 5 jt → ceil(5 jt/35.000)=143
    assert r["break_even"]["units"] == D("143")


def test_BEP_10_no_break_even():
    lines = [SalesLine("X", "1000", "1200", "100")]
    r = profit_plan(lines=lines, items=[SEWA], as_of_date=AS_OF)
    assert r["break_even"]["status"] == "NO_BREAK_EVEN"
    assert Status.NO_BREAK_EVEN in r.warning_codes


def test_DRV_01_missing_driver_activity_warns():
    labor = CostItemSpec("LEMBUR", "Lembur", Behavior.VARIABLE, driver_code="JAM", driver_type=DriverType.LABOR_HOURS, rate="50000")
    r = profit_plan(lines=LINES, items=[labor], as_of_date=AS_OF)
    assert Status.MISSING_DRIVER_ACTIVITY in r.warning_codes
    r2 = profit_plan(lines=LINES, items=[labor], as_of_date=AS_OF, other_activity={"JAM": "100"})
    assert money(r2["pnl"]["variable_costs"]) == D("5000000.00")
    # driver non-penjualan tidak bisa diatribusikan ke produk
    assert money(r2["unattributed_variable_costs"]) == D("5000000.00")


def test_VAL_01_invalid_items():
    bad = CostItemSpec("X", "x", Behavior.VARIABLE, rate="1")  # tanpa driver
    assert_status(profit_plan(lines=LINES, items=[bad], as_of_date=AS_OF), Status.INVALID_INPUT)
    assert_status(profit_plan(lines=[], items=[], as_of_date=AS_OF), Status.INVALID_INPUT)
    dup = [SalesLine("A", "1", "1", "1"), SalesLine("A", "1", "1", "1")]
    assert_status(profit_plan(lines=dup, as_of_date=AS_OF), Status.INVALID_INPUT)


def test_PRV_01_preview_costs():
    r = preview_costs(items=[SEWA, KOMISI, ONGKIR, OPERATOR], units="2500", revenue="150000000", as_of_date=AS_OF)
    assert_ok(r)
    # 20 jt + 7,5 jt + 5 jt + tier 2 (15 jt)
    assert money(r["total"]) == D("47500000.00")
    assert money(r["fixed_total"]) == D("35000000.00")


def test_REP_04_plan_reproducible():
    assert plan() == plan()


def test_PLN_09_target_beyond_capacity_warns():
    # target 50 jt butuh 3.112 unit > tier tertinggi operator (3.000)
    r = plan(target_kind=TargetKind.OPERATING_PROFIT, target_amount="50000000")
    assert r["target"]["capacity_exceeded_items"] == ["OPERATOR"]
    assert Status.CAPACITY_EXCEEDED in r.warning_codes
