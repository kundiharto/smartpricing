"""Pembatas laju sederhana (sliding window, in-memory) untuk endpoint sensitif (PRD §4.2).

Cukup untuk satu instance server. Bila backend dijalankan lebih dari satu instance,
ganti dengan penyimpanan bersama (mis. Redis).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import ApiError


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                retry = int(self.window - (now - q[0])) + 1
                raise ApiError(429, "RATE_LIMITED", f"Terlalu banyak percobaan. Coba lagi dalam {retry} detik.", [{"retry_after": retry}])
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# Login: per alamat IP dan per email (melindungi akun dari tebak password).
login_by_ip = SlidingWindowLimiter(limit=30, window_seconds=60)
login_by_email = SlidingWindowLimiter(limit=10, window_seconds=15 * 60)
# Pendaftaran akun baru per IP.
register_by_ip = SlidingWindowLimiter(limit=10, window_seconds=60 * 60)

ALL = (login_by_ip, login_by_email, register_by_ip)


def client_ip(request: Request) -> str:
    """IP klien asli. Web app (proxy Next.js) meneruskan X-Forwarded-For dari pengguna."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first[:64]
    return request.client.host if request.client else "unknown"


def reset_all() -> None:
    for limiter in ALL:
        limiter.reset()
