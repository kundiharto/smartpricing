"""Manajemen biaya, alokasi, skenario, simulasi, dan perbandingan lewat API.

Skenario sama dengan engine tests/test_planning.py sehingga angka harus identik.
"""

import pytest
from conftest import make_product, make_unit, make_user
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

APP_URL = "postgresql+psycopg://spe_app:spe_app_dev@localhost:5432/spe_test"


def costed(owner, sku, cost):
    pcs = owner._unit if hasattr(owner, "_unit") else make_unit(owner)
    owner._unit = pcs
    p = make_product(owner, sku, "TRADED_GOOD", pcs)
    owner.ok(owner.post(f"/products/{p['id']}/costing", {"costing_structure": "DIRECT_INPUT", "as_of_date": "2026-01-01",
                                                         "unit_cost": cost, "justification": "uji"}), 201)
    return p


def driver(owner, code, dtype):
    return owner.ok(owner.post("/cost-drivers", {"code": code, "name": code, "driver_type": dtype}), 201)["id"]


def cost(owner, body):
    return owner.ok(owner.post("/costs", body), 201)


@pytest.fixture
def model(owner):
    a = costed(owner, "A", "60000")
    b = costed(owner, "B", "20000")
    unit = driver(owner, "UNIT", "SALES_UNITS")
    prod = driver(owner, "PROD", "PRODUCTION_UNITS")
    start = "2026-01-01"
    cost(owner, {"code": "SEWA", "name": "Sewa", "category": "FIXED_OPERATING", "behavior_type": "FIXED",
                 "params": {"effective_from": start, "base_amount": "20000000"}})
    cost(owner, {"code": "KOMISI", "name": "Komisi", "category": "SELLING", "behavior_type": "PERCENTAGE",
                 "params": {"effective_from": start, "percentage": "0.05", "percentage_base": "REVENUE"}})
    cost(owner, {"code": "ONGKIR", "name": "Ongkir", "category": "DISTRIBUTION", "behavior_type": "VARIABLE", "driver_id": unit,
                 "params": {"effective_from": start, "rate": "2000"}})
    cost(owner, {"code": "OPERATOR", "name": "Operator", "category": "DIRECT_LABOR", "behavior_type": "STEP_FIXED", "driver_id": prod,
                 "params": {"effective_from": start, "step_mode": "TABLE", "tiers": [
                     {"from_activity": "0", "to_activity": "2000", "amount": "10000000"},
                     {"from_activity": "2001", "to_activity": "3000", "amount": "15000000"}]}})
    oh = cost(owner, {"code": "OH", "name": "Overhead pabrik", "category": "PRODUCTION_OVERHEAD", "behavior_type": "FIXED",
                      "cost_scope": "ALLOCATION_POOL", "params": {"effective_from": start, "base_amount": "6000000"}})
    cost(owner, {"code": "PENOLONG", "name": "Bahan penolong", "category": "DIRECT_MATERIAL", "behavior_type": "VARIABLE",
                 "cost_scope": "PRODUCT", "driver_id": prod, "params": {"effective_from": start, "rate": "500"}})
    owner.ok(owner.put(f"/costs/{oh["id"]}/allocation", {"basis": "DRIVER", "targets": [{"product_id": a["id"], "value": "2"}, {"product_id": b["id"], "value": "1"}]}))
    return {"a": a, "b": b, "oh": oh}


def scenario(owner, model, **assumptions):
    body = {
        "name": assumptions.pop("name", "Dasar"),
        "scenario_type": assumptions.pop("scenario_type", "BASE"),
        "period_start": "2026-06-01",
        "period_months": 1,
        "assumptions": assumptions,
        "lines": [
            {"product_id": model["a"]["id"], "unit_price": "100000", "volume": "1000"},
            {"product_id": model["b"]["id"], "unit_price": "50000", "volume": "1000"},
        ],
    }
    return owner.ok(owner.post("/scenarios", body), 201)


# --- Biaya ---------------------------------------------------------------------------


def test_cost_item_validation_by_engine(owner):
    unit = driver(owner, "UNIT", "SALES_UNITS")
    r = owner.post("/costs", {"code": "X", "name": "x", "category": "OTHER", "behavior_type": "VARIABLE",
                              "params": {"effective_from": "2026-01-01", "rate": "1"}})
    assert r.status_code == 422  # tanpa driver
    r = owner.post("/costs", {"code": "X", "name": "x", "category": "OTHER", "behavior_type": "STEP_FIXED", "driver_id": unit,
                              "params": {"effective_from": "2026-01-01", "step_mode": "TABLE", "tiers": [
                                  {"from_activity": "0", "to_activity": "100", "amount": "1"},
                                  {"from_activity": "50", "to_activity": "200", "amount": "2"}]}})
    assert r.status_code == 422
    assert "tumpang tindih" in r.json()["error"]["message"]


def test_cost_versions_are_effective_dated(owner):
    item = cost(owner, {"code": "SEWA", "name": "Sewa", "category": "FIXED_OPERATING", "behavior_type": "FIXED",
                        "params": {"effective_from": "2026-01-01", "base_amount": "20000000"}})
    upd = owner.ok(owner.post(f"/costs/{item['id']}/versions", {"effective_from": "2026-07-01", "base_amount": "22000000"}), 201)
    assert [(v["version_number"], v["effective_to"]) for v in upd["versions"]] == [(2, None), (1, "2026-07-01")]
    early = owner.post(f"/costs/{item['id']}/versions", {"effective_from": "2026-03-01", "base_amount": "1"})
    assert early.status_code == 409
    june = owner.ok(owner.post("/costs/preview", {"as_of_date": "2026-06-15"}))
    july = owner.ok(owner.post("/costs/preview", {"as_of_date": "2026-07-15"}))
    assert june["values"]["total"] == "20000000"
    assert july["values"]["total"] == "22000000"


def test_cost_version_immutable_in_database(owner):
    item = cost(owner, {"code": "SEWA", "name": "Sewa", "category": "FIXED_OPERATING", "behavior_type": "FIXED",
                        "params": {"effective_from": "2026-01-01", "base_amount": "20000000"}})
    engine = create_engine(APP_URL)
    with pytest.raises(DBAPIError, match="immutable"):
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.current_org_id', :o, true)"), {"o": owner.org_id})
            conn.execute(text("UPDATE cost_item_versions SET base_amount = 1 WHERE cost_item_id = :i"), {"i": item["id"]})
    engine.dispose()


def test_allocation_validation(owner, model):
    bad = owner.put(f"/costs/{model["oh"]["id"]}/allocation", {"basis": "PERCENTAGE", "targets": [
        {"product_id": model["a"]["id"], "value": "0.5"}, {"product_id": model["b"]["id"], "value": "0.4"}]})
    assert bad.status_code == 422
    sewa = next(c for c in owner.ok(owner.get("/costs")) if c["code"] == "SEWA")
    assert owner.put(f"/costs/{sewa["id"]}/allocation", {"basis": "EQUAL"}).status_code == 422  # bukan pool
    detail = owner.ok(owner.get(f"/costs/{model['oh']['id']}"))
    assert detail["allocation"]["basis"] == "DRIVER"


def test_cost_preview_step_tier(owner, model):
    r = owner.ok(owner.post("/costs/preview", {"as_of_date": "2026-06-01", "units": "2500", "revenue": "150000000"}))
    rows = {c["code"]: c for c in r["values"]["items"]}
    assert rows["OPERATOR"]["total"] == "15000000"
    assert "PENOLONG" not in rows
    assert r["excluded_product_scope"] == ["PENOLONG"]


# --- Skenario ------------------------------------------------------------------------


def test_scenario_run_matches_engine(owner, model):
    s = scenario(owner, model, tax_regime="PROFIT_BASED", tax_rate="0.22", target_kind="OPERATING_PROFIT", target_amount="50000000")
    run = owner.ok(owner.post(f"/scenarios/{s['id']}/run"), 201)
    v = run["result_snapshot"]["values"]
    assert v["pnl"]["revenue"] == "150000000"
    assert v["pnl"]["fixed_costs"] == "36000000"
    assert v["pnl"]["operating_profit"] == "22500000"
    assert v["pnl"]["net_profit"] == "17550000"
    assert v["break_even"]["units"] == "1231"
    assert v["target"]["units"] == "3112"
    assert v["excluded_product_scope"] == ["PENOLONG"]
    rows = {r["product"]: r for r in v["lines"]}
    assert rows[model["a"]["id"]]["profit_after_allocation"] == "29000000"
    assert run["result_snapshot"]["products"][model["a"]["id"]]["sku"] == "A"
    assert len(run["input_snapshot"]["cost_versions"]) == 6
    latest = owner.ok(owner.get(f"/scenarios/{s['id']}"))["latest_run"]
    assert latest["operating_profit"] == "22500000"


def test_scenario_requires_costing(owner):
    pcs = make_unit(owner)
    p = make_product(owner, "TANPA", "TRADED_GOOD", pcs)
    s = owner.ok(owner.post("/scenarios", {"name": "X", "period_start": "2026-06-01",
                                           "lines": [{"product_id": p["id"], "unit_price": "100", "volume": "10"}]}), 201)
    r = owner.post(f"/scenarios/{s['id']}/run")
    assert r.status_code == 422
    assert "TANPA" in r.json()["error"]["message"]
    # dengan biaya manual (override) bisa dijalankan
    owner.ok(owner.patch(f"/scenarios/{s['id']}", {"row_version": s["row_version"],
                                                  "lines": [{"product_id": p["id"], "unit_price": "100", "volume": "10", "unit_cost_override": "60"}]}))
    run = owner.ok(owner.post(f"/scenarios/{s['id']}/run"), 201)
    assert run["result_snapshot"]["values"]["pnl"]["gross_profit"] == "400"


def test_duplicate_and_compare(owner, model):
    base = scenario(owner, model)
    dup = owner.ok(owner.post(f"/scenarios/{base['id']}/duplicate", {"name": "Volume +10%", "scenario_type": "OPTIMISTIC"}), 201)
    assert dup["base_scenario_id"] == base["id"]
    assert len(dup["lines"]) == 2
    a = dict(dup["assumptions"], volume_change="0.10")
    owner.ok(owner.patch(f"/scenarios/{dup['id']}", {"row_version": dup["row_version"], "assumptions": a}))
    pess = owner.ok(owner.post(f"/scenarios/{base['id']}/duplicate", {"name": "Bahan +8%", "scenario_type": "PESSIMISTIC"}), 201)
    owner.ok(owner.patch(f"/scenarios/{pess['id']}", {"row_version": pess["row_version"],
                                                     "assumptions": dict(pess["assumptions"], unit_cost_change="0.08")}))
    cmp = owner.ok(owner.post("/scenarios/compare", {"scenario_ids": [base["id"], dup["id"], pess["id"]]}))
    ops = {c["name"]: c["pnl"]["operating_profit"] for c in cmp}
    assert ops == {"Dasar": "22500000", "Volume +10%": "23350000", "Bahan +8%": "16100000"}


def test_runs_are_append_only(owner, model):
    s = scenario(owner, model)
    owner.ok(owner.post(f"/scenarios/{s['id']}/run"), 201)
    owner.ok(owner.post(f"/scenarios/{s['id']}/run"), 201)
    runs = owner.ok(owner.get(f"/scenarios/{s['id']}/runs"))
    assert len(runs) == 2
    engine = create_engine(APP_URL)
    with pytest.raises(DBAPIError, match="permission denied"):
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.current_org_id', :o, true)"), {"o": owner.org_id})
            conn.execute(text("UPDATE simulation_runs SET status = 'X'"))
    engine.dispose()


def test_planning_permissions(client, owner, model):
    sales = make_user(client)
    owner.ok(owner.post(f"/organizations/{owner.org_id}/members", {"email": sales.email, "role_codes": ["SALES_MANAGER"]}), 201)
    sales.org_id = owner.org_id
    s = scenario(owner, model)
    assert sales.get("/scenarios").status_code == 200
    assert sales.post(f"/scenarios/{s['id']}/run").status_code == 403
    assert sales.get("/costs").status_code == 403
    assert sales.post("/scenarios/compare", {"scenario_ids": [s["id"], s["id"]], "rerun": True}).status_code == 403


def test_scenario_isolated_between_orgs(client, owner, model):
    s = scenario(owner, model)
    other = make_user(client)
    from conftest import make_org

    make_org(other)
    assert other.get(f"/scenarios/{s['id']}").status_code == 404
    assert other.ok(other.get("/costs")) == []
