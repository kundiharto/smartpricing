"""Siapkan database produksi (Neon) sebelum deploy pertama.

- membuat role aplikasi `spe_app` (LOGIN, NOBYPASSRLS, bukan superuser) dengan password acak
- memasang ekstensi btree_gist & citext
- menulis dua URL koneksi ke deploy/.secrets.local (tidak di-commit) untuk diisi di Render

Pakai (dari folder backend):
    NEON_OWNER_URL='postgresql://neondb_owner:...@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require' \
    .venv/bin/python ../deploy/bootstrap_db.py
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from psycopg import sql

APP_ROLE = "spe_app"
OUT = Path(__file__).resolve().parent / ".secrets.local"


def main() -> None:
    owner_url = os.environ.get("NEON_OWNER_URL", "").strip()
    if not owner_url:
        sys.exit("NEON_OWNER_URL belum diisi")
    parts = urlsplit(owner_url)
    if "sslmode=" not in parts.query:
        parts = parts._replace(query=(parts.query + "&" if parts.query else "") + "sslmode=require")
    owner_url = urlunsplit(parts)

    app_password = secrets.token_urlsafe(32)
    with psycopg.connect(owner_url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,)).fetchone()
        verb = "ALTER" if exists else "CREATE"
        conn.execute(
            sql.SQL("{} ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}").format(
                sql.SQL(verb), sql.Identifier(APP_ROLE), sql.Literal(app_password)
            )
        )
        db = conn.execute("SELECT current_database()").fetchone()[0]
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(db), sql.Identifier(APP_ROLE)))
        conn.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        conn.execute("CREATE EXTENSION IF NOT EXISTS citext")
        bypass = conn.execute("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = %s", (APP_ROLE,)).fetchone()
        if any(bypass):
            sys.exit("Role aplikasi memiliki BYPASSRLS/superuser — hentikan, isolasi tenant tidak aman")
        owner_bypass = conn.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user").fetchone()[0]

    host_part = parts.netloc.split("@", 1)[1]
    app_url = urlunsplit(parts._replace(netloc=f"{APP_ROLE}:{quote(app_password, safe='')}@{host_part}"))
    to_sqlalchemy = lambda u: u.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)  # noqa: E731
    OUT.write_text(
        "# JANGAN di-commit. Isi kedua nilai ini di Render (Blueprint → Environment).\n"
        f"SPE_DATABASE_URL={to_sqlalchemy(app_url)}\n"
        f"SPE_MIGRATION_DATABASE_URL={to_sqlalchemy(owner_url)}\n"
    )
    OUT.chmod(0o600)
    print(f"Role {APP_ROLE}: {verb.lower()}d (NOBYPASSRLS ✓). Ekstensi siap.")
    print(f"Owner BYPASSRLS: {owner_bypass} (tidak masalah; aplikasi memakai {APP_ROLE}).")
    print(f"URL koneksi ditulis ke {OUT} (izin 600).")


if __name__ == "__main__":
    main()
