"""TEST_SUITE_SPEC §7 Manufaktur, §8 Trading."""

from datetime import date
from decimal import Decimal as D

from conftest import assert_ok, assert_status, money

from pricing_engine.allocation import AllocationMethod, AllocationTarget, allocate
from pricing_engine.core import Status, q
from pricing_engine.costing import (
    ExchangeRate,
    MaterialLine,
    MaterialPrice,
    ResourceUsage,
    fully_loaded_unit_cost,
    landed_cost,
    manufacturing_unit_cost,
    material_input,
    resolve_fx_rate,
    resolve_material_price,
    waste_rate_from_extra,
)


def test_MFG_01_material_waste():
    r = material_input(net_quantity="2", waste_rate="0.10", unit_price="15000")
    assert q(r["input_quantity"], "0.000001") == D("2.222222")
    assert money(r["cost"]) == D("33333.33")


def test_MFG_02_review_example():
    r = material_input(net_quantity="100", waste_rate=D(10) / D(110))
    assert q(r["input_quantity"], "0.000001") == D("110.000000")


def test_MFG_03_extra_conversion():
    w = waste_rate_from_extra("0.10")
    assert q(w, "0.000001") == D("0.090909")
    r = material_input(net_quantity="100", waste_rate=w)
    assert q(r["input_quantity"], "0.000001") == D("110.000000")


MFG_04 = dict(
    planned_output="1000",
    materials=[
        MaterialLine("A", net_quantity="500", unit_price="20000", waste_rate="0.04"),
        MaterialLine("B", net_quantity="1000", unit_price="3000"),
    ],
    labor=[ResourceUsage("operator", "40", "50000")],
    machines=[ResourceUsage("mesin-1", "10", "150000")],
    overhead="5000000",
    packaging="1000000",
    scrap_rate="0.05",
)


def test_MFG_04_unit_cost_with_scrap():
    r = manufacturing_unit_cost(**MFG_04)
    assert_ok(r)
    assert money(r["breakdown"]["materials"]["A"]) == D("10416666.67")
    assert money(r["batch_cost"]) == D("22916666.67")
    assert r["good_units"] == D("950")
    assert money(r["unit_cost"]) == D("24122.81")


def test_MFG_05_rework():
    r = manufacturing_unit_cost(**MFG_04, rework_rate="0.03", rework_cost_per_unit="4000")
    assert money(r["rework_cost"]) == D("114000.00")
    assert money(r["unit_cost"]) == D("24242.81")


def test_MFG_06_full_scrap_invalid():
    r = manufacturing_unit_cost(**{**MFG_04, "scrap_rate": "1"})
    assert_status(r, Status.INVALID_INPUT)


def test_MFG_07_missing_material_price():
    r = resolve_material_price(prices=[], material="Tepung", as_of_date=date(2026, 11, 1))
    assert_status(r, Status.INVALID_INPUT)
    assert "Tepung" in r.message


def test_process_yield_reduces_good_units():
    r = manufacturing_unit_cost(planned_output="100", overhead="920", process_yield="0.92")
    assert r["good_units"] == D("92")
    assert r["unit_cost"] == D("10")


def test_TRD_01_landed_cost_import():
    r = landed_cost(
        quantity="1000",
        unit_purchase_price="5",
        fx_rate="16000",
        import_duty_rate="0.05",
        freight="4000000",
        handling="1000000",
        other_acquisition="500000",
        qty_received_good="990",
    )
    assert_ok(r)
    assert r["purchase_value"] == D("80000000")
    assert r["import_duty"] == D("4000000")
    assert money(r["landed_total"]) == D("89500000.00")
    assert money(r["landed_cost_per_unit"]) == D("90404.04")


def test_TRD_02_freight_allocation_by_weight():
    r = allocate(
        pool_amount="1000000",
        method=AllocationMethod.DRIVER,
        targets=[AllocationTarget("A", driver="30"), AllocationTarget("B", driver="70")],
        driver_name="berat (kg)",
    )
    assert r["allocations"] == {"A": D("300000"), "B": D("700000")}


def test_TRD_03_missing_fx_rate():
    rates = [ExchangeRate("USD", "IDR", "16000", date(2026, 11, 20))]
    assert_status(
        resolve_fx_rate(rates=rates, from_currency="USD", to_currency="IDR", as_of_date=date(2026, 11, 21)),
        Status.INVALID_INPUT,
    )
    ok = resolve_fx_rate(rates=rates, from_currency="USD", to_currency="IDR", as_of_date=date(2026, 11, 20))
    assert ok["rate"] == D("16000")


def test_fully_loaded_is_not_cogs():
    r = fully_loaded_unit_cost(landed_cost_per_unit="90404.04", allocated_costs_per_unit=["2500", "1000"])
    assert r["fully_loaded_unit_cost"] == D("93904.04")
    assert r["is_accounting_cogs"] is False


# --- HIS: versi historis -------------------------------------------------------

PRICES = [
    MaterialPrice("A", "20000", date(2026, 1, 1), date(2026, 7, 1), source_reference="kontrak H1"),
    MaterialPrice("A", "23000", date(2026, 7, 1), None, source_reference="kontrak H2"),
]


def test_HIS_01_historical_reproduction():
    old_price = resolve_material_price(prices=PRICES, material="A", as_of_date=date(2026, 3, 15))["unit_price"]
    new_price = resolve_material_price(prices=PRICES, material="A", as_of_date=date(2026, 11, 22))["unit_price"]
    assert (old_price, new_price) == (D("20000"), D("23000"))

    first = manufacturing_unit_cost(**MFG_04)
    # costing lama dijalankan ulang dari input yang sama setelah harga baru tercatat
    replay = manufacturing_unit_cost(**MFG_04)
    assert replay.values == first.values
    assert replay.input_hash == first.input_hash
