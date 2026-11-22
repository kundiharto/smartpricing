"""Model biaya periode dan rencana laba (CALCULATION_SPEC.md §1, §2, §9, §10, §12, §14).

Alur `profit_plan`:
1. Terapkan penyesuaian skenario ke baris penjualan (harga, volume, biaya produk).
2. Bentuk aktivitas driver: unit penjualan/produksi = total volume, pendapatan = total omzet,
   driver lain dari input.
3. Evaluasi setiap cost item (periode item diskalakan ke periode skenario, eskalasi per tanggal).
   Cost item ber-scope PRODUCT tidak dihitung lagi karena sudah ada di HPP (cegah double counting).
4. Susun laba rugi, BEP (memperhitungkan biaya bertingkat), dan volume untuk target laba.
5. Profitabilitas per produk: kontribusi, lalu alokasi pool overhead (full cost).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Sequence

from .allocation import largest_remainder
from .core import (
    ONE,
    ZERO,
    Calc,
    EngineError,
    Status,
    calculation,
    ceil_int,
    currency_quantum,
    dec,
    floor_int,
    fraction,
    invalid,
    non_negative,
    opt_dec,
    positive,
)
from .escalation import EscalationType, Frequency, full_periods


class Behavior(enum.StrEnum):
    FIXED = "FIXED"
    VARIABLE = "VARIABLE"
    SEMI_VARIABLE = "SEMI_VARIABLE"
    STEP_FIXED = "STEP_FIXED"
    PERCENTAGE = "PERCENTAGE"


class Scope(enum.StrEnum):
    PRODUCT = "PRODUCT"
    PERIOD = "PERIOD"
    ALLOCATION_POOL = "ALLOCATION_POOL"


class DriverType(enum.StrEnum):
    SALES_UNITS = "SALES_UNITS"
    PRODUCTION_UNITS = "PRODUCTION_UNITS"
    REVENUE = "REVENUE"
    LABOR_HOURS = "LABOR_HOURS"
    MACHINE_HOURS = "MACHINE_HOURS"
    CUSTOM = "CUSTOM"


VOLUME_DRIVERS = {DriverType.SALES_UNITS, DriverType.PRODUCTION_UNITS}


class TaxRegime(enum.StrEnum):
    NONE = "NONE"
    PROFIT_BASED = "PROFIT_BASED"
    TURNOVER_FINAL = "TURNOVER_FINAL"


class TargetKind(enum.StrEnum):
    OPERATING_PROFIT = "OPERATING_PROFIT"
    NET_PROFIT = "NET_PROFIT"


class AllocationBasis(enum.StrEnum):
    EQUAL = "EQUAL"
    PERCENTAGE = "PERCENTAGE"
    DRIVER = "DRIVER"
    REVENUE = "REVENUE"  # porsi omzet rencana
    UNITS = "UNITS"  # porsi volume rencana


@dataclass(frozen=True)
class Tier:
    """Baris step-fixed mode TABLE, aktivitas per periode item (inklusif)."""

    from_activity: Any
    to_activity: Any
    amount: Any


@dataclass(frozen=True)
class CostItemSpec:
    code: str
    name: str
    behavior: Behavior
    scope: Scope = Scope.PERIOD
    category: str = "OTHER"
    period_months: int = 1  # periode nominal biaya: 1 = per bulan, 12 = per tahun
    driver_code: str | None = None
    driver_type: DriverType | None = None
    base_amount: Any = None
    rate: Any = None
    percentage: Any = None
    percentage_base: str | None = None  # REVENUE | COGS
    step_mode: str | None = None  # TABLE | CEILING
    tiers: tuple[Tier, ...] = ()
    capacity_per_resource: Any = None
    cost_per_resource: Any = None
    max_resources: Any = None
    minimum_amount: Any = None
    maximum_amount: Any = None
    escalation_type: str | None = None  # NOMINAL | SIMPLE_PCT | COMPOUND_PCT
    escalation_rate: Any = None
    escalation_amount: Any = None
    escalation_frequency: str | None = None
    escalation_cap: Any = None
    effective_from: date | None = None


@dataclass(frozen=True)
class SalesLine:
    product: str
    unit_price: Any
    unit_cost: Any
    volume: Any


@dataclass(frozen=True)
class AllocationRuleSpec:
    cost_code: str
    basis: AllocationBasis
    targets: tuple[tuple[str, Any], ...] = ()  # (product, persen/nilai driver); kosong untuk EQUAL/REVENUE/UNITS = semua produk
    allow_unallocated: bool = False


@dataclass(frozen=True)
class Adjustments:
    """Penyesuaian skenario dalam pecahan (+0.08 = naik 8%)."""

    price_change: Any = 0
    volume_change: Any = 0
    unit_cost_change: Any = 0
    variable_cost_change: Any = 0
    fixed_cost_change: Any = 0
    item_changes: tuple[tuple[str, Any], ...] = ()  # (cost_code, pecahan)
    product_volume_changes: tuple[tuple[str, Any], ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Evaluasi cost item
# ---------------------------------------------------------------------------


@dataclass
class _Item:
    spec: CostItemSpec
    k: Decimal  # periode skenario / periode item
    base: Decimal | None
    rate: Decimal | None
    pct: Decimal | None
    cost_per_resource: Decimal | None
    tiers: list[tuple[Decimal, Decimal, Decimal]]
    capacity: Decimal | None
    max_resources: Decimal | None
    minimum: Decimal | None
    maximum: Decimal | None
    fixed_mult: Decimal
    var_mult: Decimal
    escalation_note: str | None


@dataclass
class _ItemResult:
    fixed: Decimal
    variable: Decimal
    slope_units: Decimal  # turunan biaya terhadap total unit (untuk BEP)
    detail: dict[str, Any]


def _escalation_factor(spec: CostItemSpec, as_of: date) -> tuple[Decimal, Decimal, str | None]:
    """(faktor pengali, tambahan nominal untuk base, catatan)."""
    if not spec.escalation_type or spec.effective_from is None:
        return ONE, ZERO, None
    etype = EscalationType(spec.escalation_type)
    freq = Frequency(spec.escalation_frequency or "ANNUAL")
    n = full_periods(spec.effective_from, as_of, freq)
    if etype is EscalationType.NOMINAL:
        add = dec(spec.escalation_amount or 0, f"{spec.code}.escalation_amount") * n
        return ONE, add, f"eskalasi nominal {n}× = +{add}"
    r = dec(spec.escalation_rate or 0, f"{spec.code}.escalation_rate")
    factor = (ONE + r) ** n if etype is EscalationType.COMPOUND_PCT else ONE + r * n
    return factor, ZERO, f"eskalasi {etype.value} {n} periode × {factor}"


def _prepare(spec: CostItemSpec, months: int, as_of: date, adj: Adjustments) -> _Item:
    if spec.period_months not in (1, 3, 6, 12):
        raise invalid(f"{spec.code}: period_months harus 1, 3, 6, atau 12")
    beh = Behavior(spec.behavior)
    factor, add, note = _escalation_factor(spec, as_of)
    base = opt_dec(spec.base_amount, f"{spec.code}.base_amount")
    if base is not None:
        base = base * factor + add
        cap = opt_dec(spec.escalation_cap, f"{spec.code}.escalation_cap")
        if cap is not None and base > cap:
            base = cap
    rate = opt_dec(spec.rate, f"{spec.code}.rate")
    if rate is not None:
        rate = rate * factor
    cpr = opt_dec(spec.cost_per_resource, f"{spec.code}.cost_per_resource")
    if cpr is not None:
        cpr = cpr * factor
    tiers = []
    for i, t in enumerate(spec.tiers):
        lo = non_negative(t.from_activity, f"{spec.code}.tiers[{i}].from")
        hi = non_negative(t.to_activity, f"{spec.code}.tiers[{i}].to")
        if hi < lo:
            raise invalid(f"{spec.code}: tier {i + 1} batas atas < batas bawah")
        tiers.append((lo, hi, non_negative(t.amount, f"{spec.code}.tiers[{i}].amount") * factor))
    tiers.sort(key=lambda r: r[0])
    for a, b in zip(tiers, tiers[1:]):
        if b[0] <= a[1]:
            raise invalid(f"{spec.code}: rentang tier tumpang tindih")

    # validasi parameter wajib per perilaku
    if beh in (Behavior.FIXED, Behavior.SEMI_VARIABLE) and base is None:
        raise invalid(f"{spec.code}: base_amount wajib untuk {beh.value}")
    if beh in (Behavior.VARIABLE, Behavior.SEMI_VARIABLE, Behavior.STEP_FIXED) and (spec.driver_type is None or not spec.driver_code):
        raise invalid(f"{spec.code}: driver wajib untuk {beh.value}")
    if beh in (Behavior.VARIABLE, Behavior.SEMI_VARIABLE) and rate is None:
        raise invalid(f"{spec.code}: rate wajib untuk {beh.value}")
    pct = None
    if beh is Behavior.PERCENTAGE:
        pct = fraction(spec.percentage, f"{spec.code}.percentage")
        if spec.percentage_base not in ("REVENUE", "COGS"):
            raise invalid(f"{spec.code}: percentage_base harus REVENUE atau COGS")
    capacity = opt_dec(spec.capacity_per_resource, f"{spec.code}.capacity_per_resource")
    if beh is Behavior.STEP_FIXED:
        if spec.step_mode == "TABLE" and not tiers:
            raise invalid(f"{spec.code}: tabel tier wajib untuk step-fixed TABLE")
        if spec.step_mode == "CEILING" and (capacity is None or capacity <= 0 or cpr is None):
            raise invalid(f"{spec.code}: kapasitas dan biaya per sumber daya wajib untuk step-fixed CEILING")
        if spec.step_mode not in ("TABLE", "CEILING"):
            raise invalid(f"{spec.code}: step_mode harus TABLE atau CEILING")

    item_change = ZERO
    for code, change in adj.item_changes:
        if code == spec.code:
            item_change += dec(change, f"item_changes[{code}]")
    fixed_mult = (ONE + dec(adj.fixed_cost_change, "fixed_cost_change")) * (ONE + item_change)
    var_mult = (ONE + dec(adj.variable_cost_change, "variable_cost_change")) * (ONE + item_change)
    return _Item(
        spec=spec,
        k=Decimal(months) / Decimal(spec.period_months),
        base=base,
        rate=rate,
        pct=pct,
        cost_per_resource=cpr,
        tiers=tiers,
        capacity=capacity,
        max_resources=opt_dec(spec.max_resources, f"{spec.code}.max_resources"),
        minimum=opt_dec(spec.minimum_amount, f"{spec.code}.minimum_amount"),
        maximum=opt_dec(spec.maximum_amount, f"{spec.code}.maximum_amount"),
        fixed_mult=fixed_mult,
        var_mult=var_mult,
        escalation_note=note,
    )


def _driver_activity(item: _Item, units: Decimal, revenue: Decimal, other: dict[str, Decimal]) -> Decimal:
    dt = DriverType(item.spec.driver_type) if item.spec.driver_type else None
    if dt in VOLUME_DRIVERS:
        return units
    if dt is DriverType.REVENUE:
        return revenue
    return other.get(item.spec.driver_code or "", ZERO)


def _driver_slope(item: _Item, avg_price: Decimal) -> Decimal:
    """d(aktivitas)/d(total unit)."""
    dt = DriverType(item.spec.driver_type) if item.spec.driver_type else None
    if dt in VOLUME_DRIVERS:
        return ONE
    if dt is DriverType.REVENUE:
        return avg_price
    return ZERO


def _evaluate(item: _Item, units: Decimal, revenue: Decimal, cogs: Decimal, other: dict[str, Decimal], avg_price: Decimal, avg_cost: Decimal) -> _ItemResult:
    beh = Behavior(item.spec.behavior)
    act = _driver_activity(item, units, revenue, other) if item.spec.driver_type else ZERO
    fixed = variable = slope = ZERO
    detail: dict[str, Any] = {}
    if beh is Behavior.FIXED:
        fixed = item.base * item.k
    elif beh is Behavior.VARIABLE:
        variable = item.rate * act
        slope = item.rate * _driver_slope(item, avg_price)
    elif beh is Behavior.SEMI_VARIABLE:
        fixed = item.base * item.k
        variable = item.rate * act
        slope = item.rate * _driver_slope(item, avg_price)
    elif beh is Behavior.STEP_FIXED:
        act_item = act / item.k  # aktivitas per periode item
        detail["activity_per_item_period"] = act_item
        if item.spec.step_mode == "TABLE":
            chosen = None
            for lo, hi, amount in item.tiers:
                if act_item <= hi:
                    chosen = (lo, hi, amount)
                    break
            if chosen is None:
                chosen = item.tiers[-1]
                detail["capacity_exceeded"] = True
            detail["tier"] = [chosen[0], chosen[1]]
            fixed = chosen[2] * item.k
        else:
            count = ceil_int(act_item / item.capacity) if act_item > 0 else ZERO
            detail["resource_count"] = count
            if item.max_resources is not None and count > item.max_resources:
                detail["capacity_exceeded"] = True
            fixed = count * item.cost_per_resource * item.k
    else:  # PERCENTAGE
        if item.spec.percentage_base == "REVENUE":
            variable = item.pct * revenue
            slope = item.pct * avg_price
        else:
            variable = item.pct * cogs
            slope = item.pct * avg_cost

    fixed *= item.fixed_mult
    variable *= item.var_mult
    slope *= item.var_mult

    # batas minimum/maksimum per periode item; selisih diperlakukan sebagai komponen tetap
    if item.minimum is not None or item.maximum is not None:
        per_item_period = (fixed + variable) / item.k
        clamped = per_item_period
        if item.minimum is not None and clamped < item.minimum:
            clamped = item.minimum
        if item.maximum is not None and clamped > item.maximum:
            clamped = item.maximum
        if clamped != per_item_period:
            fixed += (clamped - per_item_period) * item.k
            detail["clamped"] = True
    return _ItemResult(fixed=fixed, variable=variable, slope_units=slope, detail=detail)


def _breakpoints(items: list[_Item], avg_price: Decimal, limit: Decimal) -> list[Decimal]:
    """Titik volume (total unit) tempat biaya bertingkat berubah."""
    points: set[Decimal] = set()
    for it in items:
        if Behavior(it.spec.behavior) is not Behavior.STEP_FIXED:
            continue
        s = _driver_slope(it, avg_price)
        if s == 0:
            continue
        if it.spec.step_mode == "TABLE":
            for _, hi, _ in it.tiers:
                points.add(hi * it.k / s)
        else:
            step = it.capacity * it.k / s
            q = step
            count = 0
            while q < limit and count < 5000:
                points.add(q)
                q += step
                count += 1
    return sorted(p for p in points if 0 < p < limit)


# ---------------------------------------------------------------------------
# Kalkulasi publik
# ---------------------------------------------------------------------------


def _activity_map(other_activity: dict[str, Any] | None) -> dict[str, Decimal]:
    return {k: non_negative(v, f"activity[{k}]") for k, v in (other_activity or {}).items()}


@calculation
def preview_costs(
    c: Calc,
    *,
    items: Sequence[CostItemSpec],
    units: Any = 0,
    revenue: Any = 0,
    cogs: Any = 0,
    other_activity: dict[str, Any] | None = None,
    period_months: int = 1,
    as_of_date: date,
) -> dict[str, Any]:
    """Biaya periode pada tingkat aktivitas tertentu (untuk halaman Biaya)."""
    if period_months < 1 or period_months > 12:
        raise invalid("period_months harus 1–12")
    U = non_negative(units, "units")
    R = non_negative(revenue, "revenue")
    C = non_negative(cogs, "cogs")
    other = _activity_map(other_activity)
    avg_p = R / U if U > 0 else ZERO
    avg_c = C / U if U > 0 else ZERO
    rows = []
    totals = {"fixed": ZERO, "variable": ZERO}
    for spec in items:
        it = _prepare(spec, period_months, as_of_date, Adjustments())
        res = _evaluate(it, U, R, C, other, avg_p, avg_c)
        if res.detail.get("capacity_exceeded"):
            c.warn(Status.CAPACITY_EXCEEDED, f"{spec.code}: aktivitas melebihi kapasitas tier tertinggi")
        if spec.driver_type and DriverType(spec.driver_type) not in VOLUME_DRIVERS | {DriverType.REVENUE} and spec.driver_code not in other:
            c.note(f"{spec.code}: aktivitas driver {spec.driver_code} tidak diisi, dianggap 0")
        rows.append(_row(spec, res, it))
        totals["fixed"] += res.fixed
        totals["variable"] += res.variable
    return {"items": rows, "fixed_total": totals["fixed"], "variable_total": totals["variable"], "total": totals["fixed"] + totals["variable"]}


def _row(spec: CostItemSpec, res: _ItemResult, it: _Item) -> dict[str, Any]:
    row = {
        "code": spec.code,
        "name": spec.name,
        "category": spec.category,
        "behavior": Behavior(spec.behavior).value,
        "scope": Scope(spec.scope).value,
        "fixed": res.fixed,
        "variable": res.variable,
        "total": res.fixed + res.variable,
        **res.detail,
    }
    if it.escalation_note:
        row["escalation"] = it.escalation_note
    return row


@calculation
def profit_plan(
    c: Calc,
    *,
    lines: Sequence[SalesLine],
    items: Sequence[CostItemSpec] = (),
    period_months: int = 1,
    as_of_date: date,
    other_activity: dict[str, Any] | None = None,
    adjustments: Adjustments = Adjustments(),
    allocation_rules: Sequence[AllocationRuleSpec] = (),
    tax_regime: TaxRegime = TaxRegime.NONE,
    tax_rate: Any = 0,
    exempt_turnover: Any = 0,
    target_kind: TargetKind | None = None,
    target_amount: Any = None,
    currency: str = "IDR",
) -> dict[str, Any]:
    """Rencana laba periode + BEP + target + profitabilitas produk."""
    if period_months < 1 or period_months > 12:
        raise invalid("period_months harus 1–12")
    if not lines:
        raise invalid("rencana penjualan kosong: tambahkan minimal satu produk")
    regime = TaxRegime(tax_regime)
    t_rate = fraction(tax_rate, "tax_rate")
    exempt = non_negative(exempt_turnover, "exempt_turnover")
    other = _activity_map(other_activity)
    adj = adjustments
    p_chg = dec(adj.price_change, "price_change")
    v_chg = dec(adj.volume_change, "volume_change")
    u_chg = dec(adj.unit_cost_change, "unit_cost_change")
    per_product_vol = {p: dec(x, f"product_volume_changes[{p}]") for p, x in adj.product_volume_changes}
    for name, val in (("price_change", p_chg), ("volume_change", v_chg), ("unit_cost_change", u_chg)):
        if val <= -1:
            raise invalid(f"{name} tidak boleh ≤ -100%")

    # 1. Baris penjualan setelah penyesuaian
    plan_lines = []
    seen = set()
    for ln in lines:
        if ln.product in seen:
            raise invalid(f"produk {ln.product} muncul lebih dari sekali di rencana penjualan")
        seen.add(ln.product)
        price = non_negative(ln.unit_price, f"{ln.product}.unit_price") * (ONE + p_chg)
        cost = non_negative(ln.unit_cost, f"{ln.product}.unit_cost") * (ONE + u_chg)
        vol = non_negative(ln.volume, f"{ln.product}.volume") * (ONE + v_chg) * (ONE + per_product_vol.get(ln.product, ZERO))
        plan_lines.append({"product": ln.product, "unit_price": price, "unit_cost": cost, "volume": vol,
                           "revenue": price * vol, "cogs": cost * vol})
    U = sum((l["volume"] for l in plan_lines), ZERO)
    R = sum((l["revenue"] for l in plan_lines), ZERO)
    COGS = sum((l["cogs"] for l in plan_lines), ZERO)
    if U <= 0 or R <= 0:
        raise invalid("total volume dan omzet rencana harus > 0")
    avg_p, avg_c = R / U, COGS / U
    c.step("total unit (U)", U)
    c.step("omzet (R)", R)
    c.step("HPP", COGS)

    # 2–3. Cost items
    prepared: list[_Item] = []
    excluded = []
    for spec in items:
        if Scope(spec.scope) is Scope.PRODUCT:
            excluded.append(spec.code)
            continue
        prepared.append(_prepare(spec, period_months, as_of_date, adj))
        if spec.driver_type and DriverType(spec.driver_type) not in VOLUME_DRIVERS | {DriverType.REVENUE} and spec.driver_code not in other:
            c.warn(Status.MISSING_DRIVER_ACTIVITY, f"{spec.code}: aktivitas driver {spec.driver_code} tidak diisi; dianggap 0")
    if excluded:
        c.note(f"tidak dihitung ulang (sudah termasuk HPP lewat costing): {', '.join(excluded)}")

    def evaluate_all(units: Decimal) -> tuple[Decimal, Decimal, Decimal, list[tuple[_Item, _ItemResult]]]:
        rev, cg = avg_p * units, avg_c * units
        out = [(it, _evaluate(it, units, rev, cg, other, avg_p, avg_c)) for it in prepared]
        fixed = sum((r.fixed for _, r in out), ZERO)
        var = sum((r.variable for _, r in out), ZERO)
        slope = sum((r.slope_units for _, r in out), ZERO)
        return fixed, var, slope, out

    fixed_total, var_total, var_slope, evaluated = evaluate_all(U)
    for it, res in evaluated:
        if res.detail.get("capacity_exceeded"):
            c.warn(Status.CAPACITY_EXCEEDED, f"{it.spec.code}: volume rencana melebihi kapasitas tier/sumber daya maksimum")

    # 4. Laba rugi
    gross = R - COGS
    contribution = gross - var_total
    op = contribution - fixed_total
    if regime is TaxRegime.PROFIT_BASED:
        tax = max(ZERO, op) * t_rate
    elif regime is TaxRegime.TURNOVER_FINAL:
        tax = max(ZERO, R - exempt) * t_rate
    else:
        tax = ZERO
    net = op - tax
    c.step("laba kotor = R − HPP", gross)
    c.step("kontribusi = laba kotor − biaya variabel", contribution)
    c.step("laba operasional = kontribusi − biaya tetap", op)
    c.step("laba bersih = laba operasional − PPh", net)
    pnl = {
        "revenue": R, "cogs": COGS, "gross_profit": gross, "gross_margin": gross / R,
        "variable_costs": var_total, "contribution": contribution, "contribution_margin": contribution / R,
        "fixed_costs": fixed_total, "operating_profit": op, "operating_margin": op / R,
        "income_tax": tax, "net_profit": net, "net_margin": net / R,
    }

    # 5. BEP dan target (per total unit dengan sales mix tetap)
    ucm = avg_p - avg_c - var_slope
    c.step("kontribusi per unit rata-rata (UCM)", ucm)

    def profit_at(units: Decimal) -> Decimal:
        f, v, _, _ = evaluate_all(units)
        return avg_p * units - avg_c * units - v - f

    def net_at(units: Decimal) -> Decimal:
        p = profit_at(units)
        if regime is TaxRegime.PROFIT_BASED:
            return p - max(ZERO, p) * t_rate
        if regime is TaxRegime.TURNOVER_FINAL:
            return p - max(ZERO, avg_p * units - exempt) * t_rate
        return p

    limit_candidates = [U * 10]
    for it in prepared:
        if Behavior(it.spec.behavior) is Behavior.STEP_FIXED and it.spec.step_mode == "TABLE":
            s = _driver_slope(it, avg_p)
            if s > 0:
                limit_candidates.append(it.tiers[-1][1] * it.k / s * 2)
    limit = max(limit_candidates)
    bps = _breakpoints(prepared, avg_p, limit)
    segments = []
    start = ZERO
    for bp in bps:
        end = floor_int(bp)
        if end >= start:
            segments.append((start, end))
        start = end + 1
    segments.append((start, ceil_int(limit)))

    def solve(predicate_offset: Decimal, net: bool) -> Decimal | None:
        """Volume terkecil dengan laba (operasional/bersih) ≥ offset."""
        if ucm <= 0:
            return None
        for s, e in segments:
            fn = net_at if net else profit_at
            # biaya tetap efektif di segmen dihitung di titik akhir segmen
            f_seg = ucm * e - profit_at(e)
            cands = [max(s, ceil_int((f_seg + predicate_offset) / ucm))]
            if net and regime is not TaxRegime.NONE:
                rate_slope = ucm * (ONE - t_rate) if regime is TaxRegime.PROFIT_BASED else ucm - t_rate * avg_p
                if rate_slope > 0:
                    base = (f_seg * (ONE - t_rate) + predicate_offset) if regime is TaxRegime.PROFIT_BASED else (f_seg + predicate_offset - t_rate * exempt)
                    cands.append(max(s, ceil_int(base / rate_slope)))
            for q in sorted(set(cands)):
                if q <= e and fn(q) >= predicate_offset:
                    return q
                if q <= e:
                    # pembulatan/klem: maju beberapa unit untuk memastikan
                    for extra in range(1, 4):
                        if q + extra <= e and fn(q + extra) >= predicate_offset:
                            return q + extra
        return None

    bep_units = solve(ZERO, net=False)
    profitable_ranges = []
    if ucm > 0:
        for s, e in segments:
            f_seg = ucm * e - profit_at(e)
            q = max(s, ceil_int(f_seg / ucm))
            if q <= e:
                if profitable_ranges and q <= profitable_ranges[-1][1] + 1:
                    profitable_ranges[-1][1] = e
                else:
                    profitable_ranges.append([q, e])
    if ucm <= 0:
        bep_status = Status.NO_BREAK_EVEN
        c.warn(Status.NO_BREAK_EVEN, "kontribusi per unit ≤ 0: harga tidak menutup biaya variabel")
    elif bep_units is None:
        bep_status = Status.NO_BREAK_EVEN_WITHIN_CAPACITY
        c.warn(Status.NO_BREAK_EVEN_WITHIN_CAPACITY, "tidak ada titik impas dalam rentang volume yang dimodelkan")
    else:
        bep_status = Status.OK
    break_even = {
        "status": bep_status.value,
        "units": bep_units,
        "revenue": bep_units * avg_p if bep_units is not None else None,
        "margin_of_safety": (R - bep_units * avg_p) / R if bep_units is not None else None,
        "average_price": avg_p,
        "average_unit_cost": avg_c,
        "unit_contribution": ucm,
        "profitable_ranges": [tuple(r) for r in profitable_ranges],
        "modeled_up_to_units": ceil_int(limit),
        "assumption": "sales mix tetap; HPP per unit dan tarif variabel konstan",
    }
    if bep_units is not None:
        c.step("BEP (unit)", bep_units)

    target = None
    if target_kind is not None:
        if target_amount is None:
            raise invalid("target_amount wajib bila target_kind diisi")
        kind = TargetKind(target_kind)
        amount = dec(target_amount, "target_amount")
        q = solve(amount, net=kind is TargetKind.NET_PROFIT)
        over_capacity = []
        if q is not None:
            _, _, _, at_q = evaluate_all(q)
            over_capacity = [it.spec.code for it, res in at_q if res.detail.get("capacity_exceeded")]
            if over_capacity:
                c.warn(Status.CAPACITY_EXCEEDED, f"target membutuhkan {q} unit, melebihi kapasitas: {', '.join(over_capacity)}")
        target = {
            "kind": kind.value,
            "amount": amount,
            "status": "OK" if q is not None else ("NO_BREAK_EVEN" if ucm <= 0 else "NOT_REACHABLE_WITHIN_MODEL"),
            "units": q,
            "revenue": q * avg_p if q is not None else None,
            "change_vs_plan": (q - U) / U if q is not None else None,
            "achieved": (net if kind is TargetKind.NET_PROFIT else op) >= amount,
            "capacity_exceeded_items": over_capacity,
        }
        if q is not None:
            c.step(f"volume untuk target {kind.value} {amount}", q)

    # 6. Biaya per item
    cost_rows = [_row(it.spec, res, it) for it, res in evaluated]
    by_category: dict[str, Decimal] = {}
    for row in cost_rows:
        by_category[row["category"]] = by_category.get(row["category"], ZERO) + row["total"]

    # 7. Profitabilitas produk
    attributed_var = {l["product"]: ZERO for l in plan_lines}
    unattributed_var = ZERO
    for it, res in evaluated:
        beh = Behavior(it.spec.behavior)
        if beh is Behavior.PERCENTAGE:
            for l in plan_lines:
                b = l["revenue"] if it.spec.percentage_base == "REVENUE" else l["cogs"]
                attributed_var[l["product"]] += it.pct * b * it.var_mult
        elif beh in (Behavior.VARIABLE, Behavior.SEMI_VARIABLE):
            dt = DriverType(it.spec.driver_type)
            if dt in VOLUME_DRIVERS:
                for l in plan_lines:
                    attributed_var[l["product"]] += it.rate * l["volume"] * it.var_mult
            elif dt is DriverType.REVENUE:
                for l in plan_lines:
                    attributed_var[l["product"]] += it.rate * l["revenue"] * it.var_mult
            else:
                unattributed_var += res.variable
    product_rows = {}
    for l in plan_lines:
        contrib = l["revenue"] - l["cogs"] - attributed_var[l["product"]]
        product_rows[l["product"]] = {
            **l,
            "variable_costs": attributed_var[l["product"]],
            "contribution": contrib,
            "contribution_margin": contrib / l["revenue"] if l["revenue"] > 0 else None,
            "allocated_costs": ZERO,
        }

    quantum = currency_quantum(currency)
    allocations = []
    pool_totals = {it.spec.code: res.fixed + res.variable for it, res in evaluated if Scope(it.spec.scope) is Scope.ALLOCATION_POOL}
    allocated_codes = set()
    for rule in allocation_rules:
        if rule.cost_code not in pool_totals:
            c.note(f"aturan alokasi {rule.cost_code} diabaikan: bukan pool alokasi aktif")
            continue
        amount = pool_totals[rule.cost_code]
        basis = AllocationBasis(rule.basis)
        if basis in (AllocationBasis.EQUAL, AllocationBasis.REVENUE, AllocationBasis.UNITS):
            products = [p for p, _ in rule.targets] or [l["product"] for l in plan_lines]
            if basis is AllocationBasis.EQUAL:
                weights = {p: ONE for p in products}
            else:
                key = "revenue" if basis is AllocationBasis.REVENUE else "volume"
                weights = {p: product_rows[p][key] if p in product_rows else ZERO for p in products}
            total_w = sum(weights.values(), ZERO)
            if total_w == 0:
                raise invalid(f"alokasi {rule.cost_code}: total basis alokasi = 0")
            shares = {p: w / total_w for p, w in weights.items()}
        elif basis is AllocationBasis.PERCENTAGE:
            shares = {p: non_negative(v, f"{rule.cost_code}.{p}") for p, v in rule.targets}
            s = sum(shares.values(), ZERO)
            if s > 1 or (s < 1 and not rule.allow_unallocated):
                raise invalid(f"alokasi {rule.cost_code}: total persentase = {s}, harus 100%")
        else:
            drivers = {p: non_negative(v, f"{rule.cost_code}.{p}") for p, v in rule.targets}
            total_d = sum(drivers.values(), ZERO)
            if total_d == 0:
                raise invalid(f"alokasi {rule.cost_code}: total nilai driver = 0")
            shares = {p: d / total_d for p, d in drivers.items()}
        share_sum = sum(shares.values(), ZERO)
        pool_q = (amount * share_sum).quantize(quantum)
        split = largest_remainder(pool_q, {p: s / share_sum for p, s in shares.items()}, quantum) if share_sum > 0 else {}
        for p, v in split.items():
            if p in product_rows:
                product_rows[p]["allocated_costs"] += v
        allocations.append({"cost_code": rule.cost_code, "basis": basis.value, "amount": amount, "allocated": split,
                            "unallocated": amount - sum(split.values(), ZERO)})
        allocated_codes.add(rule.cost_code)
    for row in product_rows.values():
        row["profit_after_allocation"] = row["contribution"] - row["allocated_costs"]
    # Biaya level perusahaan = semua biaya operasional yang tidak masuk ke produk mana pun.
    # Σ(laba produk setelah alokasi) − biaya level perusahaan = laba operasional.
    company_level = (
        fixed_total
        + var_total
        - sum((r["variable_costs"] for r in product_rows.values()), ZERO)
        - sum((r["allocated_costs"] for r in product_rows.values()), ZERO)
    )
    for code in pool_totals:
        if code not in allocated_codes:
            c.note(f"pool {code} belum punya aturan alokasi; tetap dihitung sebagai biaya perusahaan")

    return {
        "period_months": period_months,
        "as_of_date": as_of_date,
        "pnl": pnl,
        "units": U,
        "lines": list(product_rows.values()),
        "costs": cost_rows,
        "costs_by_category": by_category,
        "excluded_product_scope": excluded,
        "break_even": break_even,
        "target": target,
        "allocations": allocations,
        "unattributed_variable_costs": unattributed_var,
        "company_level_costs": company_level,
        "adjustments": {
            "price_change": p_chg, "volume_change": v_chg, "unit_cost_change": u_chg,
            "variable_cost_change": dec(adj.variable_cost_change), "fixed_cost_change": dec(adj.fixed_cost_change),
        },
    }


__all__ = [
    "AllocationBasis",
    "AllocationRuleSpec",
    "Adjustments",
    "Behavior",
    "CostItemSpec",
    "DriverType",
    "EngineError",
    "SalesLine",
    "Scope",
    "TargetKind",
    "TaxRegime",
    "Tier",
    "positive",
    "preview_costs",
    "profit_plan",
]
