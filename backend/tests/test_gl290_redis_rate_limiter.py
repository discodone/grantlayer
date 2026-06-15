"""GL-290 — Redis-backed Rate Limiter.

Covers:
- Factory: no redis_url → RateLimiter; redis_url → RedisRateLimiter
- RedisRateLimiter with mock Redis: allow / block / retry-after
- Fallback when Redis unavailable at startup
- Fallback when Redis fails mid-request
- reset() clears both Redis keys and in-process fallback
- redis_status property values
- Health endpoint: redis field present
- Existing RateLimiter (in-process) unchanged
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_mock_redis(auth_limit: int = 5):
    """Return a mock Redis client whose eval() simulates a sliding window."""
    mock_r = MagicMock()
    mock_r.ping.return_value = True
    mock_r.scan.return_value = (0, [])

    call_count = [0]

    def _eval(script, num_keys, *args):
        call_count[0] += 1
        count = call_count[0]
        if count <= auth_limit:
            return [1, count, 0]
        retry = 30
        return [0, auth_limit, retry]

    mock_r.eval.side_effect = _eval
    return mock_r, call_count


# ── factory ──────────────────────────────────────────────────────────────────

class TestCreateRateLimiterFactory(unittest.TestCase):

    def test_no_redis_url_returns_in_process(self):
        from backend.src.core.rate_limiter import RateLimiter, RedisRateLimiter, create_rate_limiter
        limiter = create_rate_limiter()
        self.assertIsInstance(limiter, RateLimiter)
        self.assertNotIsInstance(limiter, RedisRateLimiter)

    def test_empty_redis_url_returns_in_process(self):
        from backend.src.core.rate_limiter import RateLimiter, RedisRateLimiter, create_rate_limiter
        limiter = create_rate_limiter(redis_url="")
        self.assertIsInstance(limiter, RateLimiter)
        self.assertNotIsInstance(limiter, RedisRateLimiter)

    def test_redis_url_returns_redis_limiter(self):
        import backend.src.core.rate_limiter as rl_mod
        mock_r = MagicMock()
        mock_r.ping.return_value = True
        with patch.object(rl_mod, "_redis_lib") as mock_lib:
            mock_lib.from_url.return_value = mock_r
            limiter = rl_mod.create_rate_limiter(redis_url="redis://localhost:6379")
        self.assertIsInstance(limiter, rl_mod.RedisRateLimiter)


# ── in-process RateLimiter (no regressions) ──────────────────────────────────

class TestInProcessRateLimiter(unittest.TestCase):

    def setUp(self):
        from backend.src.core.rate_limiter import RateLimiter
        self.limiter = RateLimiter(auth_limit=3, window_seconds=60)
        self.limiter.reset()

    def test_redis_status_is_disabled(self):
        self.assertEqual(self.limiter.redis_status, "disabled")

    def test_allows_within_limit(self):
        for i in range(3):
            allowed, _ = self.limiter.check("1.2.3.4", "auth")
            self.assertTrue(allowed, f"request {i + 1} should be allowed")

    def test_blocks_over_limit(self):
        for _ in range(3):
            self.limiter.check("1.2.3.4", "auth")
        allowed, retry = self.limiter.check("1.2.3.4", "auth")
        self.assertFalse(allowed)
        self.assertGreater(retry, 0)

    def test_reset_clears_state(self):
        for _ in range(3):
            self.limiter.check("1.2.3.4", "auth")
        self.limiter.reset()
        allowed, _ = self.limiter.check("1.2.3.4", "auth")
        self.assertTrue(allowed)


# ── RedisRateLimiter with mock Redis ─────────────────────────────────────────

class TestRedisRateLimiterWithMockRedis(unittest.TestCase):

    def _make_limiter(self, auth_limit: int = 3):
        import backend.src.core.rate_limiter as rl_mod
        mock_r, self._call_count = _make_mock_redis(auth_limit)
        self._mock_r = mock_r
        with patch.object(rl_mod, "_redis_lib") as mock_lib:
            mock_lib.from_url.return_value = mock_r
            limiter = rl_mod.RedisRateLimiter(
                auth_limit=auth_limit,
                window_seconds=60,
                redis_url="redis://localhost:6379",
            )
        return limiter

    def test_redis_status_connected(self):
        limiter = self._make_limiter()
        self.assertEqual(limiter.redis_status, "connected")

    def test_allows_within_limit(self):
        limiter = self._make_limiter(auth_limit=3)
        for i in range(3):
            allowed, _ = limiter.check("1.2.3.4", "auth")
            self.assertTrue(allowed, f"request {i + 1} should be allowed")

    def test_blocks_over_limit_returns_false(self):
        limiter = self._make_limiter(auth_limit=3)
        for _ in range(3):
            limiter.check("1.2.3.4", "auth")
        allowed, retry = limiter.check("1.2.3.4", "auth")
        self.assertFalse(allowed)

    def test_blocks_over_limit_returns_positive_retry(self):
        limiter = self._make_limiter(auth_limit=3)
        for _ in range(3):
            limiter.check("1.2.3.4", "auth")
        _, retry = limiter.check("1.2.3.4", "auth")
        self.assertGreater(retry, 0)

    def test_auth_limit_settable(self):
        limiter = self._make_limiter(auth_limit=5)
        self.assertEqual(limiter.auth_limit, 5)
        limiter.auth_limit = 10
        self.assertEqual(limiter.auth_limit, 10)

    def test_api_limit_settable(self):
        limiter = self._make_limiter()
        limiter.api_limit = 200
        self.assertEqual(limiter.api_limit, 200)

    def test_window_seconds_settable(self):
        limiter = self._make_limiter()
        limiter.window_seconds = 120
        self.assertEqual(limiter.window_seconds, 120)

    def test_reset_calls_scan_and_clears_fallback(self):
        limiter = self._make_limiter()
        self._mock_r.scan.return_value = (0, [b"rl:1.2.3.4:auth"])
        self._mock_r.delete.return_value = 1
        limiter.reset()
        self._mock_r.scan.assert_called()
        self._mock_r.delete.assert_called()

    def test_reset_without_keys_does_not_call_delete(self):
        limiter = self._make_limiter()
        self._mock_r.scan.return_value = (0, [])
        limiter.reset()
        self._mock_r.delete.assert_not_called()

    def test_uses_redis_not_fallback_when_connected(self):
        limiter = self._make_limiter(auth_limit=3)
        limiter.check("1.2.3.4", "auth")
        self._mock_r.eval.assert_called_once()


# ── Fallback behavior ─────────────────────────────────────────────────────────

class TestRedisRateLimiterFallback(unittest.TestCase):

    def test_falls_back_when_redis_unavailable_at_startup(self):
        import backend.src.core.rate_limiter as rl_mod
        mock_r = MagicMock()
        mock_r.ping.side_effect = Exception("connection refused")
        with patch.object(rl_mod, "_redis_lib") as mock_lib:
            mock_lib.from_url.return_value = mock_r
            limiter = rl_mod.RedisRateLimiter(
                auth_limit=5,
                redis_url="redis://bad-host:6379",
            )
        self.assertEqual(limiter.redis_status, "unavailable")
        # Should still work via in-process fallback
        allowed, _ = limiter.check("1.2.3.4", "auth")
        self.assertTrue(allowed)

    def test_falls_back_when_redis_fails_mid_request(self):
        import backend.src.core.rate_limiter as rl_mod
        mock_r = MagicMock()
        mock_r.ping.return_value = True
        mock_r.eval.side_effect = Exception("connection lost")
        with patch.object(rl_mod, "_redis_lib") as mock_lib:
            mock_lib.from_url.return_value = mock_r
            limiter = rl_mod.RedisRateLimiter(
                auth_limit=5,
                redis_url="redis://localhost:6379",
            )
        # First call triggers Redis error → fallback
        allowed, _ = limiter.check("1.2.3.4", "auth")
        self.assertTrue(allowed)
        # Status reflects degraded state
        self.assertEqual(limiter.redis_status, "unavailable")

    def test_redis_status_disabled_when_no_url(self):
        from backend.src.core.rate_limiter import RedisRateLimiter
        limiter = RedisRateLimiter(auth_limit=5, redis_url=None)
        self.assertEqual(limiter.redis_status, "disabled")

    def test_redis_lib_missing_uses_fallback(self):
        import backend.src.core.rate_limiter as rl_mod
        with patch.object(rl_mod, "_redis_lib", None):
            limiter = rl_mod.RedisRateLimiter(
                auth_limit=5,
                redis_url="redis://localhost:6379",
            )
        self.assertEqual(limiter.redis_status, "unavailable")
        allowed, _ = limiter.check("1.2.3.4", "auth")
        self.assertTrue(allowed)


# ── Health endpoint redis field ───────────────────────────────────────────────

class TestHealthEndpointRedisField(unittest.TestCase):

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._saved = {k: os.environ.get(k) for k in [
            "GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL",
            "GRANTLAYER_ADMIN_TOKEN", "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
            "GRANTLAYER_ENABLE_OPERATOR_MODEL", "GRANTLAYER_REDIS_URL",
        ]}
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "gl290-test-admin-token-valid"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ.pop("GRANTLAYER_REDIS_URL", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, val in self._saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def test_health_response_includes_redis_field(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("redis", body)

    def test_health_redis_disabled_when_no_url(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["redis"], "disabled")


if __name__ == "__main__":
    unittest.main()
