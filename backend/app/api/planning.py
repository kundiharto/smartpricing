"""Revenue & profit planning, skenario, simulasi, dan perbandingan (MOD-006, MOD-007)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pricing_engine import planning as eng
from pricing_engine.core import canonical
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DB, OrgContext, require
from app.core.errors import ApiError, conflict, not_found
from app.models import CostingVersion, Organization, Product, Scenario, ScenarioSalesLine, SimulationRun
from app.schemas import Envelope, ok
from app.schemas.planning import (
    Assumptions,
    CompareIn,
    DuplicateIn,
    RunOut,
    RunSummary,
    SalesLineIn,
    SalesLineOut,
    ScenarioCreate,
    ScenarioOut,
    ScenarioUpdate,
)
from app.services import audit
from app.services.cost_model import load_allocation_rules, load_specs

router = APIRouter(tags=["planning"])

Read = Annotated[OrgContext, Depends(require("planning.read"))]
Write = Annotated[OrgContext, Depends(require("planning.write"))]

SCENARIO_FIELDS = ["name", "description", "scenario_type", "period_start", "period_months", "assumptions", "status"]


def _scenario(db: Session, ctx: OrgContext, sid: uuid.UUID) -> Scenario:
    s = db.scalar(select(Scenario).where(Scenario.id == sid, Scenario.organization_id == ctx.org_id))
    if s is None:
        raise not_found("Skenario")
    return s


def _active_costs(db: Session, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(CostingVersion.product_id, CostingVersion.calculated_unit_cost).where(
            CostingVersion.product_id.in_(product_ids), CostingVersion.status == "ACTIVE"
        )
    ).all()
    return {r.product_id: r.calculated_unit_cost for r in rows}


def _summary(run: SimulationRun | None) -> RunSummary | None:
    if run is None:
        return None
    values = run.result_snapshot.get("values", {})
    pnl = values.get("pnl", {})
    bep = values.get("break_even", {})
    dec = lambda v: Decimal(v) if v is not None else None  # noqa: E731
    return RunSummary(
        id=run.id,
        created_at=run.created_at,
        status=run.status,
        revenue=dec(pnl.get("revenue")),
        operating_profit=dec(pnl.get("operating_profit")),
        net_profit=dec(pnl.get("net_profit")),
        break_even_units=dec(bep.get("units")),
        warnings=run.result_snapshot.get("warnings", []),
    )


def _latest_run(db: Session, sid: uuid.UUID) -> SimulationRun | None:
    return db.scalar(select(SimulationRun).where(SimulationRun.scenario_id == sid).order_by(SimulationRun.created_at.desc()).limit(1))


def _out(db: Session, s: Scenario) -> ScenarioOut:
    out = ScenarioOut.model_validate(s)
    rows = db.execute(
        select(ScenarioSalesLine, Product.sku, Product.name)
        .join(Product, Product.id == ScenarioSalesLine.product_id)
        .where(ScenarioSalesLine.scenario_id == s.id)
        .order_by(Product.name)
    ).all()
    costs = _active_costs(db, [r[0].product_id for r in rows])
    out.lines = [
        SalesLineOut(
            product_id=l.product_id, unit_price=l.unit_price, volume=l.volume, unit_cost_override=l.unit_cost_override,
            sku=sku, product_name=name, active_unit_cost=costs.get(l.product_id),
        )
        for l, sku, name in rows
    ]
    out.latest_run = _summary(_latest_run(db, s.id))
    return out


def _replace_lines(db: Session, ctx: OrgContext, s: Scenario, lines: list[SalesLineIn]) -> None:
    ids = [l.product_id for l in lines]
    if ids:
        found = dict(
            db.execute(select(Product.id, Product.product_type).where(Product.id.in_(ids), Product.organization_id == ctx.org_id)).all()
        )
        if len(found) != len(ids):
            raise ApiError(422, "VALIDATION_ERROR", "Produk dalam rencana penjualan tidak ditemukan")
        if any(t == "MATERIAL" for t in found.values()):
            raise ApiError(422, "VALIDATION_ERROR", "Bahan baku tidak dijual; pilih barang jadi, barang dagang, atau jasa")
    for row in db.scalars(select(ScenarioSalesLine).where(ScenarioSalesLine.scenario_id == s.id)).all():
        db.delete(row)
    db.flush()
    for l in lines:
        db.add(ScenarioSalesLine(organization_id=ctx.org_id, scenario_id=s.id, **l.model_dump()))
    db.flush()


@router.get("/scenarios", response_model=Envelope[list[ScenarioOut]])
def list_scenarios(ctx: Read, db: DB, include_archived: bool = False) -> Envelope:
    stmt = select(Scenario).where(Scenario.organization_id == ctx.org_id)
    if not include_archived:
        stmt = stmt.where(Scenario.status == "ACTIVE")
    rows = db.scalars(stmt.order_by(Scenario.period_start.desc(), Scenario.name)).all()
    return ok([_out(db, s) for s in rows], total=len(rows))


@router.post("/scenarios", response_model=Envelope[ScenarioOut], status_code=201)
def create_scenario(body: ScenarioCreate, ctx: Write, db: DB) -> Envelope:
    s = Scenario(
        organization_id=ctx.org_id,
        name=body.name,
        description=body.description,
        scenario_type=body.scenario_type,
        period_start=body.period_start,
        period_months=body.period_months,
        assumptions=body.assumptions.model_dump(mode="json"),
        created_by=ctx.user_id,
    )
    db.add(s)
    db.flush()
    _replace_lines(db, ctx, s, body.lines)
    db.refresh(s)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="CREATE", entity_type="scenario", entity_id=s.id,
                 new={**audit.snapshot(s, SCENARIO_FIELDS), "lines": [l.model_dump() for l in body.lines]})
    out = _out(db, s)
    db.commit()
    return ok(out)


@router.get("/scenarios/{sid}", response_model=Envelope[ScenarioOut])
def read_scenario(sid: uuid.UUID, ctx: Read, db: DB) -> Envelope:
    return ok(_out(db, _scenario(db, ctx, sid)))


@router.patch("/scenarios/{sid}", response_model=Envelope[ScenarioOut])
def update_scenario(sid: uuid.UUID, body: ScenarioUpdate, ctx: Write, db: DB) -> Envelope:
    s = _scenario(db, ctx, sid)
    if s.row_version != body.row_version:
        raise conflict("Skenario telah diubah oleh pengguna lain; muat ulang lalu coba lagi")
    old = audit.snapshot(s, SCENARIO_FIELDS)
    data = body.model_dump(exclude_unset=True, exclude={"row_version", "lines", "assumptions"})
    for k, v in data.items():
        if v is not None:
            setattr(s, k, v)
    if body.assumptions is not None:
        s.assumptions = body.assumptions.model_dump(mode="json")
    if body.lines is not None:
        _replace_lines(db, ctx, s, body.lines)
    s.row_version += 1
    db.flush()
    db.refresh(s)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="UPDATE", entity_type="scenario", entity_id=s.id,
                 old=old, new={**audit.snapshot(s, SCENARIO_FIELDS), **({"lines": [l.model_dump() for l in body.lines]} if body.lines is not None else {})})
    out = _out(db, s)
    db.commit()
    return ok(out)


@router.delete("/scenarios/{sid}", response_model=Envelope[ScenarioOut])
def archive_scenario(sid: uuid.UUID, ctx: Write, db: DB) -> Envelope:
    s = _scenario(db, ctx, sid)
    if s.status != "ARCHIVED":
        s.status = "ARCHIVED"
        s.row_version += 1
        db.flush()
        audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="ARCHIVE", entity_type="scenario", entity_id=s.id)
    db.refresh(s)
    out = _out(db, s)
    db.commit()
    return ok(out)


@router.post("/scenarios/{sid}/duplicate", response_model=Envelope[ScenarioOut], status_code=201)
def duplicate_scenario(sid: uuid.UUID, body: DuplicateIn, ctx: Write, db: DB) -> Envelope:
    src = _scenario(db, ctx, sid)
    copy = Scenario(
        organization_id=ctx.org_id, name=body.name, description=src.description, scenario_type=body.scenario_type,
        base_scenario_id=src.id, period_start=src.period_start, period_months=src.period_months,
        assumptions=dict(src.assumptions), created_by=ctx.user_id,
    )
    db.add(copy)
    db.flush()
    lines = db.scalars(select(ScenarioSalesLine).where(ScenarioSalesLine.scenario_id == src.id)).all()
    _replace_lines(db, ctx, copy, [SalesLineIn(product_id=l.product_id, unit_price=l.unit_price, volume=l.volume,
                                                unit_cost_override=l.unit_cost_override) for l in lines])
    db.refresh(copy)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="DUPLICATE", entity_type="scenario", entity_id=copy.id,
                 new={"source_id": src.id, "name": body.name})
    out = _out(db, copy)
    db.commit()
    return ok(out)


def _run(db: Session, ctx: OrgContext, s: Scenario) -> SimulationRun:
    """Membangun input engine dari database, menjalankan profit_plan, menyimpan snapshot."""
    a = Assumptions.model_validate(s.assumptions)
    lines = db.execute(
        select(ScenarioSalesLine, Product.sku, Product.name)
        .join(Product, Product.id == ScenarioSalesLine.product_id)
        .where(ScenarioSalesLine.scenario_id == s.id)
    ).all()
    if not lines:
        raise ApiError(422, "INVALID_INPUT", "Rencana penjualan masih kosong: tambahkan produk, harga, dan volume")
    costs = _active_costs(db, [l.product_id for l, _, _ in lines])
    missing = [sku for l, sku, _ in lines if l.unit_cost_override is None and l.product_id not in costs]
    if missing:
        raise ApiError(422, "INVALID_INPUT", f"Produk tanpa costing aktif: {', '.join(missing)}. Jalankan costing atau isi biaya manual.")
    engine_lines = [
        eng.SalesLine(str(l.product_id), l.unit_price, l.unit_cost_override if l.unit_cost_override is not None else costs[l.product_id], l.volume)
        for l, _, _ in lines
    ]
    product_names = {str(l.product_id): {"sku": sku, "name": name} for l, sku, name in lines}
    specs, version_refs, without_version = load_specs(db, ctx.org_id, s.period_start, a.data_nature)
    rules = load_allocation_rules(db, ctx.org_id, {})
    currency = db.scalar(select(Organization.default_currency).where(Organization.id == ctx.org_id))
    kwargs: dict[str, Any] = dict(
        lines=engine_lines,
        items=specs,
        period_months=s.period_months,
        as_of_date=s.period_start,
        other_activity=dict(a.other_activity),
        adjustments=eng.Adjustments(
            price_change=a.price_change, volume_change=a.volume_change, unit_cost_change=a.unit_cost_change,
            variable_cost_change=a.variable_cost_change, fixed_cost_change=a.fixed_cost_change,
            item_changes=tuple(a.item_changes.items()), product_volume_changes=tuple(a.product_volume_changes.items()),
        ),
        allocation_rules=rules,
        tax_regime=eng.TaxRegime(a.tax_regime),
        tax_rate=a.tax_rate,
        exempt_turnover=a.exempt_turnover,
        target_kind=eng.TargetKind(a.target_kind) if a.target_kind and a.target_amount is not None else None,
        target_amount=a.target_amount if a.target_kind else None,
        currency=currency,
    )
    result = eng.profit_plan(**kwargs)
    snapshot = result.to_dict()
    snapshot["products"] = product_names
    snapshot["items_without_version"] = without_version
    run = SimulationRun(
        organization_id=ctx.org_id,
        scenario_id=s.id,
        engine_version=result.engine_version,
        input_snapshot={
            "scenario": {"id": str(s.id), "name": s.name, "row_version": s.row_version},
            "engine_inputs": canonical(kwargs),
            "cost_versions": version_refs,
        },
        result_snapshot=snapshot,
        input_hash=result.input_hash,
        status=result.status.value,
        created_by=ctx.user_id,
    )
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


@router.post("/scenarios/{sid}/run", response_model=Envelope[RunOut], status_code=201)
def run_scenario(sid: uuid.UUID, ctx: Write, db: DB) -> Envelope:
    s = _scenario(db, ctx, sid)
    run = _run(db, ctx, s)
    audit.record(db, org_id=ctx.org_id, user_id=ctx.user_id, action="RUN", entity_type="scenario", entity_id=s.id,
                 new={"run_id": run.id, "status": run.status})
    out = RunOut.model_validate(run)
    db.commit()
    if run.status != "OK":
        raise ApiError(422, run.status, run.result_snapshot.get("message") or run.status,
                       [{"calculation": "profit_plan", "trace": run.result_snapshot.get("trace", []), "run_id": str(run.id)}])
    return ok(out)


@router.get("/scenarios/{sid}/runs", response_model=Envelope[list[RunSummary]])
def list_runs(sid: uuid.UUID, ctx: Read, db: DB, limit: int = Query(default=20, ge=1, le=100)) -> Envelope:
    _scenario(db, ctx, sid)
    rows = db.scalars(select(SimulationRun).where(SimulationRun.scenario_id == sid).order_by(SimulationRun.created_at.desc()).limit(limit)).all()
    return ok([_summary(r) for r in rows], total=len(rows))


@router.get("/simulation-runs/{run_id}", response_model=Envelope[RunOut])
def read_run(run_id: uuid.UUID, ctx: Read, db: DB) -> Envelope:
    run = db.scalar(select(SimulationRun).where(SimulationRun.id == run_id, SimulationRun.organization_id == ctx.org_id))
    if run is None:
        raise not_found("Hasil simulasi")
    return ok(RunOut.model_validate(run))


@router.post("/scenarios/compare", response_model=Envelope[list[dict[str, Any]]])
def compare(body: CompareIn, ctx: Read, db: DB) -> Envelope:
    """Bandingkan skenario. rerun=true menjalankan ulang dengan data terbaru (perlu planning.write)."""
    if body.rerun:
        ctx.require("planning.write")
    out = []
    for sid in body.scenario_ids:
        s = _scenario(db, ctx, sid)
        run = _run(db, ctx, s) if body.rerun else _latest_run(db, s.id)
        entry: dict[str, Any] = {"scenario_id": str(s.id), "name": s.name, "scenario_type": s.scenario_type,
                                 "period_start": s.period_start.isoformat(), "period_months": s.period_months}
        if run is None:
            entry["status"] = "NOT_RUN"
        else:
            vals = run.result_snapshot.get("values", {})
            entry.update({
                "run_id": str(run.id),
                "status": run.status,
                "message": run.result_snapshot.get("message"),
                "pnl": vals.get("pnl"),
                "break_even": vals.get("break_even"),
                "target": vals.get("target"),
                "units": vals.get("units"),
                "warnings": run.result_snapshot.get("warnings", []),
            })
        out.append(entry)
    if body.rerun:
        db.commit()
    return ok(out)
