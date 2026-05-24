"""Tests for GL-106: Rate Limiting Baseline.

Ensures:
1.  Limiter allows requests below auth limit.
2.  Limiter blocks requests above auth limit.
3.  Limiter resets after time window.
4.  Retry-After is calculated correctly.
5.  Auth group default is 10/min.
6.  API group default is 120/min.
7.  ENV override works for auth limit.
8.  ENV override works for api limit.
9.  Separate IPs are isolated.
10. Separate endpoint groups are isolated.
11. Protected endpoint returns 429 when exceeded.
12. 429 response includes Retry-After header.
13. Blocked request does not mutate state.
14. Protected endpoint still requires auth when rate limit allows.
15. Health remains public.
16. Readiness remains public.
17. CORS behavior is preserved.
18. Security boundary is preserved.
19. Diff scope limited to allowed files.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
import importlib
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl106(unittest.TestCase):
    """Shared helpers for GL-106 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_rate_limit_auth = os.environ.get("GRANTLAYER_RATE_LIMIT_AUTH")
        self._orig_rate_limit_api = os.environ.get("GRANTLAYER_RATE_LIMIT_API")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import src.challenges as challenges_mod
        importlib.reload(challenges_mod)
        self.challenges_mod = challenges_mod

        import src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod
        self.handler_class = server_mod.GrantLayerHandler

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_RATE_LIMIT_AUTH", self._orig_rate_limit_auth),
            ("GRANTLAYER_RATE_LIMIT_API", self._orig_rate_limit_api),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _insert_operator(self, op_id, name, role, token):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, datetime('now'))""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_handler(self, path, method="GET", auth_header=None, origin=None, body=b"", client_ip="127.0.0.1"):
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if origin is not None:
            headers["Origin"] = origin
        if body:
            headers["Content-Length"] = str(len(body))
        handler.headers = headers
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = (client_ip, 0)
        handler.server = None
        return handler

    def _run_handler(self, handler):
        if handler.command == "GET":
            handler.do_GET()
        elif handler.command == "POST":
            handler.do_POST()
        elif handler.command == "OPTIONS":
            handler.do_OPTIONS()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        header_block = parts[0].decode()
        headers = {}
        for line in header_block.split("\r\n")[1:]:
            if ": " in line:
                k, v = line.split(": ", 1)
                headers[k] = v
        if len(parts) > 1 and parts[1]:
            body = json.loads(parts[1])
        else:
            body = {}
        return status, headers, body


# ═══════════════════════════════════════════════════════════════════════
# 1-3. Limiter unit tests
# ═══════════════════════════════════════════════════════════════════════

class TestGl106LimiterUnit(_BaseGl106):
    """Direct rate limiter unit tests."""

    def test_allows_below_auth_limit(self):
        from src.rate_limiter import RateLimiter
        limiter = RateLimiter(auth_limit=5, api_limit=100, window_seconds=60)
        for _ in range(5):
            allowed, _ = limiter.check("1.2.3.4", "auth", now=1000.0)
            self.assertTrue(allowed)

    def test_blocks_above_auth_limit(self):
        from src.rate_limiter import RateLimiter
        limiter = RateLimiter(auth_limit=3, api_limit=100, window_seconds=60)
        for _ in range(3):
            allowed, _ = limiter.check("1.2.3.4", "auth", now=1000.0)
            self.assertTrue(allowed)
        allowed, retry_after = limiter.check("1.2.3.4", "auth", now=1000.0)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)

    def test_resets_after_time_window(self):
        from src.rate_limiter import RateLimiter
        limiter = RateLimiter(auth_limit=2, api_limit=100, window_seconds=10)
        limiter.check("1.2.3.4", "auth", now=0.0)
        limiter.check("1.2.3.4", "auth", now=1.0)
        allowed, _ = limiter.check("1.2.3.4", "auth", now=2.0)
        self.assertFalse(allowed)
        # After window passes, should be allowed again
        allowed, _ = limiter.check("1.2.3.4", "auth", now=11.0)
        self.assertTrue(allowed)

    def test_retry_after_calculated(self):
        from src.rate_limiter import RateLimiter
        limiter = RateLimiter(auth_limit=1, api_limit=100, window_seconds=60)
        limiter.check("1.2.3.4", "auth", now=1000.0)
        allowed, retry_after = limiter.check("1.2.3.4", "auth", now=1000.0)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)
        self.assertLessEqual(retry_after, 60)


# ═══════════════════════════════════════════════════════════════════════
# 5-6. Default limits
# ═══════════════════════════════════════════════════════════════════════

class TestGl106DefaultLimits(_BaseGl106):
    """Verify default rate limit values."""

    def test_auth_default_10_per_min(self):
        self.assertEqual(self.config_mod.GRANTLAYER_RATE_LIMIT_AUTH, 10)

    def test_api_default_120_per_min(self):
        self.assertEqual(self.config_mod.GRANTLAYER_RATE_LIMIT_API, 120)


# ═══════════════════════════════════════════════════════════════════════
# 7-8. ENV override
# ═══════════════════════════════════════════════════════════════════════

class TestGl106EnvOverride(_BaseGl106):
    """Verify ENV overrides for rate limits."""

    def test_env_override_auth(self):
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "25"
        importlib.reload(self.config_mod)
        self.assertEqual(self.config_mod.GRANTLAYER_RATE_LIMIT_AUTH, 25)

    def test_env_override_api(self):
        os.environ["GRANTLAYER_RATE_LIMIT_API"] = "500"
        importlib.reload(self.config_mod)
        self.assertEqual(self.config_mod.GRANTLAYER_RATE_LIMIT_API, 500)

    def test_invalid_env_falls_back_to_default(self):
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "not_a_number"
        importlib.reload(self.config_mod)
        self.assertEqual(self.config_mod.GRANTLAYER_RATE_LIMIT_AUTH, 10)

    def test_negative_env_clamped_to_1(self):
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "-5"
        importlib.reload(self.config_mod)
        self.assertEqual(self.config_mod.GRANTLAYER_RATE_LIMIT_AUTH, 1)


# ═══════════════════════════════════════════════════════════════════════
# 9. Separate IPs isolated
# ═══════════════════════════════════════════════════════════════════════

class TestGl106IpIsolation(_BaseGl106):
    """Verify rate limits are per-IP."""

    def test_separate_ips_are_isolated(self):
        from src.rate_limiter import RateLimiter
        limiter = RateLimiter(auth_limit=2, api_limit=100, window_seconds=60)
        limiter.check("1.2.3.4", "auth", now=1000.0)
        limiter.check("1.2.3.4", "auth", now=1000.0)
        # Same limit exceeded for first IP
        allowed, _ = limiter.check("1.2.3.4", "auth", now=1000.0)
        self.assertFalse(allowed)
        # Different IP should still be allowed
        allowed, _ = limiter.check("5.6.7.8", "auth", now=1000.0)
        self.assertTrue(allowed)


# ═══════════════════════════════════════════════════════════════════════
# 10. Separate endpoint groups isolated
# ═══════════════════════════════════════════════════════════════════════

class TestGl106GroupIsolation(_BaseGl106):
    """Verify auth and api groups are isolated."""

    def test_auth_and_api_groups_are_isolated(self):
        from src.rate_limiter import RateLimiter
        limiter = RateLimiter(auth_limit=2, api_limit=100, window_seconds=60)
        limiter.check("1.2.3.4", "auth", now=1000.0)
        limiter.check("1.2.3.4", "auth", now=1000.0)
        # Auth group exceeded
        allowed, _ = limiter.check("1.2.3.4", "auth", now=1000.0)
        self.assertFalse(allowed)
        # API group should still be allowed
        allowed, _ = limiter.check("1.2.3.4", "api", now=1000.0)
        self.assertTrue(allowed)


# ═══════════════════════════════════════════════════════════════════════
# 11-12. Protected endpoint returns 429 with Retry-After
# ═══════════════════════════════════════════════════════════════════════

class TestGl106Server429(_BaseGl106):
    """Verify server returns 429 with Retry-After when limit exceeded."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "2"
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler

        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_protected_endpoint_returns_429_when_exceeded(self):
        # Use /challenges (auth group) with limit=2
        for _ in range(2):
            handler = self._make_handler("/challenges", auth_header="Bearer owner-token")
            status, headers, body = self._run_handler(handler)
            self.assertEqual(status, 200)

        handler = self._make_handler("/challenges", auth_header="Bearer owner-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 429)
        self.assertEqual(body.get("errorCode"), "rate_limit_exceeded")

    def test_429_includes_retry_after_header(self):
        for _ in range(2):
            handler = self._make_handler("/challenges", auth_header="Bearer owner-token")
            self._run_handler(handler)

        handler = self._make_handler("/challenges", auth_header="Bearer owner-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 429)
        self.assertIn("Retry-After", headers)
        retry_after = int(headers["Retry-After"])
        self.assertGreaterEqual(retry_after, 1)
        self.assertLessEqual(retry_after, 60)


# ═══════════════════════════════════════════════════════════════════════
# 13. Blocked request does not mutate state
# ═══════════════════════════════════════════════════════════════════════

class TestGl106BlockedRequestNoMutation(_BaseGl106):
    """Verify rate-limited requests do not mutate state."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_RATE_LIMIT_API"] = "2"
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler

        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_blocked_post_does_not_create_grant(self):
        # Exhaust api limit with GET /grants
        for _ in range(2):
            handler = self._make_handler("/grants", auth_header="Bearer owner-token")
            status, headers, body = self._run_handler(handler)
            self.assertEqual(status, 200)

        # Count grants before blocked request
        conn = self.db_mod.get_conn()
        try:
            before = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        finally:
            conn.close()

        # Attempt to create a grant while rate limited
        grant_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2020-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "owner-1",
            "reason": "test",
        }).encode()
        handler = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=grant_body)
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 429)

        # Count grants after blocked request
        conn = self.db_mod.get_conn()
        try:
            after = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(before, after)


# ═══════════════════════════════════════════════════════════════════════
# 14. Protected endpoint still requires auth when rate limit allows
# ═══════════════════════════════════════════════════════════════════════

class TestGl106AuthStillRequired(_BaseGl106):
    """Verify auth is still required when rate limit allows."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler

        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

    def test_protected_endpoint_still_requires_auth(self):
        handler = self._make_handler("/grants")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))


# ═══════════════════════════════════════════════════════════════════════
# 15-16. Health and readiness remain public
# ═══════════════════════════════════════════════════════════════════════

class TestGl106PublicEndpoints(_BaseGl106):
    """Verify public endpoints remain public and un-rate-limited."""

    def test_health_public(self):
        handler = self._make_handler("/health")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_public(self):
        handler = self._make_handler("/readiness")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))
        self.assertIn(body.get("status"), ("ready", "not_ready"))

    def test_health_not_rate_limited(self):
        # Make many requests to health
        for _ in range(150):
            handler = self._make_handler("/health")
            status, headers, body = self._run_handler(handler)
            self.assertEqual(status, 200)


# ═══════════════════════════════════════════════════════════════════════
# 17. CORS behavior preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl106CorsPreserved(_BaseGl106):
    """Verify CORS behavior is preserved under rate limiting."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "2"
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler

        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_cors_headers_on_rate_limited_response(self):
        for _ in range(2):
            handler = self._make_handler("/challenges", auth_header="Bearer owner-token", origin="http://trusted.com")
            self._run_handler(handler)

        handler = self._make_handler("/challenges", auth_header="Bearer owner-token", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 429)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://trusted.com")

    def test_options_not_rate_limited(self):
        for _ in range(150):
            handler = self._make_handler("/grants", method="OPTIONS", origin="http://trusted.com")
            status, headers, body = self._run_handler(handler)
            self.assertEqual(status, 204)


# ═══════════════════════════════════════════════════════════════════════
# 18. Security boundary preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl106SecurityBoundary(_BaseGl106):
    """Verify security boundary is preserved."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler

        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("aud-1", "Auditor", "auditor", "auditor-token")

    def test_role_check_still_enforced(self):
        # Auditor cannot access owner-only endpoint
        handler = self._make_handler("/agent-permissions/profiles", auth_header="Bearer auditor-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 403)

    def test_auth_failure_before_rate_limit_check(self):
        # Unauthenticated request should fail with 401, not 429
        handler = self._make_handler("/grants")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))


# ═══════════════════════════════════════════════════════════════════════
# 19. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl106NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-106 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-106-rate-limiting-baseline":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-106 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/server.py",
            "backend/src/config.py",
            "backend/src/rate_limiter.py",
            "backend/tests/test_gl106_rate_limiting.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-106 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
