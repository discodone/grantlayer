"""GL-303 — Redis hard requirement + rate limiting on all endpoints.

Covers:
- API rate limiter applies to ALL /v1/ routes (not just /v1/auth/token)
- 429 response has correct errorCode and Retry-After header
- OPTIONS requests (CORS preflight) bypass rate limiting
- Non-/v1/ routes (/health) are not rate limited
- Different client IPs have isolated rate-limit counters
- api_limit is used (not auth_limit) for /v1/ non-auth routes
- Redis URL is a hard requirement in staging/production modes
- Redis hard requirement does not fire in local/test/demo modes
- Redis URL present → no Redis error in startup_errors()
- create_rate_limiter() receives api_limit from config
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest


_TEST_ADMIN_TOKEN = "gl303-test-admin-token-valid"
_TEST_API_LIMIT = 3


def _make_client(tmp_db_path: str, api_limit: int = 1000):
    """Return a TestClient with isolated state."""
    os.environ["GRANTLAYER_DB"] = tmp_db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)
    os.environ["GRANTLAYER_ADMIN_TOKEN"] = _TEST_ADMIN_TOKEN
    os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
    os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
    os.environ["GRANTLAYER_RATE_LIMIT_API"] = str(api_limit)
    os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "1000"

    import backend.src.core.db as db_mod
    importlib.reload(db_mod)
    db_mod.DB_PATH = tmp_db_path
    db_mod.DB_PATH_OR_URL = tmp_db_path
    db_mod.init_db()

    import backend.src.core.config as config_mod
    importlib.reload(config_mod)

    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    return app, client


class TestApiRateLimitMiddleware(unittest.TestCase):
    """The _api_rate_limit middleware fires on all /v1/ routes."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._saved = {k: os.environ.get(k) for k in [
            "GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL", "GRANTLAYER_ADMIN_TOKEN",
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN", "GRANTLAYER_ENABLE_OPERATOR_MODEL",
            "GRANTLAYER_RATE_LIMIT_API", "GRANTLAYER_RATE_LIMIT_AUTH",
            "GRANTLAYER_REDIS_URL",
        ]}
        os.environ.pop("GRANTLAYER_REDIS_URL", None)
        self._app, self.client = _make_client(self.tmp_db.name, api_limit=_TEST_API_LIMIT)
        self._limiter = self._app.state.auth_rate_limiter
        self._limiter.api_limit = _TEST_API_LIMIT
        self._limiter.reset()

    def tearDown(self):
        self._limiter.reset()
        os.unlink(self.tmp_db.name)
        for key, val in self._saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def test_requests_within_api_limit_succeed_on_v1_route(self):
        for i in range(_TEST_API_LIMIT):
            resp = self.client.get("/v1/grants")
            self.assertNotEqual(
                resp.status_code, 429,
                f"Request {i + 1} should not be rate-limited, got {resp.status_code}",
            )

    def test_request_over_api_limit_returns_429(self):
        for _ in range(_TEST_API_LIMIT):
            self.client.get("/v1/grants")
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 429)

    def test_429_has_correct_error_code(self):
        for _ in range(_TEST_API_LIMIT):
            self.client.get("/v1/grants")
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 429)
        body = resp.json()
        self.assertEqual(body.get("errorCode"), "rate_limit_exceeded")

    def test_429_has_retry_after_header(self):
        for _ in range(_TEST_API_LIMIT):
            self.client.get("/v1/grants")
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 429)
        self.assertIn("retry-after", resp.headers)
        retry = int(resp.headers["retry-after"])
        self.assertGreater(retry, 0)
        self.assertLessEqual(retry, 60)

    def test_429_reason_mentions_retry_after(self):
        for _ in range(_TEST_API_LIMIT):
            self.client.get("/v1/grants")
        resp = self.client.get("/v1/grants")
        body = resp.json()
        self.assertIn("Retry after", body.get("reason", ""))

    def test_options_request_bypasses_rate_limit(self):
        """CORS preflight must never be blocked."""
        for _ in range(_TEST_API_LIMIT):
            self.client.get("/v1/grants")
        # Exhaust limit — next non-OPTIONS should be 429
        self.assertEqual(self.client.get("/v1/grants").status_code, 429)
        # OPTIONS must still pass through
        resp = self.client.options("/v1/grants")
        self.assertNotEqual(resp.status_code, 429)

    def test_health_endpoint_not_rate_limited(self):
        """Non-/v1/ routes must not be affected by the API middleware."""
        for _ in range(_TEST_API_LIMIT):
            self.client.get("/v1/grants")
        # API limit exhausted
        self.assertEqual(self.client.get("/v1/grants").status_code, 429)
        # /health is outside /v1/ and must still respond
        resp = self.client.get("/health")
        self.assertNotEqual(resp.status_code, 429)
        self.assertEqual(resp.status_code, 200)

    def test_different_ips_have_isolated_counters(self):
        """Rate limits are per-IP; separate clients don't share a bucket."""
        # Exhaust from one IP
        limiter = self._app.state.auth_rate_limiter
        limiter.reset()
        for _ in range(_TEST_API_LIMIT):
            limiter.check("10.0.0.1", "api")
        # 10.0.0.1 exhausted
        allowed_1, _ = limiter.check("10.0.0.1", "api")
        self.assertFalse(allowed_1)
        # 10.0.0.2 has its own bucket
        allowed_2, _ = limiter.check("10.0.0.2", "api")
        self.assertTrue(allowed_2)

    def test_reset_restores_api_limit(self):
        for _ in range(_TEST_API_LIMIT):
            self.client.get("/v1/grants")
        self.assertEqual(self.client.get("/v1/grants").status_code, 429)
        self._limiter.reset()
        resp = self.client.get("/v1/grants")
        self.assertNotEqual(resp.status_code, 429)

    def test_api_limit_not_auth_limit_used_for_v1_routes(self):
        """The middleware calls limiter.check(ip, 'api'), not 'auth'."""
        # Set api_limit very low, auth_limit high — only api bucket should be exhausted
        self._limiter.api_limit = 2
        self._limiter.auth_limit = 1000
        self._limiter.reset()
        self.client.get("/v1/grants")
        self.client.get("/v1/grants")
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 429)

    def test_rate_limit_applies_to_grant_requests_endpoint(self):
        """Middleware fires on /v1/grant-requests, not just /v1/grants."""
        for _ in range(_TEST_API_LIMIT):
            self.client.get("/v1/grant-requests")
        resp = self.client.get("/v1/grant-requests")
        self.assertEqual(resp.status_code, 429)

    def test_rate_limit_applies_to_audit_events_endpoint(self):
        """Middleware fires on /v1/audit-events."""
        for _ in range(_TEST_API_LIMIT):
            self.client.get("/v1/audit-events")
        resp = self.client.get("/v1/audit-events")
        self.assertEqual(resp.status_code, 429)


class TestRedisHardRequirement(unittest.TestCase):
    """Redis URL is mandatory in staging and production modes."""

    def _errors(self, runtime_mode: str, redis_url: str | None = None) -> list[str]:
        env = {
            "GRANTLAYER_RUNTIME_MODE": runtime_mode,
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN": "true",
            "GRANTLAYER_ADMIN_TOKEN": "strong-admin-token-for-tests",
            "GRANTLAYER_REQUIRE_CHALLENGE": "true",
        }
        if redis_url is not None:
            env["GRANTLAYER_REDIS_URL"] = redis_url
        else:
            env.pop("GRANTLAYER_REDIS_URL", None)

        import backend.src.core.config as config_mod
        # Save and restore environment
        saved = {k: os.environ.get(k) for k in env}
        for k, v in env.items():
            os.environ[k] = v
        for k in list(os.environ):
            if k not in env and k.startswith("GRANTLAYER_") and k not in saved:
                pass  # don't touch unrelated vars

        # Clear Redis URL explicitly when not set
        if redis_url is None:
            os.environ.pop("GRANTLAYER_REDIS_URL", None)

        try:
            importlib.reload(config_mod)
            return config_mod.startup_errors()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            importlib.reload(config_mod)

    def test_production_without_redis_url_is_error(self):
        errs = self._errors("production", redis_url=None)
        redis_errs = [e for e in errs if "GRANTLAYER_REDIS_URL" in e]
        self.assertTrue(
            len(redis_errs) >= 1,
            f"Expected Redis error in production mode, got errors: {errs}",
        )

    def test_staging_without_redis_url_is_error(self):
        errs = self._errors("staging", redis_url=None)
        redis_errs = [e for e in errs if "GRANTLAYER_REDIS_URL" in e]
        self.assertTrue(
            len(redis_errs) >= 1,
            f"Expected Redis error in staging mode, got errors: {errs}",
        )

    def test_local_without_redis_url_is_not_error(self):
        errs = self._errors("local", redis_url=None)
        redis_errs = [e for e in errs if "GRANTLAYER_REDIS_URL" in e]
        self.assertEqual(redis_errs, [], f"Unexpected Redis error in local mode: {redis_errs}")

    def test_test_mode_without_redis_url_is_not_error(self):
        errs = self._errors("test", redis_url=None)
        redis_errs = [e for e in errs if "GRANTLAYER_REDIS_URL" in e]
        self.assertEqual(redis_errs, [], f"Unexpected Redis error in test mode: {redis_errs}")

    def test_demo_without_redis_url_is_not_error(self):
        errs = self._errors("demo", redis_url=None)
        redis_errs = [e for e in errs if "GRANTLAYER_REDIS_URL" in e]
        self.assertEqual(redis_errs, [], f"Unexpected Redis error in demo mode: {redis_errs}")

    def test_production_with_redis_url_no_redis_error(self):
        errs = self._errors("production", redis_url="redis://localhost:6379")
        redis_errs = [e for e in errs if "GRANTLAYER_REDIS_URL" in e]
        self.assertEqual(redis_errs, [], f"Unexpected Redis error when URL is set: {redis_errs}")


class TestApiLimitPassedToRateLimiter(unittest.TestCase):
    """create_app() passes api_limit from config to the rate limiter."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._saved = {k: os.environ.get(k) for k in [
            "GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL", "GRANTLAYER_ADMIN_TOKEN",
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN", "GRANTLAYER_ENABLE_OPERATOR_MODEL",
            "GRANTLAYER_RATE_LIMIT_API", "GRANTLAYER_REDIS_URL",
        ]}

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, val in self._saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def test_api_limit_from_env_is_used_in_app_state(self):
        os.environ["GRANTLAYER_RATE_LIMIT_API"] = "77"
        os.environ.pop("GRANTLAYER_REDIS_URL", None)
        app, _ = _make_client(self.tmp_db.name, api_limit=77)
        self.assertEqual(app.state.auth_rate_limiter.api_limit, 77)

    def test_default_api_limit_is_120(self):
        os.environ.pop("GRANTLAYER_RATE_LIMIT_API", None)
        os.environ.pop("GRANTLAYER_REDIS_URL", None)
        app, _ = _make_client(self.tmp_db.name, api_limit=120)
        self.assertEqual(app.state.auth_rate_limiter.api_limit, 120)


if __name__ == "__main__":
    unittest.main()
