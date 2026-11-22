from decimal import Decimal

from conftest import make_product, make_unit


def test_calculate_stateless_PRC_05(owner):
    data = owner.ok(
        owner.post(
            "/pricing/calculate",
            {"method": "TARGET_CONTRIBUTION_MARGIN", "unit_cost": "60000", "target_margin": "0.30", "discount": "0.20",
             "fees": [{"name": "marketplace", "rate": "0.10"}]},
        )
    )
    assert data["recommended_price"] == "100000"
    assert data["list_price"] == "125000"
    assert data["contribution_margin"] == "0.3"
    assert data["warnings"] == []
    assert data["engine"]["price"]["trace"]


def test_calculate_with_rounding_guard_RND_02(owner):
    data = owner.ok(
        owner.post(
            "/pricing/calculate",
            {"method": "TARGET_GROSS_MARGIN", "unit_cost": "60000", "target_margin": "0.30",
             "rounding": {"increment": "500", "mode": "NEAREST"}},
        )
    )
    assert data["list_price"] == "86000"
    assert data["engine"]["rounding"]["values"]["rounded_before_guard"] == "85500"
    assert data["engine"]["rounding"]["values"]["guard_applied"] is True


def test_infeasible_margin_is_explained(owner):
    r = owner.post("/pricing/calculate", {"method": "TARGET_CONTRIBUTION_MARGIN", "unit_cost": "60000",
                                          "target_margin": "0.60", "fees": [{"name": "fee", "rate": "0.45"}]})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "INFEASIBLE_MARGIN"
    assert err["details"][0]["trace"]


def test_float_rejected(owner):
    r = owner.post("/pricing/calculate", {"method": "MARKUP", "unit_cost": 60000.0, "markup": "0.25"})
    assert r.status_code == 422


def _costed_product(owner):
    pcs = make_unit(owner)
    p = make_product(owner, "TG-1", "TRADED_GOOD", pcs)
    owner.ok(owner.post(f"/products/{p['id']}/costing", {"costing_structure": "DIRECT_INPUT", "as_of_date": "2026-11-22",
                                                         "unit_cost": "60000", "justification": "harga beli kontrak"}), 201)
    return p


def test_direct_input_requires_justification(owner):
    pcs = make_unit(owner)
    p = make_product(owner, "TG-2", "TRADED_GOOD", pcs)
    r = owner.post(f"/products/{p['id']}/costing", {"costing_structure": "DIRECT_INPUT", "as_of_date": "2026-11-22", "unit_cost": "1"})
    assert r.status_code == 422


def test_recommend_stores_snapshot(owner):
    p = _costed_product(owner)
    rec = owner.ok(
        owner.post(
            "/pricing/recommend",
            {"method": "TARGET_CONTRIBUTION_MARGIN", "product_id": p["id"], "target_margin": "0.30", "discount": "0.20",
             "fees": [{"name": "marketplace", "rate": "0.10"}], "effective_date": "2026-12-01",
             "rounding": {"increment": "1000", "mode": "UP"}},
        ),
        201,
    )
    assert rec["status"] == "DRAFT"
    assert rec["target_price"] == "100000.0000"
    assert rec["list_price"] == "125000.0000"
    assert rec["recommended_price"] == "100000.0000"
    assert rec["margin_definition"] == "CONTRIBUTION"
    assert rec["expected_contribution_margin"] == "0.300000"
    assert rec["input_snapshot"]["engine_inputs"]["unit_cost"] == "60000"
    assert rec["calculation_snapshot"]["engine"]["price"]["engine_version"] == rec["engine_version"]

    listed = owner.ok(owner.get("/pricing/recommendations", params={"product_id": p["id"]}))
    assert [r["id"] for r in listed] == [rec["id"]]
    assert listed[0]["unit_cost"] == "60000"
    logs = owner.ok(owner.get("/audit-logs", params={"entity_type": "pricing_recommendation"}))
    assert logs[0]["entity_id"] == rec["id"]


def test_recommend_rounding_on_list_keeps_margin(owner):
    p = _costed_product(owner)
    rec = owner.ok(
        owner.post(
            "/pricing/recommend",
            {"method": "TARGET_CONTRIBUTION_MARGIN", "product_id": p["id"], "target_margin": "0.30", "discount": "0.15",
             "fees": [{"name": "marketplace", "rate": "0.10"}], "effective_date": "2026-12-01",
             "rounding": {"increment": "500", "mode": "NEAREST", "apply_to": "LIST_PRICE"}},
        ),
        201,
    )
    # target list = 100000 / 0.85 = 117647.06 → NEAREST 117500 < target → guard → 118000
    assert rec["list_price"] == "118000.0000"
    assert rec["recommended_price"] == "100300.0000"
    assert Decimal(rec["expected_contribution_margin"]) >= Decimal("0.30")
    assert rec["warnings"] == []


def test_recommend_requires_active_costing(owner):
    pcs = make_unit(owner)
    p = make_product(owner, "TG-3", "TRADED_GOOD", pcs)
    r = owner.post("/pricing/recommend", {"method": "MARKUP", "product_id": p["id"], "markup": "0.2", "effective_date": "2026-12-01"})
    assert r.status_code == 422
    assert "costing" in r.json()["error"]["message"]
