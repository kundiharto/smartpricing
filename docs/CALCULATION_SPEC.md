# SMART PRICING ENGINE
## Calculation Specification v1.0

**Status:** Draft untuk review
**Berlaku untuk:** Calculation Engine `engine_version = 1.0.x`
**Menggantikan:** PRD v1.0 Bagian 8.3 dan 8.4 (rumus di PRD bersifat ringkasan; dokumen ini yang mengikat)
**Dokumen terkait:** `PRD.md` (v1.1), `DATABASE_SPEC.md`, `TEST_SUITE_SPEC.md`

Dokumen ini mendefinisikan setiap rumus, basis perhitungan, asumsi, batasan, dan kode status yang harus diimplementasikan oleh Calculation Engine. Setiap rumus yang tidak tercantum di sini tidak boleh diimplementasikan tanpa memperbarui dokumen ini terlebih dahulu.

---

## 0. Konvensi Umum

### 0.1 Aritmetika
| Aturan | Ketentuan |
|---|---|
| Tipe angka | `decimal.Decimal` dengan presisi konteks 28 digit. Dilarang memakai `float` di jalur kalkulasi. |
| Input persen | Disimpan sebagai pecahan: 30% = `0.30`. UI boleh menampilkan sebagai persen. |
| Pembulatan antara | **Tidak ada.** Seluruh hasil antara memakai presisi penuh. |
| Pembulatan output | Hanya pada nilai yang ditampilkan atau dipublikasikan, mengikuti kebijakan di §7. |
| Mode pembulatan default | `ROUND_HALF_UP` untuk tampilan. |
| Presisi mata uang | Mengikuti ISO 4217 minor unit: IDR = 0 desimal, USD = 2 desimal. |
| Pembagian dengan nol | Tidak boleh terjadi. Setiap pembagi divalidasi dulu; jika ≤ 0 → kode status (§0.3). |
| Toleransi margin | Pembandingan margin terhadap target memakai toleransi `1E-20`, karena hasil bagi 28 digit bisa menyisakan selisih di digit terakhir (mis. 0,2999…9999). Ditemukan lewat property test. |

### 0.2 Determinisme
- Engine adalah fungsi murni: `output = f(input, engine_version)`. Tidak membaca jam sistem, database, atau jaringan. Tanggal "hari ini" selalu dikirim sebagai input `as_of_date`.
- Setiap output menyertakan `engine_version`, `input_hash` (SHA-256 dari input yang dikanonikalisasi), dan `trace` (langkah-langkah perhitungan untuk penjelasan).
- Input yang sama + versi engine yang sama → output identik sampai ke bit.

### 0.3 Kode Status
| Kode | Jenis | Arti |
|---|---|---|
| `OK` | sukses | Perhitungan valid. |
| `INVALID_INPUT` | error | Data tidak lengkap, negatif yang tidak diizinkan, atau pembagi = 0. |
| `INFEASIBLE_MARGIN` | error | Jumlah target margin + biaya persentase ≥ 100%, sehingga tidak ada harga yang bisa memenuhinya. |
| `NO_BREAK_EVEN` | hasil | Kontribusi per unit ≤ 0; biaya tetap tidak akan pernah tertutup. |
| `NO_BREAK_EVEN_WITHIN_CAPACITY` | hasil | BEP ada secara matematis, tetapi di luar kapasitas yang dimodelkan. |
| `UNBOUNDED` | hasil | Kondisi matematis tidak menghasilkan nilai bermakna (mis. biaya tetap 0 dan target 0). |
| `CAPACITY_EXCEEDED` | peringatan | Volume melebihi kapasitas maksimum yang dikonfigurasi. |
| `BELOW_MIN_PRICE` | peringatan | Harga bersih di bawah harga minimum; publikasi memerlukan override yang tercatat. |
| `BELOW_TARGET_MARGIN` | peringatan | Harga memenuhi minimum tetapi tidak memenuhi target margin. |

Error menghentikan perhitungan. Peringatan tidak menghentikan, tetapi wajib ikut di output dan di snapshot.

### 0.4 Data Aktual vs Data Perencanaan
Setiap nilai biaya dan harga memiliki atribut `data_nature`:
- `ACTUAL` — harga/biaya yang benar-benar terjadi (mis. invoice pembelian).
- `STANDARD` — nilai baku yang ditetapkan perusahaan.
- `ESTIMATE` — perkiraan.
- `SCENARIO` — nilai hasil override skenario.

Engine tidak boleh mencampur sumber tanpa instruksi eksplisit. Input menyebutkan sumber yang dipakai, dan `trace` mencatat sumber setiap komponen.

---

## 1. Definisi Laba (Wajib Konsisten di Seluruh Aplikasi)

Semua nilai di bawah **tidak termasuk PPN** (PPN adalah pajak yang dipungut, bukan pendapatan).

```
Harga daftar (List Price)                 L
− Diskon                                   L × D
= Harga bersih / Net Price                 N = L × (1 − D)

Pendapatan bersih (Net Revenue)            R = Σ N × Q
− HPP / Product Cost (COGS)                biaya produk saja (§3, §4)
= Laba Kotor (Gross Profit)                GP

Pendapatan bersih                          R
− Seluruh biaya variabel                   HPP variabel + biaya penjualan variabel (fee, komisi, ongkir variabel)
= Kontribusi (Contribution)                CM

Kontribusi                                 CM
− Biaya tetap (produksi + operasional)     FC
= Laba Operasional (Operating Profit)      OP

Laba Operasional                           OP
+ Pendapatan lain − Biaya keuangan
= Laba Sebelum Pajak (PBT)                 PBT

Laba Sebelum Pajak                         PBT
− Pajak Penghasilan (berbasis laba ATAU berbasis omzet, §8.3)
= Laba Bersih (Net Profit)                 NP
```

Rasio:
- Gross Margin `GM = GP / R`
- Contribution Margin Ratio `CMR = CM / R`
- Operating Margin `OM = OP / R`

**Aturan:** Laba Kotor dan Kontribusi adalah dua sudut pandang yang berbeda dan ditampilkan berdampingan. Biaya kantor/administrasi tidak masuk HPP kecuali pengguna secara eksplisit mengklasifikasikannya sebagai biaya produk (PRD MOD-004 "Important Rule").

---

## 2. Perilaku Biaya (Cost Behavior)

Notasi: `A` = kuantitas aktivitas dari cost driver pada periode tersebut.

| Tipe | Rumus | Parameter |
|---|---|---|
| `FIXED` | `cost = amount` | Berlaku dalam rentang kapasitas `[min_activity, max_activity]`; di luar rentang → `CAPACITY_EXCEEDED`. |
| `VARIABLE` | `cost = Σ (A_d × rate_d)` | Boleh lebih dari satu driver `d`. |
| `SEMI_VARIABLE` | `cost = base + A × rate` | |
| `STEP_FIXED` | lihat §2.1 | |
| `PERCENTAGE` | `cost = pct × base_value` | `base` wajib eksplisit, lihat §2.2. |
| `TIERED` | lihat §2.3 | |
| `TIME_BASED` | `cost = time_units × rate` | `time_unit`: jam, hari, bulan. |

Opsional untuk semua tipe: `minimum_amount` dan `maximum_amount` diterapkan setelah rumus: `cost = min(max(cost, minimum), maximum)`.

### 2.1 Step-Fixed Cost
Dua mode:

**Mode `TABLE`** — tabel ambang, non-kumulatif:

| from_activity | to_activity | amount |
|---|---|---|
| 0 | 10.000 | 5 operator × gaji |
| 10.001 | 15.000 | 8 operator × gaji |
| 15.001 | 20.000 | 11 operator × gaji |

`cost(A) = amount` dari baris yang memuat `A`. Jika `A` > `to_activity` tertinggi → status `CAPACITY_EXCEEDED`, biaya memakai baris tertinggi, dan kebutuhan tambahan dilaporkan di §9.

**Mode `CEILING`** — kapasitas per sumber daya:
`jumlah_sumber_daya = ceil(A / kapasitas_per_sumber_daya)` (minimal `min_resources`)
`cost = jumlah_sumber_daya × biaya_per_sumber_daya`

### 2.2 Basis Biaya Persentase (`PercentageBase`)
Biaya persentase tidak boleh diasumsikan berbasis harga jual yang sama. Basis yang didukung:

| Kode basis | Arti |
|---|---|
| `LIST_PRICE` | Harga daftar sebelum diskon, tanpa PPN |
| `NET_PRICE` | Harga setelah diskon, tanpa PPN |
| `GROSS_PRICE` | Harga setelah diskon, termasuk PPN |
| `PRODUCT_COST` | Biaya produk per unit |
| `UNIT` | Bukan persen; nominal tetap per unit (untuk keseragaman struktur fee) |
| `NET_REVENUE_PERIOD` | Persentase dari total pendapatan bersih periode (untuk level perusahaan) |

Dalam pricing (§5), biaya persentase berbasis harga diperlakukan secara aljabar karena nilainya bergantung pada harga yang sedang dicari.

### 2.3 Tiered Cost
Dua mode:
- `GRADUATED` — setiap bracket dikenakan tarifnya masing-masing (seperti tarif pajak progresif).
- `ALL_UNITS` — seluruh aktivitas dikenakan tarif dari bracket tempat total aktivitas berada.

### 2.4 Larangan Double Counting
1. Setiap `cost_item` memiliki tepat satu `cost_scope`: `PRODUCT` (masuk HPP), `PERIOD` (beban periode), atau `ALLOCATION_POOL`.
2. Dalam satu periode, satu cost item tidak boleh sekaligus dibebankan langsung (direct assignment) dan masuk pool alokasi.
3. Nilai hasil alokasi diberi tanda `is_allocated = true` dan dikecualikan dari penjumlahan biaya langsung.
4. Validator engine menolak input yang melanggar aturan di atas dengan `INVALID_INPUT` dan menyebutkan cost item yang bermasalah.

---

## 3. Product Costing — Manufacturing

### 3.1 Definisi Parameter Kehilangan (Loss)
Empat parameter dengan definisi yang tidak saling tumpang tindih:

| Parameter | Level | Definisi | Contoh |
|---|---|---|---|
| `material_waste_rate` (w) | per bahan di BOM | Persentase **dari material yang masuk** yang hilang sebelum menjadi bagian produk (potong, tumpah, susut). | Kain dipotong, 10% dari kain yang dipakai jadi sisa. |
| `process_yield_rate` (y) | per BOM / proses | Rasio output terhadap input untuk proses yang mengubah kuantitas (umumnya industri proses). | 100 kg adonan → 92 kg biskuit, y = 0,92. |
| `scrap_rate` (s) | per produk | Persentase **unit jadi** yang ditolak/reject dan tidak dapat dijual. Seluruh biaya unit reject dibebankan ke unit baik. | 5% botol cacat setelah QC. |
| `rework_rate` (r) | per produk | Persentase unit baik yang perlu diproses ulang; menambah biaya pengerjaan ulang, tidak mengurangi output. | 3% unit perlu dicat ulang. |

**Aturan:** satu jenis kehilangan hanya boleh dicatat di satu parameter. UI wajib menampilkan definisi ini saat pengguna mengisi nilai. Semua parameter dalam rentang `0 ≤ w, s, r < 1` dan `0 < y ≤ 1`.

### 3.2 Rumus
Untuk satu batch dengan rencana output `Q_plan` unit:

```
Kebutuhan material input per bahan i:
    input_qty_i = net_qty_i / (1 − w_i)
    material_cost_i = input_qty_i × unit_price_i(as_of_date)

Biaya batch:
    material   = Σ material_cost_i                      (untuk Q_plan)
    labor      = Σ labor_hours_j × hourly_rate_j
    machine    = Σ machine_hours_k × hourly_rate_k
    overhead   = overhead produksi yang dibebankan ke batch (langsung atau hasil alokasi §6)
    packaging  = packaging per unit × unit yang dikemas
    other      = biaya langsung lain
    batch_cost = material + labor + machine + overhead + packaging + other

Unit baik:
    good_units = Q_plan × y × (1 − s)

Rework:
    rework_cost = good_units × r × rework_cost_per_unit

Biaya per unit:
    unit_cost = (batch_cost + rework_cost) / good_units
```

`good_units` harus > 0, jika tidak → `INVALID_INPUT`.

Catatan konversi waste: jika data lapangan berbentuk "tambahan X% dari kebutuhan bersih" (bukan persentase dari input), konversikan dulu: `w = X / (1 + X)`. UI menyediakan pilihan input ini dan engine menerima `w` yang sudah dikonversi.

### 3.3 Harga Material Berlaku
`unit_price_i(as_of_date)` diambil dari `material_prices` dengan `effective_from ≤ as_of_date < effective_to` dan `data_nature` sesuai input. Jika tidak ada harga berlaku → `INVALID_INPUT` dengan nama material.

### 3.4 Metode Costing
`STANDARD`, `ACTUAL`, `ESTIMATED` hanya membedakan **sumber data** (§0.4); rumusnya sama. `BOM_BASED` dan `PROCESS_BASED` membedakan struktur input (BOM vs routing proses). Hasil disimpan sebagai `costing_version` yang immutable.

---

## 4. Product Costing — Trading & Distribution

```
purchase_value = Σ (qty × unit_purchase_price × fx_rate(as_of_date))
landed_total   = purchase_value + freight + insurance + import_duty + handling + other_acquisition
landed_cost_per_unit = landed_total / qty_received_good
```

- `qty_received_good` = kuantitas diterima dalam kondisi baik. Selisih rusak/hilang dibebankan ke unit baik.
- Bea masuk dihitung dari basis yang dikonfigurasi (mis. nilai CIF); engine menerima basis dan tarif sebagai input, tidak menanamkan aturan kepabeanan.
- **Pengiriman multi-produk:** freight dan biaya bersama dialokasikan per produk berdasarkan `VALUE`, `WEIGHT`, `VOLUME`, atau `QUANTITY` (dipilih pengguna), memakai aturan sisa terbesar (§6.3).
- **Kurs:** `fx_rate` diambil dari `exchange_rates` sesuai tanggal dan tipe kurs yang dipilih. Kurs yang dipakai disimpan di snapshot.

**Fully loaded unit cost (analisis manajerial):**
`fully_loaded = landed_cost_per_unit + alokasi biaya gudang/distribusi/penjualan per unit`
Nilai ini **bukan** HPP akuntansi dan diberi label "Biaya penuh (manajerial)".

## 4A. Service Costing
```
service_cost = Σ (labor_hours × rate) + direct_expenses + allocated_overhead
```
Mendukung tarif per jam, paket jasa, dan proyek (durasi × sumber daya). Di MVP tersedia di engine, belum di UI.

---

## 5. Pricing

### 5.1 Notasi
| Simbol | Arti |
|---|---|
| `C` | Biaya produk per unit (HPP) dari costing version terpilih |
| `V` | Biaya variabel non-persentase per unit di luar HPP (ongkir per unit, packaging channel, fee nominal per transaksi ÷ unit) |
| `D` | Diskon, pecahan dari harga daftar |
| `F_L` | Total biaya persentase berbasis `LIST_PRICE` |
| `F_N` | Total biaya persentase berbasis `NET_PRICE` (fee marketplace, komisi, payment fee) |
| `T_N` | Beban pajak berbasis omzet yang dimuat ke harga (opsional, §8.3), berbasis `NET_PRICE` |
| `M` | Target margin (pecahan dari `N`) |
| `k` | Target markup (pecahan dari biaya) |
| `N` | Harga bersih (setelah diskon, tanpa PPN) — **yang dicari** |
| `L` | Harga daftar = `N / (1 − D)` |

Hubungan `F_L × L = F_L × N / (1 − D)`, sehingga beban persentase efektif terhadap `N`:

```
P = F_N + T_N + F_L / (1 − D)
```

### 5.2 Rumus per Metode

| Metode | Rumus `N` | Syarat valid |
|---|---|---|
| **Cost Plus (Markup)** | `N = (C × (1 + k) + V) / (1 − P)` | `1 − P > 0` |
| **Target Gross Margin** | `N = C / (1 − M)` — margin dihitung terhadap HPP saja; fee **tidak** ikut. | `M < 1` |
| **Target Contribution Margin** | `N = (C + V) / (1 − M − P)` — margin setelah seluruh biaya variabel termasuk fee. | `1 − M − P > 0` |
| **Minimum Viable Price** | `N_min = (C + V) / (1 − P)` — kontribusi per unit = 0. | `1 − P > 0` |
| **Break-Even Price** (volume `Q`) | `N = (C + V + FC/Q) / (1 − P)` | `Q > 0`, `1 − P > 0` |
| **Target Operating Profit Price** (volume `Q`) | `N = (C + V + (FC + TOP)/Q) / (1 − P)` | `Q > 0`, `1 − P > 0` |
| **Competitive** | `N = harga pesaing × (1 + penyesuaian)`; engine lalu menghitung margin hasilnya dan memeriksa terhadap `N_min`. | |
| **Value-Based** | `N` diinput pengguna (nilai persepsi); engine hanya mengevaluasi margin dan memeriksa `N_min`. | |
| **Volume-Based** | Tabel harga per bracket kuantitas (§2.3 mode `GRADUATED`/`ALL_UNITS`); setiap bracket diperiksa terhadap `N_min`. | |
| **Customer Segment** | Metode mana pun di atas dengan parameter (`D`, `F`, `M`, `V`) per segmen/channel. | |

Jika syarat valid tidak terpenuhi → `INFEASIBLE_MARGIN` dengan penjelasan komponen mana yang membuat total ≥ 100%.

**Penting — Gross Margin vs Contribution Margin:** Rumus PRD v1.0 `Price = Unit Cost / (1 − Target Gross Margin)` tetap benar **untuk gross margin**, tetapi salah jika target margin dimaksudkan setelah fee. UI wajib meminta pengguna memilih definisi margin, dan default yang disarankan untuk penjualan lewat marketplace/channel berbayar adalah **Contribution Margin**.

### 5.3 Contoh Acuan
- `C = 60.000`, `M = 30%` (contribution), `F_N = 10%`, `D = 0` → `N = 60.000 / 0,60 = 100.000`.
  Rincian: fee 10.000, biaya 60.000, kontribusi 30.000 (30%).
- `C = 60.000`, `M = 30%`, `D = 20%`, tanpa fee → `N = 85.714,29`, `L = 107.142,86`.
- `C = 60.000`, `M = 30%`, `D = 20%`, `F_N = 10%` → `N = 100.000`, `L = 125.000`.

### 5.4 Output Rekomendasi Harga
Setiap rekomendasi menghasilkan: `current_cost`, `current_price`, `minimum_price` (`N_min`), `recommended_price` (setelah pembulatan §7), `target_price` (sebelum pembulatan), `list_price`, `gross_margin`, `contribution_margin`, `required_volume` (jika ada target laba), `expected_revenue`, `expected_profit` (dengan definisi laba yang disebut), `vat_impact`, `assumptions`, `warnings`, `trace`.

### 5.5 Diskon pada Harga yang Sudah Ada
```
N = L × (1 − D)
```
Jika `N < N_min` → `BELOW_MIN_PRICE`; jika `N_min ≤ N` tetapi margin < target → `BELOW_TARGET_MARGIN`. Publikasi harga dengan `BELOW_MIN_PRICE` hanya boleh melalui override yang tercatat (pengguna berwenang, alasan, waktu).

---

## 6. Alokasi Biaya

### 6.1 Metode
| Metode | Porsi target `i` |
|---|---|
| `DIRECT` | 100% ke satu target |
| `EQUAL` | `1 / n` |
| `PERCENTAGE` | persentase yang diinput |
| `REVENUE` / `UNIT` / `LABOR_HOUR` / `MACHINE_HOUR` / `ACTIVITY` | `driver_i / Σ driver` |
| `CUSTOM` | rumus terdaftar (tidak boleh kode bebas) |

### 6.2 Validasi
- Pool penuh: `Σ persentase = 1` **tepat** (perbandingan Decimal, tanpa toleransi).
- Jika `allow_unallocated = true`: `Σ persentase ≤ 1`, dan sisa dilaporkan sebagai `unallocated_amount`.
- `Σ driver = 0` → `INVALID_INPUT`.

### 6.3 Pembulatan Alokasi (Largest Remainder)
Ketika jumlah teralokasi harus dibulatkan ke unit mata uang:
1. Hitung porsi presisi penuh.
2. Bulatkan ke bawah setiap porsi.
3. Bagikan sisa satu unit mata uang ke target dengan sisa pecahan terbesar (seri diputus berdasarkan urutan ID target).

Hasil: `Σ alokasi = nilai pool` secara tepat.

### 6.4 Multi-Stage
MVP: metode **step-down** (urutan departemen pendukung ditetapkan pengguna; departemen yang sudah dialokasikan tidak menerima alokasi lagi). Metode resiprokal ditunda ke versi berikutnya.

---

## 7. Kebijakan Pembulatan Harga

Parameter: `rounding_increment` (mis. 100, 500, 1.000), `rounding_mode` (`UP`, `NEAREST`, `DOWN`), `apply_to` (`NET_PRICE`, `LIST_PRICE`, atau `GROSS_PRICE`), opsional `price_ending` (mis. akhiran 900).

Algoritma:
1. Hitung `target_price` presisi penuh.
2. Bulatkan sesuai mode dan increment.
3. **Margin guard:** jika hasil pembulatan membuat margin < target margin (atau harga < `N_min`), naikkan satu increment hingga syarat terpenuhi.
4. Simpan kedua nilai: `target_price` (presisi penuh) dan `recommended_price` (dibulatkan).

Contoh: target 10.237, increment 500, mode `NEAREST` → 10.000 (margin turun di bawah target) → guard → **10.500**.

---

## 8. Pajak

Engine **tidak menanamkan tarif atau aturan pajak** di dalam kode. Semua aturan berasal dari `tax_rules` (konfigurasi, berlaku per periode) dan dikirim sebagai input. Angka di dokumen ini hanya contoh.

### 8.1 PPN
Parameter aturan: `nominal_rate`, `dpp_method` (`FULL`, `OTHER_VALUE`, `SPECIFIC_AMOUNT`), `dpp_factor` (mis. 11/12), `effective_from/to`, `transaction_type`, `goods_service_class`, dan `price_includes_vat`.

```
DPP = N × dpp_factor           (FULL → dpp_factor = 1)
VAT = DPP × nominal_rate
G   = N + VAT                  (harga termasuk PPN)
```

Harga termasuk PPN (tax-inclusive), dicari `N` dari `G`:
```
N = G / (1 + nominal_rate × dpp_factor)
```

Contoh (nilai lain 11/12, tarif 12%): `N = 100.000` → `DPP = 91.666,67`, `PPN = 11.000`, `G = 111.000`.

PPN tidak masuk pendapatan, HPP, maupun margin. Pembulatan PPN dilakukan pada level faktur sesuai konfigurasi (default `ROUND_HALF_UP` ke rupiah).

### 8.2 Profil Wajib Pajak
Setiap organisasi memiliki `tax_profile`: jenis wajib pajak (orang pribadi, perseroan perorangan, koperasi, PT, CV, dll.), status PKP, dan rezim PPh yang berlaku pada periode tertentu (`PROFIT_BASED` atau `TURNOVER_FINAL`). Kelayakan atas fasilitas tertentu ditentukan oleh pengguna/konsultan pajak dan dicatat di profil — **engine tidak memutuskan kelayakan**.

### 8.3 PPh Berbasis Laba vs Berbasis Omzet
- **`PROFIT_BASED`:** `income_tax = max(0, PBT) × rate` (rate dari aturan; kompensasi rugi dan fasilitas di luar MVP).
- **`TURNOVER_FINAL`:** `income_tax = max(0, taxable_turnover) × rate`, dengan `taxable_turnover = omzet bruto periode − bagian omzet yang dibebaskan (jika diatur, mis. ambang tahunan untuk orang pribadi)`. Ambang omzet maksimum rezim dicek; jika terlampaui → peringatan `TAX_REGIME_THRESHOLD_EXCEEDED`.

Penempatan:
- Di laporan laba rugi, PPh (rezim apa pun) berada di baris **Pajak Penghasilan**, di bawah PBT — bukan HPP, bukan biaya operasional.
- Di pricing, pengguna **boleh** memuat PPh berbasis omzet ke harga sebagai `T_N` (§5.1). Jika dimuat, output wajib memberi label "alokasi beban pajak untuk perencanaan".

> Catatan regulasi: tim review merujuk PP Nomor 20 Tahun 2026 (berlaku 22 April 2026) untuk ketentuan PPh Final UMKM, termasuk jenis wajib pajak yang memenuhi syarat, ambang omzet Rp4,8 miliar, dan bagian omzet Rp500 juta yang tidak dikenai pajak untuk orang pribadi. Nilai ini **harus diverifikasi dengan konsultan pajak** sebelum dijadikan data awal (seed) `tax_rules`.

### 8.4 PPh yang Dipotong/Dipungut Pihak Lain (PPh 22, PPh 23)
Bagi pihak yang dipotong: **kredit pajak**, bukan biaya. Engine mencatatnya di kategori terpisah. Kategori pajak yang harus dibedakan:

| Kategori | Masuk laba rugi? | Masuk arus kas? |
|---|---|---|
| Beban pajak (`TAX_EXPENSE`) | Ya | Ya |
| Pajak terutang (`TAX_PAYABLE`) | — | Saat dibayar |
| Kredit pajak (`TAX_CREDIT`) | Tidak | Ya (kas berkurang saat dipotong) |
| Dipotong pihak lain (`WITHHELD_BY_OTHERS`) | Tidak | Ya |
| PPN keluaran/masukan | Tidak | Ya |

---

## 9. Break-Even dan Target Laba

### 9.1 Produk Tunggal
```
UCM = N − (C + V) − P × N        (kontribusi per unit)
```
- `UCM ≤ 0` → `NO_BREAK_EVEN`.
- `BEP_units = ceil(FC / UCM)` untuk unit diskrit (desimal jika satuan kontinu).
- `BEP_revenue = FC / CMR`, dengan `CMR = UCM / N`.
- `FC = 0` → `BEP = 0` dengan status `OK`.

### 9.2 Dengan Step-Fixed Cost
Untuk setiap tier `t` dengan biaya tetap `FC_t` pada rentang `[a_t, b_t]`:
```
Q*_t = ceil(FC_t / UCM)
```
- Jika `a_t ≤ Q*_t ≤ b_t` → titik impas di tier tersebut; tier menguntungkan pada `[Q*_t, b_t]`.
- Jika `Q*_t < a_t` → seluruh tier menguntungkan `[a_t, b_t]`.
- Jika `Q*_t > b_t` → tier tidak menguntungkan.

Output: `first_break_even_units` (titik impas terendah) **dan** `profitable_ranges` (daftar rentang dengan laba operasional ≥ 0). Jika tidak ada rentang menguntungkan → `NO_BREAK_EVEN_WITHIN_CAPACITY`.

Laba bisa menjadi negatif kembali saat tier berikutnya terpicu. UI wajib menampilkan rentang, bukan hanya satu angka.

### 9.3 Multi-Produk (Weighted Contribution Margin)
Input: sales mix berdasarkan unit (`mix_basis = UNITS`) atau pendapatan (`REVENUE`).
```
Per satu "paket mix":
    R_mix  = Σ mix_i × N_i
    CM_mix = Σ mix_i × UCM_i
    WCMR   = CM_mix / R_mix
BEP_revenue    = FC / WCMR
BEP_mix_units  = FC / CM_mix        → BEP_units_i = BEP_mix_units × mix_i
```
Asumsi sales mix wajib ditampilkan di output.

### 9.4 Pendapatan yang Dibutuhkan untuk Target Laba
| Target | Rumus | Syarat |
|---|---|---|
| Laba operasional `TOP` | `R = (FC + TOP) / CMR` | `CMR > 0` |
| Laba bersih, PPh berbasis laba (tarif `t`) | `PBT = NP / (1 − t)`, lalu `R = (FC + PBT) / CMR` (dengan asumsi tidak ada pendapatan/biaya non-operasional) | `t < 1` |
| Laba bersih, PPh berbasis omzet (tarif `r`) | `R = (FC + NP) / (CMR − r)` | `CMR − r > 0` |

Rumus berlaku jika CMR konstan di rentang volume dan tidak ada step-fixed cost. Jika ada step-fixed cost, engine menghitung per tier seperti §9.2 dan mengembalikan pendapatan terendah yang memenuhi target. Rumus omzet mengabaikan ambang bebas pajak; jika ada ambang, engine menyelesaikannya secara bertahap per segmen omzet.

---

## 10. Eskalasi Biaya

`n` = jumlah periode eskalasi **penuh** yang telah lewat sejak `effective_from` sampai `as_of_date` (dibulatkan ke bawah).

| Tipe | Rumus |
|---|---|
| `NOMINAL` | `base + n × amount` |
| `SIMPLE_PCT` | `base × (1 + r × n)` |
| `COMPOUND_PCT` | `base × (1 + r)^n` |
| `ACTIVITY_DRIVEN` | dihitung ulang dari §2 dengan aktivitas baru |
| `TIER_BASED` | perubahan tier §2.1 |
| `SCENARIO_OVERRIDE` | nilai atau rate dari skenario menggantikan nilai dasar |

`cap` dan `floor` diterapkan pada **nilai hasil**: `min(max(value, floor), cap)`.

Contoh: base 10.000, 5% per tahun, n = 3 → compound 11.576,25; simple 11.500; dengan cap 11.000 → 11.000.

---

## 11. Kapasitas

```
utilization       = required / available_regular
overtime_needed   = max(0, required − available_regular)     (dibatasi max_overtime)
unmet_demand      = max(0, required − (available_regular + overtime_allowed + expansion))
```
- `utilization > 1` → `CAPACITY_EXCEEDED`.
- Biaya lembur = jam lembur × tarif × multiplier lembur.
- Kebutuhan tenaga kerja dan shift dihitung dari aturan step-fixed (§2.1), **bukan** dengan mengalikan biaya lama dengan persentase pertumbuhan.
- Semua tambahan sumber daya tercatat di `trace` dan `simulation_results`.

---

## 12. Skenario & Reproduksibilitas

- Skenario = kumpulan override terhadap input dasar (mis. bahan baku +8%, volume −3%). Override diterapkan setelah data dasar dimuat dan sebelum kalkulasi.
- Setiap run menyimpan `input_snapshot` lengkap (setelah override), `result_snapshot`, `engine_version`, dan `input_hash`.
- Menjalankan ulang snapshot lama dengan engine versi yang sama wajib menghasilkan output identik. Jika engine diperbarui, run lama tetap dapat direproduksi dengan versi engine lamanya.

---

## 13. Batasan Versi Ini (Out of Scope v1.0)
- Optimasi harga berbasis elastisitas permintaan (PRD §8.4 Price Optimization). Tanpa kurva permintaan, engine **tidak boleh** mengklaim harga optimal pasar.
- Alokasi resiprokal.
- Kompensasi rugi fiskal dan fasilitas pajak khusus.
- Konsolidasi multi-currency lintas organisasi.
