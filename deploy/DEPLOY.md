# Deploy: Vercel + Render + Neon

| Bagian | Layanan | Region |
|---|---|---|
| Database PostgreSQL | Neon (free) | AWS ap-southeast-1 (Singapura) |
| Server API (FastAPI, Docker) | Render (free) | Singapore |
| Web app (Next.js) | Vercel (Hobby) | sin1 (Singapura) |

Browser hanya bicara dengan Vercel. Vercel meneruskan request ke Render (`SPE_BACKEND_URL`) dan
menyimpan token di cookie httpOnly. Render menjalankan migrasi database setiap kali start.

## 1. Neon

1. Buat project di region **AWS Asia Pacific (Singapore)**, PostgreSQL 16.
2. Ambil connection string role pemilik (non-pooled), lalu jalankan dari folder `backend`:

```bash
NEON_OWNER_URL='postgresql://...' .venv/bin/python ../deploy/bootstrap_db.py
```

Skrip membuat role `spe_app` (NOBYPASSRLS) dengan password acak dan menulis dua URL ke
`deploy/.secrets.local` (tidak di-commit).

## 2. Render

1. Dashboard → **New → Blueprint** → pilih repository → Render membaca `render.yaml`.
2. Isi `SPE_DATABASE_URL` dan `SPE_MIGRATION_DATABASE_URL` dari `deploy/.secrets.local`.
   `SPE_JWT_SECRET` dibuat otomatis oleh Render.
3. Tunggu deploy selesai; cek `https://<nama>.onrender.com/api/v1/health`.

Catatan paket gratis: server tidur setelah 15 menit tanpa akses; akses pertama butuh ±1 menit.

## 3. Vercel

Dari folder `frontend`:

```bash
npx vercel link
```

```bash
npx vercel env add SPE_BACKEND_URL production
```

```bash
npx vercel deploy --prod
```

`SPE_BACKEND_URL` = URL Render tanpa `/api/v1`, mis. `https://smartpricing-api.onrender.com`.

## 4. Data demo (opsional)

```bash
SPE_API_BASE=https://<render>/api/v1 SPE_DEMO_PASSWORD='<acak>' .venv/bin/python scripts/seed_demo.py
```

```bash
SPE_API_BASE=https://<render>/api/v1 SPE_DEMO_PASSWORD='<acak>' .venv/bin/python scripts/seed_demo_planning.py
```

## Keamanan produksi

- Server menolak start bila `SPE_JWT_SECRET` < 32 karakter atau URL database masih nilai development.
- Login dibatasi 10 percobaan / 15 menit per email dan 30 / menit per IP; pendaftaran 10 / jam per IP.
- Aplikasi memakai role `spe_app` tanpa BYPASSRLS; migrasi memakai role pemilik.
- Header keamanan (X-Frame-Options, nosniff, Referrer-Policy) di web app; cookie sesi `Secure` di production.
