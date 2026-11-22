"""Product costing: manufaktur (§3), trading/landed cost (§4), jasa (§4A)."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Sequence

from .core import (
    ONE,
    ZERO,
    Calc,
    calculation,
    dec,
    fraction,
    invalid,
    non_negative,
    positive,
)


class DataNature(enum.StrEnum):
    ACTUAL = "ACTUAL"
    STANDARD = "STANDARD"
    ESTIMATE = "ESTIMATE"
    SCENARIO = "SCENARIO"


# ---------------------------------------------------------------------------
# Lookups effective-dated
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaterialPrice:
    material: str
    unit_price: Any
    effective_from: date
    effective_to: date | None = None  # eksklusif
    data_nature: DataNature = DataNature.STANDARD
    currency: str = "IDR"
    source_reference: str = ""


def _in_effect(start: date, end: date | None, as_of: date) -> bool:
    return start <= as_of and (end is None or as_of < end)


@calculation
def resolve_material_price(
    c: Calc,
    *,
    prices: Sequence[MaterialPrice],
    material: str,
    as_of_date: date,
    data_nature: DataNature = DataNature.STANDARD,
) -> dict[str, Any]:
    """Harga material yang berlaku pada tanggal tertentu (§3.3)."""
    nature = DataNature(data_nature)
    matches = [
        p
        for p in prices
        if p.material == material and DataNature(p.data_nature) is nature and _in_effect(p.effective_from, p.effective_to, as_of_date)
    ]
    if not matches:
        raise invalid(f"harga material '{material}' ({nature.value}) tidak tersedia pada {as_of_date.isoformat()}")
    if len(matches) > 1:
        raise invalid(f"lebih dari satu harga material '{material}' berlaku pada {as_of_date.isoformat()}")
    p = matches[0]
    price = non_negative(p.unit_price, f"{material}.unit_price")
    c.step(f"harga {material} per {as_of_date.isoformat()} ({p.source_reference or nature.value})", price)
    return {"unit_price": price, "currency": p.currency, "effective_from": p.effective_from}


@dataclass(frozen=True)
class ExchangeRate:
    from_currency: str
    to_currency: str
    rate: Any
    rate_date: date
    rate_type: str = "SPOT"


@calculation
def resolve_fx_rate(
    c: Calc,
    *,
    rates: Sequence[ExchangeRate],
    from_currency: str,
    to_currency: str,
    as_of_date: date,
    rate_type: str = "SPOT",
) -> dict[str, Any]:
    """Kurs pada tanggal tertentu (persis tanggal tersebut)."""
    if from_currency == to_currency:
        return {"rate": ONE}
    for r in rates:
        if (r.from_currency, r.to_currency, r.rate_type, r.rate_date) == (from_currency, to_currency, rate_type, as_of_date):
            return {"rate": c.step(f"kurs {from_currency}/{to_currency} {rate_type} {as_of_date.isoformat()}", positive(r.rate, "rate"))}
    raise invalid(f"kurs {from_currency}→{to_currency} ({rate_type}) tidak tersedia pada {as_of_date.isoformat()}")


# ---------------------------------------------------------------------------
# Manufaktur
# ---------------------------------------------------------------------------


def waste_rate_from_extra(extra: Any) -> Decimal:
    """Konversi "tambahan X% dari kebutuhan bersih" → waste rate dari input: w = X / (1 + X)."""
    x = non_negative(extra, "extra")
    return x / (ONE + x)


@calculation
def material_input(c: Calc, *, net_quantity: Any, waste_rate: Any = 0, unit_price: Any = None) -> dict[str, Any]:
    """input = net / (1 − w); w adalah persentase dari material input."""
    net = non_negative(net_quantity, "net_quantity")
    w = fraction(waste_rate, "waste_rate")
    qty = c.step("input = net / (1 − w)", net / (ONE - w))
    values: dict[str, Any] = {"input_quantity": qty, "waste_quantity": qty - net}
    if unit_price is not None:
        values["cost"] = c.step("biaya = input × harga", qty * non_negative(unit_price, "unit_price"))
    return values


@dataclass(frozen=True)
class MaterialLine:
    """Kebutuhan bersih untuk seluruh batch (planned_output)."""

    material: str
    net_quantity: Any
    unit_price: Any
    waste_rate: Any = 0


@dataclass(frozen=True)
class ResourceUsage:
    name: str
    hours: Any
    hourly_rate: Any


@calculation
def manufacturing_unit_cost(
    c: Calc,
    *,
    planned_output: Any,
    materials: Sequence[MaterialLine] = (),
    labor: Sequence[ResourceUsage] = (),
    machines: Sequence[ResourceUsage] = (),
    overhead: Any = 0,
    packaging: Any = 0,
    other_direct: Any = 0,
    process_yield: Any = 1,
    scrap_rate: Any = 0,
    rework_rate: Any = 0,
    rework_cost_per_unit: Any = 0,
) -> dict[str, Any]:
    """Biaya per unit baik untuk satu batch (§3.2)."""
    q_plan = positive(planned_output, "planned_output")
    y = fraction(process_yield, "process_yield", allow_one=True)
    if y == 0:
        raise invalid("process_yield harus > 0")
    s = fraction(scrap_rate, "scrap_rate")
    r = fraction(rework_rate, "rework_rate")
    rework_unit = non_negative(rework_cost_per_unit, "rework_cost_per_unit")

    material_costs: dict[str, Decimal] = {}
    for m in materials:
        if m.unit_price is None:
            raise invalid(f"harga material '{m.material}' tidak tersedia")
        w = fraction(m.waste_rate, f"{m.material}.waste_rate")
        qty_in = non_negative(m.net_quantity, f"{m.material}.net_quantity") / (ONE - w)
        cost = qty_in * non_negative(m.unit_price, f"{m.material}.unit_price")
        c.step(f"material {m.material}: input {qty_in} × harga", cost)
        material_costs[m.material] = material_costs.get(m.material, ZERO) + cost
    material_total = sum(material_costs.values(), ZERO)

    def resources(rows: Sequence[ResourceUsage], label: str) -> Decimal:
        total = ZERO
        for u in rows:
            part = non_negative(u.hours, f"{u.name}.hours") * non_negative(u.hourly_rate, f"{u.name}.hourly_rate")
            total += c.step(f"{label} {u.name}: jam × tarif", part)
        return total

    labor_total = resources(labor, "tenaga kerja")
    machine_total = resources(machines, "mesin")
    oh = non_negative(overhead, "overhead")
    pack = non_negative(packaging, "packaging")
    other = non_negative(other_direct, "other_direct")
    batch_cost = c.step("biaya batch", material_total + labor_total + machine_total + oh + pack + other)

    good_units = c.step("unit baik = Q_plan × y × (1 − s)", q_plan * y * (ONE - s))
    rework_cost = c.step("biaya rework = unit baik × r × biaya rework", good_units * r * rework_unit)
    unit_cost = c.step("biaya per unit = (batch + rework) / unit baik", (batch_cost + rework_cost) / good_units)
    return {
        "unit_cost": unit_cost,
        "batch_cost": batch_cost,
        "rework_cost": rework_cost,
        "good_units": good_units,
        "breakdown": {
            "material": material_total,
            "materials": material_costs,
            "labor": labor_total,
            "machine": machine_total,
            "overhead": oh,
            "packaging": pack,
            "other_direct": other,
            "rework": rework_cost,
        },
    }


# ---------------------------------------------------------------------------
# Trading / distribusi
# ---------------------------------------------------------------------------


@calculation
def landed_cost(
    c: Calc,
    *,
    quantity: Any,
    unit_purchase_price: Any,
    fx_rate: Any = 1,
    freight: Any = 0,
    insurance: Any = 0,
    import_duty_rate: Any = 0,
    import_duty_base: Any = None,
    handling: Any = 0,
    other_acquisition: Any = 0,
    qty_received_good: Any = None,
) -> dict[str, Any]:
    """Landed cost per unit baik (§4).

    Bea masuk = tarif × basis. Basis default = nilai pembelian dalam mata uang lokal;
    kirim `import_duty_base` (mis. nilai CIF) bila aturan kepabeanan memakai basis lain.
    """
    qty = positive(quantity, "quantity")
    price = non_negative(unit_purchase_price, "unit_purchase_price")
    fx = positive(fx_rate, "fx_rate")
    purchase_value = c.step("nilai beli = qty × harga × kurs", qty * price * fx)
    duty_rate = fraction(import_duty_rate, "import_duty_rate")
    duty_base = purchase_value if import_duty_base is None else non_negative(import_duty_base, "import_duty_base")
    duty = c.step("bea masuk = tarif × basis", duty_rate * duty_base)
    fr = non_negative(freight, "freight")
    ins = non_negative(insurance, "insurance")
    hd = non_negative(handling, "handling")
    oth = non_negative(other_acquisition, "other_acquisition")
    total = c.step("total landed", purchase_value + fr + ins + duty + hd + oth)
    good = qty if qty_received_good is None else positive(qty_received_good, "qty_received_good")
    if good > qty:
        raise invalid("qty_received_good tidak boleh melebihi quantity")
    per_unit = c.step("landed cost per unit baik", total / good)
    return {
        "purchase_value": purchase_value,
        "import_duty": duty,
        "landed_total": total,
        "qty_received_good": good,
        "landed_cost_per_unit": per_unit,
    }


@calculation
def fully_loaded_unit_cost(c: Calc, *, landed_cost_per_unit: Any, allocated_costs_per_unit: Sequence[Any] = ()) -> dict[str, Any]:
    """Biaya penuh manajerial — BUKAN HPP akuntansi (§4)."""
    base = non_negative(landed_cost_per_unit, "landed_cost_per_unit")
    extra = sum((non_negative(v, "allocated_cost_per_unit") for v in allocated_costs_per_unit), ZERO)
    return {
        "fully_loaded_unit_cost": c.step("landed + alokasi per unit", base + extra),
        "label": "Biaya penuh (manajerial)",
        "is_accounting_cogs": False,
    }


# ---------------------------------------------------------------------------
# Jasa
# ---------------------------------------------------------------------------


@calculation
def service_cost(
    c: Calc,
    *,
    labor: Sequence[ResourceUsage],
    direct_expenses: Any = 0,
    allocated_overhead: Any = 0,
) -> dict[str, Any]:
    """service_cost = Σ jam × tarif + biaya langsung + overhead dialokasikan (§4A)."""
    total_labor = ZERO
    for u in labor:
        total_labor += non_negative(u.hours, f"{u.name}.hours") * non_negative(u.hourly_rate, f"{u.name}.hourly_rate")
    c.step("tenaga kerja", total_labor)
    total = total_labor + non_negative(direct_expenses, "direct_expenses") + non_negative(allocated_overhead, "allocated_overhead")
    return {"service_cost": c.step("biaya jasa", total), "labor": total_labor}


__all__ = [
    "DataNature",
    "ExchangeRate",
    "MaterialLine",
    "MaterialPrice",
    "ResourceUsage",
    "fully_loaded_unit_cost",
    "landed_cost",
    "manufacturing_unit_cost",
    "material_input",
    "resolve_fx_rate",
    "resolve_material_price",
    "service_cost",
    "waste_rate_from_extra",
]
