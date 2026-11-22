# Smart Pricing Engine — Calculation Engine

Library Python murni untuk seluruh kalkulasi finansial Smart Pricing Engine.
Tidak memakai database, jaringan, atau jam sistem. Semua angka memakai `Decimal`.

- Spesifikasi rumus: [`../docs/CALCULATION_SPEC.md`](../docs/CALCULATION_SPEC.md)
- Spesifikasi tes: [`../docs/TEST_SUITE_SPEC.md`](../docs/TEST_SUITE_SPEC.md)

## Menjalankan tes

```bash
cd engine
uv venv .venv && uv pip install --python .venv/bin/python pytest hypothesis
.venv/bin/python -m pytest -q
```

## Modul

| Modul | Isi | Spec |
|---|---|---|
| `core` | Decimal, kode status, `Result`, hash input, decorator `@calculation` | §0 |
| `pricing` | 8 metode pricing, biaya persentase per basis, evaluasi diskon, validasi publikasi | §5 |
| `rounding` | Pembulatan harga dengan margin guard | §7 |
| `tax` | PPN (DPP nilai lain), pemilihan aturan per tanggal, PPh berbasis laba/omzet | §8 |
| `cost_behavior` | Fixed, variable, semi-variable, step-fixed (TABLE/CEILING), tiered, time-based | §2 |
| `allocation` | Alokasi biaya dengan largest remainder, cek double counting | §2.4, §6 |
| `costing` | Manufaktur (waste/yield/scrap/rework), landed cost, jasa, harga material & kurs berlaku | §3, §4 |
| `break_even` | BEP tunggal, step-fixed (rentang menguntungkan), multi-produk, pendapatan untuk target laba | §9 |
| `escalation` | Eskalasi nominal/simple/compound dengan cap/floor dan override skenario | §10 |
| `capacity` | Utilisasi, lembur, permintaan tidak terpenuhi | §11 |

## Contoh

```python
from pricing_engine.pricing import PercentageFee, PricingMethod, calculate_price

r = calculate_price(
    method=PricingMethod.TARGET_CONTRIBUTION_MARGIN,
    unit_cost="60000",
    target_margin="0.30",
    discount="0.20",
    fees=[PercentageFee("marketplace", "0.10")],
)
r.status        # Status.OK
r["net_price"]  # Decimal('100000')
r["list_price"] # Decimal('125000')
r.trace         # langkah-langkah perhitungan untuk penjelasan
r.input_hash    # SHA-256 input (untuk snapshot & reproduksi)
```

## Aturan

- Argumen hanya keyword. Angka dikirim sebagai `str`, `int`, atau `Decimal`; `float` ditolak.
- Input salah tidak melempar exception: hasilnya `Result` dengan status `INVALID_INPUT` dan pesan.
- Rumus baru wajib ditambahkan ke `CALCULATION_SPEC.md` dan `TEST_SUITE_SPEC.md` lebih dulu.
