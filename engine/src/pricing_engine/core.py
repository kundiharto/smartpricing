"""Core primitives: Decimal context, status codes, result envelope, hashing.

Lihat CALCULATION_SPEC.md §0.
"""

from __future__ import annotations

import dataclasses
import enum
import functools
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from typing import Any, Callable

ENGINE_VERSION = "1.0.0"

PRECISION = 28

# ISO 4217 minor units. Mata uang lain default 2.
CURRENCY_MINOR_UNITS: dict[str, int] = {
    "IDR": 0,
    "JPY": 0,
    "KRW": 0,
    "VND": 0,
    "USD": 2,
    "EUR": 2,
    "SGD": 2,
    "MYR": 2,
    "CNY": 2,
    "AUD": 2,
}

ZERO = Decimal(0)
ONE = Decimal(1)


class Status(enum.StrEnum):
    OK = "OK"
    # errors
    INVALID_INPUT = "INVALID_INPUT"
    INFEASIBLE_MARGIN = "INFEASIBLE_MARGIN"
    # result states
    NO_BREAK_EVEN = "NO_BREAK_EVEN"
    NO_BREAK_EVEN_WITHIN_CAPACITY = "NO_BREAK_EVEN_WITHIN_CAPACITY"
    UNBOUNDED = "UNBOUNDED"
    # warnings
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    BELOW_MIN_PRICE = "BELOW_MIN_PRICE"
    BELOW_TARGET_MARGIN = "BELOW_TARGET_MARGIN"
    TAX_REGIME_THRESHOLD_EXCEEDED = "TAX_REGIME_THRESHOLD_EXCEEDED"
    MISSING_DRIVER_ACTIVITY = "MISSING_DRIVER_ACTIVITY"


class EngineError(Exception):
    """Menghentikan perhitungan dengan status non-OK (§0.3)."""

    def __init__(self, status: Status, message: str, values: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.values = values or {}


def invalid(message: str) -> EngineError:
    return EngineError(Status.INVALID_INPUT, message)


@dataclass(frozen=True)
class Warning_:
    code: Status
    message: str


@dataclass(frozen=True)
class Result:
    """Amplop output standar setiap kalkulasi."""

    calculation: str
    status: Status
    values: dict[str, Any]
    warnings: tuple[Warning_, ...]
    trace: tuple[str, ...]
    message: str | None
    engine_version: str
    input_hash: str

    @property
    def ok(self) -> bool:
        return self.status is Status.OK

    @property
    def warning_codes(self) -> tuple[Status, ...]:
        return tuple(w.code for w in self.warnings)

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def to_dict(self) -> dict[str, Any]:
        """Bentuk JSON-safe untuk disimpan sebagai snapshot."""
        return {
            "calculation": self.calculation,
            "status": self.status.value,
            "values": _canonical(self.values),
            "warnings": [{"code": w.code.value, "message": w.message} for w in self.warnings],
            "trace": list(self.trace),
            "message": self.message,
            "engine_version": self.engine_version,
            "input_hash": self.input_hash,
        }


class Calc:
    """Konteks per kalkulasi: mengumpulkan trace dan peringatan."""

    def __init__(self) -> None:
        self.trace: list[str] = []
        self.warnings: list[Warning_] = []

    def step(self, label: str, value: Any) -> Any:
        self.trace.append(f"{label} = {_fmt(value)}")
        return value

    def note(self, text: str) -> None:
        self.trace.append(text)

    def warn(self, code: Status, message: str) -> None:
        if not any(w.code is code and w.message == message for w in self.warnings):
            self.warnings.append(Warning_(code, message))


# ---------------------------------------------------------------------------
# Decimal helpers
# ---------------------------------------------------------------------------


def _engine_context() -> Context:
    return Context(
        prec=PRECISION,
        rounding=ROUND_HALF_EVEN,
        traps=[InvalidOperation, DivisionByZero, Overflow],
    )


def dec(value: Any, name: str = "value") -> Decimal:
    """Konversi input ke Decimal. Float ditolak (§0.1)."""
    if isinstance(value, bool):
        raise invalid(f"{name}: boolean bukan angka")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise invalid(f"{name}: harus angka hingga")
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            d = Decimal(value.strip())
        except (InvalidOperation, ValueError):
            raise invalid(f"{name}: '{value}' bukan angka") from None
        if not d.is_finite():
            raise invalid(f"{name}: harus angka hingga")
        return d
    if isinstance(value, float):
        raise invalid(f"{name}: tipe float tidak diizinkan; kirim sebagai string atau Decimal")
    raise invalid(f"{name}: tipe {type(value).__name__} tidak didukung")


def opt_dec(value: Any, name: str) -> Decimal | None:
    return None if value is None else dec(value, name)


def non_negative(value: Any, name: str) -> Decimal:
    d = dec(value, name)
    if d < 0:
        raise invalid(f"{name} tidak boleh negatif (diberikan {d})")
    return d


def positive(value: Any, name: str) -> Decimal:
    d = dec(value, name)
    if d <= 0:
        raise invalid(f"{name} harus > 0 (diberikan {d})")
    return d


def fraction(value: Any, name: str, *, allow_one: bool = False) -> Decimal:
    """Pecahan 0 ≤ x < 1 (atau ≤ 1 bila allow_one)."""
    d = dec(value, name)
    upper_ok = d <= 1 if allow_one else d < 1
    if d < 0 or not upper_ok:
        bound = "≤ 1" if allow_one else "< 1"
        raise invalid(f"{name} harus 0 ≤ x {bound} (diberikan {d})")
    return d


def minor_units(currency: str) -> int:
    return CURRENCY_MINOR_UNITS.get(currency.upper(), 2)


def currency_quantum(currency: str) -> Decimal:
    return Decimal(1).scaleb(-minor_units(currency))


def quantize_money(value: Decimal, currency: str = "IDR") -> Decimal:
    """Pembulatan tampilan mata uang (ROUND_HALF_UP, §0.1)."""
    with localcontext(_engine_context()):
        return value.quantize(currency_quantum(currency), rounding=ROUND_HALF_UP)


def q(value: Decimal, places: str = "0.01") -> Decimal:
    """Quantize untuk tampilan/tes: ROUND_HALF_UP."""
    with localcontext(_engine_context()):
        return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def ceil_int(value: Decimal) -> Decimal:
    return value.to_integral_value(rounding=ROUND_CEILING)


def floor_int(value: Decimal) -> Decimal:
    return value.to_integral_value(rounding=ROUND_FLOOR)


# ---------------------------------------------------------------------------
# Hashing / canonical form
# ---------------------------------------------------------------------------


def _canonical(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        # normalize agar "1.0" dan "1" menghasilkan hash yang sama
        n = obj.normalize()
        return format(n, "f") if n == n.to_integral_value() and abs(n.adjusted()) < 30 else str(n)
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, int):
        return _canonical(Decimal(obj))
    if isinstance(obj, str):
        return obj
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            "__type__": type(obj).__name__,
            **{f.name: _canonical(getattr(obj, f.name)) for f in dataclasses.fields(obj)},
        }
    if isinstance(obj, dict):
        return {str(k): _canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    if isinstance(obj, float):
        return f"float:{obj!r}"  # tetap ter-hash; validasi menolaknya
    return repr(obj)


def canonical(obj: Any) -> Any:
    """Bentuk JSON-safe dan stabil dari input/output (untuk snapshot)."""
    return _canonical(obj)


def input_hash(calculation: str, inputs: dict[str, Any]) -> str:
    payload = {"calculation": calculation, "engine_version": ENGINE_VERSION, "inputs": _canonical(inputs)}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _fmt(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f") if value == value.to_integral_value() else str(value)
    return str(value)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def calculation(fn: Callable[..., dict[str, Any]]) -> Callable[..., Result]:
    """Membungkus fungsi kalkulasi: keyword-only, konteks Decimal, hash, trace.

    Fungsi yang dibungkus menerima `c: Calc` sebagai argumen pertama dan
    mengembalikan dict nilai. EngineError diubah menjadi Result non-OK.
    """

    name = fn.__name__

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Result:
        if args:
            raise TypeError(f"{name}() hanya menerima argumen keyword")
        h = input_hash(name, kwargs)
        c = Calc()
        message: str | None = None
        with localcontext(_engine_context()):
            try:
                values = fn(c, **kwargs)
                status = Status.OK
            except EngineError as e:
                status, message, values = e.status, e.message, e.values
                c.note(f"STOP {status.value}: {message}")
            except (DecimalException, ZeroDivisionError) as e:
                status, message, values = Status.INVALID_INPUT, f"aritmetika tidak valid: {e!r}", {}
                c.note(f"STOP {status.value}: {message}")
        return Result(
            calculation=name,
            status=status,
            values=values,
            warnings=tuple(c.warnings),
            trace=tuple(c.trace),
            message=message,
            engine_version=ENGINE_VERSION,
            input_hash=h,
        )

    wrapper.calculation_name = name  # type: ignore[attr-defined]
    return wrapper


__all__ = [
    "ENGINE_VERSION",
    "ONE",
    "ZERO",
    "Calc",
    "EngineError",
    "Result",
    "Status",
    "Warning_",
    "calculation",
    "canonical",
    "ceil_int",
    "currency_quantum",
    "dec",
    "floor_int",
    "fraction",
    "input_hash",
    "invalid",
    "minor_units",
    "non_negative",
    "opt_dec",
    "positive",
    "q",
    "quantize_money",
]
