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

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.grants.grant_requests as requests_mod
        importlib.reload(requests_mod)
        self.requests_mod = requests_mod

        import backend.src.auth.auth as auth_mod
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
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, token_hash=EXCLUDED.token_hash, active=EXCLUDED.active""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _create_request(self, **kwargs):
        from backend.src.core.models import GrantRequest
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
        return self.requests_mod.create_grant_request(req, tenant_id="demo")

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


class TestGl046OperatorMode(_BaseGl046):
    """Operator-model auth tests for GET /grant-requests and /grant-requests/{id}."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
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

        self.request = self._create_request()

    # ──────────────────────────────────────────────
    # No auth
    # ──────────────────────────────────────────────
    def test_list_without_auth_returns_401(self):
        handler = self._make_handler("/v1/grant-requests", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_detail_without_auth_returns_401(self):
        handler = self._make_handler(f"/v1/grant-requests/{self.request.id}", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    # ──────────────────────────────────────────────
    # Valid roles
    # ──────────────────────────────────────────────
    def test_list_owner_succeeds(self):
        handler = self._make_handler("/v1/grant-requests", auth_header="Bearer owner-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body.get("items"), list)

    def test_list_grant_admin_succeeds(self):
        handler = self._make_handler("/v1/grant-requests", auth_header="Bearer admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body.get("items"), list)

    def test_list_auditor_succeeds(self):
        handler = self._make_handler("/v1/grant-requests", auth_header="Bearer auditor-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body.get("items"), list)

    def test_detail_owner_succeeds(self):
        handler = self._make_handler(f"/v1/grant-requests/{self.request.id}", auth_header="Bearer owner-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), self.request.id)

    def test_detail_grant_admin_succeeds(self):
        handler = self._make_handler(f"/v1/grant-requests/{self.request.id}", auth_header="Bearer admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), self.request.id)

    def test_detail_auditor_succeeds(self):
        handler = self._make_handler(f"/v1/grant-requests/{self.request.id}", auth_header="Bearer auditor-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), self.request.id)

    # ──────────────────────────────────────────────
    # demo_operator forbidden
    # ──────────────────────────────────────────────
    def test_list_demo_operator_forbidden(self):
        handler = self._make_handler("/v1/grant-requests", auth_header="Bearer demo-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    def test_detail_demo_operator_forbidden(self):
        handler = self._make_handler(f"/v1/grant-requests/{self.request.id}", auth_header="Bearer demo-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    # ──────────────────────────────────────────────
    # Error hygiene
    # ──────────────────────────────────────────────
    def test_error_list_does_not_expose_token(self):
        handler = self._make_handler("/v1/grant-requests", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        body_str = json.dumps(body)
        self.assertNotIn("owner-token", body_str)
        self.assertNotIn("admin-token", body_str)
        self.assertNotIn("Bearer", body_str)

    def test_error_detail_does_not_expose_token(self):
        handler = self._make_handler(f"/v1/grant-requests/{self.request.id}", auth_header="Bearer demo-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        body_str = json.dumps(body)
        self.assertNotIn("demo-token", body_str)
        self.assertNotIn("Bearer", body_str)

    # ──────────────────────────────────────────────
    # Endpoint paths unchanged
    # ──────────────────────────────────────────────
    def test_list_endpoint_path_unchanged(self):
        handler = self._make_handler("/v1/grant-requests", auth_header="Bearer owner-token")
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)

    def test_detail_endpoint_path_unchanged(self):
        handler = self._make_handler(f"/v1/grant-requests/{self.request.id}", auth_header="Bearer owner-token")
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)


class TestGl046LegacyMode(_BaseGl046):
    """Legacy-mode auth tests for GET /grant-requests and /grant-requests/{id}."""

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

        self.request = self._create_request()

    def test_list_without_auth_returns_401(self):
        handler = self._make_handler("/v1/grant-requests", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)

    def test_detail_without_auth_returns_401(self):
        handler = self._make_handler(f"/v1/grant-requests/{self.request.id}", auth_header=None)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)

    def test_list_with_valid_admin_token_succeeds(self):
        handler = self._make_handler("/v1/grant-requests", auth_header="Bearer legacy-admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body.get("items"), list)

    def test_detail_with_valid_admin_token_succeeds(self):
        handler = self._make_handler(f"/v1/grant-requests/{self.request.id}", auth_header="Bearer legacy-admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), self.request.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
