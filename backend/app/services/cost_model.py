"""Mengubah data biaya di database menjadi input Calculation Engine."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pricing_engine import planning as eng
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import CostAllocationRule, CostAllocationTarget, CostDriver, CostItem, CostItemVersion


def version_in_effect(db: Session, item_id: uuid.UUID, as_of: date, nature: str) -> CostItemVersion | None:
    return db.scalar(
        select(CostItemVersion).where(
            CostItemVersion.cost_item_id == item_id,
            CostItemVersion.data_nature == nature,
            CostItemVersion.effective_from <= as_of,
            or_(CostItemVersion.effective_to.is_(None), CostItemVersion.effective_to > as_of),
        )
    )


def to_spec(item: CostItem, version: CostItemVersion | Any, driver: CostDriver | None) -> eng.CostItemSpec:
    """`version` boleh model ORM atau objek dengan atribut yang sama (mis. CostParams)."""
    tiers = tuple(
        eng.Tier(t["from_activity"] if isinstance(t, dict) else t.from_activity,
                 t["to_activity"] if isinstance(t, dict) else t.to_activity,
                 t["amount"] if isinstance(t, dict) else t.amount)
        for t in (version.tiers or [])
    )
    return eng.CostItemSpec(
        code=item.code,
        name=item.name,
        behavior=eng.Behavior(item.behavior_type),
        scope=eng.Scope(item.cost_scope),
        category=item.category,
        period_months=item.period_months,
        driver_code=driver.code if driver else None,
        driver_type=eng.DriverType(driver.driver_type) if driver else None,
        base_amount=version.base_amount,
        rate=version.rate,
        percentage=version.percentage,
        percentage_base=version.percentage_base,
        step_mode=version.step_mode,
        tiers=tiers,
        capacity_per_resource=version.capacity_per_resource,
        cost_per_resource=version.cost_per_resource,
        max_resources=version.max_resources,
        minimum_amount=version.minimum_amount,
        maximum_amount=version.maximum_amount,
        escalation_type=version.escalation_type,
        escalation_rate=version.escalation_rate,
        escalation_amount=version.escalation_amount,
        escalation_frequency=version.escalation_frequency,
        escalation_cap=version.escalation_cap,
        effective_from=version.effective_from,
    )


def load_specs(db: Session, org_id: uuid.UUID, as_of: date, nature: str) -> tuple[list[eng.CostItemSpec], list[dict[str, Any]], list[str]]:
    """Semua cost item aktif + versi yang berlaku. Mengembalikan (specs, referensi versi, item tanpa versi)."""
    drivers = {d.id: d for d in db.scalars(select(CostDriver).where(CostDriver.organization_id == org_id))}
    items = db.scalars(
        select(CostItem).where(CostItem.organization_id == org_id, CostItem.status == "ACTIVE").order_by(CostItem.code)
    ).all()
    specs, refs, missing = [], [], []
    for item in items:
        v = version_in_effect(db, item.id, as_of, nature)
        if v is None:
            missing.append(item.code)
            continue
        specs.append(to_spec(item, v, drivers.get(item.driver_id) if item.driver_id else None))
        refs.append({"cost_item_id": str(item.id), "code": item.code, "version_id": str(v.id), "version_number": v.version_number})
    return specs, refs, missing


def load_allocation_rules(db: Session, org_id: uuid.UUID, product_key: dict[uuid.UUID, str]) -> list[eng.AllocationRuleSpec]:
    rules = []
    rows = db.execute(
        select(CostAllocationRule, CostItem.code)
        .join(CostItem, CostItem.id == CostAllocationRule.cost_item_id)
        .where(CostAllocationRule.organization_id == org_id, CostItem.status == "ACTIVE")
    ).all()
    for rule, code in rows:
        targets = db.scalars(select(CostAllocationTarget).where(CostAllocationTarget.rule_id == rule.id)).all()
        rules.append(
            eng.AllocationRuleSpec(
                cost_code=code,
                basis=eng.AllocationBasis(rule.basis),
                targets=tuple((product_key.get(t.product_id, str(t.product_id)), t.value if t.value is not None else 1) for t in targets),
                allow_unallocated=rule.allow_unallocated,
            )
        )
    return rules
