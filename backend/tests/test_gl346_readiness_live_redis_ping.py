"""GL-346 — Readiness probe must perform a LIVE Redis PING, not read a cached status.

Bug (false GL-343 claim): /readiness read the cached `redis_status` property, which
only flips to "unavailable" AFTER a `check()` round-trip has already failed. A Redis
that dies *after* startup therefore left /readiness at 200 until real user traffic
failed. GL-343 "proved" the death case by mocking the status property to return
"unavailable" — it never exercised live detection.

These tests drive the REAL RedisRateLimiter code path with a fake redis *client*
object (the external dependency) that is actually closed — NOT by mocking the
limiter's `redis_status` property. The new `live_redis_health()` method issues a
real PING at probe time.

Design tension resolved here (and documented on `RedisRateLimiter.live_redis_health`):
- The limiter is SOFT at request time (falls back to the in-process window so no
  request is ever dropped when Redis blips).
- Readiness is HARD: a configured-but-unreachable Redis means rate limiting is
  degraded to per-process (unsafe across workers), so the instance reports 503 and
  is pulled from the load balancer until Redis recovers.
Readiness is authoritative for "is the configured Redis healthy".

Before fix:
  test_live_health_method_exists                       → FAIL (AttributeError)
  test_live_health_detects_closed_connection           → FAIL (method missing)
  test_readiness_flips_503_on_real_redis_death         → FAIL (stays 200)
After fix: all pass.
"""

from __future__ import annotations

import os
import unittest


class _FakeRedisClient:
    """Stand-in for a real redis client connection (the external dependency).

    Supports the single call live_redis_health() makes — ping() — and a close()
    that makes subsequent pings raise, exactly like a dropped TCP connection.
    No part of the limiter's own status logic is mocked.
    """

    def __init__(self) -> None:
        self.alive = True
        self.ping_calls = 0

    def ping(self) -> bool:
        self.ping_calls += 1
        if not self.alive:
            raise ConnectionError("Connection closed by server")
        return True

    def close(self) -> None:
        self.alive = False


def _limiter_with_fake(fake: _FakeRedisClient):
    """Build a real RedisRateLimiter pointed at a dead port, then inject the fake.

    The constructor's _try_connect() fails fast (connection refused on an unused
    port), leaving _redis = None; we then inject the fake client so the limiter's
    own live-ping logic runs against it.
    """
    from backend.src.core.rate_limiter import RedisRateLimiter
    limiter = RedisRateLimiter(redis_url="redis://127.0.0.1:6390")
    limiter._redis = fake
    return limiter


def _make_client():
    os.environ.pop("GRANTLAYER_JWT_SECRET", None)
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    from fastapi.testclient import TestClient

    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestLiveRedisHealthMethod(unittest.TestCase):
    """RedisRateLimiter must expose a live-ping health probe."""

    def test_live_health_method_exists(self):
        from backend.src.core.rate_limiter import RateLimiter, RedisRateLimiter
        self.assertTrue(
            hasattr(RedisRateLimiter, "live_redis_health"),
            "RedisRateLimiter.live_redis_health is missing — readiness needs a live PING.",
        )
        self.assertTrue(
            hasattr(RateLimiter, "live_redis_health"),
            "RateLimiter.live_redis_health is missing — must return 'disabled'.",
        )

    def test_in_process_limiter_reports_disabled(self):
        from backend.src.core.rate_limiter import RateLimiter
        self.assertEqual(RateLimiter().live_redis_health(), "disabled")

    def test_unconfigured_redis_limiter_reports_disabled(self):
        from backend.src.core.rate_limiter import RedisRateLimiter
        limiter = RedisRateLimiter(redis_url=None)
        self.assertEqual(limiter.live_redis_health(), "disabled")

    def test_live_health_ok_when_connection_alive(self):
        fake = _FakeRedisClient()
        limiter = _limiter_with_fake(fake)
        self.assertEqual(limiter.live_redis_health(), "ok")
        self.assertGreaterEqual(fake.ping_calls, 1, "live_redis_health did not PING")

    def test_live_health_detects_closed_connection(self):
        """A connection that dies post-startup is detected by a live PING.

        The cached redis_status property still reports 'connected' (no check() has
        run), proving the property is stale — only the live probe catches the death.
        """
        fake = _FakeRedisClient()
        limiter = _limiter_with_fake(fake)
        self.assertEqual(limiter.live_redis_health(), "ok")

        fake.close()  # Redis dies; no check() call happens.

        # Cached property is STALE — still claims connected.
        self.assertEqual(limiter.redis_status, "connected")
        # Live probe catches the real death.
        self.assertEqual(limiter.live_redis_health(), "unavailable")


class TestReadinessLiveDetection(unittest.TestCase):
    """/readiness must flip to 503 on a real (closed) Redis death — no status mocking."""

    def test_readiness_200_when_redis_alive(self):
        fake = _FakeRedisClient()
        client = _make_client()
        client.app.state.auth_rate_limiter = _limiter_with_fake(fake)
        resp = client.get("/readiness")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json().get("status"), "ready")

    def test_readiness_flips_503_on_real_redis_death(self):
        """Connected at startup → connection closed → next probe must be 503.

        RED before fix: readiness reads the cached redis_status property which stays
        'connected' after the close, so it returns 200 (the bug). After fix it issues
        a live PING and returns 503.
        """
        fake = _FakeRedisClient()
        limiter = _limiter_with_fake(fake)
        client = _make_client()
        client.app.state.auth_rate_limiter = limiter

        # Phase 1: alive → ready
        resp1 = client.get("/readiness")
        self.assertEqual(resp1.status_code, 200, f"Phase 1 expected 200: {resp1.text}")

        # Phase 2: Redis dies (real closed connection, NOT a mocked status string)
        fake.close()
        resp2 = client.get("/readiness")
        self.assertEqual(
            resp2.status_code, 503,
            f"Phase 2 expected 503 after live Redis death; got {resp2.status_code}: {resp2.text}",
        )
        body = resp2.json()
        self.assertEqual(body.get("status"), "not_ready")
        self.assertEqual(body.get("errorCode"), "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
