"""GL-046 — Auth-Fix for Grant Request Read Endpoints.

Covers:
1. GET /grant-requests requires authentication.
2. GET /grant-requests/{id} requires authentication.
3. In operator model mode, both endpoints require owner, grant_admin, or auditor.
4. demo_operator is forbidden.
5. In legacy mode, admin-token behavior is preserved.
6. Error responses do not expose token values.
7. Endpoint paths are unchanged.
"""

import os
import sys
import json
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl046(unittest.TestCase):
    """Shared helpers for GL-046 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import src.grant_requests as requests_mod
        importlib.reload(requests_mod)
        self.requests_mod = requests_mod

        import src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
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

    def _create_request(self, **kwargs):
        from src.models import GrantRequest
        defaults = dict(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
        )
        defaults.update(kwargs)
        req = GrantRequest(**defaults)
        return self.requests_mod.create_grant_request(req)

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
        # Parse status line + body
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        body = json.loads(parts[1]) if len(parts) > 1 else {}
        return status, body


class TestGl046OperatorMode(_BaseGl046):
    """Operator-model auth tests for GET /grant-requests and /grant-requests/{id}."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        # Insert operators with varying roles
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("admin-1", "Grant Admin", "grant_admin", "admin-token")
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        self._insert_operator("demo-1", "Demo", "demo_operator", "demo-token")

        # Seed a grant request for detail-fetch tests
        self.request = self._create_request()

    # ──────────────────────────────────────────────
    # No auth
    # ──────────────────────────────────────────────
    def test_list_without_auth_returns_401(self):
        handler = self._make_handler("/grant-requests", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_detail_without_auth_returns_401(self):
        handler = self._make_handler(f"/grant-requests/{self.request.id}", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    # ──────────────────────────────────────────────
    # Valid roles
    # ──────────────────────────────────────────────
    def test_list_owner_succeeds(self):
        handler = self._make_handler("/grant-requests", auth_header="Bearer owner-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_list_grant_admin_succeeds(self):
        handler = self._make_handler("/grant-requests", auth_header="Bearer admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_list_auditor_succeeds(self):
        handler = self._make_handler("/grant-requests", auth_header="Bearer auditor-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_detail_owner_succeeds(self):
        handler = self._make_handler(f"/grant-requests/{self.request.id}", auth_header="Bearer owner-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), self.request.id)

    def test_detail_grant_admin_succeeds(self):
        handler = self._make_handler(f"/grant-requests/{self.request.id}", auth_header="Bearer admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), self.request.id)

    def test_detail_auditor_succeeds(self):
        handler = self._make_handler(f"/grant-requests/{self.request.id}", auth_header="Bearer auditor-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), self.request.id)

    # ──────────────────────────────────────────────
    # demo_operator forbidden
    # ──────────────────────────────────────────────
    def test_list_demo_operator_forbidden(self):
        handler = self._make_handler("/grant-requests", auth_header="Bearer demo-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    def test_detail_demo_operator_forbidden(self):
        handler = self._make_handler(f"/grant-requests/{self.request.id}", auth_header="Bearer demo-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    # ──────────────────────────────────────────────
    # Error hygiene
    # ──────────────────────────────────────────────
    def test_error_list_does_not_expose_token(self):
        handler = self._make_handler("/grant-requests", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        body_str = json.dumps(body)
        self.assertNotIn("owner-token", body_str)
        self.assertNotIn("admin-token", body_str)
        self.assertNotIn("Bearer", body_str)

    def test_error_detail_does_not_expose_token(self):
        handler = self._make_handler(f"/grant-requests/{self.request.id}", auth_header="Bearer demo-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        body_str = json.dumps(body)
        self.assertNotIn("demo-token", body_str)
        self.assertNotIn("Bearer", body_str)

    # ──────────────────────────────────────────────
    # Endpoint paths unchanged
    # ──────────────────────────────────────────────
    def test_list_endpoint_path_unchanged(self):
        handler = self._make_handler("/grant-requests", auth_header="Bearer owner-token")
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)

    def test_detail_endpoint_path_unchanged(self):
        handler = self._make_handler(f"/grant-requests/{self.request.id}", auth_header="Bearer owner-token")
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)


class TestGl046LegacyMode(_BaseGl046):
    """Legacy-mode auth tests for GET /grant-requests and /grant-requests/{id}."""

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

        self.request = self._create_request()

    def test_list_without_auth_returns_401(self):
        handler = self._make_handler("/grant-requests", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)

    def test_detail_without_auth_returns_401(self):
        handler = self._make_handler(f"/grant-requests/{self.request.id}", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)

    def test_list_with_valid_admin_token_succeeds(self):
        handler = self._make_handler("/grant-requests", auth_header="Bearer legacy-admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_detail_with_valid_admin_token_succeeds(self):
        handler = self._make_handler(f"/grant-requests/{self.request.id}", auth_header="Bearer legacy-admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), self.request.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
