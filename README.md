# Smart Pricing Engine

Aplikasi web perencanaan harga & profit: costing produk, rekomendasi harga, dan simulasi — dengan
perhitungan yang deterministik, dapat dijelaskan, dan tersimpan sebagai snapshot.

| Folder | Isi | Status |
|---|---|---|
| [`docs/`](docs) | PRD v1.1, Calculation Spec, Database Spec, Test Suite Spec | Spesifikasi acuan |
| [`engine/`](engine) | Calculation Engine (Python murni, Decimal) | 122 tes lulus |
| [`backend/`](backend) | REST API FastAPI + PostgreSQL 16 (RLS multi-tenant) | 54 tes integrasi lulus |
| [`frontend/`](frontend) | Web app Next.js 15 | Tahap pertama |

## Menjalankan di komputer lokal

Prasyarat: PostgreSQL 16, Python 3.12+ dengan `uv`, Node.js 20+. Persiapan database ada di
[`backend/README.md`](backend/README.md).

1. API — di folder `backend`:

```bash
.venv/bin/uvicorn app.main:app --port 8000
```

2. Web app — di folder `frontend`:

```bash
npm run dev
```

3. Buka http://localhost:3000. Data contoh: jalankan `backend/scripts/seed_demo.py`, lalu `backend/scripts/seed_demo_planning.py` (biaya & skenario), saat API berjalan.

## Belum dibangun

Approval & publikasi harga, price list, pengaturan pajak/channel/kurs, perencanaan kapasitas
(selain biaya bertingkat), laporan & ekspor, impor CSV, AI Advisor, serta deployment online.
