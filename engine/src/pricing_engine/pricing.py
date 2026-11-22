"""Pricing (CALCULATION_SPEC.md §5) dan evaluasi diskon (§5.5)."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from .core import (
    ONE,
    ZERO,
    Calc,
    EngineError,
    Status,
    calculation,
    dec,
    fraction,
    invalid,
    non_negative,
    opt_dec,
    positive,
)

TAX_LOAD_LABEL = "alokasi beban pajak untuk perencanaan"

# Toleransi pembandingan margin terhadap target. Hasil bagi Decimal 28 digit bisa
# menyisakan selisih di digit terakhir (mis. 0.2999…9999); selisih sekecil ini
# bukan pelanggaran target.
MARGIN_TOLERANCE = Decimal("1E-20")


class PriceBase(enum.StrEnum):
    """Basis biaya persentase (§2.2)."""

    LIST_PRICE = "LIST_PRICE"
    NET_PRICE = "NET_PRICE"
    GROSS_PRICE = "GROSS_PRICE"
    PRODUCT_COST = "PRODUCT_COST"


class PricingMethod(enum.StrEnum):
    MARKUP = "MARKUP"
    TARGET_GROSS_MARGIN = "TARGET_GROSS_MARGIN"
    TARGET_CONTRIBUTION_MARGIN = "TARGET_CONTRIBUTION_MARGIN"
    MINIMUM_VIABLE = "MINIMUM_VIABLE"
    BREAK_EVEN = "BREAK_EVEN"
    TARGET_OPERATING_PROFIT = "TARGET_OPERATING_PROFIT"
    COMPETITIVE = "COMPETITIVE"
    VALUE_BASED = "VALUE_BASED"


class MarginDefinition(enum.StrEnum):
    GROSS = "GROSS"
    CONTRIBUTION = "CONTRIBUTION"


@dataclass(frozen=True)
class PercentageFee:
    name: str
    rate: Any
    base: PriceBase = PriceBase.NET_PRICE


@dataclass(frozen=True)
class _Load:
    """Beban persentase yang sudah direduksi ke basis N."""

    p: Decimal  # P = F_N + T_N + F_L/(1-D) + F_G(1+vat)
    cost_pct: Decimal  # fee berbasis PRODUCT_COST (ditambahkan ke sisi biaya)
    fees: tuple[tuple[str, Decimal, PriceBase], ...]


def _load(
    c: Calc,
    fees: Sequence[PercentageFee],
    discount: Decimal,
    turnover_tax_load: Decimal,
    vat_effective_rate: Decimal,
) -> _Load:
    p = turnover_tax_load
    cost_pct = ZERO
    parsed: list[tuple[str, Decimal, PriceBase]] = []
    for i, f in enumerate(fees):
        if not isinstance(f, PercentageFee):
            raise invalid(f"fees[{i}] harus PercentageFee")
        rate = fraction(f.rate, f"fee '{f.name}'.rate")
        base = PriceBase(f.base)
        parsed.append((f.name, rate, base))
        if base is PriceBase.NET_PRICE:
            p += rate
        elif base is PriceBase.LIST_PRICE:
            p += rate / (ONE - discount)
        elif base is PriceBase.GROSS_PRICE:
            p += rate * (ONE + vat_effective_rate)
        else:
            cost_pct += rate
    c.step("P (beban persentase efektif terhadap N)", p)
    return _Load(p=p, cost_pct=cost_pct, fees=tuple(parsed))


def _breakdown(
    c: Calc,
    *,
    net: Decimal,
    unit_cost: Decimal,
    variable_cost: Decimal,
    discount: Decimal,
    load: _Load,
    turnover_tax_load: Decimal,
    vat_effective_rate: Decimal,
) -> dict[str, Any]:
    list_price = net / (ONE - discount)
    fee_amounts: dict[str, Decimal] = {}
    for name, rate, base in load.fees:
        if base is PriceBase.NET_PRICE:
            amt = rate * net
        elif base is PriceBase.LIST_PRICE:
            amt = rate * list_price
        elif base is PriceBase.GROSS_PRICE:
            amt = rate * net * (ONE + vat_effective_rate)
        else:
            amt = rate * unit_cost
        fee_amounts[name] = fee_amounts.get(name, ZERO) + amt
    fee_total = sum(fee_amounts.values(), ZERO)
    tax_load_amount = turnover_tax_load * net
    contribution = net - unit_cost - variable_cost - fee_total
    gross_profit = net - unit_cost
    values: dict[str, Any] = {
        "net_price": net,
        "list_price": list_price,
        "discount_amount": list_price - net,
        "fee_amounts": fee_amounts,
        "fee_total": fee_total,
        "contribution": contribution,
        "contribution_margin": contribution / net,
        "gross_profit": gross_profit,
        "gross_margin": gross_profit / net,
    }
    if turnover_tax_load > 0:
        values["tax_load_amount"] = tax_load_amount
        values["contribution_after_tax_load"] = contribution - tax_load_amount
        values["margin_after_tax_load"] = (contribution - tax_load_amount) / net
        values["tax_load_label"] = TAX_LOAD_LABEL
    c.step("N (harga bersih)", net)
    c.step("L (harga daftar) = N / (1 − D)", list_price)
    c.step("total fee", fee_total)
    c.step("kontribusi = N − C − V − fee", contribution)
    return values


def _minimum_price(load: _Load, unit_cost: Decimal, variable_cost: Decimal) -> Decimal:
    denom = ONE - load.p
    if denom <= 0:
        raise EngineError(
            Status.INFEASIBLE_MARGIN,
            f"total beban persentase P = {load.p} ≥ 100%; tidak ada harga yang menutup biaya",
        )
    return (unit_cost * (ONE + load.cost_pct) + variable_cost) / denom


def _margin_for_target(values: dict[str, Any], definition: MarginDefinition) -> Decimal:
    if definition is MarginDefinition.GROSS:
        return values["gross_margin"]
    return values.get("margin_after_tax_load", values["contribution_margin"])


@calculation
def calculate_price(
    c: Calc,
    *,
    method: PricingMethod,
    unit_cost: Any,
    variable_cost: Any = 0,
    discount: Any = 0,
    fees: Sequence[PercentageFee] = (),
    turnover_tax_load: Any = 0,
    vat_effective_rate: Any = 0,
    target_margin: Any = None,
    markup: Any = None,
    fixed_cost: Any = None,
    volume: Any = None,
    target_operating_profit: Any = None,
    reference_price: Any = None,
    adjustment: Any = 0,
) -> dict[str, Any]:
    """Menghitung harga bersih N per metode (§5.2)."""
    method = PricingMethod(method)
    C = non_negative(unit_cost, "unit_cost")
    V = non_negative(variable_cost, "variable_cost")
    D = fraction(discount, "discount")
    T = fraction(turnover_tax_load, "turnover_tax_load")
    vat = non_negative(vat_effective_rate, "vat_effective_rate")
    c.step("C (biaya produk per unit)", C)
    c.step("V (biaya variabel lain per unit)", V)
    c.step("D (diskon)", D)
    load = _load(c, fees, D, T, vat)
    cost_side = C * (ONE + load.cost_pct) + V

    def require_margin() -> Decimal:
        if target_margin is None:
            raise invalid(f"{method.value} memerlukan target_margin")
        return fraction(target_margin, "target_margin")

    def divide(numerator: Decimal, denom: Decimal, what: str) -> Decimal:
        if denom <= 0:
            raise EngineError(
                Status.INFEASIBLE_MARGIN,
                f"{what}: penyebut = {denom} ≤ 0 (target margin + beban persentase ≥ 100%)",
            )
        return numerator / denom

    margin_definition = MarginDefinition.CONTRIBUTION
    M: Decimal | None = None
    if method is PricingMethod.MARKUP:
        if markup is None:
            raise invalid("MARKUP memerlukan markup")
        k = non_negative(markup, "markup")
        c.step("k (markup)", k)
        net = divide(C * (ONE + k) + load.cost_pct * C + V, ONE - load.p, "N = (C(1+k) + V) / (1 − P)")
    elif method is PricingMethod.TARGET_GROSS_MARGIN:
        M = require_margin()
        margin_definition = MarginDefinition.GROSS
        c.step("M (target gross margin)", M)
        net = divide(C, ONE - M, "N = C / (1 − M)")
    elif method is PricingMethod.TARGET_CONTRIBUTION_MARGIN:
        M = require_margin()
        c.step("M (target contribution margin)", M)
        net = divide(cost_side, ONE - M - load.p, "N = (C + V) / (1 − M − P)")
    elif method is PricingMethod.MINIMUM_VIABLE:
        net = _minimum_price(load, C, V)
    elif method in (PricingMethod.BREAK_EVEN, PricingMethod.TARGET_OPERATING_PROFIT):
        if fixed_cost is None or volume is None:
            raise invalid(f"{method.value} memerlukan fixed_cost dan volume")
        FC = non_negative(fixed_cost, "fixed_cost")
        Q = positive(volume, "volume")
        TOP = ZERO
        if method is PricingMethod.TARGET_OPERATING_PROFIT:
            if target_operating_profit is None:
                raise invalid("TARGET_OPERATING_PROFIT memerlukan target_operating_profit")
            TOP = dec(target_operating_profit, "target_operating_profit")
        c.step("FC", FC)
        c.step("Q", Q)
        c.step("TOP", TOP)
        net = divide(cost_side + (FC + TOP) / Q, ONE - load.p, "N = (C + V + (FC + TOP)/Q) / (1 − P)")
    elif method is PricingMethod.COMPETITIVE:
        if reference_price is None:
            raise invalid("COMPETITIVE memerlukan reference_price (harga pesaing)")
        net = positive(reference_price, "reference_price") * (ONE + dec(adjustment, "adjustment"))
        if net <= 0:
            raise invalid("harga hasil penyesuaian harus > 0")
    else:  # VALUE_BASED
        if reference_price is None:
            raise invalid("VALUE_BASED memerlukan reference_price (nilai persepsi)")
        net = positive(reference_price, "reference_price")

    if net <= 0:
        raise invalid(f"harga bersih hasil perhitungan = {net} ≤ 0")

    values = _breakdown(
        c,
        net=net,
        unit_cost=C,
        variable_cost=V,
        discount=D,
        load=load,
        turnover_tax_load=T,
        vat_effective_rate=vat,
    )
    values["method"] = method.value
    values["target_price"] = net

    try:
        n_min = _minimum_price(load, C, V)
    except EngineError:
        n_min = None
    values["minimum_price"] = n_min
    if n_min is not None and net < n_min:
        c.warn(Status.BELOW_MIN_PRICE, f"N = {net} di bawah harga minimum {n_min}")
    if target_margin is not None and M is None:
        M = fraction(target_margin, "target_margin")
    if M is not None and _margin_for_target(values, margin_definition) < M - MARGIN_TOLERANCE:
        c.warn(Status.BELOW_TARGET_MARGIN, f"margin di bawah target {M}")
    return values


@calculation
def evaluate_price(
    c: Calc,
    *,
    list_price: Any,
    unit_cost: Any,
    discount: Any = 0,
    variable_cost: Any = 0,
    fees: Sequence[PercentageFee] = (),
    turnover_tax_load: Any = 0,
    vat_effective_rate: Any = 0,
    target_margin: Any = None,
    margin_definition: MarginDefinition = MarginDefinition.CONTRIBUTION,
) -> dict[str, Any]:
    """Evaluasi harga yang sudah ada setelah diskon (§5.5)."""
    L = positive(list_price, "list_price")
    C = non_negative(unit_cost, "unit_cost")
    V = non_negative(variable_cost, "variable_cost")
    D = fraction(discount, "discount")
    T = fraction(turnover_tax_load, "turnover_tax_load")
    vat = non_negative(vat_effective_rate, "vat_effective_rate")
    definition = MarginDefinition(margin_definition)
    load = _load(c, fees, D, T, vat)
    net = c.step("N = L × (1 − D)", L * (ONE - D))
    values = _breakdown(
        c,
        net=net,
        unit_cost=C,
        variable_cost=V,
        discount=D,
        load=load,
        turnover_tax_load=T,
        vat_effective_rate=vat,
    )
    n_min = _minimum_price(load, C, V)
    values["minimum_price"] = c.step("N_min", n_min)
    if net < n_min:
        c.warn(Status.BELOW_MIN_PRICE, f"N = {net} di bawah harga minimum {n_min}; publikasi memerlukan override")
    elif target_margin is not None:
        M = fraction(target_margin, "target_margin")
        if _margin_for_target(values, definition) < M - MARGIN_TOLERANCE:
            c.warn(Status.BELOW_TARGET_MARGIN, f"margin di bawah target {M}")
    return values


@calculation
def validate_publication(
    c: Calc,
    *,
    net_price: Any,
    minimum_price: Any,
    override_reason: str | None = None,
    override_by: str | None = None,
) -> dict[str, Any]:
    """Harga di bawah minimum hanya boleh dipublikasikan dengan override tercatat (§5.5)."""
    N = positive(net_price, "net_price")
    n_min = opt_dec(minimum_price, "minimum_price")
    below = n_min is not None and N < n_min
    if below:
        if not (override_reason and override_reason.strip()) or not override_by:
            raise invalid("harga di bawah harga minimum: override_reason dan override_by wajib diisi")
        c.warn(Status.BELOW_MIN_PRICE, f"dipublikasikan dengan override oleh {override_by}")
    return {"publishable": True, "override_applied": below}
