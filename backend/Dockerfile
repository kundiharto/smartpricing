# Dibangun dari root repository: docker build -f backend/Dockerfile .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY engine /srv/engine
COPY backend /srv/backend
RUN pip install /srv/engine /srv/backend \
 && useradd --create-home --uid 10001 app
WORKDIR /srv/backend
USER app

# Migrasi dijalankan sebelum server start (memakai SPE_MIGRATION_DATABASE_URL, role pemilik tabel).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
