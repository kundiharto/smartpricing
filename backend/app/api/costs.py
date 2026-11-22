"""Cost management (MOD-003): driver, cost item berversi, alokasi, dan pratinjau biaya."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pricing_engine import planning as eng
from sqlalchemy import func, select

from app.api.deps import DB, OrgContext, require
from app.core.errors import ApiError, conflict, not_found
from app.models import (
    CostAllocationRule,
    CostAllocationTarget,
    CostDriver,
    CostItem,
    CostItemVersion,
    Product,
)
from app.schemas import Envelope, ok
from app.schemas.planning import (
    AllocationIn,
    AllocationOut,
    AllocationTargetIn,
    CostItemCreate,
    CostItemDetail,
    CostItemOut,
    CostItemUpdate,
    CostParams,
    CostPreviewIn,
    CostVersionOut,
    DriverCreate,
    DriverOut,
)
from app.services import audit
from app.services.cost_model import load_specs, to_spec, version_in_effect
from app.services.engine import require_ok

router = APIRouter(tags=["costs"])

Read = Annotated[OrgContext, Depends(require("costs.read"))]
Write = Annotated[OrgContext, Depends(require("costs.write"))]

ITEM_FIELDS = ["code", "name", "category", "behavior_type", "cost_scope", "driver_id", "period_months", "description", "status"]
VERSION_FIELDS = list(CostParams.model_fields)


# --- Driver ---------------------------------------------------------------------


@router.get("/cost-drivers", response_model=Envelope[list[DriverOut]])
def list_drivers(ctx: Read, db: DB) -> Envelope:
    rows = db.scalars(select(CostDriver).where(CostDriver.organization_id == ctx.org_id).order_by(CostDriver.code)).all()
    return ok([DriverOut.model_validate(r) for r in rows], total=len(rows))


@router.post("/cost-drivers", response_model=Envelope[DriverOut], status_code=201)
def create_driver(body: DriverCreate, ctx: Write, db: DB) -> Envelope:
    d = CostDriver(organization_id=ctx.org_id, **body.model_dump())
    db.add(d)
    db.flush()
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="CREATE", entity_type="cost_driver", entity_id=d.id, new=body.model_dump())
    out = DriverOut.model_validate(d)
    db.commit()
    return ok(out)


# --- Helpers ----------------------------------------------------------------------


def _item(db: DB, ctx: OrgContext, item_id: uuid.UUID) -> CostItem:
    item = db.scalar(select(CostItem).where(CostItem.id == item_id, CostItem.organization_id == ctx.org_id))
    if item is None:
        raise not_found("Biaya")
    return item


def _driver(db: DB, ctx: OrgContext, driver_id: uuid.UUID | None) -> CostDriver | None:
    if driver_id is None:
        return None
    d = db.scalar(select(CostDriver).where(CostDriver.id == driver_id, CostDriver.organization_id == ctx.org_id))
    if d is None:
        raise ApiError(422, "VALIDATION_ERROR", "Driver tidak ditemukan")
    return d


def _validate(item: CostItem, params: CostParams, driver: CostDriver | None) -> None:
    """Parameter divalidasi oleh engine yang sama yang nanti menghitungnya."""
    if item.behavior_type != "STEP_FIXED" and (params.tiers or params.step_mode):
        raise ApiError(422, "VALIDATION_ERROR", "Tier hanya untuk biaya bertingkat (STEP_FIXED)")
    spec = to_spec(item, params, driver)
    require_ok(eng.preview_costs(items=[spec], as_of_date=params.effective_from))


def _version_from_params(item: CostItem, params: CostParams, number: int, ctx: OrgContext) -> CostItemVersion:
    data = params.model_dump()
    data["tiers"] = [t.model_dump(mode="json") for t in params.tiers] if params.tiers else None
    return CostItemVersion(organization_id=ctx.org_id, cost_item_id=item.id, version_number=number, created_by=ctx.user_id, **data)


def _out(db: DB, item: CostItem, as_of=None, nature: str = "STANDARD") -> CostItemOut:
    out = CostItemOut.model_validate(item)
    if item.driver_id:
        d = db.get(CostDriver, item.driver_id)
        out.driver = DriverOut.model_validate(d) if d else None
    current = None
    if as_of is not None:
        current = version_in_effect(db, item.id, as_of, nature)
    if current is None:
        current = db.scalar(
            select(CostItemVersion).where(CostItemVersion.cost_item_id == item.id).order_by(CostItemVersion.version_number.desc()).limit(1)
        )
    out.current_version = CostVersionOut.model_validate(current) if current else None
    out.has_allocation = db.scalar(select(func.count()).select_from(CostAllocationRule).where(CostAllocationRule.cost_item_id == item.id)) > 0
    return out


def _allocation(db: DB, item_id: uuid.UUID) -> AllocationOut | None:
    rule = db.scalar(select(CostAllocationRule).where(CostAllocationRule.cost_item_id == item_id))
    if rule is None:
        return None
    targets = db.scalars(select(CostAllocationTarget).where(CostAllocationTarget.rule_id == rule.id)).all()
    return AllocationOut(
        basis=rule.basis,
        driver_label=rule.driver_label,
        allow_unallocated=rule.allow_unallocated,
        targets=[AllocationTargetIn(product_id=t.product_id, value=t.value) for t in targets],
    )


def _detail(db: DB, item: CostItem) -> CostItemDetail:
    base = _out(db, item)
    versions = db.scalars(
        select(CostItemVersion).where(CostItemVersion.cost_item_id == item.id).order_by(CostItemVersion.version_number.desc())
    ).all()
    return CostItemDetail(
        **base.model_dump(),
        versions=[CostVersionOut.model_validate(v) for v in versions],
        allocation=_allocation(db, item.id),
    )


# --- Cost items -------------------------------------------------------------------


@router.get("/costs", response_model=Envelope[list[CostItemOut]])
def list_costs(
    ctx: Read,
    db: DB,
    status: str | None = Query(default=None, pattern="^(ACTIVE|INACTIVE|ARCHIVED)$"),
    scope: str | None = Query(default=None, pattern="^(PRODUCT|PERIOD|ALLOCATION_POOL)$"),
) -> Envelope:
    stmt = select(CostItem).where(CostItem.organization_id == ctx.org_id)
    stmt = stmt.where(CostItem.status == status) if status else stmt.where(CostItem.status != "ARCHIVED")
    if scope:
        stmt = stmt.where(CostItem.cost_scope == scope)
    rows = db.scalars(stmt.order_by(CostItem.cost_scope, CostItem.code)).all()
    return ok([_out(db, r) for r in rows], total=len(rows))


@router.post("/costs", response_model=Envelope[CostItemDetail], status_code=201)
def create_cost(body: CostItemCreate, ctx: Write, db: DB) -> Envelope:
    driver = _driver(db, ctx, body.driver_id)
    if body.behavior_type not in ("FIXED", "PERCENTAGE") and driver is None:
        raise ApiError(422, "VALIDATION_ERROR", f"Perilaku {body.behavior_type} memerlukan driver biaya")
    item = CostItem(organization_id=ctx.org_id, created_by=ctx.user_id, **body.model_dump(exclude={"params"}))
    _validate(item, body.params, driver)
    db.add(item)
    db.flush()
    db.add(_version_from_params(item, body.params, 1, ctx))
    db.flush()
    db.refresh(item)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="CREATE", entity_type="cost_item", entity_id=item.id,
                 new={**audit.snapshot(item, ITEM_FIELDS), "params": body.params.model_dump()})
    out = _detail(db, item)
    db.commit()
    return ok(out)


@router.get("/costs/{item_id}", response_model=Envelope[CostItemDetail])
def read_cost(item_id: uuid.UUID, ctx: Read, db: DB) -> Envelope:
    return ok(_detail(db, _item(db, ctx, item_id)))


@router.patch("/costs/{item_id}", response_model=Envelope[CostItemDetail])
def update_cost(item_id: uuid.UUID, body: CostItemUpdate, ctx: Write, db: DB) -> Envelope:
    item = _item(db, ctx, item_id)
    if item.row_version != body.row_version:
        raise conflict("Data telah diubah oleh pengguna lain; muat ulang lalu coba lagi")
    old = audit.snapshot(item, ITEM_FIELDS)
    for k, v in body.model_dump(exclude_unset=True, exclude={"row_version"}).items():
        if v is not None:
            setattr(item, k, v)
    item.row_version += 1
    db.flush()
    db.refresh(item)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="UPDATE", entity_type="cost_item", entity_id=item.id,
                 old=old, new=audit.snapshot(item, ITEM_FIELDS))
    out = _detail(db, item)
    db.commit()
    return ok(out)


@router.delete("/costs/{item_id}", response_model=Envelope[CostItemDetail])
def archive_cost(item_id: uuid.UUID, ctx: Write, db: DB) -> Envelope:
    item = _item(db, ctx, item_id)
    if item.status != "ARCHIVED":
        old_status = item.status
        item.status = "ARCHIVED"
        item.row_version += 1
        db.flush()
        audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="ARCHIVE", entity_type="cost_item", entity_id=item.id,
                     old={"status": old_status}, new={"status": "ARCHIVED"})
    db.refresh(item)
    out = _detail(db, item)
    db.commit()
    return ok(out)


@router.post("/costs/{item_id}/versions", response_model=Envelope[CostItemDetail], status_code=201)
def add_version(item_id: uuid.UUID, body: CostParams, ctx: Write, db: DB) -> Envelope:
    """Parameter baru berlaku sejak tanggal tertentu; versi terbuka sebelumnya ditutup, tidak diubah."""
    item = _item(db, ctx, item_id)
    driver = _driver(db, ctx, item.driver_id)
    _validate(item, body, driver)
    open_row = db.scalar(
        select(CostItemVersion)
        .where(CostItemVersion.cost_item_id == item.id, CostItemVersion.data_nature == body.data_nature, CostItemVersion.effective_to.is_(None))
        .with_for_update()
    )
    if open_row is not None:
        if open_row.effective_from >= body.effective_from:
            raise conflict(f"Versi yang berlaku sejak {open_row.effective_from.isoformat()} sudah ada; tanggal baru harus setelahnya")
        open_row.effective_to = body.effective_from
        db.flush()
    number = (db.scalar(select(func.max(CostItemVersion.version_number)).where(CostItemVersion.cost_item_id == item.id)) or 0) + 1
    db.add(_version_from_params(item, body, number, ctx))
    item.row_version += 1
    db.flush()
    db.refresh(item)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="NEW_VERSION", entity_type="cost_item", entity_id=item.id,
                 new={"version_number": number, **body.model_dump()})
    out = _detail(db, item)
    db.commit()
    return ok(out)


@router.put("/costs/{item_id}/allocation", response_model=Envelope[CostItemDetail])
def set_allocation(item_id: uuid.UUID, body: AllocationIn, ctx: Write, db: DB) -> Envelope:
    item = _item(db, ctx, item_id)
    if item.cost_scope != "ALLOCATION_POOL":
        raise ApiError(422, "VALIDATION_ERROR", "Aturan alokasi hanya untuk biaya ber-scope pool alokasi")
    if body.basis in ("PERCENTAGE", "DRIVER"):
        if not body.targets or any(t.value is None for t in body.targets):
            raise ApiError(422, "VALIDATION_ERROR", "Metode ini memerlukan produk tujuan beserta nilainya")
        total = sum((t.value for t in body.targets), Decimal(0))
        if body.basis == "PERCENTAGE" and (total > 1 or (total < 1 and not body.allow_unallocated)):
            raise ApiError(422, "VALIDATION_ERROR", f"Total persentase = {total}; harus tepat 100%")
        if body.basis == "DRIVER" and total == 0:
            raise ApiError(422, "VALIDATION_ERROR", "Total nilai driver tidak boleh 0")
    if body.targets:
        ids = [t.product_id for t in body.targets]
        found = db.scalar(select(func.count()).select_from(Product).where(Product.id.in_(ids), Product.organization_id == ctx.org_id))
        if found != len(ids):
            raise ApiError(422, "VALIDATION_ERROR", "Produk tujuan alokasi tidak ditemukan")

    rule = db.scalar(select(CostAllocationRule).where(CostAllocationRule.cost_item_id == item.id).with_for_update())
    old = _allocation(db, item.id)
    if rule is None:
        rule = CostAllocationRule(organization_id=ctx.org_id, cost_item_id=item.id, basis=body.basis)
        db.add(rule)
    rule.basis = body.basis
    rule.driver_label = body.driver_label
    rule.allow_unallocated = body.allow_unallocated
    rule.updated_by = ctx.user_id
    db.flush()
    for t in db.scalars(select(CostAllocationTarget).where(CostAllocationTarget.rule_id == rule.id)).all():
        db.delete(t)
    db.flush()
    for t in body.targets:
        db.add(CostAllocationTarget(organization_id=ctx.org_id, rule_id=rule.id, product_id=t.product_id, value=t.value))
    db.flush()
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="SET_ALLOCATION", entity_type="cost_item", entity_id=item.id,
                 old=old.model_dump() if old else None, new=body.model_dump())
    db.refresh(item)
    out = _detail(db, item)
    db.commit()
    return ok(out)


@router.post("/costs/preview", response_model=Envelope[dict[str, Any]])
def preview(body: CostPreviewIn, ctx: Read, db: DB) -> Envelope:
    """Total biaya periode pada tingkat aktivitas tertentu (tidak menyimpan apa pun)."""
    specs, refs, missing = load_specs(db, ctx.org_id, body.as_of_date, body.data_nature)
    # Sama dengan simulasi skenario: biaya ber-scope PRODUCT sudah ada di HPP, tidak dihitung lagi.
    excluded = [sp.code for sp in specs if sp.scope == eng.Scope.PRODUCT]
    specs = [sp for sp in specs if sp.scope != eng.Scope.PRODUCT]
    result = require_ok(
        eng.preview_costs(
            items=specs,
            units=body.units,
            revenue=body.revenue,
            cogs=body.cogs,
            other_activity=dict(body.activity),
            period_months=body.period_months,
            as_of_date=body.as_of_date,
        )
    )
    data = result.to_dict()
    data["items_without_version"] = missing
    data["excluded_product_scope"] = excluded
    data["versions"] = refs
    return ok(data)
