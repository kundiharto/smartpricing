"""Smart Pricing Engine — calculation engine.

Library Python murni (tanpa database, jaringan, atau jam sistem). Semua angka
memakai Decimal. Spesifikasi: docs/CALCULATION_SPEC.md.

Setiap fungsi kalkulasi publik:
- hanya menerima argumen keyword,
- mengembalikan `Result` (status, values, warnings, trace, engine_version, input_hash),
- tidak melempar exception untuk input yang salah; status-nya `INVALID_INPUT`.
"""

from .core import ENGINE_VERSION, Result, Status, quantize_money

__all__ = ["ENGINE_VERSION", "Result", "Status", "quantize_money"]
__version__ = ENGINE_VERSION
