"""Break-even dan pendapatan untuk target laba (CALCULATION_SPEC.md §9)."""

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
    ceil_int,
    dec,
    fraction,
    invalid,
    non_negative,
    positive,
)


def _unit_contribution(
    c: Calc,
    unit_price: Any,
    unit_variable_cost: Any,
    unit_contribution: Any,
    pct_load: Any,
) -> tuple[Decimal, Decimal | None]:
    if unit_contribution is not None:
        return c.step("UCM (input)", dec(unit_contribution, "unit_contribution")), None
    if unit_price is None or unit_variable_cost is None:
        raise invalid("berikan unit_contribution, atau unit_price dan unit_variable_cost")
    N = positive(unit_price, "unit_price")
    vc = non_negative(unit_variable_cost, "unit_variable_cost")
    P = fraction(pct_load, "pct_load")
    return c.step("UCM = N − (C + V) − P × N", N - vc - P * N), N


@calculation
def break_even_single(
    c: Calc,
    *,
    fixed_cost: Any,
    unit_price: Any = None,
    unit_variable_cost: Any = None,
    unit_contribution: Any = None,
    pct_load: Any = 0,
    discrete: bool = True,
) -> dict[str, Any]:
    """BEP produk tunggal (§9.1)."""
    FC = non_negative(fixed_cost, "fixed_cost")
    ucm, N = _unit_contribution(c, unit_price, unit_variable_cost, unit_contribution, pct_load)
    if ucm <= 0:
        raise EngineError(
            Status.NO_BREAK_EVEN,
            f"kontribusi per unit = {ucm} ≤ 0; biaya tetap tidak akan tertutup",
            {"unit_contribution": ucm},
        )
    exact_units = FC / ucm
    units = c.step("BEP unit = FC / UCM" + (" (dibulatkan ke atas)" if discrete else ""), ceil_int(exact_units) if discrete else exact_units)
    values: dict[str, Any] = {"unit_contribution": ucm, "bep_units_exact": exact_units, "bep_units": units}
    if N is not None:
        cmr = ucm / N
        values["cmr"] = c.step("CMR = UCM / N", cmr)
        values["bep_revenue"] = c.step("BEP pendapatan = FC / CMR", FC / cmr)
    return values


@calculation
def break_even_revenue(c: Calc, *, fixed_cost: Any, cmr: Any) -> dict[str, Any]:
    """BEP pendapatan = FC / CMR."""
    FC = non_negative(fixed_cost, "fixed_cost")
    ratio = dec(cmr, "cmr")
    if ratio <= 0:
        raise EngineError(Status.NO_BREAK_EVEN, f"CMR = {ratio} ≤ 0", {"cmr": ratio})
    if ratio >= 1:
        raise invalid("CMR harus < 1")
    return {"bep_revenue": c.step("FC / CMR", FC / ratio)}


@dataclass(frozen=True)
class FixedCostTier:
    """Biaya tetap yang berlaku pada rentang volume [from_units, to_units] (inklusif)."""

    from_units: Any
    to_units: Any
    fixed_cost: Any


@calculation
def break_even_step(
    c: Calc,
    *,
    unit_contribution: Any,
    tiers: Sequence[FixedCostTier],
) -> dict[str, Any]:
    """BEP dengan step-fixed cost; output rentang menguntungkan (§9.2)."""
    ucm = dec(unit_contribution, "unit_contribution")
    if ucm <= 0:
        raise EngineError(Status.NO_BREAK_EVEN, f"kontribusi per unit = {ucm} ≤ 0", {"unit_contribution": ucm})
    if not tiers:
        raise invalid("tiers kosong")
    rows = sorted(
        (
            (non_negative(t.from_units, "from_units"), non_negative(t.to_units, "to_units"), non_negative(t.fixed_cost, "fixed_cost"))
            for t in tiers
        ),
        key=lambda r: r[0],
    )
    for prev, nxt in zip(rows, rows[1:]):
        if nxt[0] <= prev[1]:
            raise invalid("rentang tier tumpang tindih")

    analysis = []
    ranges: list[list[Decimal]] = []
    for lo, hi, fc in rows:
        q_star = ceil_int(fc / ucm)
        profit_at_start = lo * ucm - fc
        if q_star > hi:
            profitable = None
        else:
            profitable = (max(q_star, lo), hi)
        c.step(f"tier [{lo}, {hi}] FC {fc}: Q* = ceil(FC / UCM)", q_star)
        analysis.append(
            {
                "from_units": lo,
                "to_units": hi,
                "fixed_cost": fc,
                "q_star": q_star,
                "profit_at_start": profit_at_start,
                "profitable_range": profitable,
            }
        )
        if profitable:
            if ranges and profitable[0] <= ranges[-1][1] + 1:
                ranges[-1][1] = profitable[1]
            else:
                ranges.append([profitable[0], profitable[1]])

    values: dict[str, Any] = {
        "unit_contribution": ucm,
        "tiers": analysis,
        "profitable_ranges": [tuple(r) for r in ranges],
    }
    if not ranges:
        raise EngineError(
            Status.NO_BREAK_EVEN_WITHIN_CAPACITY,
            "tidak ada rentang volume yang menguntungkan dalam kapasitas yang dimodelkan",
            values,
        )
    values["first_break_even_units"] = ranges[0][0]
    return values


class MixBasis(enum.StrEnum):
    UNITS = "UNITS"
    REVENUE = "REVENUE"


@dataclass(frozen=True)
class MixItem:
    product: str
    unit_price: Any
    unit_variable_cost: Any
    mix: Any


@calculation
def break_even_multi(
    c: Calc,
    *,
    fixed_cost: Any,
    products: Sequence[MixItem],
    mix_basis: MixBasis = MixBasis.UNITS,
) -> dict[str, Any]:
    """BEP multi-produk dengan weighted contribution margin (§9.3)."""
    FC = non_negative(fixed_cost, "fixed_cost")
    basis = MixBasis(mix_basis)
    if not products:
        raise invalid("products kosong")
    total_mix = sum((non_negative(p.mix, f"{p.product}.mix") for p in products), ZERO)
    if total_mix != ONE:
        raise invalid(f"Σ sales mix = {total_mix}; harus tepat 1")

    weights: dict[str, Decimal] = {}
    r_mix = ZERO
    cm_mix = ZERO
    for p in products:
        N = positive(p.unit_price, f"{p.product}.unit_price")
        vc = non_negative(p.unit_variable_cost, f"{p.product}.unit_variable_cost")
        m = dec(p.mix)
        w = m if basis is MixBasis.UNITS else m / N  # unit per paket mix
        weights[p.product] = w
        r_mix += w * N
        cm_mix += w * (N - vc)
    c.step("R_mix", r_mix)
    c.step("CM_mix", cm_mix)
    if cm_mix <= 0:
        raise EngineError(Status.NO_BREAK_EVEN, f"kontribusi gabungan = {cm_mix} ≤ 0", {"cm_mix": cm_mix})
    wcmr = c.step("WCMR = CM_mix / R_mix", cm_mix / r_mix)
    bep_mix = c.step("BEP paket mix = FC / CM_mix", FC / cm_mix)
    return {
        "r_mix": r_mix,
        "cm_mix": cm_mix,
        "wcmr": wcmr,
        "bep_revenue": c.step("BEP pendapatan = FC / WCMR", FC / wcmr),
        "bep_mix_units": bep_mix,
        "bep_units": {k: bep_mix * w for k, w in weights.items()},
        "mix_basis": basis.value,
        "assumption": "sales mix konstan",
    }


class TargetType(enum.StrEnum):
    OPERATING_PROFIT = "OPERATING_PROFIT"
    NET_PROFIT = "NET_PROFIT"


class TaxRegime(enum.StrEnum):
    PROFIT_BASED = "PROFIT_BASED"
    TURNOVER_FINAL = "TURNOVER_FINAL"


@calculation
def required_revenue(
    c: Calc,
    *,
    fixed_cost: Any,
    cmr: Any,
    target_amount: Any,
    target_type: TargetType = TargetType.OPERATING_PROFIT,
    tax_regime: TaxRegime | None = None,
    tax_rate: Any = 0,
) -> dict[str, Any]:
    """Pendapatan yang dibutuhkan untuk target laba (§9.4). CMR konstan, tanpa step-fixed."""
    FC = non_negative(fixed_cost, "fixed_cost")
    ratio = dec(cmr, "cmr")
    target = dec(target_amount, "target_amount")
    ttype = TargetType(target_type)
    if ratio >= 1:
        raise invalid("CMR harus < 1")

    if ttype is TargetType.OPERATING_PROFIT:
        if ratio <= 0:
            raise EngineError(Status.INFEASIBLE_MARGIN, f"CMR = {ratio} ≤ 0")
        return {"required_revenue": c.step("R = (FC + TOP) / CMR", (FC + target) / ratio)}

    if tax_regime is None:
        raise invalid("NET_PROFIT memerlukan tax_regime")
    regime = TaxRegime(tax_regime)
    t = fraction(tax_rate, "tax_rate")
    if regime is TaxRegime.PROFIT_BASED:
        if ratio <= 0:
            raise EngineError(Status.INFEASIBLE_MARGIN, f"CMR = {ratio} ≤ 0")
        pbt = c.step("PBT = NP / (1 − t)", target / (ONE - t))
        return {"required_pbt": pbt, "required_revenue": c.step("R = (FC + PBT) / CMR", (FC + pbt) / ratio)}

    denom = ratio - t
    if denom <= 0:
        raise EngineError(Status.INFEASIBLE_MARGIN, f"CMR − tarif omzet = {denom} ≤ 0")
    revenue = c.step("R = (FC + NP) / (CMR − r)", (FC + target) / denom)
    return {"required_revenue": revenue, "turnover_tax": revenue * t}
