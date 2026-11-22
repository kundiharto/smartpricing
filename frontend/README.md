# Smart Pricing Engine — Web App

Next.js 15 (App Router) + TypeScript + Tailwind CSS 4 + TanStack Query + Recharts.

Frontend **tidak menghitung apa pun**: semua angka finansial berasal dari backend sebagai string desimal
dan hanya diformat untuk tampilan. Input persen dikonversi ke pecahan dengan operasi string, tanpa floating point.

## Menjalankan

Backend harus berjalan di `http://127.0.0.1:8000` (lihat [`../backend/README.md`](../backend/README.md)).

```bash
npm install
```

```bash
npm run dev
```

Buka http://localhost:3000. Untuk data contoh, jalankan `../backend/scripts/seed_demo.py` (kredensial demo ada di file itu).

Alamat backend dapat diubah dengan variabel lingkungan `SPE_BACKEND_URL`.

## Keamanan sesi

| Aspek | Implementasi |
|---|---|
| Token | Disimpan di cookie `httpOnly` + `SameSite=Lax` (+ `Secure` di production). JavaScript di browser tidak pernah melihat token. |
| Akses API | Browser memanggil `/api/v1/*` di Next.js; route handler meneruskan ke backend dan menambahkan `Authorization` dari cookie. |
| CSRF | Request yang mengubah data wajib membawa header `x-spe-client: web`. Situs lain tidak bisa mengirim header kustom tanpa preflight CORS. |
| Halaman | `middleware.ts` mengarahkan pengguna tanpa sesi ke `/login`. |
| Izin | Menu & tombol disembunyikan sesuai permission organisasi aktif; backend tetap memeriksa setiap request. |

## Halaman

| Rute | Isi |
|---|---|
| `/login`, `/register`, `/onboarding` | Masuk, daftar, buat organisasi (mendukung Hybrid) |
| `/dashboard` | Ringkasan, grafik biaya vs harga, aktivitas, rekomendasi terbaru |
| `/products`, `/products/[id]` | Daftar & detail produk: info umum, harga bahan (berversi), BOM, costing, pricing |
| `/pricing/calculator` | Kalkulator harga 8 metode, fee per basis, diskon, pembulatan + margin guard, simpan rekomendasi |
| `/pricing/recommendations[/id]` | Daftar & detail rekomendasi dengan asumsi dan penjelasan perhitungan |
| `/settings/*` | Organisasi, pengguna & role, satuan & kategori, audit log |

Bahasa UI: Indonesia / English (tombol ID/EN). Nama produk dan data pengguna tidak diterjemahkan.

## Perbedaan dari rekomendasi PRD §10

- **shadcn/ui** diganti komponen ringan sendiri di `components/ui.tsx` (gaya serupa, tanpa generator CLI).
- **next-intl** diganti kamus sederhana di `lib/i18n.tsx`; bisa dimigrasikan bila butuh routing per bahasa.
- **React Hook Form + Zod** belum dipakai; validasi utama ada di backend dan ditampilkan per field.
