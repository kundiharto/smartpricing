# Smart Pricing Engine — Backend API

FastAPI + PostgreSQL 16. Seluruh kalkulasi dijalankan oleh [`../engine`](../engine); backend
menyimpan input, hasil, dan snapshot-nya.

## Menjalankan secara lokal (PostgreSQL Homebrew)

Persiapan satu kali:

```bash
brew install postgresql@16 && brew services start postgresql@16
```

```bash
psql -d postgres -f ../infrastructure/docker/init-db.sql
```

```bash
psql -d postgres -c "CREATE DATABASE spe_test OWNER spe_owner" && psql -d spe_test -c "CREATE EXTENSION btree_gist; CREATE EXTENSION citext; GRANT CONNECT ON DATABASE spe_test TO spe_app"
```

Install dan migrasi:

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ../engine -e ".[dev]"
```

```bash
.venv/bin/alembic upgrade head
```

Jalankan API (dokumentasi interaktif di http://localhost:8000/api/v1/docs):

```bash
.venv/bin/uvicorn app.main:app --reload
```

Tes integrasi (memakai database `spe_test`, dibangun ulang setiap sesi):

```bash
.venv/bin/python -m pytest -q
```

## Keamanan data antar-organisasi

| Lapis | Implementasi |
|---|---|
| Role database | Aplikasi memakai `spe_app`: bukan pemilik tabel, `NOBYPASSRLS`, tanpa hak `DELETE` (data diarsipkan). Migrasi memakai `spe_owner`. |
| Row-Level Security | Semua tabel tenant `FORCE ROW LEVEL SECURITY`. Backend mengatur `app.current_org_id` dan `app.current_user_id` di awal setiap transaksi. |
| Composite foreign key | `(organization_id, id)` sehingga baris organisasi A tidak dapat merujuk baris organisasi B, bahkan oleh superuser. |
| Otorisasi API | Header `X-Organization-Id` selalu diverifikasi terhadap keanggotaan aktif; izin dicek per endpoint (RBAC). |

## Endpoint (prefix `/api/v1`)

| Area | Endpoint |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Organisasi | `GET/POST /organizations`, `GET/PATCH /organizations/{id}`, `GET/POST /organizations/{id}/members` |
| Katalog | `GET/POST /units`, `GET/POST /product-categories` |
| Produk | `GET/POST /products`, `GET/PATCH/DELETE /products/{id}` (DELETE = arsip) |
| Harga material | `GET/POST /products/{id}/material-prices` (berversi tanggal) |
| BOM | `GET/POST /products/{id}/bom` (versi baru menggantikan versi aktif) |
| Costing | `GET/POST /products/{id}/costing`, `GET /products/{id}/costing/{versionId}` |
| Pricing | `POST /pricing/calculate`, `POST /pricing/recommend`, `GET /pricing/recommendations[/{id}]` |
| Audit | `GET /audit-logs` |

Endpoint selain auth dan organisasi memerlukan header `Authorization: Bearer <token>` dan `X-Organization-Id`.
Angka finansial dikirim sebagai string desimal (`"0.30"`); angka float ditolak.

## Belum termasuk di tahap ini

Approval harga & publikasi price list, cost items/driver/alokasi via API, pajak (`tax_rules`),
sales channel, kurs, undangan pengguna via email, reset password, rate limiting, dan idempotency key.
