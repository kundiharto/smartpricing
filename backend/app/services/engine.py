"""Jembatan ke Calculation Engine: hasil non-OK menjadi error API yang bisa dijelaskan."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pricing_engine.core import Result

from app.core.errors import ApiError


def require_ok(result: Result) -> Result:
    if not result.ok:
        raise ApiError(
            422,
            result.status.value,
            result.message or result.status.value,
            [{"calculation": result.calculation, "trace": list(result.trace)}],
        )
    return result


def to_numeric(value: Decimal, places: int) -> Decimal:
    """Pembulatan ke presisi kolom NUMERIC (ROUND_HALF_UP)."""
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def warnings_json(result: Result) -> list[dict[str, str]]:
    return [{"code": w.code.value, "message": w.message} for w in result.warnings]
