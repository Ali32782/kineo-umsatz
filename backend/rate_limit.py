"""Einfaches In-Memory-Rate-Limit (pro Prozess / Render-Instanz)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

_lock = Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    """Wirft 429 wenn zu viele Versuche im Zeitfenster."""
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and q[0] <= now - window_seconds:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Zu viele Versuche — bitte kurz warten und erneut versuchen.",
            )
        q.append(now)
