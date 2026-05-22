"""Tests for GL-088 POST /challenges Auth Enforcement.

Ensures POST /challenges requires authentication and authorization,
using existing GrantLayer auth patterns. GET /challenges behavior remains
consistent. Public endpoints (/health, /readiness) remain accessible
without auth. Prior GL protections remain intact.
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


class _BaseGl088(unittest.TestCase):
    """Shared helpers for GL-088 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")

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

        import src.challenges as challenges_mod
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

    def _make_handler(self, path, method="GET", auth_header=None, body=b""):
        import src.server as server_mod
        importlib.reload(server_mod)
        handler_class = server_mod.GrantLayerHandler
        from io import BytesIO

        handler = handler_class.__new__(handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
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
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        body = json.loads(parts[1]) if len(parts) > 1 else {}
        return status, body

    def _assert_gl030_full(self, payload):
        self.assertIn("error", payload)
        self.assertIn("errorCode", payload)
        self.assertIn("reason", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)

    def _assert_no_secrets_in_body(self, body):
        body_str = json.dumps(body).lower()
        forbidden_terms = [
            "password", "api_key", "traceback", "exception",
            "postgresql://", "db_url", "secret_value", "private_key",
        ]
        for term in forbidden_terms:
            self.assertNotIn(term, body_str, f"Error response contains forbidden term: {term}")

    def _challenge_body(self):
        return json.dumps({
            "subjectId": "sub-1",
            "action": "read",
            "resource": "repo-a",
        }).encode()


class TestGl088OperatorMode(_BaseGl088):
    """Operator-model auth tests for POST /challenges."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.auth as fresh_auth
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

    def test_post_challenges_without_auth_returns_401(self):
        handler = self._make_handler("/challenges", method="POST", body=self._challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_post_challenges_without_auth_does_not_create(self):
        before = self.challenges_mod.list_challenges()
        handler = self._make_handler("/challenges", method="POST", body=self._challenge_body())
        self._run_handler(handler)
        after = self.challenges_mod.list_challenges()
        self.assertEqual(len(after), len(before))

    def test_post_challenges_demo_operator_forbidden(self):
        handler = self._make_handler("/challenges", method="POST", auth_header="Bearer demo-token", body=self._challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    def test_post_challenges_demo_operator_does_not_create(self):
        before = self.challenges_mod.list_challenges()
        handler = self._make_handler("/challenges", method="POST", auth_header="Bearer demo-token", body=self._challenge_body())
        self._run_handler(handler)
        after = self.challenges_mod.list_challenges()
        self.assertEqual(len(after), len(before))

    def test_post_challenges_owner_succeeds(self):
        handler = self._make_handler("/challenges", method="POST", auth_header="Bearer owner-token", body=self._challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 201)
        self.assertIn("challengeId", body)
        self.assertIn("subjectId", body)
        self.assertIn("action", body)
        self.assertIn("resource", body)
        self.assertIn("expiresAt", body)

    def test_post_challenges_grant_admin_succeeds(self):
        handler = self._make_handler("/challenges", method="POST", auth_header="Bearer admin-token", body=self._challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 201)
        self.assertIn("challengeId", body)

    def test_post_challenges_auditor_succeeds(self):
        handler = self._make_handler("/challenges", method="POST", auth_header="Bearer auditor-token", body=self._challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 201)
        self.assertIn("challengeId", body)

    def test_post_challenges_response_shape_compatible(self):
        handler = self._make_handler("/challenges", method="POST", auth_header="Bearer owner-token", body=self._challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 201)
        self.assertIsInstance(body.get("challengeId"), str)
        self.assertIsInstance(body.get("subjectId"), str)
        self.assertIsInstance(body.get("action"), str)
        self.assertIsInstance(body.get("resource"), str)
        self.assertIsInstance(body.get("expiresAt"), str)

    def test_get_challenges_still_requires_auth(self):
        handler = self._make_handler("/challenges", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_get_challenges_owner_succeeds(self):
        handler = self._make_handler("/challenges", auth_header="Bearer owner-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_gl087_auth_error_response_shape_preserved(self):
        handler = self._make_handler("/challenges", method="POST", body=self._challenge_body())
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


class TestGl088LegacyMode(_BaseGl088):
    """Legacy-mode auth tests for POST /challenges."""

    def setUp(self):
        super().setUp()
        os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-admin-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.auth as fresh_auth
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

    def test_post_challenges_without_auth_returns_401(self):
        handler = self._make_handler("/challenges", method="POST", body=self._challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_post_challenges_without_auth_does_not_create(self):
        before = self.challenges_mod.list_challenges()
        handler = self._make_handler("/challenges", method="POST", body=self._challenge_body())
        self._run_handler(handler)
        after = self.challenges_mod.list_challenges()
        self.assertEqual(len(after), len(before))

    def test_post_challenges_invalid_token_forbidden(self):
        handler = self._make_handler("/challenges", method="POST", auth_header="Bearer wrong-token", body=self._challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_invalid")

    def test_post_challenges_invalid_token_does_not_create(self):
        before = self.challenges_mod.list_challenges()
        handler = self._make_handler("/challenges", method="POST", auth_header="Bearer wrong-token", body=self._challenge_body())
        self._run_handler(handler)
        after = self.challenges_mod.list_challenges()
        self.assertEqual(len(after), len(before))

    def test_post_challenges_with_valid_admin_token_succeeds(self):
        handler = self._make_handler("/challenges", method="POST", auth_header="Bearer legacy-admin-token", body=self._challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 201)
        self.assertIn("challengeId", body)

    def test_get_challenges_still_requires_auth(self):
        handler = self._make_handler("/challenges", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_get_challenges_with_valid_admin_token_succeeds(self):
        handler = self._make_handler("/challenges", auth_header="Bearer legacy-admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

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


class TestGl088OpenAPIContract(_BaseGl088):
    """Verify OpenAPI contract includes security and 401/403 for POST /challenges."""

    def _openapi_text(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        return openapi_path.read_text(encoding="utf-8")

    def _section_between(self, text, start, end):
        idx_start = text.find(start)
        idx_end = text.find(end)
        if idx_start == -1:
            return ""
        if idx_end == -1:
            return text[idx_start:]
        return text[idx_start:idx_end]

    def test_openapi_challenges_has_security(self):
        text = self._openapi_text()
        section = self._section_between(text, "/challenges:", "/operators/me:")
        self.assertIn("security:", section)
        self.assertIn("LegacyAdminToken", section)
        self.assertIn("OperatorToken", section)

    def test_openapi_challenges_has_401_403(self):
        text = self._openapi_text()
        section = self._section_between(text, "/challenges:", "/operators/me:")
        self.assertIn('"401"', section)
        self.assertIn('"403"', section)

    def test_openapi_health_no_security(self):
        text = self._openapi_text()
        section = self._section_between(text, "/health:", "/readiness:")
        self.assertNotIn("security:", section)

    def test_openapi_readiness_no_security(self):
        text = self._openapi_text()
        section = self._section_between(text, "/readiness:", "/:")
        self.assertNotIn("security:", section)


class TestGl088NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-088 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-088-challenge-auth-enforcement":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-088 feature branch"
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
            "backend/tests/test_gl088_challenge_auth_enforcement.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-088 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
