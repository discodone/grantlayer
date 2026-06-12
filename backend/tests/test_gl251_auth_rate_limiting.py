"""GL-251 — Rate limiting on /v1/auth/token.

Verifies that the sliding-window rate limiter blocks brute-force attempts
on the token endpoint while allowing legitimate traffic within the window.

Test limit is set to 3 req/min for speed; production default is 10/min
(GRANTLAYER_RATE_LIMIT_AUTH env var).
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest

_TEST_ADMIN_TOKEN = "gl251-test-admin-token-valid"
_TEST_JWT_SECRET = "gl251-test-jwt-secret-value-x"
_TEST_LIMIT = 3


class TestAuthRateLimiting(unittest.TestCase):

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

        self._saved = {
            "GRANTLAYER_DB": os.environ.get("GRANTLAYER_DB"),
            "GRANTLAYER_DATABASE_URL": os.environ.get("GRANTLAYER_DATABASE_URL"),
            "GRANTLAYER_ADMIN_TOKEN": os.environ.get("GRANTLAYER_ADMIN_TOKEN"),
            "GRANTLAYER_JWT_SECRET": os.environ.get("GRANTLAYER_JWT_SECRET"),
            "GRANTLAYER_ENABLE_OPERATOR_MODEL": os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL"),
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN": os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN"),
            "GRANTLAYER_RATE_LIMIT_AUTH": os.environ.get("GRANTLAYER_RATE_LIMIT_AUTH"),
        }

        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = _TEST_ADMIN_TOKEN
        os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_JWT_SECRET
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)

        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self._app = create_app()
        self.client = TestClient(self._app, raise_server_exceptions=False)

        # Each create_app() call produces a fresh RateLimiter on app.state,
        # so tests are fully isolated from one another.
        self._limiter = self._app.state.auth_rate_limiter
        self._orig_limit = self._limiter.auth_limit
        self._limiter.auth_limit = _TEST_LIMIT
        self._limiter.reset()

    def tearDown(self):
        self._limiter.auth_limit = self._orig_limit
        self._limiter.reset()

        os.unlink(self.tmp_db.name)

        for key, val in self._saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def _post_token(self):
        return self.client.post(
            "/v1/auth/token",
            json={"operator_id": "test-op", "secret": _TEST_ADMIN_TOKEN},
        )

    # ── core behaviour ────────────────────────────────────────────────────

    def test_requests_within_limit_return_200(self):
        """All requests up to the limit must succeed with a JWT."""
        for i in range(_TEST_LIMIT):
            resp = self._post_token()
            self.assertEqual(
                resp.status_code, 200,
                f"Request {i + 1} should be 200, got {resp.status_code}: {resp.text}",
            )
            data = resp.json()
            self.assertIn("access_token", data)
            self.assertEqual(data["token_type"], "bearer")

    def test_request_over_limit_returns_429(self):
        """The first request past the limit must return 429."""
        for _ in range(_TEST_LIMIT):
            self._post_token()

        resp = self._post_token()
        self.assertEqual(resp.status_code, 429)
        data = resp.json()
        self.assertEqual(data["errorCode"], "rate_limit_exceeded")
        self.assertIn("Retry after", data["reason"])

    def test_429_has_retry_after_header(self):
        """429 response must include a Retry-After header with a positive integer."""
        for _ in range(_TEST_LIMIT):
            self._post_token()

        resp = self._post_token()
        self.assertEqual(resp.status_code, 429)
        self.assertIn("retry-after", resp.headers)
        retry = int(resp.headers["retry-after"])
        self.assertGreater(retry, 0)
        self.assertLessEqual(retry, 60)

    def test_subsequent_requests_over_limit_also_return_429(self):
        """Multiple requests past the limit all return 429."""
        for _ in range(_TEST_LIMIT):
            self._post_token()

        for _ in range(3):
            resp = self._post_token()
            self.assertEqual(resp.status_code, 429)

    def test_reset_clears_state_and_allows_new_requests(self):
        """After reset() the counter clears and requests succeed again."""
        for _ in range(_TEST_LIMIT):
            self._post_token()

        # Confirm exhausted.
        self.assertEqual(self._post_token().status_code, 429)

        self._limiter.reset()

        resp = self._post_token()
        self.assertEqual(resp.status_code, 200)

    # ── rate limit fires before auth ─────────────────────────────────────

    def test_rate_limit_applies_to_invalid_credentials_too(self):
        """Brute-force with wrong credentials is still rate-limited."""
        for _ in range(_TEST_LIMIT):
            self.client.post(
                "/v1/auth/token",
                json={"operator_id": "attacker", "secret": "wrong-secret"},
            )

        resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "attacker", "secret": "wrong-secret"},
        )
        self.assertEqual(resp.status_code, 429)


if __name__ == "__main__":
    unittest.main()
