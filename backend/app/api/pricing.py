"""Pricing (MOD-005): kalkulator stateless dan rekomendasi harga tersimpan."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pricing_engine import pricing as eng
from pricing_engine.core import canonical, minor_units
from pricing_engine.rounding import RoundingMode, round_price
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, OrgContext, require
from app.api.products import get_product
from app.core.errors import ApiError, not_found
from app.models import CostingVersion, Organization, PricingRecommendation
from app.schemas import (
    Envelope,
    PricingInput,
    RecommendationDetail,
    RecommendationOut,
    RecommendIn,
    ok,
)
from app.services import audit
from app.services.engine import require_ok, to_numeric, warnings_json

router = APIRouter(prefix="/pricing", tags=["pricing"])

Calculate = Annotated[OrgContext, Depends(require("pricing.calculate"))]
Recommend = Annotated[OrgContext, Depends(require("pricing.recommend"))]
Read = Annotated[OrgContext, Depends(require("pricing.read"))]


def _active_costing(db: Session, ctx: OrgContext, product_id: uuid.UUID) -> CostingVersion:
    get_product(db, ctx, product_id)
    version = db.scalar(
        select(CostingVersion).where(CostingVersion.product_id == product_id, CostingVersion.status == "ACTIVE")
    )
    if version is None:
        raise ApiError(422, "INVALID_INPUT", "Produk belum memiliki costing aktif; jalankan costing terlebih dahulu")
    return version


def _run(db: Session, ctx: OrgContext, body: PricingInput) -> dict[str, Any]:
    costing = None
    if body.product_id is not None:
        costing = _active_costing(db, ctx, body.product_id)
        if body.unit_cost is not None and body.unit_cost != costing.calculated_unit_cost:
            raise ApiError(422, "VALIDATION_ERROR", "Kirim product_id atau unit_cost, bukan keduanya dengan nilai berbeda")
        unit_cost = costing.calculated_unit_cost
    elif body.unit_cost is not None:
        unit_cost = body.unit_cost
    else:
        raise ApiError(422, "VALIDATION_ERROR", "product_id atau unit_cost wajib diisi")

    currency = body.currency or (costing.currency if costing else None) or db.scalar(
        select(Organization.default_currency).where(Organization.id == ctx.org_id)
    )
    kwargs = dict(
        method=eng.PricingMethod(body.method),
        unit_cost=unit_cost,
        variable_cost=body.variable_cost,
        discount=body.discount,
        fees=[eng.PercentageFee(f.name, f.rate, eng.PriceBase(f.base)) for f in body.fees],
        turnover_tax_load=body.turnover_tax_load,
        vat_effective_rate=body.vat_effective_rate,
        target_margin=body.target_margin,
        markup=body.markup,
        fixed_cost=body.fixed_cost,
        volume=body.volume,
        target_operating_profit=body.target_operating_profit,
        reference_price=body.reference_price,
        adjustment=body.adjustment,
    )
    price = require_ok(eng.calculate_price(**kwargs))
    net_target: Decimal = price["net_price"]
    list_target: Decimal = price["list_price"]
    one_minus_d = Decimal(1) - body.discount

    rounding = None
    if body.rounding is not None:
        r = body.rounding
        on_list = r.apply_to == "LIST_PRICE"
        min_price = price["minimum_price"]
        rounding = require_ok(
            round_price(
                target_price=list_target if on_list else net_target,
                increment=r.increment,
                mode=RoundingMode(r.mode),
                margin_guard=r.margin_guard,
                minimum_price=(min_price / one_minus_d if on_list else min_price) if min_price is not None else None,
            )
        )
        if on_list:
            list_final = rounding["recommended_price"]
            net_final = list_final * one_minus_d
        else:
            net_final = rounding["recommended_price"]
            list_final = net_final / one_minus_d
    else:
        net_final, list_final = net_target, list_target

    # Evaluasi ulang pada harga final agar margin yang dilaporkan sesuai harga yang dipublikasikan.
    final = require_ok(
        eng.evaluate_price(
            list_price=list_final,
            discount=body.discount,
            unit_cost=unit_cost,
            variable_cost=body.variable_cost,
            fees=kwargs["fees"],
            turnover_tax_load=body.turnover_tax_load,
            vat_effective_rate=body.vat_effective_rate,
            target_margin=body.target_margin,
            margin_definition=eng.MarginDefinition.GROSS
            if body.method == "TARGET_GROSS_MARGIN"
            else eng.MarginDefinition.CONTRIBUTION,
        )
    )
    return {
        "costing": costing,
        "unit_cost": unit_cost,
        "currency": currency,
        "kwargs": kwargs,
        "price": price,
        "rounding": rounding,
        "final": final,
        "net_final": net_final,
        "list_final": list_final,
    }


def _summary(run: dict[str, Any]) -> dict[str, Any]:
    price, final, rounding = run["price"], run["final"], run["rounding"]
    places = minor_units(run["currency"])
    warnings = {w["code"]: w for w in warnings_json(price) + warnings_json(final)}
    return canonical(
        {
            "currency": run["currency"],
            "unit_cost": run["unit_cost"],
            "costing_version_id": run["costing"].id if run["costing"] else None,
            "minimum_price": price["minimum_price"],
            "target_price": price["net_price"],
            "recommended_price": to_numeric(run["net_final"], places),
            "list_price": to_numeric(run["list_final"], places),
            "gross_margin": final["gross_margin"],
            "contribution_margin": final["contribution_margin"],
            "fee_total": final["fee_total"],
            "contribution": final["contribution"],
            "warnings": list(warnings.values()),
            "engine": {
                "price": price.to_dict(),
                "rounding": rounding.to_dict() if rounding else None,
                "final": final.to_dict(),
            },
        }
    )


@router.post("/calculate", response_model=Envelope[dict[str, Any]])
def calculate(body: PricingInput, ctx: Calculate, db: DB) -> Envelope:
    """Kalkulator harga: tidak menyimpan apa pun."""
    return ok(_summary(_run(db, ctx, body)))


@router.post("/recommend", response_model=Envelope[RecommendationDetail], status_code=201)
def recommend(body: RecommendIn, ctx: Recommend, db: DB) -> Envelope:
    run = _run(db, ctx, body)
    summary = _summary(run)
    price, final = run["price"], run["final"]
    rec = PricingRecommendation(
        organization_id=ctx.org_id,
        product_id=body.product_id,
        costing_version_id=run["costing"].id,
        pricing_method=body.method,
        margin_definition="GROSS" if body.method == "TARGET_GROSS_MARGIN" else "CONTRIBUTION",
        minimum_price=to_numeric(price["minimum_price"], 4) if price["minimum_price"] is not None else None,
        target_price=to_numeric(price["net_price"], 4),
        recommended_price=to_numeric(run["net_final"], minor_units(run["currency"])),
        list_price=to_numeric(run["list_final"], minor_units(run["currency"])),
        expected_gross_margin=to_numeric(final["gross_margin"], 6),
        expected_contribution_margin=to_numeric(final["contribution_margin"], 6),
        currency=run["currency"],
        effective_date=body.effective_date,
        warnings=summary["warnings"],
        engine_version=price.engine_version,
        input_snapshot={"request": body.model_dump(mode="json"), "engine_inputs": canonical(run["kwargs"]),
                        "costing_version_id": str(run["costing"].id)},
        calculation_snapshot=summary,
        input_hash=price.input_hash,
        status="DRAFT",
        created_by=ctx.user_id,
    )
    db.add(rec)
    db.flush()
    db.refresh(rec)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="RECOMMEND", entity_type="pricing_recommendation",
                 entity_id=rec.id, new={"product_id": rec.product_id, "recommended_price": rec.recommended_price,
                                        "list_price": rec.list_price, "method": rec.pricing_method})
    out = RecommendationDetail.model_validate(rec)
    db.commit()
    return ok(out)


@router.get("/recommendations", response_model=Envelope[list[RecommendationOut]])
def list_recommendations(
    ctx: Read,
    db: DB,
    product_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Envelope:
    stmt = select(PricingRecommendation).where(PricingRecommendation.organization_id == ctx.org_id)
    if product_id:
        stmt = stmt.where(PricingRecommendation.product_id == product_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(PricingRecommendation.created_at.desc()).limit(limit).offset(offset)).all()
    return ok([_with_unit_cost(RecommendationOut, r) for r in rows], total=total, limit=limit, offset=offset)


def _with_unit_cost(schema: type[RecommendationOut], rec: PricingRecommendation) -> RecommendationOut:
    out = schema.model_validate(rec)
    raw = (rec.calculation_snapshot or {}).get("unit_cost")
    out.unit_cost = Decimal(raw) if raw is not None else None
    return out


@router.get("/recommendations/{rec_id}", response_model=Envelope[RecommendationDetail])
def read_recommendation(rec_id: uuid.UUID, ctx: Read, db: DB) -> Envelope:
    rec = db.get(PricingRecommendation, rec_id)
    if rec is None or rec.organization_id != ctx.org_id:
        raise not_found("Rekomendasi harga")
    return ok(_with_unit_cost(RecommendationDetail, rec))
