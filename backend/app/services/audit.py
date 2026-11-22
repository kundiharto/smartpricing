"""Audit trail (append-only)."""

from __future__ import annotations

import uuid
from typing import Any

from pricing_engine.core import canonical
from sqlalchemy.orm import Session

from app.core.request_context import current_request_id
from app.models import AuditLog


def snapshot(obj: Any, fields: list[str]) -> dict[str, Any]:
    return canonical({f: getattr(obj, f) for f in fields})


def record(
    db: Session,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            organization_id=org_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=canonical(old) if old is not None else None,
            new_values=canonical(new) if new is not None else None,
            request_id=current_request_id() or None,
        )
    )
