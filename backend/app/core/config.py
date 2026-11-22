"""Konfigurasi aplikasi dari environment (prefix SPE_)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-0000000000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPE_", env_file=".env", extra="ignore")

    environment: str = "development"  # development | test | production

    # Koneksi aplikasi: role TANPA hak BYPASSRLS dan bukan pemilik tabel.
    database_url: str = "postgresql+psycopg://spe_app:spe_app_dev@localhost:5432/spe_dev"
    # Koneksi migrasi: pemilik tabel.
    migration_database_url: str = "postgresql+psycopg://spe_owner:spe_owner_dev@localhost:5432/spe_dev"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 480

    def validate_for_runtime(self) -> None:
        if self.environment == "production" and self.jwt_secret == DEV_JWT_SECRET:
            raise RuntimeError("SPE_JWT_SECRET wajib diisi di production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
