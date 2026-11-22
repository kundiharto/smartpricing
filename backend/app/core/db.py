"""Koneksi database dan konteks tenant untuk Row-Level Security.

Setiap transaksi otomatis menjalankan set_config('app.current_user_id' / 'app.current_org_id', …, true)
dari `session.info`, sehingga policy RLS berlaku walaupun ada commit di tengah request.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_SET_CONTEXT = text(
    "SELECT set_config('app.current_user_id', :user_id, true), set_config('app.current_org_id', :org_id, true)"
)


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=True)


def _context_params(session: Session) -> dict[str, str]:
    user_id = session.info.get("user_id")
    org_id = session.info.get("org_id")
    return {"user_id": str(user_id) if user_id else "", "org_id": str(org_id) if org_id else ""}


@event.listens_for(Session, "after_begin")
def _apply_tenant_context(session: Session, transaction, connection) -> None:  # noqa: ANN001
    connection.execute(_SET_CONTEXT, _context_params(session))


def set_context(session: Session, *, user_id: uuid.UUID | None = None, org_id: uuid.UUID | None = None) -> None:
    """Mengatur identitas pengguna/organisasi untuk transaksi berjalan dan berikutnya."""
    if user_id is not None:
        session.info["user_id"] = user_id
    if org_id is not None:
        session.info["org_id"] = org_id
    session.execute(_SET_CONTEXT, _context_params(session))


def get_db() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.rollback()  # transaksi yang tidak di-commit eksplisit selalu dibatalkan
        session.close()
