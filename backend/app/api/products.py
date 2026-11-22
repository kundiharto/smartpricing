"""Satuan, kategori, produk, harga material, dan BOM (MOD-002)."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.api.deps import DB, OrgContext, require
from app.core.errors import ApiError, conflict, not_found
from app.models import BillOfMaterials, BomItem, MaterialPrice, Organization, Product, ProductCategory, UnitOfMeasure
from app.schemas import (
    BomCreate,
    BomItemOut,
    BomOut,
    CategoryCreate,
    CategoryOut,
    Envelope,
    MaterialPriceCreate,
    MaterialPriceOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    UnitCreate,
    UnitOut,
    ok,
)
from app.services import audit

router = APIRouter(tags=["products"])

Read = Annotated[OrgContext, Depends(require("products.read"))]
Write = Annotated[OrgContext, Depends(require("products.write"))]

PRODUCT_FIELDS = ["sku", "name", "product_type", "business_model", "pricing_model_type", "base_unit_id",
                  "category_id", "description", "status"]


def get_product(db: DB, ctx: OrgContext, product_id: uuid.UUID) -> Product:
    product = db.scalar(select(Product).where(Product.id == product_id, Product.organization_id == ctx.org_id))
    if product is None:
        raise not_found("Produk")
    return product


# --- Units & categories --------------------------------------------------------


@router.get("/units", response_model=Envelope[list[UnitOut]])
def list_units(ctx: Read, db: DB) -> Envelope:
    rows = db.scalars(select(UnitOfMeasure).order_by(UnitOfMeasure.code)).all()
    return ok([UnitOut.model_validate(r) for r in rows], total=len(rows))


@router.post("/units", response_model=Envelope[UnitOut], status_code=201)
def create_unit(body: UnitCreate, ctx: Write, db: DB) -> Envelope:
    unit = UnitOfMeasure(organization_id=ctx.org_id, **body.model_dump())
    db.add(unit)
    db.flush()
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="CREATE", entity_type="unit", entity_id=unit.id,
                 new=body.model_dump())
    out = UnitOut.model_validate(unit)
    db.commit()
    return ok(out)


@router.get("/product-categories", response_model=Envelope[list[CategoryOut]])
def list_categories(ctx: Read, db: DB) -> Envelope:
    rows = db.scalars(select(ProductCategory).order_by(ProductCategory.name)).all()
    return ok([CategoryOut.model_validate(r) for r in rows], total=len(rows))


@router.post("/product-categories", response_model=Envelope[CategoryOut], status_code=201)
def create_category(body: CategoryCreate, ctx: Write, db: DB) -> Envelope:
    cat = ProductCategory(organization_id=ctx.org_id, **body.model_dump())
    db.add(cat)
    db.flush()
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="CREATE", entity_type="product_category",
                 entity_id=cat.id, new=body.model_dump())
    out = CategoryOut.model_validate(cat)
    db.commit()
    return ok(out)


# --- Products --------------------------------------------------------------------


@router.get("/products", response_model=Envelope[list[ProductOut]])
def list_products(
    ctx: Read,
    db: DB,
    q: str | None = Query(default=None, max_length=100, description="Cari nama atau SKU"),
    status: Literal["ACTIVE", "INACTIVE", "ARCHIVED"] | None = None,
    product_type: Literal["FINISHED_GOOD", "MATERIAL", "TRADED_GOOD", "SERVICE"] | None = None,
    category_id: uuid.UUID | None = None,
    sort: Literal["name", "sku", "-created_at"] = "name",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Envelope:
    stmt = select(Product).where(Product.organization_id == ctx.org_id)
    if q:
        like = f"%{q.replace('%', r'\%').replace('_', r'\_')}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.sku.ilike(like)))
    if status:
        stmt = stmt.where(Product.status == status)
    else:
        stmt = stmt.where(Product.status != "ARCHIVED")
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = {"name": Product.name, "sku": Product.sku, "-created_at": Product.created_at.desc()}[sort]
    rows = db.scalars(stmt.order_by(order, Product.id).limit(limit).offset(offset)).all()
    return ok([ProductOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("/products", response_model=Envelope[ProductOut], status_code=201)
def create_product(body: ProductCreate, ctx: Write, db: DB) -> Envelope:
    product = Product(organization_id=ctx.org_id, created_by=ctx.user_id, **body.model_dump())
    db.add(product)
    db.flush()
    db.refresh(product)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="CREATE", entity_type="product",
                 entity_id=product.id, new=audit.snapshot(product, PRODUCT_FIELDS))
    out = ProductOut.model_validate(product)
    db.commit()
    return ok(out)


@router.get("/products/{product_id}", response_model=Envelope[ProductOut])
def read_product(product_id: uuid.UUID, ctx: Read, db: DB) -> Envelope:
    return ok(ProductOut.model_validate(get_product(db, ctx, product_id)))


@router.patch("/products/{product_id}", response_model=Envelope[ProductOut])
def update_product(product_id: uuid.UUID, body: ProductUpdate, ctx: Write, db: DB) -> Envelope:
    product = get_product(db, ctx, product_id)
    if product.row_version != body.row_version:
        raise conflict("Data telah diubah oleh pengguna lain; muat ulang lalu coba lagi")
    if product.status == "ARCHIVED":
        raise conflict("Produk yang diarsipkan tidak dapat diubah")
    old = audit.snapshot(product, PRODUCT_FIELDS)
    for field, value in body.model_dump(exclude_unset=True, exclude={"row_version"}).items():
        setattr(product, field, value)
    product.row_version += 1
    db.flush()
    db.refresh(product)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="UPDATE", entity_type="product",
                 entity_id=product.id, old=old, new=audit.snapshot(product, PRODUCT_FIELDS))
    out = ProductOut.model_validate(product)
    db.commit()
    return ok(out)


@router.delete("/products/{product_id}", response_model=Envelope[ProductOut])
def archive_product(product_id: uuid.UUID, ctx: Write, db: DB) -> Envelope:
    """Produk tidak dihapus: status menjadi ARCHIVED dan histori tetap utuh."""
    product = get_product(db, ctx, product_id)
    if product.status != "ARCHIVED":
        old_status = product.status
        product.status = "ARCHIVED"
        product.row_version += 1
        db.flush()
        db.refresh(product)
        audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="ARCHIVE", entity_type="product",
                     entity_id=product.id, old={"status": old_status}, new={"status": "ARCHIVED"})
    out = ProductOut.model_validate(product)
    db.commit()
    return ok(out)


# --- Material prices (effective-dated) -----------------------------------------------


@router.get("/products/{product_id}/material-prices", response_model=Envelope[list[MaterialPriceOut]])
def list_material_prices(product_id: uuid.UUID, ctx: Read, db: DB) -> Envelope:
    get_product(db, ctx, product_id)
    rows = db.scalars(
        select(MaterialPrice)
        .where(MaterialPrice.material_product_id == product_id)
        .order_by(MaterialPrice.data_nature, MaterialPrice.effective_from.desc())
    ).all()
    return ok([MaterialPriceOut.model_validate(r) for r in rows], total=len(rows))


@router.post("/products/{product_id}/material-prices", response_model=Envelope[MaterialPriceOut], status_code=201)
def add_material_price(product_id: uuid.UUID, body: MaterialPriceCreate, ctx: Write, db: DB) -> Envelope:
    """Harga baru menutup periode harga terbuka sebelumnya; baris lama tidak diubah nilainya."""
    product = get_product(db, ctx, product_id)
    if product.product_type != "MATERIAL":
        raise ApiError(422, "VALIDATION_ERROR", "Harga material hanya untuk produk bertipe MATERIAL")
    currency = body.currency or db.scalar(select(Organization.default_currency).where(Organization.id == ctx.org_id))
    open_row = db.scalar(
        select(MaterialPrice)
        .where(
            MaterialPrice.material_product_id == product_id,
            MaterialPrice.data_nature == body.data_nature,
            MaterialPrice.effective_to.is_(None),
        )
        .with_for_update()
    )
    if open_row is not None:
        if open_row.effective_from >= body.effective_from:
            raise conflict(
                f"Harga yang berlaku sejak {open_row.effective_from.isoformat()} sudah ada; "
                "tanggal berlaku baru harus setelahnya"
            )
        open_row.effective_to = body.effective_from
    price = MaterialPrice(
        organization_id=ctx.org_id,
        material_product_id=product_id,
        currency=currency,
        created_by=ctx.user_id,
        **body.model_dump(exclude={"currency"}),
    )
    db.add(price)
    db.flush()
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="CREATE", entity_type="material_price",
                 entity_id=price.id, new={**body.model_dump(exclude={"currency"}), "currency": currency,
                                          "closed_previous_id": open_row.id if open_row else None})
    out = MaterialPriceOut.model_validate(price)
    db.commit()
    return ok(out)


# --- BOM ---------------------------------------------------------------------------------


def _bom_out(db: DB, bom: BillOfMaterials) -> BomOut:
    out = BomOut.model_validate(bom)
    items = db.scalars(select(BomItem).where(BomItem.bom_id == bom.id).order_by(BomItem.line_no)).all()
    out.items = [BomItemOut.model_validate(i) for i in items]
    return out


@router.get("/products/{product_id}/bom", response_model=Envelope[list[BomOut]])
def list_boms(product_id: uuid.UUID, ctx: Read, db: DB) -> Envelope:
    get_product(db, ctx, product_id)
    boms = db.scalars(
        select(BillOfMaterials).where(BillOfMaterials.product_id == product_id).order_by(BillOfMaterials.version_number.desc())
    ).all()
    return ok([_bom_out(db, b) for b in boms], total=len(boms))


@router.post("/products/{product_id}/bom", response_model=Envelope[BomOut], status_code=201)
def create_bom(product_id: uuid.UUID, body: BomCreate, ctx: Write, db: DB) -> Envelope:
    """Membuat versi BOM baru (ACTIVE); versi aktif sebelumnya menjadi SUPERSEDED."""
    product = get_product(db, ctx, product_id)
    if product.product_type != "FINISHED_GOOD":
        raise ApiError(422, "VALIDATION_ERROR", "BOM hanya untuk produk bertipe FINISHED_GOOD")
    material_ids = [i.material_product_id for i in body.items]
    if len(set(material_ids)) != len(material_ids):
        raise ApiError(422, "VALIDATION_ERROR", "Material tidak boleh duplikat dalam satu BOM")
    materials = dict(
        db.execute(select(Product.id, Product.product_type).where(Product.id.in_(material_ids))).all()
    )
    unknown = [str(m) for m in material_ids if m not in materials]
    if unknown:
        raise ApiError(422, "VALIDATION_ERROR", "Material tidak ditemukan", [{"material_product_id": u} for u in unknown])
    wrong = [str(m) for m, t in materials.items() if t != "MATERIAL"]
    if wrong:
        raise ApiError(422, "VALIDATION_ERROR", "Item BOM harus produk bertipe MATERIAL", [{"material_product_id": w} for w in wrong])

    current = db.scalar(
        select(BillOfMaterials)
        .where(BillOfMaterials.product_id == product_id, BillOfMaterials.status == "ACTIVE")
        .with_for_update()
    )
    next_version = (db.scalar(select(func.max(BillOfMaterials.version_number)).where(BillOfMaterials.product_id == product_id)) or 0) + 1
    if current is not None:
        if current.effective_from > body.effective_from:
            raise conflict("Tanggal berlaku BOM baru tidak boleh sebelum BOM aktif")
        current.status = "SUPERSEDED"
        current.effective_to = body.effective_from
        db.flush()
    bom = BillOfMaterials(
        organization_id=ctx.org_id,
        product_id=product_id,
        version_number=next_version,
        planned_output_qty=body.planned_output_qty,
        process_yield_rate=body.process_yield_rate,
        status="ACTIVE",
        effective_from=body.effective_from,
        notes=body.notes,
        created_by=ctx.user_id,
    )
    db.add(bom)
    db.flush()
    for line_no, item in enumerate(body.items, start=1):
        db.add(BomItem(organization_id=ctx.org_id, bom_id=bom.id, line_no=line_no, **item.model_dump()))
    db.flush()
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="CREATE", entity_type="bom", entity_id=bom.id,
                 new={**body.model_dump(), "version_number": next_version,
                      "superseded_id": current.id if current else None})
    out = _bom_out(db, bom)
    db.commit()
    return ok(out)
