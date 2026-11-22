from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select, text

from app.api.deps import DB, CurrentUser, OrgContext, load_org_context
from app.core.db import set_context
from app.core.errors import ApiError, conflict, not_found
from app.models import MemberRole, Organization, OrganizationBusinessModel, OrganizationMember, Role, User
from app.schemas import (
    Envelope,
    MemberAdd,
    MemberOut,
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
    ok,
)
from app.services import audit

router = APIRouter(prefix="/organizations", tags=["organizations"])

ORG_FIELDS = ["name", "slug", "default_currency", "default_language", "fiscal_year_start_month", "timezone", "status"]


def _org_out(db: DB, org: Organization, roles: frozenset[str] | list[str]) -> OrganizationOut:
    models = db.execute(
        select(OrganizationBusinessModel.business_model, OrganizationBusinessModel.is_primary).where(
            OrganizationBusinessModel.organization_id == org.id
        )
    ).all()
    out = OrganizationOut.model_validate(org)
    out.business_models = sorted(m.business_model for m in models)
    out.primary_business_model = next((m.business_model for m in models if m.is_primary), None)
    out.is_hybrid = len(models) > 1
    out.my_roles = sorted(roles)
    return out


def _roles_for(db: DB, member_id: uuid.UUID) -> list[str]:
    return sorted(
        db.scalars(select(Role.code).join(MemberRole, MemberRole.role_id == Role.id).where(MemberRole.member_id == member_id))
    )


@router.get("", response_model=Envelope[list[OrganizationOut]])
def list_organizations(user: CurrentUser, db: DB) -> Envelope:
    rows = db.execute(
        select(Organization, OrganizationMember.id)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id, OrganizationMember.status == "ACTIVE")
        .order_by(Organization.name)
    ).all()
    return ok([_org_out(db, org, _roles_for(db, member_id)) for org, member_id in rows], total=len(rows))


@router.post("", response_model=Envelope[OrganizationOut], status_code=201)
def create_organization(body: OrganizationCreate, user: CurrentUser, db: DB) -> Envelope:
    if body.primary_business_model not in body.business_models:
        raise ApiError(422, "VALIDATION_ERROR", "primary_business_model harus termasuk dalam business_models")
    org_id = uuid.uuid4()
    set_context(db, org_id=org_id)
    org = Organization(
        id=org_id,
        name=body.name,
        slug=body.slug,
        default_currency=body.default_currency,
        default_language=body.default_language,
        fiscal_year_start_month=body.fiscal_year_start_month,
        timezone=body.timezone,
        created_by=user.id,
    )
    db.add(org)
    db.flush()
    for bm in body.business_models:
        db.add(OrganizationBusinessModel(organization_id=org_id, business_model=bm, is_primary=bm == body.primary_business_model))
    member = OrganizationMember(organization_id=org_id, user_id=user.id)
    db.add(member)
    db.flush()
    owner_role = db.scalar(select(Role.id).where(Role.code == "OWNER", Role.organization_id.is_(None)))
    db.add(MemberRole(organization_id=org_id, member_id=member.id, role_id=owner_role))
    db.flush()
    db.refresh(org)
    audit.record(
        db, org_id=org_id, user_id=user.id, action="CREATE", entity_type="organization", entity_id=org_id,
        new={**audit.snapshot(org, ORG_FIELDS), "business_models": body.business_models},
    )
    out = _org_out(db, org, ["OWNER"])
    db.commit()
    return ok(out)


@router.get("/{org_id}", response_model=Envelope[OrganizationOut])
def get_organization(org_id: uuid.UUID, user: CurrentUser, db: DB) -> Envelope:
    ctx = load_org_context(db, user, org_id)
    ctx.require("org.read")
    org = db.get(Organization, org_id)
    if org is None:
        raise not_found("Organisasi")
    return ok(_org_out(db, org, ctx.role_codes))


@router.patch("/{org_id}", response_model=Envelope[OrganizationOut])
def update_organization(org_id: uuid.UUID, body: OrganizationUpdate, user: CurrentUser, db: DB) -> Envelope:
    ctx = load_org_context(db, user, org_id)
    ctx.require("org.manage")
    org = db.get(Organization, org_id, with_for_update=True)
    if org is None:
        raise not_found("Organisasi")
    if org.row_version != body.row_version:
        raise conflict("Data telah diubah oleh pengguna lain; muat ulang lalu coba lagi")
    old = audit.snapshot(org, ORG_FIELDS)
    for field, value in body.model_dump(exclude_unset=True, exclude={"row_version"}).items():
        if value is not None:
            setattr(org, field, value)
    org.row_version += 1
    db.flush()
    db.refresh(org)
    audit.record(db, org_id=org_id, user_id=user.id, action="UPDATE", entity_type="organization", entity_id=org_id,
                 old=old, new=audit.snapshot(org, ORG_FIELDS))
    out = _org_out(db, org, ctx.role_codes)
    db.commit()
    return ok(out)


def _members(db: DB, ctx: OrgContext) -> list[MemberOut]:
    rows = db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == ctx.org_id)
        .order_by(User.full_name)
    ).all()
    return [
        MemberOut(member_id=m.id, user_id=u.id, email=u.email, full_name=u.full_name, status=m.status, roles=_roles_for(db, m.id))
        for m, u in rows
    ]


@router.get("/{org_id}/members", response_model=Envelope[list[MemberOut]])
def list_members(org_id: uuid.UUID, user: CurrentUser, db: DB) -> Envelope:
    ctx = load_org_context(db, user, org_id)
    ctx.require("org.read")
    members = _members(db, ctx)
    return ok(members, total=len(members))


@router.post("/{org_id}/members", response_model=Envelope[MemberOut], status_code=201)
def add_member(org_id: uuid.UUID, body: MemberAdd, user: CurrentUser, db: DB) -> Envelope:
    ctx = load_org_context(db, user, org_id)
    ctx.require("members.manage")
    target_id = db.scalar(text("SELECT auth_find_user_id(:e)"), {"e": body.email})
    if target_id is None:
        raise ApiError(404, "USER_NOT_REGISTERED", "Pengguna dengan email ini belum terdaftar")
    roles = db.execute(select(Role.id, Role.code).where(Role.code.in_(body.role_codes))).all()
    missing = set(body.role_codes) - {r.code for r in roles}
    if missing:
        raise ApiError(422, "VALIDATION_ERROR", f"Role tidak dikenal: {', '.join(sorted(missing))}")
    if "OWNER" in body.role_codes and "OWNER" not in ctx.role_codes:
        raise ApiError(403, "FORBIDDEN", "Hanya Owner yang dapat menunjuk Owner lain")
    member = OrganizationMember(organization_id=org_id, user_id=target_id)
    db.add(member)
    db.flush()
    for r in roles:
        db.add(MemberRole(organization_id=org_id, member_id=member.id, role_id=r.id))
    db.flush()
    audit.record(db, org_id=org_id, user_id=user.id, action="ADD_MEMBER", entity_type="organization_member",
                 entity_id=member.id, new={"user_id": target_id, "roles": sorted(body.role_codes)})
    out = next(m for m in _members(db, ctx) if m.member_id == member.id)
    db.commit()
    return ok(out)
