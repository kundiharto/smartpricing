"""Isi database development dengan data demo lewat API yang sedang berjalan.

Pakai:  .venv/bin/python scripts/seed_demo.py  (server harus jalan di http://127.0.0.1:8000)

Akun demo (HANYA untuk database development lokal):
    email:    demo@example.com
    password: demo-smartpricing-2026
"""

from __future__ import annotations

import sys

import httpx

import os

# Untuk server lain (mis. produksi): SPE_API_BASE=https://.../api/v1 SPE_DEMO_PASSWORD=<acak>
BASE = os.environ.get("SPE_API_BASE", "http://127.0.0.1:8000/api/v1")
EMAIL = os.environ.get("SPE_DEMO_EMAIL", "demo@example.com")
PASSWORD = os.environ.get("SPE_DEMO_PASSWORD", "demo-smartpricing-2026")


def ok(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        sys.exit(f"{r.request.method} {r.request.url} → {r.status_code}: {r.text}")
    return r.json()["data"]


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=90)
    r = c.post("/auth/register", json={"email": EMAIL, "password": PASSWORD, "full_name": "Pengguna Demo"})
    if r.status_code == 409:
        print("Akun demo sudah ada; data demo tidak dibuat ulang.")
        return
    ok(r)
    token = ok(c.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}))["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"

    org = ok(c.post("/organizations", json={
        "name": "PT Demo Roti Nusantara", "slug": "demo-roti",
        "business_models": ["MANUFACTURING", "TRADING"], "primary_business_model": "MANUFACTURING",
    }))
    c.headers["X-Organization-Id"] = org["id"]

    pcs = ok(c.post("/units", json={"code": "pcs", "name": "Pieces", "dimension": "COUNT"}))["id"]
    kg = ok(c.post("/units", json={"code": "kg", "name": "Kilogram", "dimension": "MASS"}))["id"]

    def product(sku: str, name: str, ptype: str, unit: str, model: str = "MANUFACTURING") -> str:
        return ok(c.post("/products", json={"sku": sku, "name": name, "product_type": ptype,
                                            "business_model": model, "base_unit_id": unit}))["id"]

    roti = product("RT-001", "Roti Tawar 400g", "FINISHED_GOOD", pcs)
    tepung = product("BB-TPG", "Tepung Terigu", "MATERIAL", kg)
    gula = product("BB-GLA", "Gula Pasir", "MATERIAL", kg)
    plastik = product("BB-PLS", "Plastik Kemasan", "MATERIAL", pcs)
    selai = product("TG-SLI", "Selai Stroberi Impor", "TRADED_GOOD", pcs, "TRADING")

    for mat, price in [(tepung, "12500"), (gula, "17000"), (plastik, "350")]:
        ok(c.post(f"/products/{mat}/material-prices", json={"unit_price": price, "effective_from": "2026-01-01"}))

    ok(c.post(f"/products/{roti}/bom", json={
        "planned_output_qty": "1000", "effective_from": "2026-01-01",
        "items": [
            {"material_product_id": tepung, "net_quantity": "250", "material_waste_rate": "0.03"},
            {"material_product_id": gula, "net_quantity": "30", "material_waste_rate": "0.01"},
            {"material_product_id": plastik, "net_quantity": "1000"},
        ],
    }))
    roti_cost = ok(c.post(f"/products/{roti}/costing", json={
        "costing_structure": "BOM_BASED", "as_of_date": "2026-11-22",
        "labor": [{"name": "Baker", "hours": "24", "hourly_rate": "35000"}],
        "machines": [{"name": "Oven", "hours": "8", "hourly_rate": "90000"}],
        "overhead": "1500000", "scrap_rate": "0.02",
    }))
    selai_cost = ok(c.post(f"/products/{selai}/costing", json={
        "costing_structure": "LANDED_COST", "costing_method": "ACTUAL", "data_nature": "ACTUAL", "as_of_date": "2026-11-22",
        "landed": {"quantity": "500", "unit_purchase_price": "2.5", "fx_rate": "16000", "import_duty_rate": "0.05",
                   "freight": "1500000", "handling": "250000", "qty_received_good": "495"},
    }))
    rec = ok(c.post("/pricing/recommend", json={
        "method": "TARGET_CONTRIBUTION_MARGIN", "product_id": roti, "target_margin": "0.30",
        "fees": [{"name": "Komisi marketplace", "rate": "0.08"}], "effective_date": "2026-12-01",
        "rounding": {"increment": "500", "mode": "NEAREST"},
    }))

    print("Data demo dibuat.")
    print(f"  Organisasi       : {org['name']}  (X-Organization-Id: {org['id']})")
    print(f"  Biaya roti/unit  : Rp {roti_cost['calculated_unit_cost']}")
    print(f"  Biaya selai/unit : Rp {selai_cost['calculated_unit_cost']}")
    print(f"  Harga roti       : Rp {rec['list_price']} (margin kontribusi {rec['expected_contribution_margin']})")


if __name__ == "__main__":
    main()
