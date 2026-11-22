"""Tes integrasi terhadap PostgreSQL `spe_test` (role aplikasi spe_app, RLS aktif)."""

from __future__ import annotations

import os
import uuid
import warnings
from collections.abc import Iterator
from typing import Any

os.environ["SPE_ENVIRONMENT"] = "test"
os.environ["SPE_DATABASE_URL"] = "postgresql+psycopg://spe_app:spe_app_dev@localhost:5432/spe_test"
os.environ["SPE_MIGRATION_DATABASE_URL"] = "postgresql+psycopg://spe_owner:spe_owner_dev@localhost:5432/spe_test"
# Koneksi superuser lokal hanya untuk membersihkan data dan tes tingkat database.
ADMIN_URL = os.environ.get("SPE_TEST_ADMIN_URL", "postgresql+psycopg:///spe_test")

warnings.filterwarnings("ignore", message=".*httpx2.*")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.main import app  # noqa: E402

TABLES = [
    "simulation_runs", "scenario_sales_lines", "scenarios", "cost_allocation_targets", "cost_allocation_rules",
    "cost_item_versions", "cost_items", "cost_drivers",
    "pricing_recommendations", "costing_versions", "bom_items", "bill_of_materials", "material_prices",
    "products", "units_of_measure", "product_categories", "audit_logs", "member_roles",
    "organization_members", "organization_business_models", "organizations", "users",
]


@pytest.fixture(scope="session")
def admin_engine():
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
    # Skema dibangun ulang dari nol setiap sesi: sekaligus menguji downgrade/upgrade migrasi.
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(ADMIN_URL)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_db(admin_engine) -> Iterator[None]:
    # DELETE berurutan, bukan TRUNCATE CASCADE: CASCADE ikut mengosongkan role & permission sistem.
    with admin_engine.begin() as conn:
        conn.execute(text("DELETE FROM member_roles"))
        conn.execute(text("DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE organization_id IS NOT NULL)"))
        conn.execute(text("DELETE FROM roles WHERE organization_id IS NOT NULL"))
        for table in TABLES:
            if table != "member_roles":
                conn.execute(text(f"DELETE FROM {table}"))
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class Api:
    """Pembantu: satu pengguna terautentikasi dengan organisasi aktif opsional."""

    def __init__(self, client: TestClient, token: str, user_id: str):
        self.client = client
        self.token = token
        self.user_id = user_id
        self.org_id: str | None = None

    def headers(self, org_id: str | None = None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.token}"}
        org = org_id or self.org_id
        if org:
            h["X-Organization-Id"] = org
        return h

    def get(self, path: str, org_id: str | None = None, **kw: Any):
        return self.client.get(f"/api/v1{path}", headers=self.headers(org_id), **kw)

    def post(self, path: str, json: Any = None, org_id: str | None = None):
        return self.client.post(f"/api/v1{path}", json=json, headers=self.headers(org_id))

    def patch(self, path: str, json: Any = None, org_id: str | None = None):
        return self.client.patch(f"/api/v1{path}", json=json, headers=self.headers(org_id))

    def put(self, path: str, json: Any = None, org_id: str | None = None):
        return self.client.put(f"/api/v1{path}", json=json, headers=self.headers(org_id))

    def delete(self, path: str, org_id: str | None = None):
        return self.client.delete(f"/api/v1{path}", headers=self.headers(org_id))

    def ok(self, response, status: int = 200) -> Any:
        assert response.status_code == status, response.json()
        body = response.json()
        assert body["success"] is True
        return body["data"]


def make_user(client: TestClient, email: str | None = None, password: str = "rahasia-uji-123") -> Api:
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Pengguna Uji"})
    assert r.status_code == 201, r.json()
    user_id = r.json()["data"]["id"]
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.json()
    api = Api(client, r.json()["data"]["access_token"], user_id)
    api.email = email  # type: ignore[attr-defined]
    return api


def make_org(api: Api, slug: str | None = None, models: list[str] | None = None) -> str:
    models = models or ["MANUFACTURING"]
    data = api.ok(
        api.post(
            "/organizations",
            {
                "name": "PT Uji",
                "slug": slug or f"org-{uuid.uuid4().hex[:8]}",
                "business_models": models,
                "primary_business_model": models[0],
            },
        ),
        201,
    )
    api.org_id = data["id"]
    return data["id"]


@pytest.fixture
def owner(client: TestClient) -> Api:
    api = make_user(client)
    make_org(api)
    return api


def make_unit(api: Api, code: str = "pcs", dimension: str = "COUNT") -> str:
    return api.ok(api.post("/units", {"code": code, "name": code, "dimension": dimension}), 201)["id"]


def make_product(api: Api, sku: str, product_type: str, unit_id: str, **extra: Any) -> dict[str, Any]:
    body = {"sku": sku, "name": sku, "product_type": product_type, "business_model": "MANUFACTURING",
            "base_unit_id": unit_id, **extra}
    return api.ok(api.post("/products", body), 201)
