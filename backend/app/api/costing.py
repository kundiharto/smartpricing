"""Product costing (MOD-004): hasil engine disimpan sebagai versi immutable."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pricing_engine import ENGINE_VERSION
from pricing_engine import costing as eng
from pricing_engine.core import canonical, input_hash
from sqlalchemy import func, select

from app.api.deps import DB, OrgContext, require
from app.api.products import get_product
from app.core.errors import ApiError, not_found
from app.models import BillOfMaterials, BomItem, CostingVersion, MaterialPrice, Organization, Product
from app.schemas import CostingRun, CostingVersionDetail, CostingVersionOut, Envelope, ok
from app.services import audit
from app.services.engine import require_ok, to_numeric

router = APIRouter(tags=["costing"])

Read = Annotated[OrgContext, Depends(require("costing.read"))]
Write = Annotated[OrgContext, Depends(require("costing.write"))]


def _bom_inputs(db: DB, product: Product, body: CostingRun) -> tuple[dict[str, Any], dict[str, Any], uuid.UUID]:
    bom = db.scalar(
        select(BillOfMaterials).where(BillOfMaterials.product_id == product.id, BillOfMaterials.status == "ACTIVE")
    )
    if bom is None:
        raise ApiError(422, "INVALID_INPUT", "Produk belum memiliki BOM aktif")
    items = db.scalars(select(BomItem).where(BomItem.bom_id == bom.id).order_by(BomItem.line_no)).all()
    material_ids = [i.material_product_id for i in items]
    names = dict(db.execute(select(Product.id, Product.sku).where(Product.id.in_(material_ids))).all())
    price_rows = db.scalars(select(MaterialPrice).where(MaterialPrice.material_product_id.in_(material_ids))).all()
    engine_prices = [
        eng.MaterialPrice(
            material=str(p.material_product_id),
            unit_price=p.unit_price,
            effective_from=p.effective_from,
            effective_to=p.effective_to,
            data_nature=eng.DataNature(p.data_nature),
            currency=p.currency,
            source_reference=p.source_reference or "",
        )
        for p in price_rows
    ]

    lines: list[eng.MaterialLine] = []
    resolved: list[dict[str, Any]] = []
    for item in items:
        r = eng.resolve_material_price(
            prices=engine_prices,
            material=str(item.material_product_id),
            as_of_date=body.as_of_date,
            data_nature=eng.DataNature(body.data_nature),
        )
        if not r.ok:
            raise ApiError(
                422, "INVALID_INPUT",
                f"Harga material {names.get(item.material_product_id, item.material_product_id)} "
                f"({body.data_nature}) tidak tersedia pada {body.as_of_date.isoformat()}",
            )
        lines.append(
            eng.MaterialLine(
                material=names.get(item.material_product_id, str(item.material_product_id)),
                net_quantity=item.net_quantity,
                unit_price=r["unit_price"],
                waste_rate=item.material_waste_rate,
            )
        )
        resolved.append({"material_product_id": item.material_product_id, "sku": names.get(item.material_product_id),
                         "unit_price": r["unit_price"], "currency": r["currency"], "effective_from": r["effective_from"]})

    kwargs = dict(
        planned_output=bom.planned_output_qty,
        materials=lines,
        labor=[eng.ResourceUsage(x.name, x.hours, x.hourly_rate) for x in body.labor],
        machines=[eng.ResourceUsage(x.name, x.hours, x.hourly_rate) for x in body.machines],
        overhead=body.overhead,
        packaging=body.packaging,
        other_direct=body.other_direct,
        process_yield=bom.process_yield_rate,
        scrap_rate=body.scrap_rate,
        rework_rate=body.rework_rate,
        rework_cost_per_unit=body.rework_cost_per_unit,
    )
    context = {"bom_id": bom.id, "bom_version": bom.version_number, "material_prices": resolved}
    return kwargs, context, bom.id


@router.get("/products/{product_id}/costing", response_model=Envelope[list[CostingVersionOut]])
def list_costing(product_id: uuid.UUID, ctx: Read, db: DB) -> Envelope:
    get_product(db, ctx, product_id)
    rows = db.scalars(
        select(CostingVersion).where(CostingVersion.product_id == product_id).order_by(CostingVersion.version_number.desc())
    ).all()
    return ok([CostingVersionOut.model_validate(r) for r in rows], total=len(rows))


@router.get("/products/{product_id}/costing/{version_id}", response_model=Envelope[CostingVersionDetail])
def read_costing(product_id: uuid.UUID, version_id: uuid.UUID, ctx: Read, db: DB) -> Envelope:
    row = db.scalar(select(CostingVersion).where(CostingVersion.id == version_id, CostingVersion.product_id == product_id))
    if row is None:
        raise not_found("Costing version")
    return ok(CostingVersionDetail.model_validate(row))


@router.post("/products/{product_id}/costing", response_model=Envelope[CostingVersionDetail], status_code=201)
def run_costing(product_id: uuid.UUID, body: CostingRun, ctx: Write, db: DB) -> Envelope:
    product = get_product(db, ctx, product_id)
    if product.status == "ARCHIVED":
        raise ApiError(409, "CONFLICT", "Produk diarsipkan")
    currency = db.scalar(select(Organization.default_currency).where(Organization.id == ctx.org_id))
    bom_id = None
    context: dict[str, Any] = {}

    if body.costing_structure == "BOM_BASED":
        kwargs, context, bom_id = _bom_inputs(db, product, body)
        result = require_ok(eng.manufacturing_unit_cost(**kwargs))
        unit_cost = result["unit_cost"]
    elif body.costing_structure == "LANDED_COST":
        if body.landed is None:
            raise ApiError(422, "VALIDATION_ERROR", "LANDED_COST memerlukan field 'landed'")
        kwargs = body.landed.model_dump()
        result = require_ok(eng.landed_cost(**kwargs))
        unit_cost = result["landed_cost_per_unit"]
    else:
        if body.unit_cost is None or not (body.justification and body.justification.strip()):
            raise ApiError(422, "VALIDATION_ERROR", "DIRECT_INPUT memerlukan unit_cost dan justification")
        kwargs = {"unit_cost": body.unit_cost, "justification": body.justification}
        result = None
        unit_cost = body.unit_cost

    current = db.scalar(
        select(CostingVersion)
        .where(CostingVersion.product_id == product_id, CostingVersion.status == "ACTIVE")
        .with_for_update()
    )
    effective_from = body.effective_from or body.as_of_date
    if body.activate and current is not None:
        current.status = "SUPERSEDED"
        current.effective_to = effective_from
        db.flush()
    version_number = (db.scalar(select(func.max(CostingVersion.version_number)).where(CostingVersion.product_id == product_id)) or 0) + 1

    input_snapshot = {
        "calculation": result.calculation if result else "direct_input",
        "inputs": canonical(kwargs),
        "context": canonical(context),
        "request": body.model_dump(mode="json"),
    }
    version = CostingVersion(
        organization_id=ctx.org_id,
        product_id=product_id,
        version_number=version_number,
        costing_method=body.costing_method,
        costing_structure=body.costing_structure,
        data_nature=body.data_nature,
        bom_id=bom_id,
        scrap_rate=body.scrap_rate,
        rework_rate=body.rework_rate,
        rework_cost_per_unit=body.rework_cost_per_unit,
        calculated_unit_cost=to_numeric(unit_cost, 4),
        currency=currency,
        as_of_date=body.as_of_date,
        effective_from=effective_from,
        status="ACTIVE" if body.activate else "DRAFT",
        engine_version=result.engine_version if result else ENGINE_VERSION,
        input_snapshot=input_snapshot,
        calculation_snapshot=result.to_dict() if result else {"unit_cost": canonical(unit_cost)},
        input_hash=result.input_hash if result else input_hash("direct_input", kwargs),
        created_by=ctx.user_id,
    )
    db.add(version)
    db.flush()
    db.refresh(version)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="CALCULATE", entity_type="costing_version",
                 entity_id=version.id, new={"version_number": version_number, "unit_cost": version.calculated_unit_cost,
                                            "structure": body.costing_structure, "status": version.status,
                                            "superseded_id": current.id if (current and body.activate) else None})
    out = CostingVersionDetail.model_validate(version)
    db.commit()
    return ok(out)
