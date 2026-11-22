"""Tambahkan data demo biaya & skenario ke organisasi demo (jalankan setelah seed_demo.py).

Pakai:  .venv/bin/python scripts/seed_demo_planning.py   (API harus berjalan di http://127.0.0.1:8000)
"""

from __future__ import annotations

import sys

import httpx
from seed_demo import BASE, EMAIL, PASSWORD, ok


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=20)
    token = ok(c.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}))["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"
    org = next(o for o in ok(c.get("/organizations")) if o["slug"] == "demo-roti")
    c.headers["X-Organization-Id"] = org["id"]
    if ok(c.get("/costs")):
        print("Data biaya demo sudah ada; tidak dibuat ulang.")
        return

    products = {p["sku"]: p["id"] for p in ok(c.get("/products", params={"limit": 200}))}
    drv = {}
    for code, name, dtype, label in [
        ("UNIT", "Unit terjual", "SALES_UNITS", "pcs"),
        ("PROD", "Unit diproduksi", "PRODUCTION_UNITS", "pcs"),
        ("JAM-MESIN", "Jam mesin oven", "MACHINE_HOURS", "jam"),
    ]:
        drv[code] = ok(c.post("/cost-drivers", json={"code": code, "name": name, "driver_type": dtype, "unit_label": label}))["id"]

    start = "2026-01-01"
    items = [
        {"code": "SEWA-TOKO", "name": "Sewa toko & gudang", "category": "FIXED_OPERATING", "behavior_type": "FIXED",
         "params": {"effective_from": start, "base_amount": "15000000", "escalation_type": "COMPOUND_PCT", "escalation_rate": "0.08", "escalation_frequency": "ANNUAL"}},
        {"code": "GAJI-KANTOR", "name": "Gaji staf kantor", "category": "ADMINISTRATIVE", "behavior_type": "FIXED",
         "params": {"effective_from": start, "base_amount": "25000000"}},
        {"code": "MARKETPLACE", "name": "Komisi marketplace", "category": "SELLING", "behavior_type": "PERCENTAGE",
         "params": {"effective_from": start, "percentage": "0.08", "percentage_base": "REVENUE"}},
        {"code": "ONGKIR", "name": "Ongkir ke pelanggan", "category": "DISTRIBUTION", "behavior_type": "VARIABLE", "driver_id": drv["UNIT"],
         "params": {"effective_from": start, "rate": "350"}},
        {"code": "OPERATOR", "name": "Operator produksi", "category": "DIRECT_LABOR", "behavior_type": "STEP_FIXED", "driver_id": drv["PROD"],
         "params": {"effective_from": start, "step_mode": "CEILING", "capacity_per_resource": "6000", "cost_per_resource": "5500000", "max_resources": "8"}},
        {"code": "LISTRIK-OVEN", "name": "Listrik oven", "category": "PRODUCTION_OVERHEAD", "behavior_type": "SEMI_VARIABLE", "driver_id": drv["JAM-MESIN"],
         "params": {"effective_from": start, "base_amount": "2000000", "rate": "45000"}},
        {"code": "OH-PABRIK", "name": "Overhead pabrik", "category": "PRODUCTION_OVERHEAD", "behavior_type": "FIXED", "cost_scope": "ALLOCATION_POOL",
         "params": {"effective_from": start, "base_amount": "12000000"}},
        {"code": "BAHAN-PENOLONG", "name": "Bahan penolong (sudah di HPP)", "category": "DIRECT_MATERIAL", "behavior_type": "VARIABLE",
         "cost_scope": "PRODUCT", "driver_id": drv["PROD"], "params": {"effective_from": start, "rate": "150"}},
    ]
    ids = {}
    for it in items:
        ids[it["code"]] = ok(c.post("/costs", json=it))["id"]
    ok(c.put(f"/costs/{ids['OH-PABRIK']}/allocation", json={"basis": "REVENUE"}))

    lines = [
        {"product_id": products["RT-001"], "unit_price": "12000", "volume": "30000"},
        {"product_id": products["TG-SLI"], "unit_price": "65000", "volume": "1500"},
    ]
    base_assumptions = {"tax_regime": "PROFIT_BASED", "tax_rate": "0.22", "target_kind": "OPERATING_PROFIT", "target_amount": "100000000",
                        "other_activity": {"JAM-MESIN": "520"}}
    base = ok(c.post("/scenarios", json={"name": "Rencana Desember 2026", "scenario_type": "BASE", "period_start": "2026-12-01",
                                          "period_months": 1, "assumptions": base_assumptions, "lines": lines}))
    ok(c.post(f"/scenarios/{base['id']}/run"))
    for name, stype, changes in [
        ("Optimis: volume +15%", "OPTIMISTIC", {"volume_change": "0.15"}),
        ("Pesimis: bahan +8%, volume −5%", "PESSIMISTIC", {"unit_cost_change": "0.08", "volume_change": "-0.05"}),
    ]:
        s = ok(c.post(f"/scenarios/{base['id']}/duplicate", json={"name": name, "scenario_type": stype}))
        ok(c.patch(f"/scenarios/{s['id']}", json={"row_version": s["row_version"], "assumptions": {**s["assumptions"], **changes}}))
        ok(c.post(f"/scenarios/{s['id']}/run"))
    print("Data biaya & 3 skenario demo dibuat.")


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    main()
