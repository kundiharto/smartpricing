from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from sqlalchemy import select, text

from app.api.deps import DB, CurrentUser
from app.core.db import set_context
from app.core.errors import ApiError, conflict
from app.core.rate_limit import client_ip, login_by_email, login_by_ip, register_by_ip
from app.core.security import create_access_token, hash_password, verify_password
from app.models import MemberRole, Organization, OrganizationMember, Role, User
from app.schemas import Envelope, LoginIn, MembershipOut, MeOut, RegisterIn, TokenOut, UserOut, ok

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Envelope[UserOut], status_code=201)
def register(body: RegisterIn, db: DB, request: Request) -> Envelope:
    register_by_ip.check(client_ip(request))
    if db.scalar(text("SELECT auth_email_exists(:e)"), {"e": body.email}):
        raise conflict("Email sudah terdaftar")
    user_id = uuid.uuid4()
    set_context(db, user_id=user_id)
    user = User(
        id=user_id,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        preferred_language=body.preferred_language,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    out = UserOut.model_validate(user)
    db.commit()
    return ok(out)


@router.post("/login", response_model=Envelope[TokenOut])
def login(body: LoginIn, db: DB, request: Request) -> Envelope:
    login_by_ip.check(client_ip(request))
    login_by_email.check(body.email.lower())
    row = db.execute(text("SELECT id, password_hash, status FROM auth_lookup_user(:e)"), {"e": body.email}).first()
    valid = verify_password(row.password_hash if row else None, body.password)
    if not row or not valid or row.status != "ACTIVE":
        raise ApiError(401, "INVALID_CREDENTIALS", "Email atau password salah")
    token, expires = create_access_token(row.id)
    return ok(TokenOut(access_token=token, expires_at=expires))


@router.post("/logout", response_model=Envelope[dict])
def logout(user: CurrentUser) -> Envelope:
    # Token stateless: klien wajib menghapus token. Daftar pencabutan token menyusul.
    return ok({"logged_out": True})


@router.get("/me", response_model=Envelope[MeOut])
def me(user: CurrentUser, db: DB) -> Envelope:
    rows = db.execute(
        select(Organization.id, Organization.name, OrganizationMember.id.label("member_id"))
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id, OrganizationMember.status == "ACTIVE")
        .order_by(Organization.name)
    ).all()
    memberships = []
    for r in rows:
        roles = db.scalars(
            select(Role.code).join(MemberRole, MemberRole.role_id == Role.id).where(MemberRole.member_id == r.member_id)
        ).all()
        memberships.append(MembershipOut(organization_id=r.id, organization_name=r.name, roles=sorted(roles)))
    return ok(MeOut(user=UserOut.model_validate(user), memberships=memberships))
