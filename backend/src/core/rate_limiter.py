"""GrantLayer MVP — In-process rate limiter.

Uses Python stdlib only.  Sliding-window counter with collections.deque.
Keys by client IP and endpoint group.  Prunes old timestamps on each
access to avoid unbounded memory growth.
"""

from __future__ import annotations

import collections
import threading
import time


class RateLimiter:
    """Sliding-window rate limiter.

    Args:
        auth_limit: Maximum requests per window for the ``auth`` group.
        api_limit: Maximum requests per window for the ``api`` group.
        window_seconds: Length of the sliding window in seconds.
    """

    def __init__(
        self,
        auth_limit: int = 10,
        api_limit: int = 120,
        window_seconds: int = 60,
    ) -> None:
        self.auth_limit = auth_limit
        self.api_limit = api_limit
        self.window_seconds = window_seconds
        self._storage: dict[tuple[str, str], collections.deque[float]] = {}
        self._lock = threading.Lock()

    def check(
        self,
        client_ip: str,
        group: str,
        now: float | None = None,
    ) -> tuple[bool, int]:
        """Return *(allowed, retry_after_seconds)* for *client_ip* in *group*.

        *now* is optional and intended for deterministic tests.
        """
        if now is None:
            now = time.time()

        limit = self.auth_limit if group == "auth" else self.api_limit
        key = (client_ip, group)

        with self._lock:
            dq = self._storage.get(key)
            if dq is None:
                dq = collections.deque()
                self._storage[key] = dq

            # Prune timestamps outside the sliding window
            while dq and dq[0] < now - self.window_seconds:
                dq.popleft()

            if len(dq) >= limit:
                retry_after = int(self.window_seconds - (now - dq[0])) + 1
                return False, max(1, min(self.window_seconds, retry_after))

            dq.append(now)
            return True, 0

    def reset(self) -> None:
        """Clear all stored state.  Useful for tests."""
        with self._lock:
            self._storage.clear()
