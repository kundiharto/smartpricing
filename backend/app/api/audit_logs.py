from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import DB, OrgContext, require
from app.models import AuditLog
from app.schemas import AuditLogOut, Envelope, ok

router = APIRouter(tags=["audit"])


@router.get("/audit-logs", response_model=Envelope[list[AuditLogOut]])
def list_audit_logs(
    ctx: Annotated[OrgContext, Depends(require("audit.read"))],
    db: DB,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Envelope:
    stmt = select(AuditLog).where(AuditLog.organization_id == ctx.org_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id).limit(limit).offset(offset)).all()
    return ok([AuditLogOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)
