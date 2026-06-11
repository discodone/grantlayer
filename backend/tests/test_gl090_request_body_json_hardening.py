"""Tests for GL-090 Request Body Size Limit / Safe JSON Read Hardening.

Ensures:
- JSON request bodies are bounded by MAX_JSON_BODY_BYTES.
- Missing Content-Length returns safe HTTP 400.
- Non-integer Content-Length returns safe HTTP 400.
- Negative Content-Length returns safe HTTP 400.
- Content-Length exceeding max returns safe HTTP 413.
- Oversized requests do not reach mutation logic.
- Malformed JSON returns safe HTTP 400.
- Empty request body returns safe error.
- Valid JSON under limit continues to work.
- Error responses do not leak internals, stack traces, or secrets.
- Prior GL protections remain intact.
- Public endpoints remain public.
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


class _BaseGl090(unittest.TestCase):
    """Shared helpers for GL-090 tests."""

    _MISSING_CL = object()

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")

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

        import backend.src.challenges as challenges_mod
        importlib.reload(challenges_mod)
        self.challenges_mod = challenges_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
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

    def _make_handler(self, path, method="GET", auth_header=None, body=b"", content_length=_MISSING_CL):
        handler_class = self.server_mod.GrantLayerHandler
        from io import BytesIO

        handler = handler_class.__new__(handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if content_length is not self._MISSING_CL:
            if content_length is not None and content_length != "":
                headers["Content-Length"] = str(content_length)
        elif body:
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
        body_str = json.dumps(body)
        forbidden_terms = [
            "password", "api_key", "traceback", "exception",
            "postgresql://", "db_url", "secret_value", "private_key",
            "GRANTLAYER_ADMIN_TOKEN", "GRANTLAYER_DB",
        ]
        for term in forbidden_terms:
            self.assertNotIn(term, body_str.lower(), f"Error response contains forbidden term: {term}")

    def _valid_grant_body(self):
        return json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2020-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "owner-1",
            "reason": "test",
        }).encode()

    def _valid_challenge_body(self):
        return json.dumps({
            "subjectId": "sub-1",
            "action": "read",
            "resource": "repo-a",
        }).encode()


class TestGl090RequestBodyLimits(_BaseGl090):
    """Test JSON body size limits and Content-Length safety."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_missing_content_length_returns_400(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=self._valid_grant_body(), content_length=None,
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "missing_content_length")

    def test_non_integer_content_length_returns_400(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=self._valid_grant_body(), content_length="abc",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "invalid_content_length")

    def test_negative_content_length_returns_400(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=self._valid_grant_body(), content_length="-5",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "invalid_content_length")

    def test_oversized_content_length_returns_413(self):
        oversized = b"x" * (self.server_mod.MAX_JSON_BODY_BYTES + 1)
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=oversized, content_length=str(len(oversized)),
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 413)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "payload_too_large")

    def test_oversized_request_does_not_create_grant(self):
        before = self.grants_mod.list_grants()
        oversized = b"x" * (self.server_mod.MAX_JSON_BODY_BYTES + 1)
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=oversized, content_length=str(len(oversized)),
        )
        self._run_handler(handler)
        after = self.grants_mod.list_grants()
        self.assertEqual(len(after), len(before))

    def test_empty_body_returns_400(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=b"", content_length="0",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "empty_request_body")

    def test_malformed_json_returns_400(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=b"{not json", content_length="9",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "invalid_json")

    def test_valid_json_under_limit_succeeds(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=self._valid_grant_body(),
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 201)
        self.assertIn("id", body)

    def test_error_response_does_not_leak_valueerror_message(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=b"{bad", content_length="4",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self._assert_no_secrets_in_body(body)
        body_str = json.dumps(body)
        self.assertNotIn("expecting", body_str.lower())
        self.assertNotIn("delimiter", body_str.lower())

    def test_error_response_does_not_leak_internals_on_missing_cl(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=self._valid_grant_body(), content_length=None,
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self._assert_no_secrets_in_body(body)
        self.assertNotIn("rfile", json.dumps(body).lower())
        self.assertNotIn("headers", json.dumps(body).lower())


class TestGl090MutationEndpointsProtected(_BaseGl090):
    """Ensure invalid/oversized bodies skip mutation logic on key endpoints."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("demo-1", "Demo", "demo_operator", "demo-token")

    def test_post_challenges_oversized_does_not_create(self):
        before = self.challenges_mod.list_challenges()
        oversized = b"x" * (self.server_mod.MAX_JSON_BODY_BYTES + 1)
        handler = self._make_handler(
            "/challenges", method="POST", auth_header="Bearer owner-token",
            body=oversized, content_length=str(len(oversized)),
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 413)
        after = self.challenges_mod.list_challenges()
        self.assertEqual(len(after), len(before))

    def test_post_challenges_malformed_json_does_not_create(self):
        before = self.challenges_mod.list_challenges()
        handler = self._make_handler(
            "/challenges", method="POST", auth_header="Bearer owner-token",
            body=b"{not json", content_length="9",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        after = self.challenges_mod.list_challenges()
        self.assertEqual(len(after), len(before))

    def test_post_demo_action_oversized_does_not_run(self):
        # demo-action is protected by auth first, so use valid auth
        oversized = b"x" * (self.server_mod.MAX_JSON_BODY_BYTES + 1)
        handler = self._make_handler(
            "/demo-action", method="POST", auth_header="Bearer owner-token",
            body=oversized, content_length=str(len(oversized)),
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 413)

    def test_post_demo_action_malformed_json_returns_400(self):
        handler = self._make_handler(
            "/demo-action", method="POST", auth_header="Bearer owner-token",
            body=b"{bad", content_length="4",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "invalid_json")


class TestGl090AuthProtectionsPreserved(_BaseGl090):
    """Verify prior GL protections remain intact after body hardening."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_post_challenges_still_requires_auth(self):
        handler = self._make_handler(
            "/challenges", method="POST", body=self._valid_challenge_body(),
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_post_challenges_invalid_body_does_not_create(self):
        before = self.challenges_mod.list_challenges()
        handler = self._make_handler(
            "/challenges", method="POST", auth_header="Bearer owner-token",
            body=b"{bad", content_length="4",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        after = self.challenges_mod.list_challenges()
        self.assertEqual(len(after), len(before))

    def test_post_demo_action_still_requires_auth(self):
        demo_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler(
            "/demo-action", method="POST", body=demo_body,
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_get_grants_still_requires_auth(self):
        handler = self._make_handler("/grants")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_get_audit_events_still_requires_auth(self):
        handler = self._make_handler("/audit-events")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_health_remains_public(self):
        handler = self._make_handler("/health")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_remains_public(self):
        handler = self._make_handler("/readiness")
        status, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))


class TestGl090LegacyMode(_BaseGl090):
    """Verify body hardening works in legacy admin-token mode."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-admin-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

    def test_missing_content_length_legacy_mode(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer legacy-admin-token",
            body=self._valid_grant_body(), content_length=None,
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "missing_content_length")

    def test_oversized_body_legacy_mode(self):
        oversized = b"x" * (self.server_mod.MAX_JSON_BODY_BYTES + 1)
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer legacy-admin-token",
            body=oversized, content_length=str(len(oversized)),
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 413)
        self.assertEqual(body.get("errorCode"), "payload_too_large")

    def test_malformed_json_legacy_mode(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer legacy-admin-token",
            body=b"{bad", content_length="4",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json")

    def test_valid_json_legacy_mode_succeeds(self):
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer legacy-admin-token",
            body=self._valid_grant_body(),
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 201)
        self.assertIn("id", body)


class TestGl090NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-090 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-090-request-body-json-hardening":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-090 feature branch"
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
            "backend/tests/test_gl090_request_body_json_hardening.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-090 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
