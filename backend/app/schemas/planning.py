"""Skema untuk biaya, alokasi, skenario, dan simulasi."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from app.schemas import ORM, Dec, Fraction, NonNegDec, _no_float

Change = Annotated[Decimal, BeforeValidator(_no_float), Field(gt=-1, le=10)]
Category = Literal[
    "DIRECT_MATERIAL", "DIRECT_LABOR", "PRODUCTION_OVERHEAD", "FIXED_OPERATING", "VARIABLE_OPERATING",
    "SELLING", "DISTRIBUTION", "ADMINISTRATIVE", "FINANCIAL", "TAX_STATUTORY", "OTHER",
]
Behavior = Literal["FIXED", "VARIABLE", "SEMI_VARIABLE", "STEP_FIXED", "PERCENTAGE"]
ScopeT = Literal["PRODUCT", "PERIOD", "ALLOCATION_POOL"]
DriverType = Literal["SALES_UNITS", "PRODUCTION_UNITS", "REVENUE", "LABOR_HOURS", "MACHINE_HOURS", "CUSTOM"]
DataNature = Literal["ACTUAL", "STANDARD", "ESTIMATE", "SCENARIO"]


class DriverCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=100)
    driver_type: DriverType
    unit_label: str | None = Field(default=None, max_length=30)


class DriverOut(ORM):
    id: uuid.UUID
    code: str
    name: str
    driver_type: str
    unit_label: str | None


class TierIn(BaseModel):
    from_activity: NonNegDec
    to_activity: NonNegDec
    amount: NonNegDec


class CostParams(BaseModel):
    effective_from: date
    data_nature: DataNature = "STANDARD"
    base_amount: NonNegDec | None = None
    rate: NonNegDec | None = None
    percentage: Fraction | None = None
    percentage_base: Literal["REVENUE", "COGS"] | None = None
    step_mode: Literal["TABLE", "CEILING"] | None = None
    tiers: list[TierIn] | None = None
    capacity_per_resource: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=0)] | None = None
    cost_per_resource: NonNegDec | None = None
    max_resources: NonNegDec | None = None
    minimum_amount: NonNegDec | None = None
    maximum_amount: NonNegDec | None = None
    escalation_type: Literal["NOMINAL", "SIMPLE_PCT", "COMPOUND_PCT"] | None = None
    escalation_rate: Annotated[Decimal, BeforeValidator(_no_float), Field(gt=-1, le=5)] | None = None
    escalation_amount: Dec | None = None
    escalation_frequency: Literal["MONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL"] | None = None
    escalation_cap: NonNegDec | None = None
    source_reference: str | None = Field(default=None, max_length=300)


class CostItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=200)
    category: Category
    behavior_type: Behavior
    cost_scope: ScopeT = "PERIOD"
    driver_id: uuid.UUID | None = None
    period_months: Literal[1, 3, 6, 12] = 1
    description: str | None = None
    params: CostParams


class CostItemUpdate(BaseModel):
    row_version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: Category | None = None
    description: str | None = None
    status: Literal["ACTIVE", "INACTIVE"] | None = None


class CostVersionOut(ORM):
    id: uuid.UUID
    version_number: int
    effective_from: date
    effective_to: date | None
    data_nature: str
    base_amount: Decimal | None
    rate: Decimal | None
    percentage: Decimal | None
    percentage_base: str | None
    step_mode: str | None
    tiers: list[Any] | None
    capacity_per_resource: Decimal | None
    cost_per_resource: Decimal | None
    max_resources: Decimal | None
    minimum_amount: Decimal | None
    maximum_amount: Decimal | None
    escalation_type: str | None
    escalation_rate: Decimal | None
    escalation_amount: Decimal | None
    escalation_frequency: str | None
    escalation_cap: Decimal | None
    source_reference: str | None
    created_at: datetime


class AllocationTargetIn(BaseModel):
    product_id: uuid.UUID
    value: NonNegDec | None = None


class AllocationIn(BaseModel):
    basis: Literal["EQUAL", "PERCENTAGE", "DRIVER", "REVENUE", "UNITS"]
    driver_label: str | None = Field(default=None, max_length=60)
    allow_unallocated: bool = False
    targets: list[AllocationTargetIn] = []

    @field_validator("targets")
    @classmethod
    def _unique(cls, v: list[AllocationTargetIn]) -> list[AllocationTargetIn]:
        ids = [t.product_id for t in v]
        if len(ids) != len(set(ids)):
            raise ValueError("produk tidak boleh duplikat")
        return v


class AllocationOut(BaseModel):
    basis: str
    driver_label: str | None
    allow_unallocated: bool
    targets: list[AllocationTargetIn]


class CostItemOut(ORM):
    id: uuid.UUID
    code: str
    name: str
    category: str
    behavior_type: str
    cost_scope: str
    driver_id: uuid.UUID | None
    period_months: int
    description: str | None
    status: str
    row_version: int
    updated_at: datetime
    driver: DriverOut | None = None
    current_version: CostVersionOut | None = None
    has_allocation: bool = False


class CostItemDetail(CostItemOut):
    versions: list[CostVersionOut] = []
    allocation: AllocationOut | None = None


class CostPreviewIn(BaseModel):
    units: NonNegDec = Decimal(0)
    revenue: NonNegDec = Decimal(0)
    cogs: NonNegDec = Decimal(0)
    period_months: int = Field(default=1, ge=1, le=12)
    as_of_date: date
    data_nature: DataNature = "STANDARD"
    activity: dict[str, NonNegDec] = {}


# --- Skenario -----------------------------------------------------------------


class SalesLineIn(BaseModel):
    product_id: uuid.UUID
    unit_price: NonNegDec
    volume: NonNegDec
    unit_cost_override: NonNegDec | None = None


class SalesLineOut(SalesLineIn):
    sku: str
    product_name: str
    active_unit_cost: Decimal | None = None


class Assumptions(BaseModel):
    price_change: Change = Decimal(0)
    volume_change: Change = Decimal(0)
    unit_cost_change: Change = Decimal(0)
    variable_cost_change: Change = Decimal(0)
    fixed_cost_change: Change = Decimal(0)
    item_changes: dict[str, Change] = {}
    product_volume_changes: dict[str, Change] = {}
    other_activity: dict[str, NonNegDec] = {}
    tax_regime: Literal["NONE", "PROFIT_BASED", "TURNOVER_FINAL"] = "NONE"
    tax_rate: Fraction = Decimal(0)
    exempt_turnover: NonNegDec = Decimal(0)
    target_kind: Literal["OPERATING_PROFIT", "NET_PROFIT"] | None = None
    target_amount: Dec | None = None
    data_nature: DataNature = "STANDARD"


ScenarioType = Literal["BASE", "OPTIMISTIC", "PESSIMISTIC", "CUSTOM"]


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    scenario_type: ScenarioType = "CUSTOM"
    period_start: date
    period_months: int = Field(default=1, ge=1, le=12)
    assumptions: Assumptions = Assumptions()
    lines: list[SalesLineIn] = []

    @field_validator("lines")
    @classmethod
    def _unique(cls, v: list[SalesLineIn]) -> list[SalesLineIn]:
        ids = [l.product_id for l in v]
        if len(ids) != len(set(ids)):
            raise ValueError("produk tidak boleh duplikat dalam rencana penjualan")
        return v


class ScenarioUpdate(BaseModel):
    row_version: int
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    scenario_type: ScenarioType | None = None
    period_start: date | None = None
    period_months: int | None = Field(default=None, ge=1, le=12)
    assumptions: Assumptions | None = None
    lines: list[SalesLineIn] | None = None

    @field_validator("lines")
    @classmethod
    def _unique(cls, v: list[SalesLineIn] | None) -> list[SalesLineIn] | None:
        if v is not None and len({l.product_id for l in v}) != len(v):
            raise ValueError("produk tidak boleh duplikat dalam rencana penjualan")
        return v


class DuplicateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scenario_type: ScenarioType = "CUSTOM"


class RunSummary(BaseModel):
    id: uuid.UUID
    created_at: datetime
    status: str
    revenue: Decimal | None = None
    operating_profit: Decimal | None = None
    net_profit: Decimal | None = None
    break_even_units: Decimal | None = None
    warnings: list[Any] = []


class ScenarioOut(ORM):
    id: uuid.UUID
    name: str
    description: str | None
    scenario_type: str
    base_scenario_id: uuid.UUID | None
    period_start: date
    period_months: int
    assumptions: dict[str, Any]
    status: str
    row_version: int
    updated_at: datetime
    lines: list[SalesLineOut] = []
    latest_run: RunSummary | None = None


class RunOut(ORM):
    id: uuid.UUID
    scenario_id: uuid.UUID
    engine_version: str
    input_hash: str
    status: str
    created_at: datetime
    input_snapshot: dict[str, Any]
    result_snapshot: dict[str, Any]


class CompareIn(BaseModel):
    scenario_ids: list[uuid.UUID] = Field(min_length=2, max_length=6)
    rerun: bool = True
