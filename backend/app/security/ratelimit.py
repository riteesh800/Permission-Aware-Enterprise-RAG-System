from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        with self._lock:
            bucket = self._events[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")
            bucket.append(now)


limiter = SlidingWindowLimiter()


def rate_limit_login(request: Request) -> None:
    host = request.client.host if request.client else "unknown"
    limiter.check(f"login:{host}", 20, 60)


def rate_limit_chat(request: Request, user_id: str) -> None:
    limiter.check(f"chat:{user_id}", 40, 60)
