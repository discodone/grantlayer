"""Tests for GL-095 CORS Origin Hardening.

Ensures:
- No wildcard Access-Control-Allow-Origin: * is granted.
- Arbitrary Origin headers are not reflected.
- Only exact-origin matches from an allowlist receive CORS access.
- OPTIONS/preflight is deterministic and does not mutate state.
- CORS does not bypass auth.
- Public endpoints (/health, /readiness) remain public.
- Protected endpoints remain protected.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl095(unittest.TestCase):
    """Shared helpers for GL-095 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_cors_origins = os.environ.get("GRANTLAYER_CORS_ALLOWED_ORIGINS")

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.challenges as challenges_mod
        importlib.reload(challenges_mod)
        self.challenges_mod = challenges_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_CORS_ALLOWED_ORIGINS", self._orig_cors_origins),
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

    def _create_matching_grant(self):
        grant = self.models_mod.Grant(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2030-01-01T00:00:00Z",
            created_by="owner-1",
            reason="test",
        )
        self.grants_mod.create_grant(grant)
        return grant

    def _make_handler(self, path, method="GET", auth_header=None, origin=None, body=b""):
        import backend.src.server as server_mod
        importlib.reload(server_mod)
        handler_class = server_mod.GrantLayerHandler
        from io import BytesIO

        handler = handler_class.__new__(handler_class)
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
        handler.client_address = ("127.0.0.1", 0)
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

    def _assert_gl030_full(self, payload):
        self.assertIn("error", payload)
        self.assertIn("errorCode", payload)
        self.assertIn("reason", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)


class TestGl095CorsWildcardRemoved(_BaseGl095):
    """Verify wildcard CORS is removed from all responses."""

    def test_no_wildcard_on_public_health(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = ""
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        handler = self._make_handler("/health", origin="http://evil.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotEqual(headers.get("Access-Control-Allow-Origin"), "*")

    def test_no_wildcard_on_protected_401(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = ""
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin-token"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        handler = self._make_handler("/grants", origin="http://evil.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertNotEqual(headers.get("Access-Control-Allow-Origin"), "*")

    def test_no_wildcard_on_404(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = ""
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        handler = self._make_handler("/nonexistent", origin="http://evil.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 404)
        self.assertNotEqual(headers.get("Access-Control-Allow-Origin"), "*")


class TestGl095ArbitraryOriginNotReflected(_BaseGl095):
    """Verify arbitrary Origin headers are never reflected."""

    def test_malicious_origin_not_reflected_on_health(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        handler = self._make_handler("/health", origin="http://malicious.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_malicious_origin_not_reflected_on_401(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin-token"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        handler = self._make_handler("/grants", origin="http://malicious.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_malicious_origin_not_reflected_on_options(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        handler = self._make_handler("/grants", method="OPTIONS", origin="http://malicious.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 204)
        self.assertNotIn("Access-Control-Allow-Origin", headers)


class TestGl095AllowlistExactMatching(_BaseGl095):
    """Verify allowlist exact matching behavior."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com,https://app.example.com"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server

    def test_allowed_origin_gets_cors_headers(self):
        handler = self._make_handler("/health", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://trusted.com")
        self.assertIn("Access-Control-Allow-Methods", headers)
        self.assertIn("Vary", headers)

    def test_second_allowed_origin_gets_cors_headers(self):
        handler = self._make_handler("/health", origin="https://app.example.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "https://app.example.com")

    def test_unlisted_origin_gets_no_cors_grant(self):
        handler = self._make_handler("/health", origin="http://untrusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_similar_looking_origin_does_not_match(self):
        # Subdomain, scheme, and port differences must not match
        handler = self._make_handler("/health", origin="http://sub.trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

        handler = self._make_handler("/health", origin="https://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

        handler = self._make_handler("/health", origin="http://trusted.com:8080")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_no_origin_header_gets_no_cors_grant(self):
        handler = self._make_handler("/health")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)


class TestGl095OptionsPreflight(_BaseGl095):
    """Verify OPTIONS/preflight behavior."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server

    def test_options_allowed_origin_returns_204_with_cors(self):
        handler = self._make_handler("/grants", method="OPTIONS", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://trusted.com")
        self.assertIn("Access-Control-Allow-Methods", headers)

    def test_options_unlisted_origin_returns_204_without_cors(self):
        handler = self._make_handler("/grants", method="OPTIONS", origin="http://evil.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 204)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_options_does_not_mutate_state(self):
        # Count grants before and after OPTIONS request
        import backend.src.server as server_mod
        importlib.reload(server_mod)
        from backend.src.db import get_conn
        conn = get_conn()
        before = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        conn.close()

        handler = self._make_handler("/grants", method="OPTIONS", origin="http://trusted.com")
        self._run_handler(handler)

        conn = get_conn()
        after = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        conn.close()
        self.assertEqual(before, after)

        # Also verify no audit events were created
        conn = get_conn()
        after_audit = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        conn.close()
        # There should be no new audit events from OPTIONS
        self.assertEqual(after_audit, 0)


class TestGl095CorsDoesNotBypassAuth(_BaseGl095):
    """Verify CORS presence does not weaken auth requirements."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server

        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._create_matching_grant()

    def test_grants_still_requires_auth_with_allowed_origin(self):
        handler = self._make_handler("/grants", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_grants_succeeds_with_allowed_origin_and_auth(self):
        handler = self._make_handler("/grants", auth_header="Bearer owner-token", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://trusted.com")

    def test_demo_action_still_requires_auth_with_allowed_origin(self):
        demo_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/demo-action", method="POST", origin="http://trusted.com", body=demo_body)
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_challenges_still_requires_auth_with_allowed_origin(self):
        challenge_body = json.dumps({
            "subjectId": "sub-1",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/challenges", method="POST", origin="http://trusted.com", body=challenge_body)
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)


class TestGl095PublicAndProtectedEndpoints(_BaseGl095):
    """Verify public endpoints remain public and protected remain protected."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server

        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._create_matching_grant()

    def test_health_public(self):
        handler = self._make_handler("/health", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_public(self):
        handler = self._make_handler("/readiness", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))
        self.assertIn(body.get("status"), ("ready", "not_ready"))

    def test_get_grants_protected(self):
        handler = self._make_handler("/grants", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)

    def test_post_demo_action_protected(self):
        demo_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/demo-action", method="POST", origin="http://trusted.com", body=demo_body)
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)

    def test_post_challenges_protected(self):
        challenge_body = json.dumps({
            "subjectId": "sub-1",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/challenges", method="POST", origin="http://trusted.com", body=challenge_body)
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)


class TestGl095NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-095 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-095-cors-origin-hardening":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-095 feature branch"
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
            "backend/tests/test_gl095_cors_origin_hardening.py",
            "docs/openapi.yaml",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-095 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
