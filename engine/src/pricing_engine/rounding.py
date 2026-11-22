"""Kebijakan pembulatan harga dengan margin guard (CALCULATION_SPEC.md §7)."""

from __future__ import annotations

import enum
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any

from .core import ZERO, Calc, calculation, opt_dec, positive


class RoundingMode(enum.StrEnum):
    UP = "UP"
    NEAREST = "NEAREST"
    DOWN = "DOWN"


_MODES = {
    RoundingMode.UP: ROUND_CEILING,
    RoundingMode.NEAREST: ROUND_HALF_UP,
    RoundingMode.DOWN: ROUND_FLOOR,
}


@calculation
def round_price(
    c: Calc,
    *,
    target_price: Any,
    increment: Any,
    mode: RoundingMode = RoundingMode.NEAREST,
    margin_guard: bool = True,
    minimum_price: Any = None,
) -> dict[str, Any]:
    """Membulatkan harga ke kelipatan `increment`.

    `target_price` adalah harga presisi penuh yang tepat memenuhi target margin.
    Karena margin naik monoton terhadap harga, syarat "margin ≥ target" setara
    dengan "harga ≥ target_price". Margin guard menaikkan harga satu increment
    sampai harga ≥ target_price (bila guard aktif) dan ≥ minimum_price.
    """
    target = positive(target_price, "target_price")
    inc = positive(increment, "increment")
    mode = RoundingMode(mode)
    n_min = opt_dec(minimum_price, "minimum_price")

    units = (target / inc).to_integral_value(rounding=_MODES[mode])
    rounded = c.step(f"pembulatan {mode.value} ke kelipatan {inc}", units * inc)
    before_guard = rounded

    floor_price = ZERO
    if margin_guard:
        floor_price = target
    if n_min is not None and n_min > floor_price:
        floor_price = n_min

    steps = 0
    while rounded < floor_price:
        rounded += inc
        steps += 1
    if steps:
        c.step(f"margin guard: naik {steps} increment", rounded)

    return {
        "target_price": target,
        "rounded_before_guard": before_guard,
        "recommended_price": rounded,
        "guard_applied": steps > 0,
    }
