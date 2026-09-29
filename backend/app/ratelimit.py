"""Small in-memory rate limiter (per client address, per action).

Protects sign-in and the anonymous write endpoints (carts, events, waitlist)
from floods. In-memory is enough for one server process; limits reset when the
server restarts.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def client_key(request: Request) -> str:
    # The storefront proxy forwards the visitor's address; otherwise use the socket peer.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


def _scale() -> int:
    # Automated test runs sign in many times from one address. RATE_LIMIT_MULTIPLIER
    # raises every limit for them; it is ignored in production, which keeps the real limits.
    from .config import settings
    if settings.is_production:
        return 1
    return max(1, min(settings.rate_limit_multiplier, 1000))


def limit(action: str, max_hits: int, window_seconds: int):
    def check(request: Request) -> None:
        key = (action, client_key(request))
        allowed = max_hits * _scale()
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= allowed:
                raise HTTPException(429, "Too many requests. Please wait a few minutes and try again.")
            q.append(now)
    return check


def reset() -> None:
    """For tests."""
    with _lock:
        _hits.clear()
