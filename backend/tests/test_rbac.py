from conftest import make_product, make_unit, make_user


def test_viewer_can_read_but_not_write(client, owner):
    unit = make_unit(owner)
    make_product(owner, "FG-1", "FINISHED_GOOD", unit)
    viewer = make_user(client)
    owner.ok(owner.post(f"/organizations/{owner.org_id}/members", {"email": viewer.email, "role_codes": ["VIEWER"]}), 201)
    viewer.org_id = owner.org_id

    assert [p["sku"] for p in viewer.ok(viewer.get("/products"))] == ["FG-1"]
    org = viewer.ok(viewer.get(f"/organizations/{owner.org_id}"))
    assert org["my_permissions"] == ["costing.read", "costs.read", "org.read", "planning.read", "pricing.read", "products.read"]
    r = viewer.post("/products", {"sku": "X", "name": "x", "product_type": "MATERIAL", "business_model": "MANUFACTURING",
                                  "base_unit_id": unit})
    assert r.status_code == 403
    assert "products.write" in r.json()["error"]["message"]
    assert viewer.get("/audit-logs").status_code == 403
    assert viewer.post("/pricing/calculate", {"method": "MARKUP", "unit_cost": "100", "markup": "0.2"}).status_code == 403


def test_sales_manager_can_calculate_but_not_recommend(client, owner):
    sales = make_user(client)
    owner.ok(owner.post(f"/organizations/{owner.org_id}/members", {"email": sales.email, "role_codes": ["SALES_MANAGER"]}), 201)
    sales.org_id = owner.org_id
    data = sales.ok(sales.post("/pricing/calculate", {"method": "MARKUP", "unit_cost": "60000", "markup": "0.25"}))
    assert data["recommended_price"] == "75000"
    r = sales.post("/pricing/recommend", {"method": "MARKUP", "product_id": owner.org_id, "markup": "0.25",
                                          "effective_date": "2026-12-01"})
    assert r.status_code == 403


def test_only_owner_can_appoint_owner(client, owner):
    fm = make_user(client)
    owner.ok(owner.post(f"/organizations/{owner.org_id}/members", {"email": fm.email, "role_codes": ["FINANCE_MANAGER"]}), 201)
    fm.org_id = owner.org_id
    other = make_user(client)
    # Finance Manager tidak punya members.manage
    assert fm.post(f"/organizations/{owner.org_id}/members", {"email": other.email, "role_codes": ["VIEWER"]}).status_code == 403


def test_add_unknown_user_or_role(client, owner):
    r = owner.post(f"/organizations/{owner.org_id}/members", {"email": "tidakada@example.com", "role_codes": ["VIEWER"]})
    assert r.status_code == 404
    someone = make_user(client)
    r = owner.post(f"/organizations/{owner.org_id}/members", {"email": someone.email, "role_codes": ["SUPERHERO"]})
    assert r.status_code == 422


def test_members_list(client, owner):
    other = make_user(client)
    owner.ok(owner.post(f"/organizations/{owner.org_id}/members", {"email": other.email, "role_codes": ["DIRECTOR", "VIEWER"]}), 201)
    members = owner.ok(owner.get(f"/organizations/{owner.org_id}/members"))
    roles = {m["email"]: m["roles"] for m in members}
    assert roles[other.email] == ["DIRECTOR", "VIEWER"]
