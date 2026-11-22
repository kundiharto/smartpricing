FROM python:3.13-slim
WORKDIR /srv
COPY engine /srv/engine
COPY backend /srv/backend
RUN pip install --no-cache-dir /srv/engine /srv/backend
WORKDIR /srv/backend
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
