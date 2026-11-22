"""Produk, harga material berversi, BOM, dan costing tersimpan (cocok dengan engine MFG-04)."""

import pytest
from conftest import make_product, make_unit
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

APP_URL = "postgresql+psycopg://spe_app:spe_app_dev@localhost:5432/spe_test"

COSTING_BODY = {
    "costing_structure": "BOM_BASED",
    "as_of_date": "2026-11-22",
    "labor": [{"name": "operator", "hours": "40", "hourly_rate": "50000"}],
    "machines": [{"name": "mesin-1", "hours": "10", "hourly_rate": "150000"}],
    "overhead": "5000000",
    "packaging": "1000000",
    "scrap_rate": "0.05",
}


@pytest.fixture
def setup_bom(owner):
    pcs = make_unit(owner, "pcs")
    kg = make_unit(owner, "kg", "MASS")
    fg = make_product(owner, "FG-1", "FINISHED_GOOD", pcs)
    mat_a = make_product(owner, "MAT-A", "MATERIAL", kg)
    mat_b = make_product(owner, "MAT-B", "MATERIAL", pcs)
    owner.ok(owner.post(f"/products/{mat_a['id']}/material-prices", {"unit_price": "20000", "effective_from": "2026-01-01"}), 201)
    owner.ok(owner.post(f"/products/{mat_b['id']}/material-prices", {"unit_price": "3000", "effective_from": "2026-01-01"}), 201)
    owner.ok(
        owner.post(
            f"/products/{fg['id']}/bom",
            {
                "planned_output_qty": "1000",
                "effective_from": "2026-01-01",
                "items": [
                    {"material_product_id": mat_a["id"], "net_quantity": "500", "material_waste_rate": "0.04"},
                    {"material_product_id": mat_b["id"], "net_quantity": "1000"},
                ],
            },
        ),
        201,
    )
    return fg, mat_a, mat_b


def test_product_crud_and_archive(owner):
    unit = make_unit(owner)
    p = make_product(owner, "SKU-1", "TRADED_GOOD", unit, description="awal")
    updated = owner.ok(owner.patch(f"/products/{p['id']}", {"row_version": p["row_version"], "name": "Nama Baru"}))
    assert updated["name"] == "Nama Baru"
    assert owner.patch(f"/products/{p['id']}", {"row_version": p["row_version"], "name": "Lama"}).status_code == 409
    archived = owner.ok(owner.delete(f"/products/{p['id']}"))
    assert archived["status"] == "ARCHIVED"
    assert owner.ok(owner.get("/products")) == []
    assert len(owner.ok(owner.get("/products", params={"status": "ARCHIVED"}))) == 1
    assert owner.ok(owner.get(f"/products/{p['id']}"))["status"] == "ARCHIVED"


def test_product_search_and_pagination(owner):
    unit = make_unit(owner)
    for i in range(5):
        make_product(owner, f"KOPI-{i}", "TRADED_GOOD", unit)
    make_product(owner, "TEH-1", "TRADED_GOOD", unit)
    r = owner.get("/products", params={"q": "kopi", "limit": 2, "offset": 2, "sort": "sku"})
    body = r.json()
    assert body["meta"]["total"] == 5
    assert [p["sku"] for p in body["data"]] == ["KOPI-2", "KOPI-3"]


def test_duplicate_sku_conflict(owner):
    unit = make_unit(owner)
    make_product(owner, "DUP", "MATERIAL", unit)
    r = owner.post("/products", {"sku": "DUP", "name": "x", "product_type": "MATERIAL", "business_model": "MANUFACTURING",
                                 "base_unit_id": unit})
    assert r.status_code == 409


def test_material_price_versioning(owner):
    kg = make_unit(owner, "kg", "MASS")
    mat = make_product(owner, "MAT", "MATERIAL", kg)
    owner.ok(owner.post(f"/products/{mat['id']}/material-prices", {"unit_price": "20000", "effective_from": "2026-01-01"}), 201)
    owner.ok(owner.post(f"/products/{mat['id']}/material-prices", {"unit_price": "23000", "effective_from": "2026-07-01"}), 201)
    prices = owner.ok(owner.get(f"/products/{mat['id']}/material-prices"))
    assert [(p["unit_price"], p["effective_from"], p["effective_to"]) for p in prices] == [
        ("23000.0000", "2026-07-01", None),
        ("20000.0000", "2026-01-01", "2026-07-01"),
    ]
    backdated = owner.post(f"/products/{mat['id']}/material-prices", {"unit_price": "1", "effective_from": "2026-03-01"})
    assert backdated.status_code == 409


def test_material_price_only_for_materials(owner):
    unit = make_unit(owner)
    fg = make_product(owner, "FG", "FINISHED_GOOD", unit)
    assert owner.post(f"/products/{fg['id']}/material-prices", {"unit_price": "1", "effective_from": "2026-01-01"}).status_code == 422


def test_float_rejected(owner):
    kg = make_unit(owner, "kg", "MASS")
    mat = make_product(owner, "MAT", "MATERIAL", kg)
    r = owner.post(f"/products/{mat['id']}/material-prices", {"unit_price": 20000.5, "effective_from": "2026-01-01"})
    assert r.status_code == 422
    assert "float" in str(r.json()["error"]["details"])


def test_bom_costing_matches_engine_MFG_04(owner, setup_bom):
    fg, *_ = setup_bom
    cv = owner.ok(owner.post(f"/products/{fg['id']}/costing", COSTING_BODY), 201)
    assert cv["calculated_unit_cost"] == "24122.8070"
    assert cv["status"] == "ACTIVE"
    assert cv["version_number"] == 1
    assert len(cv["input_hash"]) == 64
    snap = cv["calculation_snapshot"]
    assert snap["status"] == "OK"
    assert snap["values"]["good_units"] == "950"
    assert cv["input_snapshot"]["context"]["bom_version"] == "1"
    assert [m["unit_price"] for m in cv["input_snapshot"]["context"]["material_prices"]] == ["20000", "3000"]


def test_new_costing_supersedes_and_keeps_history_HIS_02(owner, setup_bom):
    fg, mat_a, _ = setup_bom
    v1 = owner.ok(owner.post(f"/products/{fg['id']}/costing", COSTING_BODY), 201)
    owner.ok(owner.post(f"/products/{mat_a['id']}/material-prices", {"unit_price": "23000", "effective_from": "2026-12-01"}), 201)
    v2 = owner.ok(owner.post(f"/products/{fg['id']}/costing", {**COSTING_BODY, "as_of_date": "2026-12-15"}), 201)
    assert v2["version_number"] == 2
    assert v2["calculated_unit_cost"] != v1["calculated_unit_cost"]

    versions = owner.ok(owner.get(f"/products/{fg['id']}/costing"))
    assert [(v["version_number"], v["status"]) for v in versions] == [(2, "ACTIVE"), (1, "SUPERSEDED")]
    old = owner.ok(owner.get(f"/products/{fg['id']}/costing/{v1['id']}"))
    assert old["calculated_unit_cost"] == "24122.8070"  # nilai lama tidak berubah
    assert old["effective_to"] == "2026-12-15"

    # Re-run dengan tanggal lama tetap memakai harga lama → hasil identik (reproduksi historis)
    again = owner.ok(owner.post(f"/products/{fg['id']}/costing", {**COSTING_BODY, "activate": False}), 201)
    assert again["calculated_unit_cost"] == v1["calculated_unit_cost"]
    assert again["input_hash"] == v1["input_hash"]
    assert again["status"] == "DRAFT"


def test_costing_snapshot_is_immutable_in_database(owner, setup_bom):
    fg, *_ = setup_bom
    cv = owner.ok(owner.post(f"/products/{fg['id']}/costing", COSTING_BODY), 201)
    engine = create_engine(APP_URL)
    with pytest.raises(DBAPIError, match="immutable"):
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.current_org_id', :o, true)"), {"o": owner.org_id})
            conn.execute(text("UPDATE costing_versions SET calculated_unit_cost = 1 WHERE id = :id"), {"id": cv["id"]})
    engine.dispose()


def test_costing_missing_material_price(owner):
    pcs = make_unit(owner)
    fg = make_product(owner, "FG", "FINISHED_GOOD", pcs)
    mat = make_product(owner, "MAT-X", "MATERIAL", pcs)
    owner.ok(owner.post(f"/products/{fg['id']}/bom", {"planned_output_qty": "10", "effective_from": "2026-01-01",
                                                      "items": [{"material_product_id": mat["id"], "net_quantity": "10"}]}), 201)
    r = owner.post(f"/products/{fg['id']}/costing", COSTING_BODY)
    assert r.status_code == 422
    assert "MAT-X" in r.json()["error"]["message"]


def test_engine_error_is_explained(owner, setup_bom):
    fg, *_ = setup_bom
    r = owner.post(f"/products/{fg['id']}/costing", {**COSTING_BODY, "scrap_rate": "0.9999999"})
    assert r.status_code == 201  # masih valid (< 1)
    r = owner.post(f"/products/{fg['id']}/costing", {**COSTING_BODY, "scrap_rate": "1"})
    assert r.status_code == 422


def test_bom_versioning(owner, setup_bom):
    fg, mat_a, mat_b = setup_bom
    owner.ok(owner.post(f"/products/{fg['id']}/bom", {"planned_output_qty": "500", "effective_from": "2026-06-01",
                                                      "items": [{"material_product_id": mat_b["id"], "net_quantity": "500"}]}), 201)
    boms = owner.ok(owner.get(f"/products/{fg['id']}/bom"))
    assert [(b["version_number"], b["status"], b["effective_to"]) for b in boms] == [(2, "ACTIVE", None), (1, "SUPERSEDED", "2026-06-01")]
    assert len(boms[1]["items"]) == 2


def test_bom_rejects_non_material(owner, setup_bom):
    fg, *_ = setup_bom
    r = owner.post(f"/products/{fg['id']}/bom", {"planned_output_qty": "1", "effective_from": "2026-06-01",
                                                 "items": [{"material_product_id": fg["id"], "net_quantity": "1"}]})
    assert r.status_code == 422


def test_landed_cost_costing_TRD_01(owner):
    pcs = make_unit(owner)
    tg = make_product(owner, "IMP-1", "TRADED_GOOD", pcs)
    body = {
        "costing_structure": "LANDED_COST",
        "costing_method": "ACTUAL",
        "data_nature": "ACTUAL",
        "as_of_date": "2026-11-22",
        "landed": {"quantity": "1000", "unit_purchase_price": "5", "fx_rate": "16000", "import_duty_rate": "0.05",
                   "freight": "4000000", "handling": "1000000", "other_acquisition": "500000", "qty_received_good": "990"},
    }
    cv = owner.ok(owner.post(f"/products/{tg['id']}/costing", body), 201)
    assert cv["calculated_unit_cost"] == "90404.0404"
