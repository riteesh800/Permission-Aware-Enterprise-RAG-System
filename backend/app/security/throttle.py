from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class LoginThrottle:
    """In-memory backoff for login attempts. Failures do not reveal which field was wrong."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def register_failure(self, key: str) -> None:
        now = time.time()
        with self._lock:
            bucket = self._failures[key]
            bucket.append(now)
            while bucket and now - bucket[0] > 3600:
                bucket.popleft()

    def register_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def is_limited(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            bucket = self._failures[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            return len(bucket) >= max_attempts


login_throttle = LoginThrottle()
