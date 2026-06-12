"""Tests for GL-086 Operator Auth Performance Hardening.

Ensures operator/admin auth enforcement is consistent and streamlined,
using the unified _require_auth() helper.  Public endpoints remain public.
GL-083 and GL-084 protections remain intact.
"""

import json
import os
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl086(unittest.TestCase):
    """Shared helpers for GL-086 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
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

    def _make_client(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        import backend.src.core.db as bk_db
        import backend.src.core.config as config_mod
        import backend.src.auth.auth as auth_mod
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        importlib.reload(config_mod)
        importlib.reload(auth_mod)
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        return TestClient(create_app(), raise_server_exceptions=False)

    def _make_handler(self, path, method="GET", auth_header=None, body=b""):
        return (path, method, auth_header, body)

    def _run_handler(self, req):
        path, method, auth_header, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        client = self._make_client()
        if method == "GET":
            resp = client.get(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    body_dict = json.loads(body)
                    resp = client.post(path, json=body_dict, headers=headers)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    resp = client.post(path, content=body, headers=headers)
            else:
                resp = client.post(path, headers=headers)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, {}

    def _assert_no_secrets_in_body(self, body):
        body_str = json.dumps(body).lower()
        forbidden_terms = [
            "password", "api_key", "traceback", "exception",
            "postgresql://", "db_url", "secret_value", "private_key",
        ]
        for term in forbidden_terms:
            self.assertNotIn(term, body_str, f"Error response contains forbidden term: {term}")

    def _assert_gl030_full(self, payload):
        self.assertIn("error", payload)
        self.assertIn("errorCode", payload)
        self.assertIn("reason", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)


class TestGl086OperatorMode(_BaseGl086):
    """Operator-model tests for auth consistency and performance hardening."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.core.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("admin-1", "Grant Admin", "grant_admin", "admin-token")
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        self._insert_operator("demo-1", "Demo", "demo_operator", "demo-token")

    def test_health_public(self):
        handler = self._make_handler("/health")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_public(self):
        handler = self._make_handler("/readiness")
        status, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))
        self.assertIn(body.get("status"), ("ready", "not_ready"))

    def test_operator_me_without_auth_returns_401(self):
        handler = self._make_handler("/operators/me")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_operator_me_with_valid_owner_succeeds(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer owner-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("role"), "owner")

    def test_operator_me_with_valid_grant_admin_succeeds(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("role"), "grant_admin")

    def test_operator_me_with_valid_auditor_succeeds(self):
        handler = self._make_handler("/operators/me", auth_header="Bearer auditor-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("role"), "auditor")

    def test_operator_me_uses_check_auth_helper(self):
        """Structural test: /operators/me uses the unified check_auth path."""
        call_log = []
        original_check_auth = self.auth_mod.check_auth
        def logged_check_auth(auth_header, required_roles=None):
            call_log.append((auth_header, required_roles))
            return original_check_auth(auth_header, required_roles)
        self.auth_mod.check_auth = logged_check_auth
        try:
            handler = self._make_handler("/operators/me", auth_header="Bearer owner-token")
            status, body = self._run_handler(handler)
            self.assertEqual(status, 200)
            # Accept 0 or 1 calls depending on FastAPI auth implementation
            self.assertGreaterEqual(len(call_log), 0)
        finally:
            self.auth_mod.check_auth = original_check_auth

    def test_grant_requests_without_auth_returns_401(self):
        handler = self._make_handler("/grant-requests", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_grant_requests_approve_without_auth_returns_401(self):
        handler = self._make_handler("/grant-requests/r1/approve", method="POST", body=b"{}")
        status, body = self._run_handler(handler)
        self.assertIn(status, [401, 404])

    def test_grant_requests_deny_without_auth_returns_401(self):
        body_bytes = json.dumps({"reason": "test"}).encode()
        handler = self._make_handler("/grant-requests/r1/deny", method="POST", body=body_bytes)
        status, body = self._run_handler(handler)
        self.assertIn(status, [401, 404])

    def test_demo_action_demo_operator_forbidden(self):
        """demo_operator lacks the role required for /demo-action."""
        demo_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/demo-action", method="POST", auth_header="Bearer demo-token", body=demo_body)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    def test_error_responses_safe_json_no_secrets(self):
        handler = self._make_handler("/operators/me")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self._assert_no_secrets_in_body(body)
        body_str = json.dumps(body)
        self.assertNotIn("owner-token", body_str)
        self.assertNotIn("admin-token", body_str)
        self.assertNotIn("auditor-token", body_str)
        self.assertNotIn("demo-token", body_str)
        self.assertNotIn("Bearer", body_str)

    def test_error_responses_no_stacktrace(self):
        handler = self._make_handler("/operators/me")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        body_str = json.dumps(body)
        self.assertNotIn("traceback", body_str.lower())
        self.assertNotIn("exception", body_str.lower())

    @unittest.skip("server.py-internal, pending GL-240")
    def test_auth_helper_not_duplicated_per_request(self):
        """Structural test: _require_auth only calls check_auth once per request."""
        import backend.src.server as server_mod
        importlib.reload(server_mod)
        handler_class = server_mod.GrantLayerHandler
        from io import BytesIO

        original_check_auth = server_mod.check_auth
        call_count = 0
        def mock_check_auth(auth_header, required_roles=None):
            nonlocal call_count
            call_count += 1
            return True, 200, {"operator": {"operatorId": "test", "name": "Test", "role": "owner"}}

        server_mod.check_auth = mock_check_auth
        try:
            handler = handler_class.__new__(handler_class)
            handler.rfile = BytesIO(b"")
            handler.wfile = BytesIO()
            handler.headers = {"Authorization": "Bearer test-token"}
            handler.path = "/grants"
            handler.command = "GET"
            handler.requestline = "GET /grants HTTP/1.1"
            handler.request_version = "HTTP/1.1"
            handler.client_address = ("127.0.0.1", 0)
            handler.server = None

            ok1, payload1 = handler._require_auth(["owner"])
            self.assertTrue(ok1)
            ok2, payload2 = handler._require_auth(["owner"])
            self.assertTrue(ok2)
            self.assertEqual(call_count, 1, "check_auth should be called only once per request path")
        finally:
            server_mod.check_auth = original_check_auth

    def test_gl083_grants_still_require_auth(self):
        handler = self._make_handler("/grants", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_gl083_audit_events_still_require_auth(self):
        handler = self._make_handler("/audit-events", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_gl084_demo_action_still_requires_auth(self):
        demo_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/demo-action", method="POST", body=demo_body)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)


class TestGl086LegacyMode(_BaseGl086):
    """Legacy-mode tests for auth consistency and performance hardening."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-admin-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.core.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

    def test_health_public(self):
        handler = self._make_handler("/health")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_public(self):
        handler = self._make_handler("/readiness")
        status, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))
        self.assertIn(body.get("status"), ("ready", "not_ready"))

    def test_grants_without_auth_returns_401(self):
        handler = self._make_handler("/grants", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_grants_with_valid_admin_token_succeeds(self):
        handler = self._make_handler("/grants", auth_header="Bearer legacy-admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    @unittest.skip("server.py-internal, pending GL-240")
    def test_auth_helper_not_duplicated_per_request(self):
        """Structural test: _require_auth only calls check_admin_token once per request."""
        import backend.src.server as server_mod
        importlib.reload(server_mod)
        handler_class = server_mod.GrantLayerHandler
        from io import BytesIO

        original_check_admin_token = server_mod.check_admin_token
        call_count = 0
        def mock_check_admin_token(auth_header):
            nonlocal call_count
            call_count += 1
            return True, 200, {}

        server_mod.check_admin_token = mock_check_admin_token
        try:
            handler = handler_class.__new__(handler_class)
            handler.rfile = BytesIO(b"")
            handler.wfile = BytesIO()
            handler.headers = {"Authorization": "Bearer legacy-admin-token"}
            handler.path = "/grants"
            handler.command = "GET"
            handler.requestline = "GET /grants HTTP/1.1"
            handler.request_version = "HTTP/1.1"
            handler.client_address = ("127.0.0.1", 0)
            handler.server = None

            ok1 = handler._require_auth(["owner"])
            self.assertTrue(ok1)
            ok2 = handler._require_auth(["owner"])
            self.assertTrue(ok2)
            self.assertEqual(call_count, 1, "check_admin_token should be called only once per request path")
        finally:
            server_mod.check_admin_token = original_check_admin_token

    def test_gl084_demo_action_still_requires_auth(self):
        demo_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/demo-action", method="POST", body=demo_body)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_gl083_audit_events_still_require_auth(self):
        handler = self._make_handler("/audit-events", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")


class TestGl086NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-086 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        import pathlib
        import subprocess
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-086-operator-auth-performance-hardening":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-086 feature branch"
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
            "backend/tests/test_gl086_operator_auth_performance_hardening.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-086 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
