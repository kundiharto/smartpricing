"""Isolasi tenant: API, RLS di database, dan composite foreign key (DATABASE_SPEC §1.4)."""

import pytest
from conftest import make_org, make_product, make_unit, make_user
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

APP_URL = "postgresql+psycopg://spe_app:spe_app_dev@localhost:5432/spe_test"


@pytest.fixture
def two_orgs(client):
    a = make_user(client)
    make_org(a)
    b = make_user(client)
    make_org(b)
    unit_a = make_unit(a)
    unit_b = make_unit(b)
    prod_a = make_product(a, "A-001", "FINISHED_GOOD", unit_a)
    prod_b = make_product(b, "B-001", "FINISHED_GOOD", unit_b)
    return a, b, prod_a, prod_b, unit_a, unit_b


def test_non_member_cannot_use_other_org_header(two_orgs):
    a, b, prod_a, *_ = two_orgs
    r = b.get("/products", org_id=a.org_id)
    assert r.status_code == 403
    assert b.get(f"/organizations/{a.org_id}").status_code == 403


def test_product_of_other_org_not_found(two_orgs):
    a, b, prod_a, *_ = two_orgs
    assert b.get(f"/products/{prod_a['id']}").status_code == 404


def test_list_only_own_products(two_orgs):
    a, b, *_ = two_orgs
    assert [p["sku"] for p in a.ok(a.get("/products"))] == ["A-001"]
    assert [p["sku"] for p in b.ok(b.get("/products"))] == ["B-001"]


def test_cannot_reference_other_org_unit_via_api(two_orgs):
    a, b, prod_a, prod_b, unit_a, unit_b = two_orgs
    r = a.post("/products", {"sku": "A-X", "name": "x", "product_type": "MATERIAL", "business_model": "MANUFACTURING",
                             "base_unit_id": unit_b})
    assert r.status_code == 409


def test_rls_filters_rows_at_database_level(two_orgs):
    """Walaupun query tidak memfilter organization_id, RLS hanya menampilkan baris tenant aktif."""
    a, b, prod_a, prod_b, *_ = two_orgs
    engine = create_engine(APP_URL)
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.current_org_id', :o, true)"), {"o": a.org_id})
        skus = conn.scalars(text("SELECT sku FROM products")).all()
        assert skus == ["A-001"]
        assert conn.scalar(text("SELECT count(*) FROM audit_logs WHERE organization_id = :b"), {"b": b.org_id}) == 0
    with engine.begin() as conn:
        # tanpa konteks organisasi: tidak ada baris sama sekali
        assert conn.scalar(text("SELECT count(*) FROM products")) == 0
    engine.dispose()


def test_rls_blocks_insert_into_other_org(two_orgs):
    a, b, prod_a, prod_b, unit_a, unit_b = two_orgs
    engine = create_engine(APP_URL)
    with pytest.raises(ProgrammingError, match="row-level security"):
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.current_org_id', :o, true)"), {"o": a.org_id})
            conn.execute(
                text("INSERT INTO units_of_measure (organization_id, code, name, dimension) VALUES (:b, 'kg', 'kg', 'MASS')"),
                {"b": b.org_id},
            )
    engine.dispose()


def test_app_role_cannot_delete_or_bypass(two_orgs):
    a, *_ = two_orgs
    engine = create_engine(APP_URL)
    with pytest.raises(ProgrammingError, match="permission denied"):
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.current_org_id', :o, true)"), {"o": a.org_id})
            conn.execute(text("DELETE FROM audit_logs"))
    engine.dispose()


def test_composite_fk_blocks_cross_tenant_reference_even_without_rls(admin_engine, two_orgs):
    """Superuser mengabaikan RLS, tetapi composite FK tetap menolak referensi lintas tenant."""
    a, b, prod_a, prod_b, unit_a, unit_b = two_orgs
    with pytest.raises(IntegrityError, match="foreign key"):
        with admin_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO products (organization_id, sku, name, product_type, business_model, base_unit_id) "
                    "VALUES (:a, 'X-1', 'x', 'MATERIAL', 'MANUFACTURING', :unit_b)"
                ),
                {"a": a.org_id, "unit_b": unit_b},
            )
