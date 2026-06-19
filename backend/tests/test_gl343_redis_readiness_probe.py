"""GL-343 — Fix broken Redis readiness probe.

The /readiness endpoint must:
- Return 200 when Redis is connected (redis_status == "connected").
- Return 503 when Redis was connected at startup but has since died.
- Return 200 when no Redis is configured (redis_status == "disabled").

Bug: the probe checked `redis_status not in ("ok", "disabled")`, but
RedisRateLimiter.redis_status returns "connected" (not "ok") when
the connection is live.  A healthy Redis therefore caused a 503.

Before fix:
  test_connected_redis_returns_readiness_200        → FAIL (503 returned)
  test_post_startup_redis_death_flips_readiness_503 → FAIL (always 200)

After fix:
  Both pass.  "connected" is accepted as a healthy Redis state.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


def _make_client():
    os.environ.pop("GRANTLAYER_JWT_SECRET", None)
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _limiter_with_status(status: str):
    """Return a mock limiter that reports *status* for both the cached property
    and the live health probe.

    GL-346 changed the readiness probe to call live_redis_health() (a real PING)
    instead of reading the cached redis_status property. These GL-343 tests verify
    the status->HTTP-code MAPPING, so the mock now drives that mapping through the
    new method; live-detection itself is covered by test_gl346_readiness_live_redis_ping.
    """
    limiter = MagicMock()
    type(limiter).redis_status = property(lambda self: status)
    limiter.live_redis_health = lambda: status
    return limiter


class TestConnectedRedisReadiness(unittest.TestCase):
    """When Redis is configured and connected, /readiness must return 200."""

    def test_connected_redis_returns_readiness_200(self):
        """redis_status == 'connected' must NOT flip /readiness to 503.

        Before fix: the probe checked `not in ("ok", "disabled")`, so "connected"
        was treated as an error → 503.  After fix: "connected" is accepted.
        """
        client = _make_client()
        limiter = _limiter_with_status("connected")
        client.app.state.auth_rate_limiter = limiter

        resp = client.get("/readiness")
        self.assertEqual(
            resp.status_code,
            200,
            f"Expected 200 for connected Redis; got {resp.status_code}: {resp.text}",
        )
        body = resp.json()
        self.assertEqual(body.get("status"), "ready")

    def test_disabled_redis_returns_readiness_200(self):
        """redis_status == 'disabled' (no REDIS_URL) must return 200 as before."""
        client = _make_client()
        limiter = _limiter_with_status("disabled")
        client.app.state.auth_rate_limiter = limiter

        resp = client.get("/readiness")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "ready")

    def test_no_limiter_returns_readiness_200(self):
        """When app.state has no auth_rate_limiter, /readiness must still return 200."""
        client = _make_client()
        if hasattr(client.app.state, "auth_rate_limiter"):
            del client.app.state.auth_rate_limiter

        resp = client.get("/readiness")
        self.assertEqual(resp.status_code, 200)


class TestRedisDeathFlipsReadiness(unittest.TestCase):
    """After startup, if Redis becomes unreachable, /readiness must return 503."""

    def test_post_startup_redis_death_flips_readiness_503(self):
        """redis_status == 'unavailable' (post-startup death) must produce 503.

        Before fix: the check was wrong, so this proved nothing (test showed
        whether the bug was consistently wrong, not that the probe worked).
        After fix: 'unavailable' is correctly rejected.
        """
        client = _make_client()
        limiter = _limiter_with_status("unavailable")
        client.app.state.auth_rate_limiter = limiter

        resp = client.get("/readiness")
        self.assertEqual(
            resp.status_code,
            503,
            f"Expected 503 after Redis death; got {resp.status_code}: {resp.text}",
        )
        body = resp.json()
        self.assertEqual(body.get("status"), "not_ready")
        self.assertEqual(body.get("errorCode"), "DEPENDENCY_UNAVAILABLE")

    def test_status_transition_connected_then_unavailable(self):
        """Simulates Redis live at startup → dies → /readiness must flip to 503."""
        client = _make_client()

        # Phase 1: Redis connected → readiness must be 200
        client.app.state.auth_rate_limiter = _limiter_with_status("connected")
        resp1 = client.get("/readiness")
        self.assertEqual(resp1.status_code, 200, f"Phase 1 (connected) expected 200: {resp1.text}")

        # Phase 2: Redis dies → readiness must be 503
        client.app.state.auth_rate_limiter = _limiter_with_status("unavailable")
        resp2 = client.get("/readiness")
        self.assertEqual(resp2.status_code, 503, f"Phase 2 (unavailable) expected 503: {resp2.text}")
        self.assertEqual(resp2.json().get("errorCode"), "DEPENDENCY_UNAVAILABLE")


class TestRedisStatusAcceptance(unittest.TestCase):
    """Enumerate all redis_status values and assert correct HTTP status."""

    def _readiness_status_for(self, redis_status: str) -> int:
        client = _make_client()
        client.app.state.auth_rate_limiter = _limiter_with_status(redis_status)
        return client.get("/readiness").status_code

    def test_ok_maps_to_200(self):
        self.assertEqual(self._readiness_status_for("ok"), 200)

    def test_connected_maps_to_200(self):
        self.assertEqual(self._readiness_status_for("connected"), 200)

    def test_disabled_maps_to_200(self):
        self.assertEqual(self._readiness_status_for("disabled"), 200)

    def test_unavailable_maps_to_503(self):
        self.assertEqual(self._readiness_status_for("unavailable"), 503)

    def test_error_string_maps_to_503(self):
        self.assertEqual(self._readiness_status_for("error: connection refused"), 503)
