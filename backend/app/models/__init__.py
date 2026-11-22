"""ORM mapping ke skema di migrations/versions (DDL adalah sumber kebenaran)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {uuid.UUID: UUID(as_uuid=True), dict[str, Any]: JSONB, list[Any]: JSONB}


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))


def created() -> Mapped[datetime]:
    return mapped_column(server_default=text("now()"))


MONEY = Numeric(20, 4)
RATE = Numeric(12, 6)
QTY = Numeric(20, 6)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(CITEXT)
    password_hash: Mapped[str]
    full_name: Mapped[str]
    preferred_language: Mapped[str] = mapped_column(server_default="id")
    status: Mapped[str] = mapped_column(server_default="ACTIVE")
    is_platform_admin: Mapped[bool] = mapped_column(server_default=text("false"))
    created_at: Mapped[datetime] = created()


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str]
    slug: Mapped[str] = mapped_column(CITEXT)
    default_currency: Mapped[str] = mapped_column(String(3), server_default="IDR")
    default_language: Mapped[str] = mapped_column(server_default="id")
    fiscal_year_start_month: Mapped[int] = mapped_column(server_default=text("1"))
    timezone: Mapped[str] = mapped_column(server_default="Asia/Jakarta")
    status: Mapped[str] = mapped_column(server_default="ACTIVE")
    created_at: Mapped[datetime] = created()
    created_by: Mapped[uuid.UUID | None]
    updated_at: Mapped[datetime] = created()
    row_version: Mapped[int] = mapped_column(server_default=text("1"))


class OrganizationBusinessModel(Base):
    __tablename__ = "organization_business_models"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    business_model: Mapped[str]
    is_primary: Mapped[bool] = mapped_column(server_default=text("false"))


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID]
    status: Mapped[str] = mapped_column(server_default="ACTIVE")
    joined_at: Mapped[datetime] = created()


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[uuid.UUID] = pk()
    permission_key: Mapped[str]
    description: Mapped[str]


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID | None]
    code: Mapped[str]
    name: Mapped[str]
    description: Mapped[str | None]
    is_system: Mapped[bool]


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)


class MemberRole(Base):
    __tablename__ = "member_roles"
    organization_id: Mapped[uuid.UUID]
    member_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), primary_key=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID | None]
    action: Mapped[str]
    entity_type: Mapped[str]
    entity_id: Mapped[uuid.UUID | None]
    old_values: Mapped[dict[str, Any] | None]
    new_values: Mapped[dict[str, Any] | None]
    request_id: Mapped[str | None]
    created_at: Mapped[datetime] = created()


class ProductCategory(Base):
    __tablename__ = "product_categories"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    name: Mapped[str]
    parent_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = created()


class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    code: Mapped[str]
    name: Mapped[str]
    dimension: Mapped[str]
    created_at: Mapped[datetime] = created()


class Product(Base):
    __tablename__ = "products"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    category_id: Mapped[uuid.UUID | None]
    sku: Mapped[str]
    name: Mapped[str]
    product_type: Mapped[str]
    business_model: Mapped[str]
    pricing_model_type: Mapped[str] = mapped_column(server_default="STANDARD")
    base_unit_id: Mapped[uuid.UUID]
    description: Mapped[str | None]
    status: Mapped[str] = mapped_column(server_default="ACTIVE")
    created_at: Mapped[datetime] = created()
    created_by: Mapped[uuid.UUID | None]
    updated_at: Mapped[datetime] = created()
    row_version: Mapped[int] = mapped_column(server_default=text("1"))


class MaterialPrice(Base):
    __tablename__ = "material_prices"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    material_product_id: Mapped[uuid.UUID]
    supplier_name: Mapped[str | None]
    currency: Mapped[str] = mapped_column(String(3))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    effective_from: Mapped[date]
    effective_to: Mapped[date | None]
    data_nature: Mapped[str]
    source_reference: Mapped[str | None]
    created_at: Mapped[datetime] = created()
    created_by: Mapped[uuid.UUID | None]


class BillOfMaterials(Base):
    __tablename__ = "bill_of_materials"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    product_id: Mapped[uuid.UUID]
    version_number: Mapped[int]
    planned_output_qty: Mapped[Decimal] = mapped_column(QTY)
    process_yield_rate: Mapped[Decimal] = mapped_column(RATE)
    status: Mapped[str]
    effective_from: Mapped[date]
    effective_to: Mapped[date | None]
    notes: Mapped[str | None]
    created_at: Mapped[datetime] = created()
    created_by: Mapped[uuid.UUID | None]


class BomItem(Base):
    __tablename__ = "bom_items"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    bom_id: Mapped[uuid.UUID]
    line_no: Mapped[int]
    material_product_id: Mapped[uuid.UUID]
    net_quantity: Mapped[Decimal] = mapped_column(QTY)
    material_waste_rate: Mapped[Decimal] = mapped_column(RATE)


class CostingVersion(Base):
    __tablename__ = "costing_versions"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    product_id: Mapped[uuid.UUID]
    version_number: Mapped[int]
    costing_method: Mapped[str]
    costing_structure: Mapped[str]
    data_nature: Mapped[str]
    bom_id: Mapped[uuid.UUID | None]
    scrap_rate: Mapped[Decimal] = mapped_column(RATE)
    rework_rate: Mapped[Decimal] = mapped_column(RATE)
    rework_cost_per_unit: Mapped[Decimal] = mapped_column(MONEY)
    calculated_unit_cost: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    as_of_date: Mapped[date]
    effective_from: Mapped[date]
    effective_to: Mapped[date | None]
    status: Mapped[str]
    engine_version: Mapped[str]
    input_snapshot: Mapped[dict[str, Any]]
    calculation_snapshot: Mapped[dict[str, Any]]
    input_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = created()
    created_by: Mapped[uuid.UUID | None]


class PricingRecommendation(Base):
    __tablename__ = "pricing_recommendations"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID]
    product_id: Mapped[uuid.UUID]
    costing_version_id: Mapped[uuid.UUID]
    pricing_method: Mapped[str]
    margin_definition: Mapped[str]
    minimum_price: Mapped[Decimal | None] = mapped_column(MONEY)
    target_price: Mapped[Decimal] = mapped_column(MONEY)
    recommended_price: Mapped[Decimal] = mapped_column(MONEY)
    list_price: Mapped[Decimal] = mapped_column(MONEY)
    expected_gross_margin: Mapped[Decimal | None] = mapped_column(RATE)
    expected_contribution_margin: Mapped[Decimal | None] = mapped_column(RATE)
    currency: Mapped[str] = mapped_column(String(3))
    effective_date: Mapped[date]
    warnings: Mapped[list[Any]]
    engine_version: Mapped[str]
    input_snapshot: Mapped[dict[str, Any]]
    calculation_snapshot: Mapped[dict[str, Any]]
    input_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(server_default="DRAFT")
    created_at: Mapped[datetime] = created()
    created_by: Mapped[uuid.UUID | None]
