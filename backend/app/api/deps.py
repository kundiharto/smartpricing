"""Dependency: autentikasi, konteks organisasi, dan RBAC."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db, set_context
from app.core.errors import ApiError, forbidden
from app.core.security import decode_access_token
from app.models import MemberRole, OrganizationMember, Permission, Role, RolePermission, User

_bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def current_user(
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "UNAUTHORIZED", "Token akses diperlukan")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise ApiError(401, "UNAUTHORIZED", "Token tidak valid atau kedaluwarsa")
    set_context(db, user_id=user_id)
    user = db.get(User, user_id)
    if user is None or user.status != "ACTIVE":
        raise ApiError(401, "UNAUTHORIZED", "Akun tidak aktif")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


@dataclass(frozen=True)
class OrgContext:
    user_id: uuid.UUID
    org_id: uuid.UUID
    member_id: uuid.UUID
    role_codes: frozenset[str]
    permissions: frozenset[str]

    def require(self, permission: str) -> None:
        if permission not in self.permissions:
            raise forbidden(f"Izin '{permission}' diperlukan")


def load_org_context(db: Session, user: User, org_id: uuid.UUID) -> OrgContext:
    """organization_id dari klien tidak dipercaya: keanggotaan aktif selalu diverifikasi (PRD §9.11)."""
    set_context(db, org_id=org_id)
    member = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.status == "ACTIVE",
        )
    )
    if member is None:
        raise forbidden("Anda bukan anggota aktif organisasi ini")
    roles = db.scalars(
        select(Role.code).join(MemberRole, MemberRole.role_id == Role.id).where(MemberRole.member_id == member.id)
    ).all()
    perms = db.scalars(
        select(Permission.permission_key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(MemberRole, MemberRole.role_id == RolePermission.role_id)
        .where(MemberRole.member_id == member.id)
    ).all()
    return OrgContext(user.id, org_id, member.id, frozenset(roles), frozenset(perms))


def org_context(
    db: DB,
    user: CurrentUser,
    x_organization_id: Annotated[uuid.UUID, Header(description="ID organisasi aktif")],
) -> OrgContext:
    return load_org_context(db, user, x_organization_id)


def require(permission: str) -> Callable[..., OrgContext]:
    def dependency(ctx: Annotated[OrgContext, Depends(org_context)]) -> OrgContext:
        ctx.require(permission)
        return ctx

    dependency.__name__ = f"require_{permission.replace('.', '_')}"
    return dependency
