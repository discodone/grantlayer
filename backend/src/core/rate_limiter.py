"""GrantLayer MVP — Rate limiter with Redis backend and in-process fallback.

The preferred backend is Redis (sliding window via Lua script).
When Redis is unavailable or unconfigured, falls back to an in-process
deque-based sliding window (not shared across workers).

Set GRANTLAYER_REDIS_URL to enable the Redis backend.
"""

from __future__ import annotations

import collections
import threading
import time
import uuid

try:
    import redis as _redis_lib
except ImportError:
    _redis_lib = None  # type: ignore[assignment]

# Atomic sliding-window Lua script.
# Returns {allowed (0/1), current_count, retry_after_seconds}.
_LUA_SLIDING_WINDOW = """
local key    = KEYS[1]
local now    = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit  = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window + 1)
    return {1, count + 1, 0}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry = window + 1
    if #oldest > 0 then
        retry = math.ceil(window - (now - tonumber(oldest[2]))) + 1
    end
    return {0, count, retry}
end
"""


class RateLimiter:
    """Sliding-window in-process rate limiter.

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

    @property
    def redis_status(self) -> str:
        return "disabled"


class RedisRateLimiter:
    """Redis-backed sliding-window rate limiter with in-process fallback.

    Uses an atomic Lua script (ZREMRANGEBYSCORE / ZADD / ZCARD) so each
    request is a single round-trip.  On any Redis error the limiter silently
    degrades to the in-process fallback for subsequent calls.

    Args:
        auth_limit: Maximum requests per window for the ``auth`` group.
        api_limit: Maximum requests per window for the ``api`` group.
        window_seconds: Length of the sliding window in seconds.
        redis_url: Redis connection URL (e.g. ``redis://localhost:6379``).
    """

    def __init__(
        self,
        auth_limit: int = 10,
        api_limit: int = 120,
        window_seconds: int = 60,
        redis_url: str | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._fallback = RateLimiter(auth_limit, api_limit, window_seconds)
        self._redis = None
        self._lock = threading.Lock()
        self._try_connect()

    # ── attribute proxies so tests can set auth_limit / api_limit directly ──

    @property
    def auth_limit(self) -> int:
        return self._fallback.auth_limit

    @auth_limit.setter
    def auth_limit(self, value: int) -> None:
        self._fallback.auth_limit = value

    @property
    def api_limit(self) -> int:
        return self._fallback.api_limit

    @api_limit.setter
    def api_limit(self, value: int) -> None:
        self._fallback.api_limit = value

    @property
    def window_seconds(self) -> int:
        return self._fallback.window_seconds

    @window_seconds.setter
    def window_seconds(self, value: int) -> None:
        self._fallback.window_seconds = value

    @property
    def redis_status(self) -> str:
        if not self._redis_url:
            return "disabled"
        with self._lock:
            return "connected" if self._redis is not None else "unavailable"

    # ── internals ───────────────────────────────────────────────────────────

    def _try_connect(self) -> None:
        if not self._redis_url or _redis_lib is None:
            return
        try:
            r = _redis_lib.from_url(
                self._redis_url,
                socket_connect_timeout=1,
                socket_timeout=1,
                decode_responses=False,
            )
            r.ping()
            with self._lock:
                self._redis = r
        except Exception:
            pass

    def check(
        self,
        client_ip: str,
        group: str,
        now: float | None = None,
    ) -> tuple[bool, int]:
        """Return *(allowed, retry_after_seconds)* — Redis-backed, in-process fallback."""
        with self._lock:
            r = self._redis

        if r is not None:
            try:
                return self._redis_check(r, client_ip, group, now)
            except Exception:
                with self._lock:
                    self._redis = None

        return self._fallback.check(client_ip, group, now)

    def _redis_check(
        self,
        r: object,
        client_ip: str,
        group: str,
        now: float | None = None,
    ) -> tuple[bool, int]:
        if now is None:
            now = time.time()
        limit = self._fallback.auth_limit if group == "auth" else self._fallback.api_limit
        window = self._fallback.window_seconds
        key = f"rl:{client_ip}:{group}"
        member = f"{now}:{uuid.uuid4()}"

        result = r.eval(_LUA_SLIDING_WINDOW, 1, key, now, window, limit, member)  # type: ignore[union-attr]
        allowed = int(result[0])
        retry_after = int(result[2])

        if allowed:
            return True, 0
        return False, max(1, min(window, retry_after))

    def reset(self) -> None:
        """Clear all rate-limit state (Redis keys + in-process fallback)."""
        with self._lock:
            r = self._redis

        if r is not None:
            try:
                cursor = 0
                while True:
                    cursor, keys = r.scan(cursor, match="rl:*", count=100)  # type: ignore[union-attr]
                    if keys:
                        r.delete(*keys)  # type: ignore[union-attr]
                    if cursor == 0:
                        break
            except Exception:
                pass

        self._fallback.reset()


def create_rate_limiter(
    auth_limit: int = 10,
    api_limit: int = 120,
    window_seconds: int = 60,
    redis_url: str | None = None,
) -> RateLimiter | RedisRateLimiter:
    """Return a Redis-backed limiter when *redis_url* is set, in-process otherwise."""
    if redis_url:
        return RedisRateLimiter(auth_limit, api_limit, window_seconds, redis_url)
    return RateLimiter(auth_limit, api_limit, window_seconds)
