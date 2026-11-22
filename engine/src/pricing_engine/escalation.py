"""Eskalasi biaya (CALCULATION_SPEC.md §10)."""

from __future__ import annotations

import enum
from datetime import date
from typing import Any

from .core import ONE, Calc, calculation, dec, invalid, non_negative, opt_dec


class EscalationType(enum.StrEnum):
    NOMINAL = "NOMINAL"
    SIMPLE_PCT = "SIMPLE_PCT"
    COMPOUND_PCT = "COMPOUND_PCT"


class Frequency(enum.StrEnum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMIANNUAL = "SEMIANNUAL"
    ANNUAL = "ANNUAL"


_MONTHS = {
    Frequency.MONTHLY: 1,
    Frequency.QUARTERLY: 3,
    Frequency.SEMIANNUAL: 6,
    Frequency.ANNUAL: 12,
}


def full_months_between(start: date, end: date) -> int:
    """Jumlah bulan penuh dari start sampai end."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def full_periods(start: date, end: date, frequency: Frequency) -> int:
    if end < start:
        return 0
    return full_months_between(start, end) // _MONTHS[Frequency(frequency)]


@calculation
def escalate(
    c: Calc,
    *,
    base: Any,
    escalation_type: EscalationType,
    frequency: Frequency = Frequency.ANNUAL,
    rate: Any = None,
    amount: Any = None,
    effective_from: date | None = None,
    as_of_date: date | None = None,
    periods: int | None = None,
    cap: Any = None,
    floor: Any = None,
    override_rate: Any = None,
) -> dict[str, Any]:
    """Menghitung nilai biaya setelah n periode eskalasi penuh.

    `n` dihitung dari `effective_from` → `as_of_date`, atau diberikan langsung lewat `periods`
    (untuk proyeksi skenario).
    """
    b = non_negative(base, "base")
    etype = EscalationType(escalation_type)
    freq = Frequency(frequency)

    if periods is not None:
        if isinstance(periods, bool) or not isinstance(periods, int) or periods < 0:
            raise invalid("periods harus bilangan bulat ≥ 0")
        n = periods
    else:
        if effective_from is None or as_of_date is None:
            raise invalid("berikan periods, atau effective_from dan as_of_date")
        n = full_periods(effective_from, as_of_date, freq)
    c.step(f"n (periode {freq.value} penuh)", n)

    if etype is EscalationType.NOMINAL:
        if amount is None:
            raise invalid("NOMINAL memerlukan amount")
        value = c.step("base + n × amount", b + n * dec(amount, "amount"))
    else:
        r = override_rate if override_rate is not None else rate
        if r is None:
            raise invalid(f"{etype.value} memerlukan rate")
        r = dec(r, "rate")
        if r <= -1:
            raise invalid("rate harus > -100%")
        if override_rate is not None:
            c.note(f"rate di-override skenario: {r}")
        if etype is EscalationType.SIMPLE_PCT:
            value = c.step("base × (1 + r × n)", b * (ONE + r * n))
        else:
            value = c.step("base × (1 + r)^n", b * (ONE + r) ** n)

    unclamped = value
    lo = opt_dec(floor, "floor")
    hi = opt_dec(cap, "cap")
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    if value != unclamped:
        c.step("setelah cap/floor", value)
    return {"value": value, "periods": n, "unclamped_value": unclamped}
