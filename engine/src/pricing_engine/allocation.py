"""Alokasi biaya dan pencegahan double counting (CALCULATION_SPEC.md §2.4, §6)."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any, Sequence

from .core import (
    ONE,
    ZERO,
    Calc,
    calculation,
    currency_quantum,
    dec,
    invalid,
    non_negative,
)


class AllocationMethod(enum.StrEnum):
    DIRECT = "DIRECT"
    EQUAL = "EQUAL"
    PERCENTAGE = "PERCENTAGE"
    DRIVER = "DRIVER"  # revenue, unit, labor-hour, machine-hour, activity, weight, value, ...


@dataclass(frozen=True)
class AllocationTarget:
    target_id: str
    driver: Any = None  # untuk DRIVER
    percentage: Any = None  # untuk PERCENTAGE (pecahan)


def largest_remainder(pool: Decimal, shares: dict[str, Decimal], quantum: Decimal) -> dict[str, Decimal]:
    """Membagi `pool` (sudah dalam kelipatan quantum) sesuai porsi, total tepat sama (§6.3).

    Seri dipecah berdasarkan urutan target_id.
    """
    exact = {k: pool * s for k, s in shares.items()}
    floored = {k: (v / quantum).to_integral_value(rounding=ROUND_FLOOR) * quantum for k, v in exact.items()}
    remainder_units = int(((pool - sum(floored.values(), ZERO)) / quantum).to_integral_value())
    order = sorted(exact, key=lambda k: (-(exact[k] - floored[k]), k))
    for k in order[:remainder_units]:
        floored[k] += quantum
    return floored


@calculation
def allocate(
    c: Calc,
    *,
    pool_amount: Any,
    method: AllocationMethod,
    targets: Sequence[AllocationTarget],
    currency: str = "IDR",
    allow_unallocated: bool = False,
    driver_name: str = "driver",
) -> dict[str, Any]:
    """Mengalokasikan pool biaya ke target dengan pembulatan largest remainder."""
    method = AllocationMethod(method)
    pool = non_negative(pool_amount, "pool_amount")
    if not targets:
        raise invalid("alokasi memerlukan minimal satu target")
    ids = [t.target_id for t in targets]
    if len(set(ids)) != len(ids):
        raise invalid("target_id duplikat dalam alokasi")

    if method is AllocationMethod.DIRECT:
        if len(targets) != 1:
            raise invalid("DIRECT memerlukan tepat satu target")
        shares = {ids[0]: ONE}
    elif method is AllocationMethod.EQUAL:
        shares = {i: ONE / len(ids) for i in ids}
    elif method is AllocationMethod.PERCENTAGE:
        shares = {}
        for t in targets:
            if t.percentage is None:
                raise invalid(f"{t.target_id}: percentage wajib untuk metode PERCENTAGE")
            shares[t.target_id] = non_negative(t.percentage, f"{t.target_id}.percentage")
        total_pct = sum(shares.values(), ZERO)
        c.step("Σ persentase", total_pct)
        if total_pct > ONE:
            raise invalid(f"Σ persentase = {total_pct} > 100%")
        if total_pct < ONE and not allow_unallocated:
            raise invalid(f"Σ persentase = {total_pct}; pool penuh harus tepat 100% (atau aktifkan allow_unallocated)")
    else:
        drivers = {}
        for t in targets:
            if t.driver is None:
                raise invalid(f"{t.target_id}: nilai driver wajib untuk metode DRIVER")
            drivers[t.target_id] = non_negative(t.driver, f"{t.target_id}.driver")
        total_driver = sum(drivers.values(), ZERO)
        c.step(f"Σ {driver_name}", total_driver)
        if total_driver == 0:
            raise invalid(f"Σ {driver_name} = 0; alokasi tidak dapat dihitung")
        shares = {k: v / total_driver for k, v in drivers.items()}

    quantum = currency_quantum(currency)
    pool_q = pool.quantize(quantum, rounding=ROUND_HALF_UP)
    allocated_share = sum(shares.values(), ZERO)
    allocatable = (pool_q * allocated_share).quantize(quantum, rounding=ROUND_HALF_UP)
    normalized = {k: v / allocated_share for k, v in shares.items()} if allocated_share else shares
    allocations = largest_remainder(allocatable, normalized, quantum) if allocated_share else {k: ZERO for k in ids}
    for k in ids:
        c.step(f"alokasi {k}", allocations[k])
    unallocated = pool_q - sum(allocations.values(), ZERO)
    return {
        "allocations": {k: allocations[k] for k in ids},
        "shares": shares,
        "allocated_total": sum(allocations.values(), ZERO),
        "unallocated_amount": unallocated,
        "is_allocated": True,
    }


class AssignmentMode(enum.StrEnum):
    DIRECT = "DIRECT"
    POOL = "POOL"


@dataclass(frozen=True)
class CostAssignment:
    cost_item_id: str
    period: str
    mode: AssignmentMode
    target_id: str | None = None


@calculation
def check_double_counting(c: Calc, *, assignments: Sequence[CostAssignment]) -> dict[str, Any]:
    """Satu cost item tidak boleh dibebankan langsung DAN masuk pool pada periode yang sama (§2.4)."""
    seen: dict[tuple[str, str], set[AssignmentMode]] = {}
    for a in assignments:
        seen.setdefault((a.cost_item_id, a.period), set()).add(AssignmentMode(a.mode))
    conflicts = sorted(f"{item} ({period})" for (item, period), modes in seen.items() if len(modes) > 1)
    if conflicts:
        raise invalid("double counting: cost item dibebankan langsung sekaligus masuk pool: " + ", ".join(conflicts))
    c.note(f"{len(seen)} kombinasi cost item/periode diperiksa, tidak ada double counting")
    return {"checked": len(seen)}
