"""Perilaku biaya (CALCULATION_SPEC.md §2)."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from .core import (
    ZERO,
    Calc,
    Status,
    calculation,
    ceil_int,
    dec,
    invalid,
    non_negative,
    opt_dec,
    positive,
)


def _clamp(c: Calc, cost: Decimal, minimum_amount: Any, maximum_amount: Any) -> Decimal:
    lo = opt_dec(minimum_amount, "minimum_amount")
    hi = opt_dec(maximum_amount, "maximum_amount")
    if lo is not None and hi is not None and lo > hi:
        raise invalid("minimum_amount > maximum_amount")
    original = cost
    if lo is not None and cost < lo:
        cost = lo
    if hi is not None and cost > hi:
        cost = hi
    if cost != original:
        c.step("setelah batas minimum/maksimum", cost)
    return cost


@calculation
def fixed_cost(
    c: Calc,
    *,
    amount: Any,
    activity: Any = None,
    min_activity: Any = None,
    max_activity: Any = None,
) -> dict[str, Any]:
    """Biaya tetap dalam rentang kapasitas yang ditentukan."""
    amt = non_negative(amount, "amount")
    if activity is not None:
        a = non_negative(activity, "activity")
        lo = opt_dec(min_activity, "min_activity")
        hi = opt_dec(max_activity, "max_activity")
        if (lo is not None and a < lo) or (hi is not None and a > hi):
            c.warn(Status.CAPACITY_EXCEEDED, f"aktivitas {a} di luar rentang biaya tetap [{lo}, {hi}]")
    return {"cost": c.step("biaya tetap", amt)}


@dataclass(frozen=True)
class DriverUsage:
    driver: str
    quantity: Any
    rate: Any


@calculation
def variable_cost(
    c: Calc,
    *,
    usages: Sequence[DriverUsage],
    minimum_amount: Any = None,
    maximum_amount: Any = None,
) -> dict[str, Any]:
    """VC = Σ (aktivitas × rate), boleh lebih dari satu driver."""
    if not usages:
        raise invalid("variable_cost memerlukan minimal satu driver")
    total = ZERO
    for u in usages:
        part = non_negative(u.quantity, f"{u.driver}.quantity") * non_negative(u.rate, f"{u.driver}.rate")
        total += c.step(f"{u.driver}: aktivitas × rate", part)
    return {"cost": _clamp(c, total, minimum_amount, maximum_amount)}


@calculation
def semi_variable_cost(
    c: Calc,
    *,
    base: Any,
    activity: Any,
    rate: Any,
    minimum_amount: Any = None,
    maximum_amount: Any = None,
) -> dict[str, Any]:
    """SVC = base + aktivitas × rate."""
    total = non_negative(base, "base") + non_negative(activity, "activity") * non_negative(rate, "rate")
    c.step("base + aktivitas × rate", total)
    return {"cost": _clamp(c, total, minimum_amount, maximum_amount)}


@dataclass(frozen=True)
class StepTier:
    """Baris tabel step-fixed (mode TABLE), batas inklusif."""

    from_activity: Any
    to_activity: Any
    amount: Any
    resource_count: Any = None


def _sorted_tiers(tiers: Sequence[StepTier]) -> list[tuple[Decimal, Decimal, Decimal, Decimal | None]]:
    if not tiers:
        raise invalid("tabel step-fixed kosong")
    rows = []
    for i, t in enumerate(tiers):
        lo = non_negative(t.from_activity, f"tiers[{i}].from_activity")
        hi = non_negative(t.to_activity, f"tiers[{i}].to_activity")
        if hi < lo:
            raise invalid(f"tiers[{i}]: to_activity < from_activity")
        rows.append((lo, hi, non_negative(t.amount, f"tiers[{i}].amount"), opt_dec(t.resource_count, "resource_count")))
    rows.sort(key=lambda r: r[0])
    for prev, nxt in zip(rows, rows[1:]):
        if nxt[0] <= prev[1]:
            raise invalid(f"rentang tier tumpang tindih: [{prev[0]}, {prev[1]}] dan [{nxt[0]}, {nxt[1]}]")
    return rows


@calculation
def step_fixed_table(
    c: Calc,
    *,
    activity: Any,
    tiers: Sequence[StepTier],
) -> dict[str, Any]:
    """Step-fixed mode TABLE: biaya = amount baris yang memuat aktivitas (§2.1)."""
    a = non_negative(activity, "activity")
    rows = _sorted_tiers(tiers)
    chosen = None
    for row in rows:
        lo, hi = row[0], row[1]
        if a <= hi and (a >= lo or row is rows[0]):
            chosen = row
            break
        if a < lo:  # celah antar tier → pakai tier berikutnya (konservatif)
            chosen = row
            c.note(f"aktivitas {a} berada di celah antar tier; dipakai tier [{lo}, {hi}]")
            break
    exceeded = False
    if chosen is None:
        chosen = rows[-1]
        exceeded = True
        c.warn(
            Status.CAPACITY_EXCEEDED,
            f"aktivitas {a} melebihi tier tertinggi ({rows[-1][1]}); biaya memakai tier tertinggi",
        )
    lo, hi, amount, count = chosen
    c.step(f"tier [{lo}, {hi}]", amount)
    return {
        "cost": amount,
        "resource_count": count,
        "tier_from": lo,
        "tier_to": hi,
        "capacity_exceeded": exceeded,
        "excess_activity": a - rows[-1][1] if exceeded else ZERO,
    }


@calculation
def step_fixed_ceiling(
    c: Calc,
    *,
    activity: Any,
    capacity_per_resource: Any,
    cost_per_resource: Any,
    min_resources: Any = 0,
    max_resources: Any = None,
) -> dict[str, Any]:
    """Step-fixed mode CEILING: jumlah = ceil(aktivitas / kapasitas per sumber daya)."""
    a = non_negative(activity, "activity")
    cap = positive(capacity_per_resource, "capacity_per_resource")
    unit_cost = non_negative(cost_per_resource, "cost_per_resource")
    count = max(ceil_int(a / cap), non_negative(min_resources, "min_resources"))
    c.step("jumlah sumber daya = ceil(aktivitas / kapasitas)", count)
    limit = opt_dec(max_resources, "max_resources")
    if limit is not None and count > limit:
        c.warn(Status.CAPACITY_EXCEEDED, f"butuh {count} sumber daya, maksimum {limit}")
    cost = c.step("biaya = jumlah × biaya per sumber daya", count * unit_cost)
    return {"cost": cost, "resource_count": count}


@calculation
def percentage_cost(
    c: Calc,
    *,
    rate: Any,
    base_value: Any,
    base: str,
) -> dict[str, Any]:
    """PC = pct × basis finansial. Basis wajib eksplisit."""
    if not base:
        raise invalid("basis biaya persentase wajib diisi")
    cost = non_negative(rate, "rate") * dec(base_value, "base_value")
    return {"cost": c.step(f"{rate} × {base}", cost), "base": base}


class TierMode(enum.StrEnum):
    GRADUATED = "GRADUATED"
    ALL_UNITS = "ALL_UNITS"


@dataclass(frozen=True)
class Bracket:
    """Bracket tarif; upper_bound inklusif, None = tak terbatas (harus terakhir)."""

    upper_bound: Any
    rate: Any


@calculation
def tiered_cost(
    c: Calc,
    *,
    activity: Any,
    brackets: Sequence[Bracket],
    mode: TierMode = TierMode.GRADUATED,
) -> dict[str, Any]:
    """Tiered cost (§2.3)."""
    a = non_negative(activity, "activity")
    mode = TierMode(mode)
    if not brackets:
        raise invalid("brackets kosong")
    parsed: list[tuple[Decimal | None, Decimal]] = []
    prev = ZERO
    for i, b in enumerate(brackets):
        ub = opt_dec(b.upper_bound, f"brackets[{i}].upper_bound")
        if ub is None and i != len(brackets) - 1:
            raise invalid("bracket tanpa batas atas harus berada di urutan terakhir")
        if ub is not None and ub <= prev:
            raise invalid("upper_bound bracket harus naik")
        parsed.append((ub, non_negative(b.rate, f"brackets[{i}].rate")))
        if ub is not None:
            prev = ub
    if parsed[-1][0] is not None and a > parsed[-1][0]:
        raise invalid(f"aktivitas {a} melebihi bracket tertinggi {parsed[-1][0]}")

    if mode is TierMode.ALL_UNITS:
        for ub, rate in parsed:
            if ub is None or a <= ub:
                return {"cost": c.step(f"{a} × tarif bracket {rate}", a * rate)}

    total = ZERO
    lower = ZERO
    for ub, rate in parsed:
        upper = a if ub is None else min(a, ub)
        if upper > lower:
            total += c.step(f"({lower}, {upper}] × {rate}", (upper - lower) * rate)
        if ub is None or a <= ub:
            break
        lower = ub
    return {"cost": total}


@calculation
def time_based_cost(
    c: Calc,
    *,
    time_units: Any,
    rate: Any,
    time_unit: str = "HOUR",
) -> dict[str, Any]:
    cost = non_negative(time_units, "time_units") * non_negative(rate, "rate")
    return {"cost": c.step(f"{time_units} {time_unit} × {rate}", cost)}
