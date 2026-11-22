"""Hash password (Argon2id) dan token akses (JWT)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()

# Hash tiruan agar waktu respons login sama untuk email yang tidak terdaftar.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    s = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=s.access_token_ttl_minutes)
    token = jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": expires, "jti": str(uuid.uuid4())},
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )
    return token, expires


def decode_access_token(token: str) -> uuid.UUID | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["sub", "exp"]})
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
