"""Pajak berbasis konfigurasi (CALCULATION_SPEC.md §8).

Engine tidak menanamkan tarif. Semua tarif dan faktor DPP datang dari input
(`TaxRule` yang berasal dari tabel `tax_rules`).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Sequence

from .core import ONE, ZERO, Calc, Status, calculation, dec, fraction, invalid, non_negative, opt_dec, positive


class DppMethod(enum.StrEnum):
    FULL = "FULL"
    OTHER_VALUE = "OTHER_VALUE"
    SPECIFIC_AMOUNT = "SPECIFIC_AMOUNT"


class IncomeTaxRegime(enum.StrEnum):
    PROFIT_BASED = "PROFIT_BASED"
    TURNOVER_FINAL = "TURNOVER_FINAL"


class TaxCategory(enum.StrEnum):
    TAX_EXPENSE = "TAX_EXPENSE"
    TAX_PAYABLE = "TAX_PAYABLE"
    TAX_CREDIT = "TAX_CREDIT"
    WITHHELD_BY_OTHERS = "WITHHELD_BY_OTHERS"
    PASS_THROUGH = "PASS_THROUGH"  # PPN keluaran/masukan


# Apakah kategori masuk laba rugi (§8.4)
AFFECTS_PROFIT_AND_LOSS: dict[TaxCategory, bool] = {
    TaxCategory.TAX_EXPENSE: True,
    TaxCategory.TAX_PAYABLE: False,
    TaxCategory.TAX_CREDIT: False,
    TaxCategory.WITHHELD_BY_OTHERS: False,
    TaxCategory.PASS_THROUGH: False,
}


@dataclass(frozen=True)
class DppFactor:
    """Faktor DPP sebagai pecahan eksak, mis. 11/12."""

    numerator: Any
    denominator: Any


@dataclass(frozen=True)
class TaxRule:
    code: str
    tax_type: str  # VAT, INCOME_TAX, WITHHOLDING, ...
    nominal_rate: Any
    effective_from: date
    effective_to: date | None = None  # eksklusif
    dpp_method: DppMethod = DppMethod.FULL
    dpp_factor: DppFactor | None = None
    legal_reference: str = ""


def _dpp_parts(dpp_method: DppMethod, dpp_factor: DppFactor | None) -> tuple[Decimal, Decimal]:
    method = DppMethod(dpp_method)
    if method is DppMethod.FULL:
        return ONE, ONE
    if method is DppMethod.OTHER_VALUE:
        if dpp_factor is None:
            raise invalid("dpp_method OTHER_VALUE memerlukan dpp_factor")
        num = positive(dpp_factor.numerator, "dpp_factor.numerator")
        den = positive(dpp_factor.denominator, "dpp_factor.denominator")
        return num, den
    raise invalid("dpp_method SPECIFIC_AMOUNT belum didukung di engine v1.0")


@calculation
def vat_exclusive(
    c: Calc,
    *,
    net_price: Any,
    nominal_rate: Any,
    dpp_method: DppMethod = DppMethod.FULL,
    dpp_factor: DppFactor | None = None,
) -> dict[str, Any]:
    """Harga belum termasuk PPN → hitung DPP, PPN, dan harga termasuk PPN."""
    N = non_negative(net_price, "net_price")
    rate = fraction(nominal_rate, "nominal_rate")
    num, den = _dpp_parts(dpp_method, dpp_factor)
    dpp = c.step("DPP = N × faktor DPP", N * num / den)
    vat = c.step("PPN = N × tarif × faktor DPP", N * rate * num / den)
    gross = c.step("G = N + PPN", N + vat)
    return {
        "net_price": N,
        "dpp": dpp,
        "vat": vat,
        "gross_price": gross,
        "effective_rate": rate * num / den,
    }


@calculation
def vat_inclusive(
    c: Calc,
    *,
    gross_price: Any,
    nominal_rate: Any,
    dpp_method: DppMethod = DppMethod.FULL,
    dpp_factor: DppFactor | None = None,
) -> dict[str, Any]:
    """Harga sudah termasuk PPN → urai menjadi N dan PPN: N = G / (1 + tarif × faktor)."""
    G = non_negative(gross_price, "gross_price")
    rate = fraction(nominal_rate, "nominal_rate")
    num, den = _dpp_parts(dpp_method, dpp_factor)
    net = c.step("N = G × den / (den + tarif × num)", G * den / (den + rate * num))
    vat = c.step("PPN = G − N", G - net)
    return {
        "net_price": net,
        "dpp": net * num / den,
        "vat": vat,
        "gross_price": G,
        "effective_rate": rate * num / den,
    }


@calculation
def select_tax_rule(
    c: Calc,
    *,
    rules: Sequence[TaxRule],
    tax_type: str,
    as_of_date: date,
) -> dict[str, Any]:
    """Memilih aturan pajak yang berlaku pada `as_of_date`."""
    matches = [
        r
        for r in rules
        if r.tax_type == tax_type
        and r.effective_from <= as_of_date
        and (r.effective_to is None or as_of_date < r.effective_to)
    ]
    if not matches:
        raise invalid(f"tidak ada aturan {tax_type} yang berlaku pada {as_of_date.isoformat()}")
    if len(matches) > 1:
        codes = ", ".join(r.code for r in matches)
        raise invalid(f"lebih dari satu aturan {tax_type} berlaku pada {as_of_date.isoformat()}: {codes}")
    rule = matches[0]
    c.note(f"aturan dipakai: {rule.code} ({rule.legal_reference or 'tanpa referensi'})")
    return {"rule": rule}


@calculation
def income_tax(
    c: Calc,
    *,
    regime: IncomeTaxRegime,
    rate: Any,
    profit_before_tax: Any = None,
    gross_turnover: Any = None,
    exempt_turnover: Any = 0,
    max_turnover_threshold: Any = None,
) -> dict[str, Any]:
    """PPh berbasis laba atau berbasis omzet (§8.3). Kelayakan rezim tidak diputuskan engine."""
    regime = IncomeTaxRegime(regime)
    r = fraction(rate, "rate")
    if regime is IncomeTaxRegime.PROFIT_BASED:
        if profit_before_tax is None:
            raise invalid("PROFIT_BASED memerlukan profit_before_tax")
        pbt = dec(profit_before_tax, "profit_before_tax")
        base = max(ZERO, pbt)
        tax = c.step("PPh = max(0, PBT) × tarif", base * r)
        return {"regime": regime.value, "tax_base": base, "income_tax": tax, "net_profit": pbt - tax}

    if gross_turnover is None:
        raise invalid("TURNOVER_FINAL memerlukan gross_turnover")
    turnover = non_negative(gross_turnover, "gross_turnover")
    exempt = non_negative(exempt_turnover, "exempt_turnover")
    threshold = opt_dec(max_turnover_threshold, "max_turnover_threshold")
    if threshold is not None and turnover > threshold:
        c.warn(
            Status.TAX_REGIME_THRESHOLD_EXCEEDED,
            f"omzet {turnover} melebihi ambang rezim {threshold}; periksa kelayakan rezim pajak",
        )
    base = c.step("omzet kena pajak = max(0, omzet − bagian dibebaskan)", max(ZERO, turnover - exempt))
    tax = c.step("PPh = omzet kena pajak × tarif", base * r)
    values: dict[str, Any] = {"regime": regime.value, "tax_base": base, "income_tax": tax}
    if profit_before_tax is not None:
        values["net_profit"] = dec(profit_before_tax, "profit_before_tax") - tax
    return values
