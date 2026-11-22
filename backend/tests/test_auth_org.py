from conftest import make_org, make_user


def test_register_login_me(client):
    api = make_user(client, email="ani@example.com")
    me = api.ok(api.get("/auth/me"))
    assert me["user"]["email"] == "ani@example.com"
    assert me["memberships"] == []
    assert "password_hash" not in me["user"]


def test_duplicate_email_rejected(client):
    make_user(client, email="dup@example.com")
    r = client.post("/api/v1/auth/register", json={"email": "DUP@example.com", "password": "rahasia-uji-123", "full_name": "X"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


def test_login_failures_are_indistinguishable(client):
    make_user(client, email="budi@example.com")
    wrong_pw = client.post("/api/v1/auth/login", json={"email": "budi@example.com", "password": "salah-salah-1"})
    no_user = client.post("/api/v1/auth/login", json={"email": "tidakada@example.com", "password": "salah-salah-1"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["error"] == no_user.json()["error"]


def test_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["success"] is False
    assert r.headers["X-Request-Id"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer palsu"}).status_code == 401


def test_create_hybrid_organization(client):
    api = make_user(client)
    org_id = make_org(api, slug="pt-hybrid", models=["MANUFACTURING", "TRADING"])
    org = api.ok(api.get(f"/organizations/{org_id}"))
    assert org["is_hybrid"] is True
    assert org["business_models"] == ["MANUFACTURING", "TRADING"]
    assert org["primary_business_model"] == "MANUFACTURING"
    assert org["my_roles"] == ["OWNER"]
    me = api.ok(api.get("/auth/me"))
    assert me["memberships"][0]["roles"] == ["OWNER"]


def test_primary_model_must_be_listed(client):
    api = make_user(client)
    r = api.post("/organizations", {"name": "X", "slug": "x-org", "business_models": ["TRADING"], "primary_business_model": "RETAIL"})
    assert r.status_code == 422


def test_optimistic_concurrency(owner):
    org = owner.ok(owner.get(f"/organizations/{owner.org_id}"))
    updated = owner.ok(owner.patch(f"/organizations/{owner.org_id}", {"row_version": org["row_version"], "name": "PT Baru"}))
    assert updated["name"] == "PT Baru"
    assert updated["row_version"] == org["row_version"] + 1
    stale = owner.patch(f"/organizations/{owner.org_id}", {"row_version": org["row_version"], "name": "PT Lama"})
    assert stale.status_code == 409


def test_audit_log_records_changes(owner):
    owner.ok(owner.patch(f"/organizations/{owner.org_id}", {"row_version": 1, "name": "PT Audit"}))
    logs = owner.ok(owner.get("/audit-logs", params={"entity_type": "organization"}))
    actions = [l["action"] for l in logs]
    assert actions == ["UPDATE", "CREATE"]
    assert logs[0]["old_values"]["name"] == "PT Uji"
    assert logs[0]["new_values"]["name"] == "PT Audit"
    assert logs[0]["request_id"]


def test_login_rate_limited_per_email(client):
    make_user(client, email="target@example.com")
    for _ in range(9):  # make_user sudah login sekali
        assert client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "salah-salah-1"}).status_code == 401
    r = client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "rahasia-uji-123"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    # email lain tidak terdampak
    assert client.post("/api/v1/auth/login", json={"email": "lain@example.com", "password": "x"}).status_code == 401


def test_production_settings_guard():
    import pytest

    from app.core.config import Settings

    with pytest.raises(RuntimeError, match="JWT"):
        Settings(environment="production").validate_for_runtime()
    with pytest.raises(RuntimeError, match="development"):
        Settings(environment="production", jwt_secret="x" * 40).validate_for_runtime()
    Settings(
        environment="production",
        jwt_secret="x" * 40,
        database_url="postgresql+psycopg://app:secret@db.example.com/app?sslmode=require",
        migration_database_url="postgresql+psycopg://owner:secret@db.example.com/app?sslmode=require",
    ).validate_for_runtime()
