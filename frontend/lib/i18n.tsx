"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Lang } from "./format";

// Bahasa UI terpisah dari data: nama produk/kategori milik pengguna tidak pernah diterjemahkan (PRD §4.4).
const DICT = {
  "app.name": ["Smart Pricing Engine", "Smart Pricing Engine"],
  "app.tagline": ["Perencanaan harga & profit berbasis data", "Data-driven pricing & profit planning"],

  "nav.dashboard": ["Dashboard", "Dashboard"],
  "nav.products": ["Produk", "Products"],
  "nav.calculator": ["Kalkulator Harga", "Price Calculator"],
  "nav.recommendations": ["Rekomendasi Harga", "Price Recommendations"],
  "nav.settings": ["Pengaturan", "Settings"],
  "nav.organization": ["Organisasi", "Organization"],
  "nav.users": ["Pengguna & Role", "Users & Roles"],
  "nav.catalog": ["Satuan & Kategori", "Units & Categories"],
  "nav.audit": ["Audit Log", "Audit Log"],
  "nav.pricing": ["Pricing", "Pricing"],
  "nav.logout": ["Keluar", "Sign out"],

  "common.save": ["Simpan", "Save"],
  "common.cancel": ["Batal", "Cancel"],
  "common.add": ["Tambah", "Add"],
  "common.edit": ["Ubah", "Edit"],
  "common.close": ["Tutup", "Close"],
  "common.search": ["Cari", "Search"],
  "common.loading": ["Memuat…", "Loading…"],
  "common.saving": ["Menyimpan…", "Saving…"],
  "common.empty": ["Belum ada data", "No data yet"],
  "common.all": ["Semua", "All"],
  "common.status": ["Status", "Status"],
  "common.name": ["Nama", "Name"],
  "common.code": ["Kode", "Code"],
  "common.date": ["Tanggal", "Date"],
  "common.actions": ["Aksi", "Actions"],
  "common.prev": ["Sebelumnya", "Previous"],
  "common.next": ["Berikutnya", "Next"],
  "common.of": ["dari", "of"],
  "common.optional": ["opsional", "optional"],
  "common.version": ["Versi", "Version"],
  "common.remove": ["Hapus", "Remove"],
  "common.noPermission": ["Anda tidak memiliki izin untuk tindakan ini.", "You don't have permission for this action."],

  "auth.login": ["Masuk", "Sign in"],
  "auth.register": ["Daftar", "Create account"],
  "auth.email": ["Email", "Email"],
  "auth.password": ["Password", "Password"],
  "auth.fullName": ["Nama lengkap", "Full name"],
  "auth.noAccount": ["Belum punya akun?", "Don't have an account?"],
  "auth.haveAccount": ["Sudah punya akun?", "Already have an account?"],
  "auth.passwordHint": ["Minimal 10 karakter", "At least 10 characters"],
  "auth.welcome": ["Masuk ke akun Anda", "Sign in to your account"],
  "auth.createTitle": ["Buat akun baru", "Create a new account"],

  "onb.title": ["Buat organisasi", "Create your organization"],
  "onb.subtitle": ["Satu organisasi = satu perusahaan dengan data terpisah.", "One organization = one company with isolated data."],
  "onb.slug": ["ID singkat (huruf kecil, angka, tanda -)", "Short ID (lowercase, digits, dashes)"],
  "onb.currency": ["Mata uang utama", "Base currency"],
  "onb.fiscal": ["Awal tahun fiskal (bulan)", "Fiscal year start (month)"],
  "onb.models": ["Model bisnis", "Business models"],
  "onb.primary": ["Utama", "Primary"],
  "onb.hybridHint": ["Pilih lebih dari satu untuk bisnis Hybrid.", "Select more than one for a Hybrid business."],
  "onb.create": ["Buat organisasi", "Create organization"],

  "bm.MANUFACTURING": ["Manufaktur", "Manufacturing"],
  "bm.TRADING": ["Trading", "Trading"],
  "bm.DISTRIBUTION": ["Distribusi", "Distribution"],
  "bm.RETAIL": ["Retail", "Retail"],
  "bm.SERVICES": ["Jasa", "Services"],

  "pt.FINISHED_GOOD": ["Barang jadi", "Finished good"],
  "pt.MATERIAL": ["Bahan baku", "Material"],
  "pt.TRADED_GOOD": ["Barang dagang", "Traded good"],
  "pt.SERVICE": ["Jasa", "Service"],

  "status.ACTIVE": ["Aktif", "Active"],
  "status.INACTIVE": ["Nonaktif", "Inactive"],
  "status.ARCHIVED": ["Diarsipkan", "Archived"],
  "status.SUPERSEDED": ["Digantikan", "Superseded"],
  "status.DRAFT": ["Draf", "Draft"],
  "status.PENDING_APPROVAL": ["Menunggu persetujuan", "Pending approval"],
  "status.APPROVED": ["Disetujui", "Approved"],
  "status.REJECTED": ["Ditolak", "Rejected"],
  "status.PUBLISHED": ["Dipublikasikan", "Published"],

  "dash.title": ["Ringkasan", "Overview"],
  "dash.products": ["Produk aktif", "Active products"],
  "dash.materials": ["Bahan baku", "Materials"],
  "dash.recommendations": ["Rekomendasi harga", "Price recommendations"],
  "dash.recent": ["Rekomendasi terbaru", "Latest recommendations"],
  "dash.chart": ["Biaya vs harga rekomendasi", "Cost vs recommended price"],
  "dash.activity": ["Aktivitas terbaru", "Recent activity"],
  "dash.start": ["Mulai dari sini", "Start here"],
  "dash.step1": ["Tambahkan satuan dan produk", "Add units and products"],
  "dash.step2": ["Isi harga bahan baku dan BOM", "Enter material prices and BOM"],
  "dash.step3": ["Jalankan costing produk", "Run product costing"],
  "dash.step4": ["Hitung dan simpan rekomendasi harga", "Calculate and save a price recommendation"],

  "prod.title": ["Produk", "Products"],
  "prod.add": ["Tambah produk", "Add product"],
  "prod.sku": ["SKU", "SKU"],
  "prod.type": ["Tipe", "Type"],
  "prod.model": ["Model bisnis", "Business model"],
  "prod.unit": ["Satuan dasar", "Base unit"],
  "prod.category": ["Kategori", "Category"],
  "prod.description": ["Deskripsi", "Description"],
  "prod.archive": ["Arsipkan", "Archive"],
  "prod.archiveConfirm": ["Arsipkan produk ini? Histori biaya & harga tetap tersimpan.", "Archive this product? Cost & price history is kept."],
  "prod.searchPh": ["Cari nama atau SKU", "Search name or SKU"],
  "prod.needUnit": ["Buat satuan terlebih dahulu di Pengaturan → Satuan & Kategori.", "Create a unit first in Settings → Units & Categories."],
  "prod.tab.general": ["Informasi umum", "General"],
  "prod.tab.prices": ["Harga bahan", "Material prices"],
  "prod.tab.bom": ["BOM", "BOM"],
  "prod.tab.costing": ["Costing", "Costing"],
  "prod.tab.pricing": ["Pricing", "Pricing"],

  "mp.add": ["Tambah harga", "Add price"],
  "mp.price": ["Harga per satuan", "Unit price"],
  "mp.from": ["Berlaku sejak", "Effective from"],
  "mp.to": ["Berlaku sampai", "Effective to"],
  "mp.nature": ["Jenis data", "Data type"],
  "mp.supplier": ["Pemasok", "Supplier"],
  "mp.source": ["Sumber / referensi", "Source / reference"],
  "mp.hint": ["Harga baru otomatis menutup periode harga sebelumnya. Harga lama tidak diubah.", "A new price closes the previous period automatically. Old prices are never changed."],

  "nature.ACTUAL": ["Aktual", "Actual"],
  "nature.STANDARD": ["Standar", "Standard"],
  "nature.ESTIMATE": ["Estimasi", "Estimate"],
  "nature.SCENARIO": ["Skenario", "Scenario"],

  "bom.new": ["Buat versi BOM baru", "New BOM version"],
  "bom.output": ["Rencana output per batch", "Planned output per batch"],
  "bom.yield": ["Process yield (%)", "Process yield (%)"],
  "bom.material": ["Bahan baku", "Material"],
  "bom.netQty": ["Kebutuhan bersih per batch", "Net quantity per batch"],
  "bom.waste": ["Waste (% dari input)", "Waste (% of input)"],
  "bom.addLine": ["Tambah bahan", "Add material"],
  "bom.none": ["Belum ada BOM.", "No BOM yet."],
  "bom.needMaterials": ["Tambahkan produk bertipe Bahan baku terlebih dahulu.", "Add products of type Material first."],
  "bom.wasteHint": ["Waste = persentase dari material yang masuk proses. Yield = rasio output terhadap input proses.", "Waste = share of input material lost. Yield = process output/input ratio."],

  "cost.run": ["Jalankan costing", "Run costing"],
  "cost.structure": ["Struktur costing", "Costing structure"],
  "cost.BOM_BASED": ["Berdasarkan BOM", "BOM-based"],
  "cost.LANDED_COST": ["Landed cost (impor/beli)", "Landed cost (purchase/import)"],
  "cost.DIRECT_INPUT": ["Input langsung", "Direct input"],
  "cost.method": ["Metode", "Method"],
  "cost.asOf": ["Tanggal acuan harga", "Price as-of date"],
  "cost.labor": ["Tenaga kerja per batch", "Labor per batch"],
  "cost.machines": ["Mesin per batch", "Machines per batch"],
  "cost.hours": ["Jam", "Hours"],
  "cost.rate": ["Tarif per jam", "Hourly rate"],
  "cost.overhead": ["Overhead produksi per batch", "Production overhead per batch"],
  "cost.packaging": ["Packaging per batch", "Packaging per batch"],
  "cost.other": ["Biaya langsung lain", "Other direct cost"],
  "cost.scrap": ["Scrap / reject (%)", "Scrap / reject (%)"],
  "cost.rework": ["Rework (%)", "Rework (%)"],
  "cost.reworkCost": ["Biaya rework per unit", "Rework cost per unit"],
  "cost.qty": ["Kuantitas dibeli", "Quantity purchased"],
  "cost.purchasePrice": ["Harga beli per unit (mata uang asal)", "Purchase price per unit (source currency)"],
  "cost.fx": ["Kurs", "Exchange rate"],
  "cost.freight": ["Ongkos kirim", "Freight"],
  "cost.insurance": ["Asuransi", "Insurance"],
  "cost.duty": ["Bea masuk (%)", "Import duty (%)"],
  "cost.handling": ["Handling", "Handling"],
  "cost.otherAcq": ["Biaya perolehan lain", "Other acquisition cost"],
  "cost.goodQty": ["Kuantitas diterima baik", "Quantity received in good condition"],
  "cost.unitCost": ["Biaya per unit", "Unit cost"],
  "cost.justification": ["Alasan / sumber angka", "Justification / source"],
  "cost.history": ["Riwayat versi costing", "Costing version history"],
  "cost.breakdown": ["Rincian biaya batch", "Batch cost breakdown"],
  "cost.explain": ["Penjelasan perhitungan", "Calculation explanation"],
  "cost.activate": ["Jadikan versi aktif", "Make active version"],
  "cost.goodUnits": ["Unit baik", "Good units"],
  "cost.batchCost": ["Biaya batch", "Batch cost"],
  "cost.none": ["Belum ada costing. Jalankan costing untuk menghitung biaya per unit.", "No costing yet. Run costing to compute the unit cost."],
  "cost.active": ["Biaya aktif", "Active cost"],

  "price.method": ["Metode pricing", "Pricing method"],
  "price.product": ["Produk (memakai costing aktif)", "Product (uses active costing)"],
  "price.manual": ["— Input biaya manual —", "— Manual cost input —"],
  "price.unitCost": ["Biaya produk per unit (HPP)", "Product cost per unit (COGS)"],
  "price.variable": ["Biaya variabel lain per unit", "Other variable cost per unit"],
  "price.margin": ["Target margin (%)", "Target margin (%)"],
  "price.markup": ["Markup (%)", "Markup (%)"],
  "price.discount": ["Diskon (%)", "Discount (%)"],
  "price.fixed": ["Biaya tetap periode", "Fixed cost for the period"],
  "price.volume": ["Volume penjualan", "Sales volume"],
  "price.top": ["Target laba operasional", "Target operating profit"],
  "price.reference": ["Harga acuan", "Reference price"],
  "price.adjust": ["Penyesuaian (%)", "Adjustment (%)"],
  "price.fees": ["Fee & komisi (persentase)", "Fees & commissions (percentage)"],
  "price.feeName": ["Nama fee", "Fee name"],
  "price.feeRate": ["Tarif (%)", "Rate (%)"],
  "price.feeBase": ["Dihitung dari", "Based on"],
  "price.addFee": ["Tambah fee", "Add fee"],
  "price.taxLoad": ["Muat PPh berbasis omzet ke harga (%)", "Load turnover-based income tax into price (%)"],
  "price.rounding": ["Pembulatan harga", "Price rounding"],
  "price.increment": ["Kelipatan", "Increment"],
  "price.mode": ["Mode", "Mode"],
  "price.applyTo": ["Dibulatkan", "Round the"],
  "price.guard": ["Margin guard (naikkan jika margin turun)", "Margin guard (round up if margin drops)"],
  "price.calculate": ["Hitung harga", "Calculate price"],
  "price.save": ["Simpan sebagai rekomendasi", "Save as recommendation"],
  "price.effective": ["Tanggal berlaku", "Effective date"],
  "price.result": ["Hasil", "Result"],
  "price.minimum": ["Harga minimum", "Minimum price"],
  "price.target": ["Harga target (presisi penuh)", "Target price (full precision)"],
  "price.list": ["Harga daftar rekomendasi", "Recommended list price"],
  "price.net": ["Harga bersih setelah diskon", "Net price after discount"],
  "price.gm": ["Gross margin", "Gross margin"],
  "price.cm": ["Contribution margin", "Contribution margin"],
  "price.feeTotal": ["Total fee", "Total fees"],
  "price.contribution": ["Kontribusi per unit", "Contribution per unit"],
  "price.saved": ["Rekomendasi tersimpan.", "Recommendation saved."],
  "price.empty": ["Isi parameter lalu klik Hitung harga.", "Fill in the parameters and click Calculate price."],
  "price.marginDefHint": ["Gross margin hanya memperhitungkan HPP. Contribution margin juga memperhitungkan fee & biaya variabel.", "Gross margin only covers COGS. Contribution margin also covers fees & variable costs."],

  "method.MARKUP": ["Cost plus (markup)", "Cost plus (markup)"],
  "method.TARGET_GROSS_MARGIN": ["Target gross margin", "Target gross margin"],
  "method.TARGET_CONTRIBUTION_MARGIN": ["Target contribution margin", "Target contribution margin"],
  "method.MINIMUM_VIABLE": ["Harga minimum (kontribusi = 0)", "Minimum viable price"],
  "method.BREAK_EVEN": ["Harga break-even", "Break-even price"],
  "method.TARGET_OPERATING_PROFIT": ["Target laba operasional", "Target operating profit"],
  "method.COMPETITIVE": ["Harga kompetitor", "Competitive"],
  "method.VALUE_BASED": ["Value-based", "Value-based"],

  "base.NET_PRICE": ["Harga bersih", "Net price"],
  "base.LIST_PRICE": ["Harga daftar", "List price"],
  "base.GROSS_PRICE": ["Harga + PPN", "Price incl. VAT"],
  "base.PRODUCT_COST": ["Biaya produk", "Product cost"],

  "rec.title": ["Rekomendasi harga", "Price recommendations"],
  "rec.detail": ["Detail rekomendasi", "Recommendation detail"],
  "rec.assumptions": ["Asumsi", "Assumptions"],
  "rec.snapshot": ["Snapshot perhitungan", "Calculation snapshot"],
  "rec.engine": ["Versi engine", "Engine version"],
  "rec.hash": ["Hash input", "Input hash"],

  "org.title": ["Profil organisasi", "Organization profile"],
  "org.timezone": ["Zona waktu", "Time zone"],
  "org.language": ["Bahasa default", "Default language"],
  "org.saved": ["Perubahan tersimpan.", "Changes saved."],
  "org.roles": ["Role Anda", "Your roles"],

  "users.title": ["Pengguna & role", "Users & roles"],
  "users.add": ["Tambah anggota", "Add member"],
  "users.addHint": ["Pengguna harus sudah mendaftar akun terlebih dahulu.", "The user must have registered an account first."],
  "users.roles": ["Role", "Roles"],

  "catalog.units": ["Satuan", "Units"],
  "catalog.categories": ["Kategori produk", "Product categories"],
  "catalog.dimension": ["Dimensi", "Dimension"],
  "catalog.parent": ["Induk", "Parent"],

  "audit.title": ["Audit log", "Audit log"],
  "audit.action": ["Aksi", "Action"],
  "audit.entity": ["Entitas", "Entity"],
  "audit.changes": ["Perubahan", "Changes"],
  "audit.before": ["Sebelum", "Before"],
  "audit.after": ["Sesudah", "After"],

  "warn.BELOW_MIN_PRICE": ["Harga di bawah harga minimum", "Price below minimum price"],
  "warn.BELOW_TARGET_MARGIN": ["Margin di bawah target", "Margin below target"],
  "warn.CAPACITY_EXCEEDED": ["Kapasitas terlampaui", "Capacity exceeded"],
} as const;

export type TKey = keyof typeof DICT;

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (key: TKey | string) => string };
const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("id");
  useEffect(() => {
    try {
      const saved = localStorage.getItem("spe_lang");
      if (saved === "id" || saved === "en") setLangState(saved);
    } catch {
      /* abaikan */
    }
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("spe_lang", l);
    } catch {
      /* abaikan */
    }
  }, []);
  const t = useCallback(
    (key: string) => {
      const entry = (DICT as Record<string, readonly [string, string]>)[key];
      return entry ? entry[lang === "id" ? 0 : 1] : key;
    },
    [lang],
  );
  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}
