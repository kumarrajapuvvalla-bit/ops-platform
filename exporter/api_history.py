"""api_history.py — In-memory Fleet Score history store with cursor pagination.

Stores the last 500 score snapshots in memory.
Provides cursor-based pagination via opaque base64 position cursors.

In production: replace with TimescaleDB / DynamoDB query.
"""

import base64
import time
from typing import Any, Optional

MAX_HISTORY = 500
_HISTORY: list[dict[str, Any]] = []


def record_score(
    score: float,
    environment: str,
    cluster: str,
    degraded_services: list[str],
    breach_reason: Optional[str],
) -> None:
    """Append a fleet score snapshot."""
    _HISTORY.append(
        {
            "score": score,
            "environment": environment,
            "cluster": cluster,
            "degraded_services": degraded_services,
            "breach_reason": breach_reason,
            "recorded_at": int(time.time()),
        }
    )
    if len(_HISTORY) > MAX_HISTORY:
        _HISTORY.pop(0)


def _encode(index: int) -> str:
    return base64.urlsafe_b64encode(str(index).encode()).decode()


def _decode(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return 0


def paginate_history(
    cursor: Optional[str] = None,
    limit: int = 20,
    environment: Optional[str] = None,
) -> dict[str, Any]:
    """Return a page of history entries, optionally filtered by environment."""
    limit = max(1, min(limit, 100))
    items = [
        e for e in _HISTORY
        if environment is None or e["environment"] == environment
    ]
    start = _decode(cursor) if cursor else 0
    page = items[start: start + limit]
    total = len(items)
    next_cursor = _encode(start + limit) if (start + limit) < total else None
    return {
        "items": page,
        "total": total,
        "limit": limit,
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None,
    }


def history_size() -> int:
    return len(_HISTORY)
