"""Kapasitas dan lembur (CALCULATION_SPEC.md §11)."""

from __future__ import annotations

from typing import Any

from .core import ZERO, Calc, Status, calculation, non_negative, opt_dec, positive


@calculation
def check_capacity(
    c: Calc,
    *,
    required: Any,
    regular_capacity: Any,
    max_overtime: Any = 0,
    expansion: Any = 0,
    regular_unit_cost: Any = None,
    overtime_multiplier: Any = None,
) -> dict[str, Any]:
    """Utilisasi, kebutuhan lembur, biaya lembur, dan permintaan yang tidak terpenuhi."""
    need = non_negative(required, "required")
    regular = positive(regular_capacity, "regular_capacity")
    ot_max = non_negative(max_overtime, "max_overtime")
    exp = non_negative(expansion, "expansion")

    utilization = c.step("utilisasi = kebutuhan / kapasitas reguler", need / regular)
    shortfall = max(ZERO, need - regular)
    overtime = c.step("lembur dipakai", min(shortfall, ot_max))
    unmet = c.step("permintaan tidak terpenuhi", max(ZERO, need - regular - ot_max - exp))

    if utilization > 1:
        c.warn(Status.CAPACITY_EXCEEDED, f"kebutuhan {need} melebihi kapasitas reguler {regular}")

    values: dict[str, Any] = {
        "utilization": utilization,
        "overtime_used": overtime,
        "expansion_used": min(max(ZERO, shortfall - overtime), exp),
        "unmet_demand": unmet,
        "available_total": regular + ot_max + exp,
    }
    unit_cost = opt_dec(regular_unit_cost, "regular_unit_cost")
    multiplier = opt_dec(overtime_multiplier, "overtime_multiplier")
    if unit_cost is not None and multiplier is not None:
        values["overtime_cost"] = c.step("biaya lembur = lembur × biaya reguler × multiplier", overtime * unit_cost * multiplier)
    return values
