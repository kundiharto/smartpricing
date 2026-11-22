from decimal import Decimal

from pricing_engine.core import Result, Status, q


def money(value: Decimal) -> Decimal:
    """Asersi nominal: quantize 0.01 ROUND_HALF_UP (TEST_SUITE_SPEC §0)."""
    return q(value, "0.01")


def rate(value: Decimal) -> Decimal:
    return q(value, "0.000001")


def assert_ok(result: Result, *warnings: Status) -> None:
    assert result.status is Status.OK, f"{result.status}: {result.message}"
    assert set(result.warning_codes) == set(warnings), result.warnings


def assert_status(result: Result, status: Status) -> None:
    assert result.status is status, f"expected {status}, got {result.status}: {result.message}"
