"""GL-039-A2 — Agent Permission Evaluation API Endpoint tests.

Covers endpoint routing, auth, response shape, evaluation logic,
optional fields, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAgentPermissionEvaluationAPI(unittest.TestCase):
    """Tests for POST /agent-permissions/evaluate endpoint."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        if self._orig_url is not None:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-token"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"

        import src.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

        from src.server import GrantLayerHandler
        from src import config
        from src import operators as ops

        self.handler_class = GrantLayerHandler
        self.config = config
        self.ops = ops

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_url is not None:
            os.environ["GRANTLAYER_DATABASE_URL"] = self._orig_url
        else:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        if self._orig_admin_token is not None:
            os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._orig_admin_token
        else:
            os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        if self._orig_enable_operator is not None:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = self._orig_enable_operator
        else:
            os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        if self._orig_require_admin is not None:
            os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = self._orig_require_admin
        else:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

    def _insert_operator(self, op_id, name, role, token):
        import src.db as db_mod
        conn = db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, datetime('now'))""",
                (op_id, name, role, self.ops.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _run_handler(self, path, method="POST", auth=None, body=None):
        """Simulate a server request and return (status, response_json)."""
        importlib.reload(self.config)
        from io import BytesIO

        class DummyRequest:
            def __init__(self):
                self.headers = {}
                if auth:
                    self.headers["Authorization"] = auth
                self.rfile = BytesIO(b"")
                self.wfile = BytesIO()
                self._status = None
                self._headers = {}

            def send_response(self, code):
                self._status = code

            def send_header(self, key, value):
                self._headers[key] = value

            def end_headers(self):
                pass

        class TestHandler(self.handler_class):
            def __init__(inner_self, request):
                inner_self.command = method
                inner_self.path = path
                inner_self.request_version = "HTTP/1.1"
                inner_self.headers = request.headers
                inner_self.rfile = request.rfile
                inner_self.wfile = request.wfile
                inner_self._status = None
                inner_self._headers = {}

            def send_response(inner_self, code):
                inner_self._status = code

            def send_header(inner_self, key, value):
                inner_self._headers[key] = value

            def end_headers(inner_self):
                pass

            def _send_json(inner_self, status, data):
                inner_self.send_response(status)
                inner_self._json = data
                inner_self._status = status

            def _send_html(inner_self, body):
                inner_self.send_response(200)
                inner_self._status = 200

        req = DummyRequest()
        if body is not None:
            req.rfile = BytesIO(json.dumps(body).encode("utf-8"))
            req.headers["Content-Length"] = str(len(json.dumps(body).encode("utf-8")))
        handler = TestHandler(req)
        if method == "GET":
            handler.do_GET()
        else:
            handler.do_POST()
        return handler._status, getattr(handler, "_json", None)

    # ── Endpoint routing ────────────────────────────────────────
    def test_endpoint_exists_and_returns_400_for_missing_fields(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={"agentId": "agent-1"},
        )
        self.assertEqual(status, 400)
        self.assertIn("Missing fields", body.get("error", ""))

    def test_endpoint_returns_200_for_valid_request(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])
        self.assertEqual(body["agentId"], "agent-1")
        self.assertEqual(body["requestedScope"], "evidence:read")
        self.assertEqual(body["matchedScope"], "evidence:read")
        self.assertEqual(body["reason"], "scope_matched")

    # ── Auth ────────────────────────────────────────────────────
    def test_endpoint_requires_admin_token_when_operator_disabled(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 401)
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer wrong-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 403)

    def test_endpoint_accepts_owner_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("owner-1", "Owner One", "owner", "owner-token")

        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer owner-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])

    def test_endpoint_accepts_grant_admin_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("admin-1", "Admin One", "grant_admin", "admin-token")

        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])

    def test_endpoint_rejects_auditor_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")

        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer auditor-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 403)

    def test_endpoint_rejects_demo_operator_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("demo-op-1", "Demo Op", "demo_operator", "demo-token")

        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer demo-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 403)

    # ── Response shape ──────────────────────────────────────────
    def test_response_contains_expected_keys(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
                "resourceType": "bundle",
                "resourceId": "bundle-123",
            },
        )
        self.assertEqual(status, 200)
        expected_keys = {
            "allowed",
            "agentId",
            "requestedScope",
            "matchedScope",
            "resourceType",
            "resourceId",
            "reason",
            "warnings",
        }
        self.assertEqual(set(body.keys()), expected_keys)
        self.assertEqual(body["resourceType"], "bundle")
        self.assertEqual(body["resourceId"], "bundle-123")

    # ── Evaluation logic ────────────────────────────────────────
    def test_endpoint_denies_unknown_scope(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:frobnicate",
                "assignedScopes": ["evidence:frobnicate"],
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertEqual(body["reason"], "requested_scope_unknown")

    def test_endpoint_allows_wildcard_read(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["*:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])
        self.assertEqual(body["matchedScope"], "*:read")

    def test_endpoint_denies_malformed_scope(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertEqual(body["reason"], "requested_scope_malformed")

    def test_endpoint_allows_admin_star(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["admin:*"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])
        self.assertEqual(body["matchedScope"], "admin:*")

    def test_endpoint_denies_scope_not_matched(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:write",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertEqual(body["reason"], "scope_not_matched")

    def test_endpoint_passes_context_optional(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
                "context": {"ip": "127.0.0.1"},
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])

    # ── Secrets safety ──────────────────────────────────────────
    def test_response_does_not_expose_secrets(self):
        status, body = self._run_handler(
            "/agent-permissions/evaluate",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
