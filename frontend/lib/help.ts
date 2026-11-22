"use client";

import { useCallback } from "react";
import { useI18n } from "./i18n";

/**
 * Teks bantuan per kolom form: [penjelasan, contoh] untuk ID dan EN.
 * Ditampilkan sebagai tooltip ⓘ (hover/klik) dan kotak bantuan saat kolom diisi.
 */
type Entry = { id: [string, string?]; en: [string, string?] };

const HELP: Record<string, Entry> = {
  // --- Onboarding & organisasi ---
  "org.name": {
    id: ["Nama resmi perusahaan Anda. Akan tampil di seluruh aplikasi dan laporan.", "PT Maju Bersama Sejahtera"],
    en: ["Your company's legal name. Shown across the app and in reports.", "PT Maju Bersama Sejahtera"],
  },
  "org.slug": {
    id: ["Kode unik pendek untuk organisasi, dipakai sistem. Hanya huruf kecil, angka, dan tanda '-'. Terisi otomatis dari nama.", "maju-bersama"],
    en: ["A short unique code for the organization. Lowercase letters, digits and '-' only. Filled in from the name.", "maju-bersama"],
  },
  "org.currency": {
    id: ["Mata uang utama untuk semua harga dan biaya. Harga beli dalam mata uang asing dikonversi memakai kurs saat costing.", "IDR"],
    en: ["Base currency for all prices and costs. Foreign purchase prices are converted with an exchange rate during costing.", "IDR"],
  },
  "org.fiscal": {
    id: ["Bulan pertama tahun buku perusahaan. Dipakai untuk periode perencanaan dan laporan.", "Januari (kebanyakan perusahaan di Indonesia)"],
    en: ["The first month of your fiscal year. Used for planning periods and reports.", "January"],
  },
  "org.models": {
    id: ["Jenis kegiatan bisnis Anda. Pilih lebih dari satu jika perusahaan memproduksi sekaligus menjual barang dagangan (Hybrid). 'Utama' menentukan pilihan default saat menambah produk.", "Pabrik roti yang juga menjual selai impor: Manufaktur (utama) + Trading"],
    en: ["What your business does. Pick more than one if you both manufacture and resell goods (Hybrid). 'Primary' sets the default when adding products.", "A bakery that also resells imported jam: Manufacturing (primary) + Trading"],
  },
  "org.language": {
    id: ["Bahasa default untuk organisasi. Setiap pengguna tetap bisa mengganti bahasa tampilan lewat tombol ID/EN.", "Bahasa Indonesia"],
    en: ["Default language for the organization. Each user can still switch with the ID/EN toggle.", "English"],
  },
  "org.timezone": {
    id: ["Zona waktu untuk menampilkan tanggal dan jam. Data tetap disimpan dalam UTC.", "Asia/Jakarta (WIB)"],
    en: ["Time zone used to display dates and times. Data is stored in UTC.", "Asia/Jakarta"],
  },

  // --- Produk ---
  "prod.sku": {
    id: ["Kode unik produk di perusahaan Anda (Stock Keeping Unit). Tidak bisa diubah setelah disimpan, dan tidak boleh sama dengan produk lain.", "RT-001"],
    en: ["Your unique product code (Stock Keeping Unit). Cannot be changed later and must not repeat.", "RT-001"],
  },
  "prod.type": {
    id: ["Barang jadi = produk hasil produksi (punya BOM). Bahan baku = dipakai di BOM (punya harga beli). Barang dagang = dibeli lalu dijual kembali (landed cost). Jasa = layanan.", "Roti tawar → Barang jadi; Tepung → Bahan baku"],
    en: ["Finished good = something you produce (has a BOM). Material = used in a BOM (has purchase prices). Traded good = bought and resold (landed cost). Service = a service.", "Bread → Finished good; Flour → Material"],
  },
  "prod.name": {
    id: ["Nama produk seperti yang dikenal tim Anda. Tidak diterjemahkan otomatis.", "Roti Tawar 400g"],
    en: ["Product name as your team knows it. Never auto-translated.", "White Bread 400g"],
  },
  "prod.unit": {
    id: ["Satuan dasar untuk menghitung kuantitas dan harga per unit. Buat satuan baru di Pengaturan → Satuan & Kategori.", "pcs untuk roti, kg untuk tepung"],
    en: ["Base unit for quantities and unit prices. Create new units in Settings → Units & Categories.", "pcs for bread, kg for flour"],
  },
  "prod.model": {
    id: ["Model bisnis produk ini. Menentukan cara costing yang relevan.", "Manufaktur untuk produk buatan sendiri"],
    en: ["The business model of this product. Determines which costing approach applies.", "Manufacturing for self-made products"],
  },
  "prod.category": {
    id: ["Pengelompokan produk untuk filter dan laporan. Opsional.", "Roti, Bahan kering, Kemasan"],
    en: ["Grouping for filters and reports. Optional.", "Bread, Dry goods, Packaging"],
  },
  "prod.description": {
    id: ["Catatan tambahan tentang produk. Opsional.", "Roti tawar putih, 20 iris"],
    en: ["Additional notes about the product. Optional.", "White bread, 20 slices"],
  },
  "prod.status": {
    id: ["Aktif = dipakai. Nonaktif = disembunyikan sementara tetapi masih bisa diaktifkan lagi. Untuk berhenti total, pakai tombol Arsipkan.", undefined],
    en: ["Active = in use. Inactive = temporarily hidden, can be reactivated. To retire a product, use Archive.", undefined],
  },

  // --- Harga bahan ---
  "mp.price": {
    id: ["Harga beli per 1 satuan dasar bahan (lihat satuan produk ini), tanpa PPN. Gunakan titik atau koma untuk desimal.", "12500 (Rp12.500 per kg)"],
    en: ["Purchase price per 1 base unit of the material, excluding VAT. Use a dot or comma for decimals.", "12500 (per kg)"],
  },
  "mp.from": {
    id: ["Tanggal harga ini mulai berlaku. Harga sebelumnya otomatis berakhir di tanggal ini, sehingga costing lama tetap bisa ditelusuri.", "1 Juli 2026 saat supplier menaikkan harga"],
    en: ["The date this price takes effect. The previous price ends automatically on this date, so older costings stay traceable.", "1 July 2026 when the supplier raises the price"],
  },
  "mp.nature": {
    id: ["Standar = harga patokan untuk perencanaan. Aktual = harga dari faktur nyata. Estimasi = perkiraan. Costing memilih jenis mana yang dipakai.", "Standar untuk harga kontrak tahunan"],
    en: ["Standard = planning benchmark. Actual = from real invoices. Estimate = a forecast. Costing chooses which type to use.", "Standard for annual contract prices"],
  },
  "mp.supplier": {
    id: ["Nama pemasok. Opsional, untuk catatan.", "PT Bogasari"],
    en: ["Supplier name. Optional, for reference.", "Bogasari"],
  },
  "mp.source": {
    id: ["Dari mana angka ini berasal, supaya bisa diaudit. Opsional.", "Faktur INV-2026-0412 / Penawaran 3 Juli"],
    en: ["Where this number comes from, for audit. Optional.", "Invoice INV-2026-0412"],
  },

  // --- BOM ---
  "bom.output": {
    id: ["Jumlah produk jadi yang direncanakan dari satu batch produksi. Semua kebutuhan bahan di bawah dihitung untuk jumlah ini.", "1000 (satu batch = 1000 roti)"],
    en: ["Number of finished units planned from one production batch. All material quantities below are for this amount.", "1000 (one batch = 1000 loaves)"],
  },
  "bom.yield": {
    id: ["Persentase output yang benar-benar dihasilkan proses (untuk proses yang menyusut, misalnya adonan menguap). Isi 100 jika tidak ada susut proses. Jangan isi kerugian yang sama dua kali dengan waste atau scrap.", "92 (100 kg adonan → 92 kg biskuit)"],
    en: ["Share of output the process actually yields (for processes that shrink). Enter 100 if there is no process loss. Don't count the same loss twice with waste or scrap.", "92 (100 kg dough → 92 kg biscuits)"],
  },
  "bom.material": {
    id: ["Bahan baku yang dipakai. Hanya produk bertipe Bahan baku yang muncul di sini.", "Tepung Terigu"],
    en: ["The material used. Only products of type Material appear here.", "Flour"],
  },
  "bom.netQty": {
    id: ["Kebutuhan bersih bahan untuk SELURUH batch (bukan per unit), dalam satuan dasar bahan, sebelum waste.", "250 kg tepung untuk 1000 roti"],
    en: ["Net material needed for the WHOLE batch (not per unit), in the material's base unit, before waste.", "250 kg flour for 1000 loaves"],
  },
  "bom.waste": {
    id: ["Persentase bahan yang terbuang dari bahan yang MASUK proses (potongan, tumpah, susut). Sistem menghitung kebutuhan input = bersih ÷ (1 − waste).", "3 (3% tepung tercecer)"],
    en: ["Share of the INPUT material lost (trimmings, spills, shrinkage). Required input = net ÷ (1 − waste).", "3 (3% of flour is spilled)"],
  },

  // --- Costing ---
  "cost.structure": {
    id: ["Berdasarkan BOM = biaya dihitung dari bahan di BOM + tenaga kerja + mesin + overhead. Landed cost = untuk barang yang dibeli/impor. Input langsung = Anda mengisi biaya per unit sendiri (wajib alasan).", undefined],
    en: ["BOM-based = cost from BOM materials + labor + machines + overhead. Landed cost = for purchased/imported goods. Direct input = you enter the unit cost yourself (justification required).", undefined],
  },
  "cost.asOf": {
    id: ["Tanggal acuan untuk mengambil harga bahan yang berlaku. Ganti ke tanggal lain untuk melihat biaya dengan harga masa lalu atau masa depan.", "Hari ini, atau 1 Januari 2027 untuk harga tahun depan"],
    en: ["Reference date used to pick the material prices in effect. Change it to cost with past or future prices.", "Today, or 1 January 2027 for next year's prices"],
  },
  "cost.nature": {
    id: ["Jenis harga bahan yang dipakai: Standar, Aktual, atau Estimasi. Harus sesuai dengan jenis harga yang sudah diisi di tab Harga bahan.", "Standar"],
    en: ["Which material price type to use: Standard, Actual or Estimate. Must match prices entered in the Material prices tab.", "Standard"],
  },
  "cost.labor": {
    id: ["Tenaga kerja langsung untuk SATU batch: nama peran, total jam kerja, dan tarif per jam. Klik Tambah untuk menambah baris.", "Baker · 24 jam · 35000"],
    en: ["Direct labor for ONE batch: role, total hours and hourly rate. Click Add for more rows.", "Baker · 24 h · 35000"],
  },
  "cost.machines": {
    id: ["Pemakaian mesin untuk SATU batch: nama mesin, jam pakai, dan biaya per jam (listrik, penyusutan, perawatan).", "Oven · 8 jam · 90000"],
    en: ["Machine usage for ONE batch: machine, hours used and cost per hour (power, depreciation, maintenance).", "Oven · 8 h · 90000"],
  },
  "cost.overhead": {
    id: ["Overhead pabrik yang dibebankan ke satu batch (listrik umum, sewa pabrik, supervisor). Jangan masukkan biaya kantor/administrasi di sini.", "1500000"],
    en: ["Factory overhead charged to one batch (general power, factory rent, supervisor). Don't include office/admin costs here.", "1500000"],
  },
  "cost.packaging": {
    id: ["Biaya kemasan untuk satu batch, jika kemasan TIDAK dimasukkan sebagai bahan di BOM.", "0 jika plastik kemasan sudah ada di BOM"],
    en: ["Packaging cost for one batch, if packaging is NOT already a BOM material.", "0 if packaging is in the BOM"],
  },
  "cost.other": {
    id: ["Biaya langsung lain untuk satu batch, misalnya biaya uji kualitas.", "250000"],
    en: ["Other direct cost for one batch, e.g. quality testing.", "250000"],
  },
  "cost.scrap": {
    id: ["Persentase produk jadi yang reject dan tidak bisa dijual. Biaya produk reject dibebankan ke produk yang baik.", "2 (2 dari 100 roti gosong)"],
    en: ["Share of finished units rejected and unsellable. Their cost is carried by the good units.", "2 (2 of 100 loaves burnt)"],
  },
  "cost.rework": {
    id: ["Persentase produk yang perlu dikerjakan ulang. Tidak mengurangi jumlah produk, tetapi menambah biaya rework.", "3"],
    en: ["Share of units that need rework. Doesn't reduce output but adds rework cost.", "3"],
  },
  "cost.reworkCost": {
    id: ["Biaya tambahan untuk mengerjakan ulang SATU unit.", "4000"],
    en: ["Extra cost to rework ONE unit.", "4000"],
  },
  "cost.qty": {
    id: ["Jumlah barang yang dibeli dalam satu pengiriman/pembelian.", "500"],
    en: ["Quantity bought in one shipment/purchase.", "500"],
  },
  "cost.purchasePrice": {
    id: ["Harga beli per unit dalam mata uang supplier (sebelum dikalikan kurs).", "2.5 (USD 2,50)"],
    en: ["Purchase price per unit in the supplier's currency (before the exchange rate).", "2.5 (USD 2.50)"],
  },
  "cost.fx": {
    id: ["Kurs ke mata uang organisasi. Isi 1 jika harga beli sudah dalam Rupiah.", "16000 (1 USD = Rp16.000)"],
    en: ["Exchange rate into your base currency. Enter 1 if the price is already in base currency.", "16000"],
  },
  "cost.freight": {
    id: ["Total ongkos kirim untuk seluruh pembelian ini (bukan per unit), dalam mata uang organisasi.", "1500000"],
    en: ["Total freight for the whole purchase (not per unit), in base currency.", "1500000"],
  },
  "cost.insurance": {
    id: ["Total asuransi pengiriman untuk seluruh pembelian.", "200000"],
    en: ["Total shipping insurance for the whole purchase.", "200000"],
  },
  "cost.duty": {
    id: ["Tarif bea masuk dalam persen dari nilai beli.", "5"],
    en: ["Import duty rate as a percentage of purchase value.", "5"],
  },
  "cost.handling": {
    id: ["Total biaya bongkar muat, gudang transit, dan penanganan.", "250000"],
    en: ["Total handling, transit warehouse and loading cost.", "250000"],
  },
  "cost.otherAcq": {
    id: ["Biaya perolehan lain untuk seluruh pembelian (dokumen, inspeksi).", "100000"],
    en: ["Other acquisition costs for the whole purchase (documents, inspection).", "100000"],
  },
  "cost.goodQty": {
    id: ["Jumlah yang diterima dalam kondisi baik. Barang rusak/hilang membuat biaya per unit barang baik naik. Kosongkan jika semua diterima baik.", "495 dari 500"],
    en: ["Quantity received in good condition. Damaged/lost units raise the cost of good units. Leave empty if all arrived fine.", "495 of 500"],
  },
  "cost.unitCost": {
    id: ["Biaya per unit yang Anda tentukan sendiri, dalam mata uang organisasi.", "60000"],
    en: ["The unit cost you set yourself, in base currency.", "60000"],
  },
  "cost.justification": {
    id: ["Wajib: jelaskan dari mana angka ini, supaya bisa dipertanggungjawabkan saat audit.", "Harga beli kontrak 2026 dengan supplier X"],
    en: ["Required: explain where this number comes from, for audit.", "2026 contract price with supplier X"],
  },
  "cost.activate": {
    id: ["Jika dicentang, hasil ini menjadi biaya aktif yang dipakai kalkulator harga; versi lama tetap tersimpan sebagai riwayat. Hilangkan centang untuk sekadar simulasi (draf).", undefined],
    en: ["If checked, this becomes the active cost used by the price calculator; older versions stay in history. Uncheck to just simulate (draft).", undefined],
  },

  // --- Kalkulator harga ---
  "price.product": {
    id: ["Pilih produk untuk memakai biaya dari costing aktifnya. Pilih 'Input biaya manual' untuk simulasi cepat tanpa produk (hasilnya tidak bisa disimpan).", "Roti Tawar 400g"],
    en: ["Choose a product to use its active costing. Choose 'Manual cost input' for a quick simulation (can't be saved).", "White Bread 400g"],
  },
  "price.unitCost": {
    id: ["Biaya produk per unit (HPP), tanpa PPN.", "60000"],
    en: ["Product cost per unit (COGS), excluding VAT.", "60000"],
  },
  "price.variable": {
    id: ["Biaya variabel lain per unit yang belum ada di HPP, misalnya ongkir ke pelanggan atau kemasan khusus channel. Isi 0 jika tidak ada.", "1500"],
    en: ["Other per-unit variable costs not in COGS, e.g. delivery to customer or channel-specific packaging. 0 if none.", "1500"],
  },
  "price.method": {
    id: ["Cara menentukan harga. Penjelasan metode yang dipilih ada di bawah kolom ini.", undefined],
    en: ["How the price is determined. The chosen method is explained below this field.", undefined],
  },
  "price.margin": {
    id: ["Persentase laba yang diinginkan dari harga jual bersih (bukan dari biaya).", "30 → dari harga Rp100.000, labanya Rp30.000"],
    en: ["Desired profit as a percentage of the net selling price (not of cost).", "30 → on a 100,000 price, profit is 30,000"],
  },
  "price.markup": {
    id: ["Persentase tambahan di atas biaya.", "25 → biaya Rp60.000 menjadi Rp75.000"],
    en: ["Percentage added on top of cost.", "25 → cost 60,000 becomes 75,000"],
  },
  "price.fixed": {
    id: ["Total biaya tetap periode yang harus ditutup (gaji kantor, sewa, dll.).", "50000000 per bulan"],
    en: ["Total fixed costs for the period that must be covered (salaries, rent, etc.).", "50000000 per month"],
  },
  "price.volume": {
    id: ["Perkiraan jumlah unit yang terjual dalam periode yang sama dengan biaya tetap.", "2000 unit per bulan"],
    en: ["Expected units sold in the same period as the fixed costs.", "2000 units per month"],
  },
  "price.top": {
    id: ["Laba operasional yang ingin dicapai dalam periode tersebut, di atas biaya tetap.", "30000000"],
    en: ["Operating profit you want in that period, on top of fixed costs.", "30000000"],
  },
  "price.reference": {
    id: ["Harga acuan: harga pesaing (metode kompetitor) atau nilai yang dipersepsikan pelanggan (value-based). Sistem lalu mengecek apakah harga ini masih menutup biaya.", "85000"],
    en: ["Reference price: a competitor's price or the customer-perceived value. The system then checks it still covers costs.", "85000"],
  },
  "price.adjust": {
    id: ["Penyesuaian dari harga pesaing. Positif = lebih mahal, negatif = lebih murah.", "-5 (5% di bawah pesaing)"],
    en: ["Adjustment to the competitor price. Positive = above, negative = below.", "-5 (5% below)"],
  },
  "price.discount": {
    id: ["Diskon dari harga daftar. Sistem menaikkan harga daftar agar margin tetap tercapai SETELAH diskon.", "20 → harga daftar Rp125.000, dibayar Rp100.000"],
    en: ["Discount off the list price. The list price is raised so the margin still holds AFTER the discount.", "20 → list 125,000, paid 100,000"],
  },
  "price.taxLoad": {
    id: ["Opsional: muat PPh final berbasis omzet ke harga, hanya jika perusahaan Anda memang memakai rezim itu (cek dengan konsultan pajak). Isi 0 jika tidak.", "0.5"],
    en: ["Optional: load a turnover-based final income tax into the price, only if your company uses that regime (check with a tax advisor). 0 if not.", "0.5"],
  },
  "price.fees": {
    id: ["Biaya yang dihitung sebagai persentase, misalnya komisi marketplace, komisi sales, atau fee payment gateway. Sistem memperhitungkannya agar margin tetap tercapai. Kosongkan jika tidak ada.", "Komisi marketplace · 8% · Harga bersih"],
    en: ["Percentage-based costs such as marketplace commission, sales commission or payment fees. They're built into the price so the margin holds.", "Marketplace commission · 8% · Net price"],
  },
  "price.feeBase": {
    id: ["Fee dihitung dari: Harga bersih (setelah diskon, paling umum untuk marketplace), Harga daftar (sebelum diskon), atau Biaya produk.", undefined],
    en: ["Fee is charged on: Net price (after discount, most marketplaces), List price (before discount), or Product cost.", undefined],
  },
  "price.increment": {
    id: ["Harga dibulatkan ke kelipatan angka ini agar mudah dibaca.", "500 → Rp11.762 menjadi Rp12.000"],
    en: ["The price is rounded to a multiple of this number.", "500 → 11,762 becomes 12,000"],
  },
  "price.mode": {
    id: ["NEAREST = ke kelipatan terdekat, UP = selalu ke atas, DOWN = selalu ke bawah.", undefined],
    en: ["NEAREST = closest multiple, UP = always up, DOWN = always down.", undefined],
  },
  "price.applyTo": {
    id: ["Harga mana yang dibulatkan: Harga daftar (yang tercetak di price list) atau Harga bersih (yang diterima setelah diskon).", undefined],
    en: ["Which price to round: List price (printed on the price list) or Net price (received after discount).", undefined],
  },
  "price.guard": {
    id: ["Jika pembulatan membuat margin turun di bawah target, harga otomatis dinaikkan satu kelipatan. Disarankan tetap aktif.", undefined],
    en: ["If rounding pushes the margin below target, the price is raised by one increment. Recommended.", undefined],
  },
  "price.effective": {
    id: ["Tanggal rencana harga ini mulai berlaku. Rekomendasi disimpan sebagai draf beserta seluruh asumsinya.", undefined],
    en: ["The date this price is planned to take effect. Saved as a draft with all its assumptions.", undefined],
  },

  // --- Pengguna & katalog ---
  "users.email": {
    id: ["Email akun pengguna. Orang tersebut harus sudah mendaftar di aplikasi terlebih dahulu.", "rina@perusahaan.co.id"],
    en: ["The user's account email. They must have registered first.", "rina@company.com"],
  },
  "users.roles": {
    id: ["Role menentukan apa yang boleh dilakukan. Seseorang boleh punya lebih dari satu role. Penjelasan setiap role tertera di bawah namanya.", undefined],
    en: ["Roles decide what someone may do. A person can have several roles. Each role is explained under its name.", undefined],
  },
  "unit.code": {
    id: ["Singkatan satuan, unik di organisasi.", "kg, pcs, liter, jam"],
    en: ["Unit abbreviation, unique in the organization.", "kg, pcs, l, h"],
  },
  "unit.name": {
    id: ["Nama lengkap satuan.", "Kilogram"],
    en: ["Full unit name.", "Kilogram"],
  },
  "unit.dimension": {
    id: ["Jenis ukuran: COUNT (jumlah/biji), MASS (berat), VOLUME, LENGTH (panjang), AREA (luas), TIME (waktu).", "kg → MASS, pcs → COUNT"],
    en: ["Kind of measure: COUNT, MASS, VOLUME, LENGTH, AREA, TIME.", "kg → MASS, pcs → COUNT"],
  },
  "cat.name": {
    id: ["Nama kategori produk.", "Roti Manis"],
    en: ["Product category name.", "Sweet Bread"],
  },
  "cat.parent": {
    id: ["Kategori induk jika ingin membuat sub-kategori. Opsional.", "Roti Manis → induk: Roti"],
    en: ["Parent category to create a sub-category. Optional.", "Sweet Bread → parent: Bread"],
  },
  // --- Biaya ---
  "cost.code": {
    id: ["Kode singkat unik untuk pos biaya ini. Dipakai di simulasi untuk mengubah biaya tertentu. Huruf, angka, - dan _.", "SEWA-GUDANG"],
    en: ["A short unique code for this cost. Used in scenarios to change a specific cost. Letters, digits, - and _.", "WAREHOUSE-RENT"],
  },
  "cost.name": {
    id: ["Nama pos biaya seperti yang dipakai tim keuangan.", "Sewa gudang Cikarang"],
    en: ["Cost name as your finance team uses it.", "Warehouse rent"],
  },
  "cost.category": {
    id: ["Kelompok biaya untuk laporan. Tidak memengaruhi cara perhitungan.", "Sewa → Operasional tetap; Komisi → Penjualan & pemasaran"],
    en: ["Grouping for reports. Does not change how it's calculated.", "Rent → Fixed operating; Commission → Selling"],
  },
  "cost.behavior": {
    id: ["Bagaimana biaya ini bergerak terhadap aktivitas. Penjelasan pilihan ada di bawah kolom ini.", undefined],
    en: ["How this cost moves with activity. The chosen option is explained below.", undefined],
  },
  "cost.scope": {
    id: ["Biaya periode = beban perusahaan (gaji kantor, sewa toko). Pool overhead = dibagikan ke produk untuk laba per produk. Sudah di HPP = sudah masuk costing produk, tidak akan dihitung lagi di simulasi (mencegah hitung ganda).", undefined],
    en: ["Period cost = company expense (office salaries, shop rent). Overhead pool = spread across products for product profit. Already in COGS = already in product costing, never counted again in simulations (prevents double counting).", undefined],
  },
  "cost.driver": {
    id: ["Aktivitas yang membuat biaya ini naik-turun. Unit terjual/diproduksi dan omzet dihitung otomatis dari rencana penjualan; jam kerja/mesin diisi di skenario.", "Ongkir → Unit terjual; Listrik mesin → Jam mesin"],
    en: ["The activity that drives this cost. Units sold/produced and revenue come from the sales plan; labor/machine hours are entered in the scenario.", "Freight → Units sold; Machine power → Machine hours"],
  },
  "cost.period": {
    id: ["Nominal tetap berlaku per periode berapa. Sistem menyesuaikan otomatis dengan lama skenario.", "Sewa Rp20 juta per bulan → pilih 'per bulan'"],
    en: ["Which period the fixed amount covers. Automatically scaled to the scenario length.", "Rent 20 million per month → 'per month'"],
  },
  "cost.effective": {
    id: ["Tanggal parameter ini mulai berlaku.", "1 Januari 2026"],
    en: ["Date these parameters take effect.", "1 January 2026"],
  },
  "cost.baseAmount": {
    id: ["Nominal biaya tetap per periode nominal (lihat kolom Periode).", "20000000"],
    en: ["Fixed amount per amount period.", "20000000"],
  },
  "cost.rate": {
    id: ["Biaya per 1 unit aktivitas driver. Untuk driver omzet, isi biaya per Rp1 omzet (mis. 0.02 = 2%).", "2000 per unit terjual"],
    en: ["Cost per 1 unit of driver activity. For a revenue driver, cost per 1 of revenue (e.g. 0.02 = 2%).", "2000 per unit sold"],
  },
  "cost.percentage": {
    id: ["Persentase dari omzet atau dari HPP.", "5 → komisi 5% dari omzet"],
    en: ["Percentage of revenue or of COGS.", "5 → 5% commission on revenue"],
  },
  "cost.percentageBase": {
    id: ["Omzet = harga jual × volume. HPP = biaya produk × volume.", undefined],
    en: ["Revenue = price × volume. COGS = product cost × volume.", undefined],
  },
  "cost.stepMode": {
    id: ["Tabel = Anda menentukan biaya untuk setiap rentang aktivitas. Per sumber daya = sistem menghitung jumlah orang/mesin yang dibutuhkan dari kapasitasnya.", "Tabel: 0–10.000 unit = 5 operator; Per sumber daya: 1 operator per 2.000 unit"],
    en: ["Table = you set the cost for each activity range. Per resource = the system computes how many people/machines are needed from their capacity.", "Table: 0–10,000 units = 5 operators; Per resource: 1 operator per 2,000 units"],
  },
  "cost.tiers": {
    id: ["Setiap baris: rentang aktivitas per periode nominal dan biayanya. Rentang tidak boleh tumpang tindih. Di atas tier tertinggi sistem memberi peringatan kapasitas.", "0–2.000 unit: 10 juta; 2.001–3.000 unit: 15 juta"],
    en: ["Each row: an activity range per amount period and its cost. Ranges must not overlap. Above the top tier you get a capacity warning.", "0–2,000 units: 10M; 2,001–3,000 units: 15M"],
  },
  "cost.capacity": {
    id: ["Berapa aktivitas yang bisa ditangani satu orang/mesin per periode nominal.", "2000 unit per operator per bulan"],
    en: ["How much activity one person/machine handles per amount period.", "2000 units per operator per month"],
  },
  "cost.costPerResource": {
    id: ["Biaya satu orang/mesin per periode nominal.", "6000000 gaji per operator"],
    en: ["Cost of one person/machine per amount period.", "6000000 salary per operator"],
  },
  "cost.maxResources": {
    id: ["Jumlah maksimum yang tersedia. Opsional; jika terlampaui muncul peringatan kapasitas.", "10 operator"],
    en: ["Maximum available. Optional; a capacity warning appears if exceeded.", "10 operators"],
  },
  "cost.minmax": {
    id: ["Batas bawah/atas total biaya per periode. Opsional.", "Listrik minimum Rp2 juta/bulan (abonemen)"],
    en: ["Lower/upper bound for the total per period. Optional.", "Minimum power bill 2M/month"],
  },
  "cost.escalation": {
    id: ["Kenaikan otomatis dari tanggal berlaku, misalnya kenaikan sewa tahunan. Dihitung berdasarkan tanggal mulai skenario.", "Sewa naik 10% per tahun"],
    en: ["Automatic increase from the effective date, e.g. annual rent increase. Based on the scenario start date.", "Rent +10% per year"],
  },
  "cost.source": {
    id: ["Dari mana angka ini berasal, untuk audit. Opsional.", "Kontrak sewa No. 12/2026"],
    en: ["Where the number comes from, for audit. Optional.", "Lease contract No. 12/2026"],
  },
  "cost.allocBasis": {
    id: ["Cara membagi pool overhead ke produk. Porsi omzet/volume dihitung otomatis dari rencana penjualan skenario.", "Overhead pabrik dibagi menurut jam mesin tiap produk"],
    en: ["How to spread the overhead pool across products. Revenue/volume shares come from the scenario's sales plan.", "Factory overhead by machine hours per product"],
  },
  "drv.code": {
    id: ["Kode driver, dipakai saat mengisi aktivitas di skenario.", "JAM-MESIN"],
    en: ["Driver code, used when entering activity in scenarios.", "MACHINE-H"],
  },
  "drv.type": {
    id: ["Unit terjual, unit diproduksi, dan omzet dihitung otomatis dari rencana penjualan. Jenis lain diisi manual di skenario.", undefined],
    en: ["Units sold, units produced and revenue are computed from the sales plan. Other types are entered in the scenario.", undefined],
  },
  "costs.simulate": {
    id: ["Perkiraan aktivitas dalam satu periode. Biaya bertingkat dan persentase dihitung dari angka ini.", "Unit 2.500, omzet 150.000.000"],
    en: ["Expected activity in one period. Step and percentage costs are computed from these numbers.", "Units 2,500, revenue 150,000,000"],
  },

  // --- Skenario ---
  "plan.name": {
    id: ["Nama yang mudah dibedakan saat dibandingkan.", "Rencana 2027 – dasar"],
    en: ["A name that's easy to tell apart when comparing.", "2027 plan – base"],
  },
  "plan.type": {
    id: ["Label saja untuk membedakan skenario: Dasar (rencana utama), Optimis, Pesimis, atau Kustom.", undefined],
    en: ["Just a label: Base (main plan), Optimistic, Pessimistic, or Custom.", undefined],
  },
  "plan.start": {
    id: ["Tanggal awal periode. Menentukan versi biaya dan harga bahan yang berlaku, serta eskalasi.", "1 Januari 2027"],
    en: ["Start of the period. Determines which cost versions apply, and escalation.", "1 January 2027"],
  },
  "plan.months": {
    id: ["Panjang periode simulasi. Volume yang Anda isi adalah total untuk seluruh periode ini; biaya bulanan dikalikan otomatis.", "12 untuk rencana tahunan"],
    en: ["Simulation length. Volumes you enter are totals for the whole period; monthly costs are scaled automatically.", "12 for an annual plan"],
  },
  "plan.lines": {
    id: ["Produk yang dijual, harga jual bersih (setelah diskon, tanpa PPN), dan volume untuk seluruh periode. HPP diambil dari costing aktif; isi Biaya manual hanya bila belum ada costing.", "Roti Tawar · 12.000 · 30.000 pcs"],
    en: ["Products sold, net selling price (after discount, excl. VAT) and volume for the whole period. COGS comes from active costing; use Manual cost only if there is none.", "White bread · 12,000 · 30,000 pcs"],
  },
  "plan.change": {
    id: ["Perubahan dalam persen dibanding rencana penjualan dan biaya di atas. Positif = naik, negatif = turun. Isi 0 jika tidak berubah.", "8 → bahan baku naik 8%; -3 → volume turun 3%"],
    en: ["Percentage change vs the sales plan and costs above. Positive = up, negative = down. 0 if unchanged.", "8 → materials +8%; -3 → volume −3%"],
  },
  "plan.itemChanges": {
    id: ["Ubah satu pos biaya tertentu saja, misalnya listrik naik 12% atau gaji naik 5%.", "LISTRIK +12"],
    en: ["Change one specific cost only, e.g. electricity +12% or salaries +5%.", "POWER +12"],
  },
  "plan.otherActivity": {
    id: ["Jumlah aktivitas untuk driver yang tidak berasal dari penjualan (jam kerja, jam mesin, dll.) selama periode skenario.", "JAM-MESIN 1.200"],
    en: ["Activity for drivers not derived from sales (labor hours, machine hours, ...) over the scenario period.", "MACHINE-H 1,200"],
  },
  "plan.taxRegime": {
    id: ["Berbasis laba = tarif × laba sebelum pajak. Final berbasis omzet = tarif × omzet (hanya bila perusahaan Anda memang memakai rezim ini; cek dengan konsultan pajak).", undefined],
    en: ["Profit-based = rate × profit before tax. Final turnover-based = rate × revenue (only if your company uses this regime; check with a tax advisor).", undefined],
  },
  "plan.taxRate": {
    id: ["Tarif pajak penghasilan dalam persen.", "22 untuk PPh badan"],
    en: ["Income tax rate in percent.", "22"],
  },
  "plan.exempt": {
    id: ["Bagian omzet yang tidak dikenai pajak dalam periode ini (untuk rezim berbasis omzet). Isi 0 jika tidak ada.", "0"],
    en: ["Part of turnover exempt from tax in this period (turnover regime). 0 if none.", "0"],
  },
  "plan.target": {
    id: ["Opsional. Sistem menghitung volume dan omzet yang dibutuhkan untuk mencapai target ini, termasuk jika harus menambah karyawan/mesin.", "Laba operasional 50.000.000"],
    en: ["Optional. The system computes the volume and revenue needed to reach it, including when extra staff/machines are needed.", "Operating profit 50,000,000"],
  },
  "plan.dataNature": {
    id: ["Jenis versi biaya yang dipakai: Standar untuk perencanaan, Aktual untuk realisasi, Estimasi untuk perkiraan.", undefined],
    en: ["Which cost version type to use: Standard for planning, Actual for realized, Estimate for forecasts.", undefined],
  },

};

/** Penjelasan metode pricing (ditampilkan di bawah pilihan metode). */
const METHOD_HELP: Record<string, { id: string; en: string }> = {
  TARGET_CONTRIBUTION_MARGIN: {
    id: "Paling disarankan bila ada fee/komisi. Harga = (biaya + biaya variabel) ÷ (1 − target margin − fee). Margin tetap tercapai setelah semua biaya variabel dan fee.",
    en: "Recommended when there are fees/commissions. Price = (cost + variable cost) ÷ (1 − target margin − fees). The margin holds after all variable costs and fees.",
  },
  TARGET_GROSS_MARGIN: {
    id: "Harga = biaya produk ÷ (1 − target margin). Hanya memperhitungkan HPP; fee dan biaya variabel lain TIDAK ikut. Cocok untuk penjualan langsung tanpa komisi.",
    en: "Price = product cost ÷ (1 − target margin). Covers COGS only; fees and other variable costs are NOT included. Suits direct sales without commissions.",
  },
  MARKUP: {
    id: "Harga = biaya × (1 + markup). Cara paling sederhana. Ingat: markup 25% ≠ margin 25% (markup 25% hanya menghasilkan margin 20%).",
    en: "Price = cost × (1 + markup). The simplest method. Note: 25% markup ≠ 25% margin (it yields a 20% margin).",
  },
  MINIMUM_VIABLE: {
    id: "Harga terendah yang masih menutup biaya variabel dan fee (laba per unit = 0). Jangan menjual di bawah harga ini.",
    en: "The lowest price that still covers variable costs and fees (zero contribution). Never sell below it.",
  },
  BREAK_EVEN: {
    id: "Harga agar biaya tetap periode tertutup tepat pada volume penjualan yang Anda isi (laba = 0).",
    en: "The price at which fixed costs are exactly covered at the sales volume you enter (zero profit).",
  },
  TARGET_OPERATING_PROFIT: {
    id: "Harga agar biaya tetap tertutup DAN target laba operasional tercapai pada volume penjualan yang Anda isi.",
    en: "The price that covers fixed costs AND reaches your operating profit target at the sales volume you enter.",
  },
  COMPETITIVE: {
    id: "Mulai dari harga pesaing, lalu sesuaikan naik/turun. Sistem memberi peringatan jika hasilnya di bawah harga minimum.",
    en: "Start from a competitor's price, then adjust up/down. You're warned if the result is below the minimum price.",
  },
  VALUE_BASED: {
    id: "Harga berdasarkan nilai yang dirasakan pelanggan. Sistem menghitung margin dan memberi peringatan jika di bawah harga minimum.",
    en: "Price based on customer-perceived value. The system computes the margin and warns if it's below the minimum price.",
  },
};

const STRUCTURE_HELP: Record<string, { id: string; en: string }> = {
  BOM_BASED: {
    id: "Langkah: (1) pastikan BOM dan harga bahan sudah diisi, (2) isi tenaga kerja, mesin, dan overhead untuk SATU batch, (3) isi persentase scrap bila ada. Sistem membagi total biaya batch dengan jumlah produk yang baik.",
    en: "Steps: (1) make sure the BOM and material prices exist, (2) enter labor, machines and overhead for ONE batch, (3) enter scrap if any. Total batch cost is divided by good units.",
  },
  LANDED_COST: {
    id: "Untuk barang yang dibeli/impor. Isi satu transaksi pembelian: kuantitas, harga beli, kurs, lalu biaya-biaya TOTAL (ongkir, asuransi, handling). Sistem menghitung biaya per unit yang diterima baik.",
    en: "For purchased/imported goods. Enter one purchase: quantity, price, exchange rate, then TOTAL costs (freight, insurance, handling). The system computes the cost per good unit received.",
  },
  DIRECT_INPUT: {
    id: "Isi biaya per unit secara langsung bila Anda sudah tahu angkanya (misalnya harga kontrak). Wajib menuliskan alasan/sumber agar bisa diaudit.",
    en: "Enter the unit cost directly when you already know it (e.g. a contract price). A justification/source is required for audit.",
  },
};

export const ROLE_HELP: Record<string, { id: string; en: string }> = {
  OWNER: { id: "Akses penuh, termasuk mengelola anggota dan menunjuk Owner lain.", en: "Full access, including managing members and appointing owners." },
  DIRECTOR: { id: "Melihat semua data, menghitung harga, dan menyetujui rekomendasi harga.", en: "Views everything, calculates prices and approves recommendations." },
  FINANCE_MANAGER: { id: "Mengelola produk, costing, dan menyimpan rekomendasi harga.", en: "Manages products, costing and saves price recommendations." },
  FINANCIAL_ANALYST: { id: "Mengisi data produk dan costing, menjalankan kalkulator harga.", en: "Enters product and costing data, runs the price calculator." },
  OPERATIONS_MANAGER: { id: "Mengelola produk, BOM, dan costing produksi.", en: "Manages products, BOMs and production costing." },
  SALES_MANAGER: { id: "Melihat produk dan rekomendasi, menjalankan kalkulator harga.", en: "Views products and recommendations, runs the price calculator." },
  VIEWER: { id: "Hanya melihat, tidak bisa mengubah apa pun.", en: "Read-only access." },
};

const BEHAVIOR_HELP: Record<string, { id: string; en: string }> = {
  FIXED: { id: "Jumlahnya sama berapa pun volume penjualan. Contoh: sewa, gaji staf kantor, langganan software.", en: "Same amount regardless of sales volume. E.g. rent, office salaries, software subscriptions." },
  VARIABLE: { id: "Naik-turun sebanding dengan aktivitas (tarif × aktivitas). Contoh: ongkir per paket, komisi per unit, listrik per jam mesin.", en: "Moves in proportion to activity (rate × activity). E.g. freight per parcel, per-unit commission, power per machine hour." },
  SEMI_VARIABLE: { id: "Ada bagian tetap + bagian variabel. Contoh: listrik = abonemen Rp2 juta + Rp1.500 per kWh.", en: "A fixed part plus a variable part. E.g. power = 2M subscription + 1,500 per kWh." },
  STEP_FIXED: { id: "Tetap dalam satu rentang, lalu naik bertingkat saat aktivitas melewati ambang. Contoh: 5 operator sampai 10.000 unit, 8 operator sampai 15.000 unit.", en: "Fixed within a range, then steps up when activity crosses a threshold. E.g. 5 operators up to 10,000 units, 8 up to 15,000." },
  PERCENTAGE: { id: "Persentase dari omzet atau HPP. Contoh: komisi sales 5% dari omzet, royalti 2%.", en: "A percentage of revenue or COGS. E.g. 5% sales commission, 2% royalty." },
};

const ALLOC_HELP: Record<string, { id: string; en: string }> = {
  EQUAL: { id: "Dibagi sama rata ke semua produk tujuan.", en: "Split equally across target products." },
  REVENUE: { id: "Dibagi sesuai porsi omzet tiap produk di skenario. Produk yang lebih laku menanggung overhead lebih besar.", en: "Split by each product's share of scenario revenue." },
  UNITS: { id: "Dibagi sesuai porsi volume tiap produk di skenario.", en: "Split by each product's share of scenario volume." },
  PERCENTAGE: { id: "Anda menentukan persentase tiap produk; totalnya harus 100%.", en: "You set each product's percentage; must total 100%." },
  DRIVER: { id: "Dibagi menurut nilai aktivitas yang Anda isi per produk, misalnya jam mesin atau luas gudang yang dipakai.", en: "Split by the activity value you enter per product, e.g. machine hours or warehouse space used." },
};

export type HelpText = { text: string; example?: string };

export function useHelp() {
  const { lang } = useI18n();
  const help = useCallback(
    (key: string): HelpText | undefined => {
      const e = HELP[key];
      if (!e) return undefined;
      const [text, example] = e[lang];
      return { text, example };
    },
    [lang],
  );
  const method = useCallback((m: string) => METHOD_HELP[m]?.[lang] ?? "", [lang]);
  const structure = useCallback((s: string) => STRUCTURE_HELP[s]?.[lang] ?? "", [lang]);
  const role = useCallback((r: string) => ROLE_HELP[r]?.[lang] ?? "", [lang]);
  const behavior = useCallback((b: string) => BEHAVIOR_HELP[b]?.[lang] ?? "", [lang]);
  const allocation = useCallback((b: string) => ALLOC_HELP[b]?.[lang] ?? "", [lang]);
  const exampleLabel = lang === "id" ? "Contoh" : "Example";
  return { help, method, structure, role, behavior, allocation, exampleLabel };
}
