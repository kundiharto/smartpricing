"""Skema request/response. Angka finansial dikirim dan diterima sebagai string desimal."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, field_validator

from app.core.request_context import current_request_id

T = TypeVar("T")


def _no_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError("angka finansial harus dikirim sebagai string desimal, mis. \"0.30\" (float tidak diizinkan)")
    return value


Dec = Annotated[Decimal, BeforeValidator(_no_float)]
NonNegDec = Annotated[Decimal, BeforeValidator(_no_float), Field(ge=0)]
Fraction = Annotated[Decimal, BeforeValidator(_no_float), Field(ge=0, lt=1)]

BusinessModel = Literal["MANUFACTURING", "TRADING", "DISTRIBUTION", "RETAIL", "SERVICES"]
DataNature = Literal["ACTUAL", "STANDARD", "ESTIMATE", "SCENARIO"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Meta(BaseModel):
    request_id: str = Field(default_factory=current_request_id)
    total: int | None = None
    limit: int | None = None
    offset: int | None = None


class Envelope(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: Meta = Field(default_factory=Meta)


def ok(data: Any, **meta: Any) -> Envelope[Any]:
    return Envelope(data=data, meta=Meta(**meta))


# --- Auth -------------------------------------------------------------------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    preferred_language: Literal["id", "en"] = "id"


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserOut(ORM):
    id: uuid.UUID
    email: str
    full_name: str
    preferred_language: str
    status: str


class MembershipOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    roles: list[str]


class MeOut(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]


# --- Organization -----------------------------------------------------------


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")
    default_currency: str = Field(default="IDR", pattern=r"^[A-Z]{3}$")
    default_language: Literal["id", "en"] = "id"
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    timezone: str = "Asia/Jakarta"
    business_models: list[BusinessModel] = Field(min_length=1)
    primary_business_model: BusinessModel

    @field_validator("business_models")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("business_models tidak boleh duplikat")
        return v


class OrganizationUpdate(BaseModel):
    row_version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    default_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    default_language: Literal["id", "en"] | None = None
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    timezone: str | None = None


class OrganizationOut(ORM):
    id: uuid.UUID
    name: str
    slug: str
    default_currency: str
    default_language: str
    fiscal_year_start_month: int
    timezone: str
    status: str
    row_version: int
    business_models: list[str] = []
    primary_business_model: str | None = None
    is_hybrid: bool = False
    my_roles: list[str] = []
    my_permissions: list[str] = []


class MemberAdd(BaseModel):
    email: EmailStr
    role_codes: list[str] = Field(min_length=1)


class MemberOut(BaseModel):
    member_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    status: str
    roles: list[str]


# --- Catalog ----------------------------------------------------------------


class UnitCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    dimension: Literal["COUNT", "MASS", "VOLUME", "LENGTH", "AREA", "TIME", "OTHER"]


class UnitOut(ORM):
    id: uuid.UUID
    code: str
    name: str
    dimension: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None


class CategoryOut(ORM):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None


ProductType = Literal["FINISHED_GOOD", "MATERIAL", "TRADED_GOOD", "SERVICE"]


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    product_type: ProductType
    business_model: BusinessModel
    pricing_model_type: Literal["STANDARD", "PROJECT_BASED"] = "STANDARD"
    base_unit_id: uuid.UUID
    category_id: uuid.UUID | None = None
    description: str | None = None


class ProductUpdate(BaseModel):
    row_version: int
    name: str | None = Field(default=None, min_length=1, max_length=300)
    category_id: uuid.UUID | None = None
    description: str | None = None
    status: Literal["ACTIVE", "INACTIVE"] | None = None


class ProductOut(ORM):
    id: uuid.UUID
    sku: str
    name: str
    product_type: str
    business_model: str
    pricing_model_type: str
    base_unit_id: uuid.UUID
    category_id: uuid.UUID | None
    description: str | None
    status: str
    row_version: int
    created_at: datetime
    updated_at: datetime


class MaterialPriceCreate(BaseModel):
    unit_price: NonNegDec
    effective_from: date
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    data_nature: DataNature = "STANDARD"
    supplier_name: str | None = None
    source_reference: str | None = None


class MaterialPriceOut(ORM):
    id: uuid.UUID
    material_product_id: uuid.UUID
    unit_price: Decimal
    currency: str
    effective_from: date
    effective_to: date | None
    data_nature: str
    supplier_name: str | None
    source_reference: str | None


class BomItemIn(BaseModel):
    material_product_id: uuid.UUID
    net_quantity: NonNegDec
    material_waste_rate: Fraction = Decimal(0)


class BomCreate(BaseModel):
    planned_output_qty: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=0)]
    process_yield_rate: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=0, le=1)] = Decimal(1)
    effective_from: date
    notes: str | None = None
    items: list[BomItemIn] = Field(min_length=1)


class BomItemOut(ORM):
    id: uuid.UUID
    line_no: int
    material_product_id: uuid.UUID
    net_quantity: Decimal
    material_waste_rate: Decimal


class BomOut(ORM):
    id: uuid.UUID
    product_id: uuid.UUID
    version_number: int
    planned_output_qty: Decimal
    process_yield_rate: Decimal
    status: str
    effective_from: date
    effective_to: date | None
    notes: str | None
    items: list[BomItemOut] = []


# --- Costing ----------------------------------------------------------------


class ResourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    hours: NonNegDec
    hourly_rate: NonNegDec


class LandedCostIn(BaseModel):
    quantity: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=0)]
    unit_purchase_price: NonNegDec
    fx_rate: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=0)] = Decimal(1)
    freight: NonNegDec = Decimal(0)
    insurance: NonNegDec = Decimal(0)
    import_duty_rate: Fraction = Decimal(0)
    handling: NonNegDec = Decimal(0)
    other_acquisition: NonNegDec = Decimal(0)
    qty_received_good: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=0)] | None = None


class CostingRun(BaseModel):
    costing_structure: Literal["BOM_BASED", "LANDED_COST", "DIRECT_INPUT"]
    costing_method: Literal["STANDARD", "ACTUAL", "ESTIMATED"] = "STANDARD"
    data_nature: DataNature = "STANDARD"
    as_of_date: date
    effective_from: date | None = None
    activate: bool = True
    # BOM_BASED
    labor: list[ResourceIn] = []
    machines: list[ResourceIn] = []
    overhead: NonNegDec = Decimal(0)
    packaging: NonNegDec = Decimal(0)
    other_direct: NonNegDec = Decimal(0)
    scrap_rate: Fraction = Decimal(0)
    rework_rate: Fraction = Decimal(0)
    rework_cost_per_unit: NonNegDec = Decimal(0)
    # LANDED_COST
    landed: LandedCostIn | None = None
    # DIRECT_INPUT
    unit_cost: NonNegDec | None = None
    justification: str | None = None


class CostingVersionOut(ORM):
    id: uuid.UUID
    product_id: uuid.UUID
    version_number: int
    costing_method: str
    costing_structure: str
    data_nature: str
    calculated_unit_cost: Decimal
    currency: str
    as_of_date: date
    effective_from: date
    effective_to: date | None
    status: str
    engine_version: str
    input_hash: str
    created_at: datetime


class CostingVersionDetail(CostingVersionOut):
    bom_id: uuid.UUID | None
    input_snapshot: dict[str, Any]
    calculation_snapshot: dict[str, Any]


# --- Pricing ----------------------------------------------------------------

PricingMethod = Literal[
    "MARKUP",
    "TARGET_GROSS_MARGIN",
    "TARGET_CONTRIBUTION_MARGIN",
    "MINIMUM_VIABLE",
    "BREAK_EVEN",
    "TARGET_OPERATING_PROFIT",
    "COMPETITIVE",
    "VALUE_BASED",
]


class FeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rate: Fraction
    base: Literal["LIST_PRICE", "NET_PRICE", "GROSS_PRICE", "PRODUCT_COST"] = "NET_PRICE"


class RoundingIn(BaseModel):
    increment: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=0)]
    mode: Literal["UP", "NEAREST", "DOWN"] = "NEAREST"
    margin_guard: bool = True
    apply_to: Literal["LIST_PRICE", "NET_PRICE"] = "LIST_PRICE"


class PricingInput(BaseModel):
    method: PricingMethod
    product_id: uuid.UUID | None = None
    unit_cost: NonNegDec | None = None
    variable_cost: NonNegDec = Decimal(0)
    discount: Fraction = Decimal(0)
    fees: list[FeeIn] = []
    turnover_tax_load: Fraction = Decimal(0)
    vat_effective_rate: NonNegDec = Decimal(0)
    target_margin: Fraction | None = None
    markup: NonNegDec | None = None
    fixed_cost: NonNegDec | None = None
    volume: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=0)] | None = None
    target_operating_profit: Dec | None = None
    reference_price: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=0)] | None = None
    adjustment: Dec = Decimal(0)
    rounding: RoundingIn | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class RecommendIn(PricingInput):
    product_id: uuid.UUID
    effective_date: date


class RecommendationOut(ORM):
    id: uuid.UUID
    product_id: uuid.UUID
    costing_version_id: uuid.UUID
    pricing_method: str
    margin_definition: str
    minimum_price: Decimal | None
    target_price: Decimal
    recommended_price: Decimal
    list_price: Decimal
    expected_gross_margin: Decimal | None
    expected_contribution_margin: Decimal | None
    currency: str
    effective_date: date
    warnings: list[Any]
    unit_cost: Decimal | None = None
    engine_version: str
    input_hash: str
    status: str
    created_at: datetime


class RecommendationDetail(RecommendationOut):
    input_snapshot: dict[str, Any]
    calculation_snapshot: dict[str, Any]


class AuditLogOut(ORM):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    request_id: str | None
    created_at: datetime
