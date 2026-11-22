# SMART PRICING ENGINE
## Calculation Test Suite Specification v1.0

**Status:** Draft untuk review
**Acuan rumus:** `CALCULATION_SPEC.md` v1.0 (nomor § merujuk ke dokumen tersebut)
**Mencakup:** 18 test case wajib PRD §8.5 + test tambahan dari review v1.1

---

## 0. Aturan Pengujian

- Semua input dan expected value ditulis sebagai string Decimal (contoh di bawah memakai format Indonesia untuk keterbacaan: titik = ribuan, koma = desimal; di kode tes ditulis `"85714.29"`).
- **Asersi nominal:** hasil engine di-*quantize* ke `0.01` dengan `ROUND_HALF_UP` lalu dibandingkan **sama persis** dengan expected. Rate/persen di-*quantize* ke `0.000001`.
- **Asersi integer** (unit, jumlah operator, harga setelah pembulatan): sama persis tanpa quantize.
- **Asersi status:** kode status dan daftar peringatan wajib cocok.
- Setiap expected value di dokumen ini telah dihitung ulang dengan Python `decimal` (presisi 28).
- Tes ditulis dengan `pytest`, satu file per kelompok (`test_pricing.py`, `test_break_even.py`, dst.). ID tes dipakai sebagai nama fungsi, mis. `test_PRC_03_contribution_margin_with_fee`.
- Selain kasus di bawah, setiap rumus wajib punya **property test** (Hypothesis): mis. harga hasil `TARGET_CONTRIBUTION_MARGIN`, bila dimasukkan kembali, menghasilkan margin = target (round-trip).

Pemetaan ke PRD §8.5 ditandai `[PRD-n]`.

---

## 1. Pricing (§5)

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| PRC-01 `[PRD-1]` | Markup | C = 60.000; k = 0,25; V = 0; P = 0 | N = 75.000,00 | OK |
| PRC-02 `[PRD-2]` | Target gross margin | C = 60.000; M = 0,30 (GROSS) | N = 85.714,29 | OK |
| PRC-03 | Contribution margin dengan fee | C = 60.000; M = 0,30 (CONTRIBUTION); F_N = 0,10 | N = 100.000,00; fee = 10.000,00; kontribusi = 30.000,00; CM = 0,300000 | OK |
| PRC-04 | Diskon dihitung mundur | C = 60.000; M = 0,30; D = 0,20; tanpa fee | N = 85.714,29; L = 107.142,86; diskon = 21.428,57 | OK |
| PRC-05 | Diskon + fee berbasis harga bersih | C = 60.000; M = 0,30; D = 0,20; F_N = 0,10 | N = 100.000,00; L = 125.000,00 | OK |
| PRC-06 | Fee berbasis harga daftar | C = 60.000; M = 0,30; D = 0,20; F_L = 0,05 | P = 0,062500; N = 94.117,65; L = 117.647,06; fee = 5.882,35; kontribusi = 28.235,29; CM = 0,300000 | OK |
| PRC-07 | Margin tidak mungkin tercapai | C = 60.000; M = 0,60; F_N = 0,45 | — | INFEASIBLE_MARGIN |
| PRC-08 | Harga minimum | C = 60.000; F_N = 0,10 | N_min = 66.666,67 | OK |
| PRC-09 | Break-even price | C = 60.000; V = 0; FC = 50.000.000; Q = 2.000; P = 0 | N = 85.000,00 | OK |
| PRC-10 | Target operating profit price | C = 60.000; FC = 50.000.000; TOP = 30.000.000; Q = 2.000; P = 0 | N = 100.000,00 | OK |
| PRC-11 | PPh berbasis omzet dimuat ke harga | C = 60.000; M = 0,30; F_N = 0,10; T_N = 0,005 | N = 100.840,34; label "alokasi beban pajak untuk perencanaan" ada di output | OK |
| PRC-12 | Volume < 0 atau Q = 0 pada break-even price | Q = 0 | — | INVALID_INPUT |

## 2. Diskon (§5.5) `[PRD-14]`

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| DSC-01 | Dampak diskon | L = 125.000; D = 0,25; C = 60.000; F_N = 0,10; target M = 0,30 | N = 93.750,00; fee = 9.375,00; kontribusi = 24.375,00; CM = 0,260000; N_min = 66.666,67 | OK + BELOW_TARGET_MARGIN |
| DSC-02 | Diskon menembus harga minimum | L = 125.000; D = 0,50; C = 60.000; F_N = 0,10 | N = 62.500,00 | OK + BELOW_MIN_PRICE |
| DSC-03 | Publikasi di bawah minimum tanpa override | hasil DSC-02, tanpa `override_reason` | publikasi ditolak | INVALID_INPUT |

## 3. Pembulatan Harga (§7)

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| RND-01 | Mode UP | target = 85.714,29; increment 500; UP | 86.000 | OK |
| RND-02 | Margin guard menaikkan harga | target = 85.714,29; increment 500; NEAREST; C = 60.000; M = 0,30 (GROSS) | NEAREST → 85.500 (margin 0,298246 < 0,30) → guard → **86.000** | OK |
| RND-03 | Contoh review | target = 10.237; increment 500; NEAREST; margin guard aktif dan 10.000 di bawah target | 10.500 | OK |
| RND-04 | Presisi penuh tetap tersimpan | RND-01 | `target_price` = 85714.2857142857142857142857 (28 digit), `recommended_price` = 86000 | OK |

## 4. PPN (§8.1) `[PRD-12]` `[PRD-13]`

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| VAT-01 | Tax-exclusive, DPP nilai lain | N = 100.000; rate = 0,12; dpp_factor = 11/12 | DPP = 91.666,67; PPN = 11.000,00; G = 111.000,00 | OK |
| VAT-02 | Tax-inclusive, DPP nilai lain | G = 111.000; rate = 0,12; dpp_factor = 11/12 | N = 100.000,00; PPN = 11.000,00 | OK |
| VAT-03 | DPP harga penuh | N = 100.000; rate = 0,12; dpp_method = FULL | PPN = 12.000,00; G = 112.000,00 | OK |
| VAT-04 | PPN tidak memengaruhi margin | PRC-03 + VAT-01 | CM tetap 0,300000 | OK |
| VAT-05 | Tidak ada aturan berlaku pada tanggal | as_of_date di luar semua `effective_from/to` | — | INVALID_INPUT |

## 5. Break-Even (§9)

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| BEP-01 `[PRD-3]` | BEP revenue | FC = 50.000.000; CMR = 0,40 | BEP = 125.000.000,00 | OK |
| BEP-02 `[PRD-4]` | BEP units | FC = 50.000.000; N = 100.000; C + V = 60.000 | UCM = 40.000; BEP = 1.250 unit | OK |
| BEP-03 | Pembulatan ke atas unit diskrit | FC = 50.000.000; UCM = 30.000 | 1.667 unit (dari 1.666,67) | OK |
| BEP-04 | Kontribusi negatif | N = 50.000; C + V = 60.000 | — | NO_BREAK_EVEN |
| BEP-05 | Kontribusi nol | N = 60.000; C + V = 60.000 | — | NO_BREAK_EVEN |
| BEP-06 | Biaya tetap nol | FC = 0; UCM = 40.000 | BEP = 0 | OK |
| BEP-07 | Step-fixed `[PRD-9]` | UCM = 12.000; tier: 1–1.000 → 10 jt; 1.001–2.000 → 15 jt; 2.001–3.000 → 22 jt | first BEP = 834; profitable_ranges = [834–1.000], [1.250–3.000]; laba di 2.001 = 2.012.000 | OK |
| BEP-08 | Step-fixed tanpa rentang menguntungkan | UCM = 5.000; tier sama dengan BEP-07 | Q* = 2.000 (tier1 > 1.000), 3.000 (tier2 > 2.000), 4.400 (tier3 > 3.000) | NO_BREAK_EVEN_WITHIN_CAPACITY |
| BEP-09 `[PRD-10]` | Multi-produk weighted CM | A: N = 100.000, VC = 60.000, mix 0,6; B: N = 50.000, VC = 20.000, mix 0,4 (UNITS); FC = 45.000.000 | R_mix = 80.000; CM_mix = 36.000; WCMR = 0,450000; BEP revenue = 100.000.000,00; BEP mix = 1.250; A = 750 unit; B = 500 unit | OK |

## 6. Target Laba (§9.4) `[PRD-5]`

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| TGT-01 | Target operating profit | FC = 50.000.000; TOP = 30.000.000; CMR = 0,40 | R = 200.000.000,00 | OK |
| TGT-02 | Target laba bersih, PPh berbasis laba | FC = 50.000.000; NP = 39.000.000; t = 0,22; CMR = 0,40 | PBT = 50.000.000,00; R = 250.000.000,00 | OK |
| TGT-03 | Target laba bersih, PPh berbasis omzet | FC = 50.000.000; NP = 30.000.000; r = 0,005; CMR = 0,40 | R = 202.531.645,57 | OK |
| TGT-04 | CMR ≤ tarif omzet | CMR = 0,004; r = 0,005 | — | INFEASIBLE_MARGIN |

## 7. Costing Manufaktur (§3) `[PRD-6]`

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| MFG-01 | Material waste | net 2 kg/unit; w = 0,10; harga 15.000/kg | input = 2,222222 kg; biaya = 33.333,33 | OK |
| MFG-02 | Contoh review (waste dari input) | output baik membutuhkan 100 unit material; w = 10/110 | input = 110,000000 | OK |
| MFG-03 | Konversi "tambahan X%" | X = 0,10 → w = X/(1+X) = 0,090909; net = 100 | input = 110,000000 | OK |
| MFG-04 | Unit cost dengan scrap | Q_plan = 1.000; A: net 0,5 kg/unit, w = 0,04, 20.000/kg; B: 1 pcs/unit, w = 0, 3.000/pcs; labor 40 jam × 50.000; mesin 10 jam × 150.000; overhead 5.000.000; packaging 1.000 × 1.000 unit; y = 1; s = 0,05; r = 0 | material A = 10.416.666,67; batch = 22.916.666,67; good = 950; unit cost = 24.122,81 | OK |
| MFG-05 | Rework | MFG-04 + r = 0,03; rework 4.000/unit | rework = 114.000,00; unit cost = (22.916.666,67 + 114.000) / 950 = 24.242,81 | OK |
| MFG-06 | Good units nol | y = 1; s = 1 (tidak valid, s < 1) | — | INVALID_INPUT |
| MFG-07 | Harga material tidak tersedia | material tanpa `material_prices` berlaku | — | INVALID_INPUT (menyebut nama material) |

## 8. Trading / Landed Cost (§4)

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| TRD-01 | Landed cost impor | 1.000 unit × USD 5; kurs 16.000; bea 5% dari nilai beli; freight 4.000.000; handling 1.000.000; lain-lain 500.000; diterima baik 990 | nilai beli = 80.000.000; bea = 4.000.000; total = 89.500.000,00; per unit = 90.404,04 | OK |
| TRD-02 | Alokasi freight multi-produk (berat) | freight 1.000.000; A 30 kg, B 70 kg | A = 300.000; B = 700.000 | OK |
| TRD-03 | Kurs tidak tersedia | tanggal tanpa kurs | — | INVALID_INPUT |

## 9. Perilaku Biaya (§2) `[PRD-8]` `[PRD-9]`

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| CST-01 | Semi-variable | base 2.000.000; 3.000 kWh × 1.500 | 6.500.000,00 | OK |
| CST-02 | Step-fixed TABLE | 0–10.000 → 5 op; 10.001–15.000 → 8 op; 15.001–20.000 → 11 op; gaji 6.000.000; A = 12.000 | 8 operator; 48.000.000,00 | OK |
| CST-03 | Step-fixed melebihi tabel | sama, A = 21.000 | 11 operator; 66.000.000,00 | OK + CAPACITY_EXCEEDED |
| CST-04 | Step-fixed CEILING | 2.000 unit/operator; A = 12.500; 6.000.000/operator | 7 operator; 42.000.000,00 | OK |
| CST-05 | Tiered GRADUATED | 0–1.000 @100; 1.001–5.000 @80; >5.000 @60; A = 6.000 | 480.000,00 | OK |
| CST-06 | Tiered ALL_UNITS | sama, A = 6.000 | 360.000,00 | OK |
| CST-07 | Min/max amount | hasil 4.000; minimum 5.000 | 5.000,00 | OK |
| CST-08 | Double counting ditolak | cost item yang sama: direct assignment ke produk A **dan** masuk pool alokasi pada periode sama | — | INVALID_INPUT (menyebut cost item) |

## 10. Eskalasi (§10) `[PRD-7]`

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| ESC-01 | Compound | base 10.000; r = 0,05/tahun; n = 3 | 11.576,25 | OK |
| ESC-02 | Simple | sama | 11.500,00 | OK |
| ESC-03 | Cap | ESC-01 dengan cap 11.000 | 11.000,00 | OK |
| ESC-04 | Nominal | base 10.000; +250/kuartal; n = 4 | 11.000,00 | OK |
| ESC-05 | Periode belum penuh | effective_from 2026-01-01; tahunan; as_of 2026-12-31 | n = 0 → 10.000,00 | OK |
| ESC-06 | Scenario override | ESC-01 dengan override r = 0,08 | 12.597,12 | OK |

## 11. Alokasi (§6) `[PRD-11]`

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| ALC-01 | Largest remainder | pool 10.000.000 IDR; 3 produk, revenue 1:1:1; urutan ID P1 < P2 < P3 | P1 = 3.333.334; P2 = 3.333.333; P3 = 3.333.333; total = 10.000.000 | OK |
| ALC-02 | Persentase ≠ 100% | 0,50 + 0,49 | — | INVALID_INPUT |
| ALC-03 | Unallocated diizinkan | 0,50 + 0,49; allow_unallocated; pool 1.000.000 | 500.000; 490.000; unallocated = 10.000 | OK |
| ALC-04 | Driver nol | Σ driver = 0 | — | INVALID_INPUT |
| ALC-05 | Machine-hour | pool 6.000.000; A 30 jam, B 90 jam | A = 1.500.000; B = 4.500.000 | OK |

## 12. Kapasitas (§11) `[PRD-15]`

| ID | Kasus | Input | Expected | Status |
|---|---|---|---|---|
| CAP-01 | Melebihi kapasitas | permintaan 12.000; kapasitas reguler 10.000; tanpa lembur/ekspansi | utilisasi = 1,200000; unmet = 2.000 | OK + CAPACITY_EXCEEDED |
| CAP-02 | Lembur menutup kekurangan | sama; lembur maks 3.000; biaya per unit reguler 500; multiplier 1,5 | lembur = 2.000; biaya lembur = 1.500.000,00; unmet = 0 | OK + CAPACITY_EXCEEDED |

## 13. Reproduksibilitas & Presisi `[PRD-16]` `[PRD-17]` `[PRD-18]`

| ID | Kasus | Expected |
|---|---|---|
| REP-01 | Input sama dijalankan 2× | output identik byte per byte; `input_hash` identik |
| REP-02 | Urutan key JSON input berbeda | `input_hash` identik (kanonikalisasi) |
| REP-03 | Engine tidak membaca jam sistem | hasil sama walau jam sistem diubah (dites dengan freezegun) |
| PRE-01 | Presisi Decimal | `0,1 + 0,2 = 0,3` tepat; tidak ada `float` di jalur kalkulasi (dicek dengan lint/tes statis) |
| PRE-02 | Presisi mata uang | IDR ditampilkan 0 desimal; USD 2 desimal |
| PRE-03 | Penjumlahan alokasi | Σ alokasi = pool tepat (lihat ALC-01) untuk 1.000 kasus acak (property test) |
| HIS-01 | Reproduksi versi historis | snapshot costing lama + engine version lama → `calculated_unit_cost` sama walau `material_prices` sudah berubah |
| HIS-02 | Perubahan biaya tidak menghapus histori | tambah harga material baru → costing version lama tetap `SUPERSEDED` dengan nilai lama |

---

## 14. Cakupan Wajib PRD §8.5

| PRD | Test |
|---|---|
| 1. Markup | PRC-01 |
| 2. Margin | PRC-02, PRC-03 |
| 3. Break-even revenue | BEP-01 |
| 4. Break-even units | BEP-02, BEP-03 |
| 5. Target profit revenue | TGT-01–04 |
| 6. Material yield | MFG-01–05 |
| 7. Variable cost escalation | ESC-01–06 |
| 8. Semi-variable | CST-01 |
| 9. Step-fixed threshold | CST-02–04, BEP-07–08 |
| 10. Weighted CM | BEP-09 |
| 11. Cost allocation | ALC-01–05 |
| 12. Tax-inclusive | VAT-02 |
| 13. Tax-exclusive | VAT-01, VAT-03 |
| 14. Discount impact | DSC-01–03, PRC-04–05 |
| 15. Capacity constraint | CAP-01–02, CST-03 |
| 16. Scenario reproducibility | REP-01–03 |
| 17. Currency precision | PRE-01–03 |
| 18. Historical reproduction | HIS-01–02 |

---

## 15. Rencana Laba & Skenario (CALCULATION_SPEC §14)

Data uji: A (harga 100.000, HPP 60.000, 1.000 unit), B (50.000, 20.000, 1.000 unit). Biaya per bulan: sewa tetap 20 jt; komisi 5% omzet; ongkir 2.000/unit terjual; operator step TABLE 0–2.000 → 10 jt, 2.001–3.000 → 15 jt; overhead pool 6 jt dialokasikan driver A:B = 2:1; bahan penolong scope PRODUCT 500/unit (harus diabaikan).

| ID | Kasus | Expected |
|---|---|---|
| PLN-01 | Laba rugi, PPh berbasis laba 22% | R 150 jt; HPP 80 jt; variabel 11,5 jt; tetap 36 jt; OP 22,5 jt; PPh 4,95 jt; NP 17,55 jt; PENOLONG dikecualikan |
| PLN-02 | BEP dengan step cost | UCM 29.250; BEP 1.231 unit; omzet 92.325.000; MoS 0,3845 |
| PLN-03 | Target OP 50 jt melewati tier | 3.112 unit; omzet 233.400.000 |
| PLN-04 | Target NP 39 jt (PPh 22%) | 3.112 unit |
| PLN-05 | PPh final 0,5% omzet | PPh 750.000; NP 21.750.000 |
| PLN-06 | Profitabilitas & alokasi | A: kontribusi 33 jt, alokasi 4 jt, laba 29 jt; B: 25,5 / 23,5 jt; biaya level perusahaan 30 jt; invarian terpenuhi |
| PLN-07 | Alokasi porsi omzet | A 4 jt, B 2 jt |
| PLN-08 | Alokasi persentase 90% | INVALID_INPUT |
| PLN-09 | Target melewati kapasitas maksimum | `capacity_exceeded_items = [OPERATOR]` + CAPACITY_EXCEEDED |
| SCN-01 | Volume +10% | U 2.200 → operator tier 2; tetap 41 jt; OP 23,35 jt |
| SCN-02 | Volume +60% | peringatan CAPACITY_EXCEEDED |
| SCN-03 | HPP +8%, tetap +5%, komisi +20% | HPP 86,4 jt; variabel 13 jt; tetap 37,8 jt; OP 12,8 jt |
| SCN-04 | Harga +4% | R 156 jt; variabel 11,8 jt |
| PER-01 | Skenario 12 bulan | biaya tetap 432 jt |
| ESC-07 | Eskalasi dalam rencana | sewa 22 jt (10%, 1 tahun) |
| STP-01 | Step CEILING 400 unit/operator | 5 operator, 25 jt; BEP 143 unit |
| BEP-10 | Harga < HPP | NO_BREAK_EVEN |
| DRV-01 | Driver jam tanpa aktivitas | MISSING_DRIVER_ACTIVITY; dengan 100 jam → variabel 5 jt, tidak teratribusi |
| VAL-01 | Input tidak valid | item tanpa driver / rencana kosong / produk ganda → INVALID_INPUT |
| PRV-01 | Pratinjau biaya 2.500 unit | total 47,5 jt; tetap 35 jt |
| REP-04 | Rencana dua kali | hasil identik |

Tes integrasi backend (`backend/tests/test_costs_planning.py`) menjalankan skenario yang sama lewat API dan harus menghasilkan angka identik, ditambah: versi biaya berversi tanggal & immutable, validasi alokasi, run append-only, izin, dan isolasi tenant.
