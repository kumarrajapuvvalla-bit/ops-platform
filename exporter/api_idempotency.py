"""api_idempotency.py — In-memory idempotency key cache for score overrides.

Prevents duplicate score override processing when clients retry.
Production pattern: Redis SETNX with TTL.
"""

import time
from typing import Any, Optional

_CACHE: dict[str, tuple[float, Any]] = {}
TTL_SECONDS = 60


def get_cached(key: str) -> Optional[Any]:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.monotonic() > expires_at:
        del _CACHE[key]
        return None
    return value


def set_cached(key: str, value: Any) -> None:
    _CACHE[key] = (time.monotonic() + TTL_SECONDS, value)


def cache_size() -> int:
    now = time.monotonic()
    return sum(1 for exp, _ in _CACHE.values() if now <= exp)
