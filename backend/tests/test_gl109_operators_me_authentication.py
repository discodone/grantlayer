"""Tests for GL-109: /operators/me Authentication Fix.

Ensures /operators/me is correctly authenticated and fails closed.
Does not disclose operator identity, role, token status, token hashes,
lookup hashes, or internal auth details to anonymous or invalid-token callers.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib
from io import BytesIO
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl109(unittest.TestCase):
    """Shared helpers for GL-109 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_rate_limit_auth = os.environ.get("GRANTLAYER_RATE_LIMIT_AUTH")
        self._orig_cors_origins = os.environ.get("GRANTLAYER_CORS_ALLOWED_ORIGINS")

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
            ("GRANTLAYER_CORS_ALLOWED_ORIGINS", self._orig_cors_origins),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _insert_operator(self, op_id, name, role, token, active=1):
        """Insert operator with token_lookup_hash (GL-107 compliant)."""
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, token_lookup_hash, active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (op_id, name, role, self.ops_mod.hash_token(token),
                 self.ops_mod.derive_token_lookup_hash(token), active),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_handler(self, path, method="GET", auth_header=None, origin=None, client_ip="127.0.0.1"):
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"")
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if origin is not None:
            headers["Origin"] = origin
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
# 1. Missing / invalid / inactive token fails closed
# ═══════════════════════════════════════════════════════════════════════

class TestGl109MissingTokenFailsClosed(_BaseGl109):
    """Verify unauthenticated requests to /operators/me fail closed."""

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

    def test_missing_auth_header_returns_401(self):
        handler = self._make_handler("/operators/me")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_empty_auth_header_returns_401(self):
        handler = self._make_handler("/operators/me", auth_header="")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_no_bearer_prefix_returns_401(self):
        handler = self._make_handler("/operators/me", auth_header="Basic wrong")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)


class TestGl109InvalidTokenFailsClosed(_BaseGl109):
    """Verify invalid token requests to /operators/me fail closed."""

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

        self._insert_operator("op-1", "Alice", "owner", "valid-token")

    def test_invalid_token_returns_401(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer invalid-token")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_wrong_token_for_existing_operator_returns_401(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer totally-wrong")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)


class TestGl109InactiveTokenFailsClosed(_BaseGl109):
    """Verify inactive/revoked operator token fails closed."""

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

        self._insert_operator("op-inactive", "Inactive", "owner", "inactive-token", active=0)

    def test_inactive_operator_token_returns_401(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer inactive-token")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)


# ═══════════════════════════════════════════════════════════════════════
# 2. Valid token succeeds with safe response
# ═══════════════════════════════════════════════════════════════════════

class TestGl109ValidTokenSucceeds(_BaseGl109):
    """Verify valid operator token returns safe operator data."""

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

        self._insert_operator("op-1", "Alice", "owner", "secret-token")

    def test_valid_token_returns_200(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIn("operatorId", body)
        self.assertEqual(body["operatorId"], "op-1")
        self.assertEqual(body["name"], "Alice")
        self.assertEqual(body["role"], "owner")

    def test_response_includes_safe_fields(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        # Safe fields that should be present
        self.assertIn("operatorId", body)
        self.assertIn("name", body)
        self.assertIn("role", body)
        self.assertIn("active", body)

    def test_response_does_not_include_raw_token(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        body_str = json.dumps(body)
        self.assertNotIn("secret-token", body_str)

    def test_response_does_not_include_token_hash(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        body_str = json.dumps(body)
        self.assertNotIn("token_hash", body_str)

    def test_response_does_not_include_token_lookup_hash(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        body_str = json.dumps(body)
        self.assertNotIn("token_lookup_hash", body_str)

    def test_response_does_not_include_pbkdf2_details(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        body_str = json.dumps(body)
        self.assertNotIn("pbkdf2", body_str.lower())
        self.assertNotIn("600000", body_str)
        self.assertNotIn("sha256", body_str.lower())


# ═══════════════════════════════════════════════════════════════════════
# 3. Role behavior preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl109RoleBehaviorPreserved(_BaseGl109):
    """Verify role checks are preserved for /operators/me."""

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

        self._insert_operator("op-owner", "Owner", "owner", "owner-token")
        self._insert_operator("op-admin", "Admin", "grant_admin", "admin-token")
        self._insert_operator("op-auditor", "Auditor", "auditor", "auditor-token")

    def test_owner_role_can_access(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer owner-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body["role"], "owner")

    def test_grant_admin_role_can_access(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer admin-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body["role"], "grant_admin")

    def test_auditor_role_can_access(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer auditor-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body["role"], "auditor")


# ═══════════════════════════════════════════════════════════════════════
# 4. Operator mode disabled behavior safe
# ═══════════════════════════════════════════════════════════════════════

class TestGl109OperatorModeDisabledSafe(_BaseGl109):
    """Verify operator mode disabled does not leak state to anonymous callers."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-admin-token"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler

        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

    def test_anonymous_caller_gets_401_not_404_when_disabled(self):
        """Anonymous callers must not learn operator model is disabled."""
        handler = self._make_handler("/operators/me")
        status, headers, body = self._run_handler(handler)
        # With auth required first, unauthenticated callers get 401, not 404
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_invalid_legacy_token_gets_403_not_404_when_disabled(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer wrong-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self.assertIn("errorCode", body)

    def test_valid_legacy_token_gets_404_when_disabled(self):
        """Authenticated legacy callers may receive 404 (feature not available)."""
        handler = self._make_handler("/operators/me", auth_header="Bearer legacy-admin-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 404)
        self.assertEqual(body.get("errorCode"), "operator_model_disabled")


# ═══════════════════════════════════════════════════════════════════════
# 5. GL-107 bounded token lookup preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl109Gl107BoundedLookupPreserved(_BaseGl109):
    """Verify GL-107 bounded token lookup is preserved."""

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

    def test_invalid_token_with_many_operators_bounded_pbkdf2(self):
        """Invalid token against many operators: 0 PBKDF2 calls (lookup miss)."""
        for i in range(20):
            self._insert_operator(f"op-{i}", f"Op {i}", "owner", f"token-{i}")

        with patch.object(self.ops_mod, 'verify_token') as mock_verify:
            mock_verify.return_value = False
            handler = self._make_handler("/operators/me", auth_header="Bearer totally-wrong")
            status, headers, body = self._run_handler(handler)
            self.assertIn(status, (401, 403))
            mock_verify.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# 6. GL-106 rate limiting preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl109RateLimitingPreserved(_BaseGl109):
    """Verify GL-106 rate limiting is preserved on /operators/me."""

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

        self._insert_operator("op-1", "Owner", "owner", "owner-token")

    def test_rate_limit_blocks_after_exceeded(self):
        for _ in range(2):
            handler = self._make_handler("/operators/me", auth_header="Bearer owner-token")
            status, headers, body = self._run_handler(handler)
            self.assertEqual(status, 200)

        handler = self._make_handler("/operators/me", auth_header="Bearer owner-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 429)
        self.assertEqual(body.get("errorCode"), "rate_limit_exceeded")

    def test_rate_limited_response_includes_retry_after(self):
        for _ in range(2):
            handler = self._make_handler("/operators/me", auth_header="Bearer owner-token")
            self._run_handler(handler)

        handler = self._make_handler("/operators/me", auth_header="Bearer owner-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 429)
        self.assertIn("Retry-After", headers)
        retry_after = int(headers["Retry-After"])
        self.assertGreaterEqual(retry_after, 1)


# ═══════════════════════════════════════════════════════════════════════
# 7. Public endpoints remain public
# ═══════════════════════════════════════════════════════════════════════

class TestGl109PublicEndpoints(_BaseGl109):
    """Verify health and readiness remain public."""

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


# ═══════════════════════════════════════════════════════════════════════
# 8. CORS behavior preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl109CorsPreserved(_BaseGl109):
    """Verify CORS behavior is preserved."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler

        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("op-1", "Owner", "owner", "owner-token")

    def test_cors_headers_on_success(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer owner-token", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://trusted.com")

    def test_cors_headers_on_auth_failure(self):
        handler = self._make_handler("/operators/me", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://trusted.com")

    def test_no_cors_for_untrusted_origin(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer owner-token", origin="http://evil.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)


# ═══════════════════════════════════════════════════════════════════════
# 9. Security boundary preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl109SecurityBoundary(_BaseGl109):
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

        self._insert_operator("op-1", "Owner", "owner", "owner-token")

    def test_protected_endpoint_still_requires_auth(self):
        handler = self._make_handler("/grants")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))

    def test_operators_me_requires_auth(self):
        handler = self._make_handler("/operators/me")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))


# ═══════════════════════════════════════════════════════════════════════
# 10. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl109NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-109 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-109-operators-me-authentication-fix":
            self.skipTest(
                "Branch-wide diff check only valid on GL-109 feature branch"
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
            "backend/tests/test_gl109_operators_me_authentication.py",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-109 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
