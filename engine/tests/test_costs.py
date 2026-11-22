"""TEST_SUITE_SPEC §9 Perilaku biaya, §10 Eskalasi, §11 Alokasi, §12 Kapasitas."""

from datetime import date
from decimal import Decimal as D

from conftest import assert_ok, assert_status, money, rate
from hypothesis import given
from hypothesis import strategies as st

from pricing_engine.allocation import (
    AllocationMethod,
    AllocationTarget,
    AssignmentMode,
    CostAssignment,
    allocate,
    check_double_counting,
)
from pricing_engine.capacity import check_capacity
from pricing_engine.core import Status
from pricing_engine.cost_behavior import (
    Bracket,
    DriverUsage,
    StepTier,
    TierMode,
    percentage_cost,
    semi_variable_cost,
    step_fixed_ceiling,
    step_fixed_table,
    tiered_cost,
    variable_cost,
)
from pricing_engine.escalation import EscalationType, Frequency, escalate

SALARY = 6_000_000
OPERATOR_TIERS = [
    StepTier(0, 10000, 5 * SALARY, 5),
    StepTier(10001, 15000, 8 * SALARY, 8),
    StepTier(15001, 20000, 11 * SALARY, 11),
]

# --- §9 Perilaku biaya ---------------------------------------------------------


def test_CST_01_semi_variable():
    r = semi_variable_cost(base="2000000", activity="3000", rate="1500")
    assert money(r["cost"]) == D("6500000.00")


def test_CST_02_step_fixed_table():
    r = step_fixed_table(activity="12000", tiers=OPERATOR_TIERS)
    assert_ok(r)
    assert r["resource_count"] == 8
    assert money(r["cost"]) == D("48000000.00")


def test_CST_03_step_fixed_exceeded():
    r = step_fixed_table(activity="21000", tiers=OPERATOR_TIERS)
    assert_ok(r, Status.CAPACITY_EXCEEDED)
    assert r["resource_count"] == 11
    assert money(r["cost"]) == D("66000000.00")
    assert r["excess_activity"] == D("1000")


def test_CST_04_step_fixed_ceiling():
    r = step_fixed_ceiling(activity="12500", capacity_per_resource="2000", cost_per_resource=SALARY)
    assert r["resource_count"] == 7
    assert money(r["cost"]) == D("42000000.00")


BRACKETS = [Bracket(1000, 100), Bracket(5000, 80), Bracket(None, 60)]


def test_CST_05_tiered_graduated():
    assert money(tiered_cost(activity="6000", brackets=BRACKETS, mode=TierMode.GRADUATED)["cost"]) == D("480000.00")


def test_CST_06_tiered_all_units():
    assert money(tiered_cost(activity="6000", brackets=BRACKETS, mode=TierMode.ALL_UNITS)["cost"]) == D("360000.00")


def test_CST_07_minimum_amount():
    r = variable_cost(usages=[DriverUsage("unit", "40", "100")], minimum_amount="5000")
    assert money(r["cost"]) == D("5000.00")


def test_CST_08_double_counting_rejected():
    r = check_double_counting(
        assignments=[
            CostAssignment("listrik-pabrik", "2026-11", AssignmentMode.DIRECT, "produk-A"),
            CostAssignment("listrik-pabrik", "2026-11", AssignmentMode.POOL),
            CostAssignment("sewa-gudang", "2026-11", AssignmentMode.POOL),
        ]
    )
    assert_status(r, Status.INVALID_INPUT)
    assert "listrik-pabrik" in r.message
    assert "sewa-gudang" not in r.message


def test_percentage_cost_requires_base():
    assert_status(percentage_cost(rate="0.02", base_value="1000", base=""), Status.INVALID_INPUT)
    assert percentage_cost(rate="0.02", base_value="1000", base="NET_REVENUE_PERIOD")["cost"] == D("20")


# --- §10 Eskalasi --------------------------------------------------------------


def test_ESC_01_compound():
    r = escalate(base="10000", escalation_type=EscalationType.COMPOUND_PCT, rate="0.05",
                 effective_from=date(2023, 1, 1), as_of_date=date(2026, 1, 1))
    assert r["periods"] == 3
    assert money(r["value"]) == D("11576.25")


def test_ESC_02_simple():
    r = escalate(base="10000", escalation_type=EscalationType.SIMPLE_PCT, rate="0.05", periods=3)
    assert money(r["value"]) == D("11500.00")


def test_ESC_03_cap():
    r = escalate(base="10000", escalation_type=EscalationType.COMPOUND_PCT, rate="0.05", periods=3, cap="11000")
    assert money(r["value"]) == D("11000.00")
    assert money(r["unclamped_value"]) == D("11576.25")


def test_ESC_04_nominal():
    r = escalate(base="10000", escalation_type=EscalationType.NOMINAL, amount="250",
                 frequency=Frequency.QUARTERLY, effective_from=date(2025, 11, 1), as_of_date=date(2026, 11, 1))
    assert r["periods"] == 4
    assert money(r["value"]) == D("11000.00")


def test_ESC_05_partial_period():
    r = escalate(base="10000", escalation_type=EscalationType.COMPOUND_PCT, rate="0.05",
                 effective_from=date(2026, 1, 1), as_of_date=date(2026, 12, 31))
    assert r["periods"] == 0
    assert r["value"] == D("10000")


def test_ESC_06_scenario_override():
    r = escalate(base="10000", escalation_type=EscalationType.COMPOUND_PCT, rate="0.05", override_rate="0.08", periods=3)
    assert money(r["value"]) == D("12597.12")


# --- §11 Alokasi ---------------------------------------------------------------


def test_ALC_01_largest_remainder():
    r = allocate(
        pool_amount="10000000",
        method=AllocationMethod.DRIVER,
        targets=[AllocationTarget("P1", driver=1), AllocationTarget("P2", driver=1), AllocationTarget("P3", driver=1)],
    )
    assert r["allocations"] == {"P1": D("3333334"), "P2": D("3333333"), "P3": D("3333333")}
    assert r["allocated_total"] == D("10000000")


def test_ALC_02_percentage_not_100():
    r = allocate(
        pool_amount="1000000",
        method=AllocationMethod.PERCENTAGE,
        targets=[AllocationTarget("A", percentage="0.50"), AllocationTarget("B", percentage="0.49")],
    )
    assert_status(r, Status.INVALID_INPUT)


def test_ALC_03_unallocated_allowed():
    r = allocate(
        pool_amount="1000000",
        method=AllocationMethod.PERCENTAGE,
        targets=[AllocationTarget("A", percentage="0.50"), AllocationTarget("B", percentage="0.49")],
        allow_unallocated=True,
    )
    assert r["allocations"] == {"A": D("500000"), "B": D("490000")}
    assert r["unallocated_amount"] == D("10000")


def test_ALC_04_zero_driver():
    r = allocate(pool_amount="1000", method=AllocationMethod.DRIVER, targets=[AllocationTarget("A", driver=0)])
    assert_status(r, Status.INVALID_INPUT)


def test_ALC_05_machine_hours():
    r = allocate(
        pool_amount="6000000",
        method=AllocationMethod.DRIVER,
        targets=[AllocationTarget("A", driver="30"), AllocationTarget("B", driver="90")],
        driver_name="jam mesin",
    )
    assert r["allocations"] == {"A": D("1500000"), "B": D("4500000")}


@given(
    pool=st.integers(min_value=0, max_value=10**12),
    drivers=st.lists(st.integers(min_value=0, max_value=10**6), min_size=1, max_size=12).filter(lambda xs: sum(xs) > 0),
    currency=st.sampled_from(["IDR", "USD"]),
)
def test_PRE_03_allocation_sums_exactly(pool, drivers, currency):
    targets = [AllocationTarget(f"T{i:02d}", driver=d) for i, d in enumerate(drivers)]
    r = allocate(pool_amount=pool, method=AllocationMethod.DRIVER, targets=targets, currency=currency)
    assert_ok(r)
    assert sum(r["allocations"].values()) == D(pool)


# --- §12 Kapasitas --------------------------------------------------------------


def test_CAP_01_exceeded():
    r = check_capacity(required="12000", regular_capacity="10000")
    assert_ok(r, Status.CAPACITY_EXCEEDED)
    assert rate(r["utilization"]) == D("1.200000")
    assert r["unmet_demand"] == D("2000")


def test_CAP_02_overtime_covers():
    r = check_capacity(
        required="12000", regular_capacity="10000", max_overtime="3000", regular_unit_cost="500", overtime_multiplier="1.5"
    )
    assert_ok(r, Status.CAPACITY_EXCEEDED)
    assert r["overtime_used"] == D("2000")
    assert money(r["overtime_cost"]) == D("1500000.00")
    assert r["unmet_demand"] == 0
