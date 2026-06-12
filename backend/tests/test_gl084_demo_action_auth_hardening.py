"""Tests for GL-084 /demo-action Auth-Hardening.

Ensures POST /demo-action requires authentication and authorization,
using existing GrantLayer auth patterns. Public endpoints (/health,
/readiness) remain accessible without auth. GL-083 protections remain
intact.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl084(unittest.TestCase):
    """Shared helpers for GL-084 tests."""

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

        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

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


class TestGl084OperatorMode(_BaseGl084):
    """Operator-model auth tests for POST /demo-action."""

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

        self._create_matching_grant()

    def _demo_body(self):
        return json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()

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

    def test_demo_action_without_auth_returns_401(self):
        handler = self._make_handler("/demo-action", method="POST", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_demo_action_auditor_forbidden(self):
        handler = self._make_handler("/demo-action", method="POST", auth_header="Bearer auditor-token", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    def test_demo_action_demo_operator_forbidden(self):
        handler = self._make_handler("/demo-action", method="POST", auth_header="Bearer demo-token", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    def test_demo_action_owner_succeeds(self):
        handler = self._make_handler("/demo-action", method="POST", auth_header="Bearer owner-token", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIn("approved", body)
        self.assertTrue(body["approved"])
        self.assertIn("auditEventId", body)
        self.assertIn("executionId", body)
        self.assertIn("grantSignatureResult", body)
        self.assertIn("message", body)

    def test_demo_action_grant_admin_succeeds(self):
        handler = self._make_handler("/demo-action", method="POST", auth_header="Bearer admin-token", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIn("approved", body)
        self.assertTrue(body["approved"])
        self.assertIn("auditEventId", body)
        self.assertIn("executionId", body)
        self.assertIn("grantSignatureResult", body)
        self.assertIn("message", body)

    def test_demo_action_response_shape_compatible(self):
        handler = self._make_handler("/demo-action", method="POST", auth_header="Bearer owner-token", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body.get("approved"), bool)
        self.assertIsInstance(body.get("auditEventId"), str)
        self.assertIsInstance(body.get("executionId"), str)
        self.assertIsInstance(body.get("grantSignatureResult"), str)
        if body.get("approved"):
            self.assertIsInstance(body.get("message"), str)
        else:
            self.assertIsInstance(body.get("reason"), str)

    def test_demo_action_unauthorized_safe_json(self):
        handler = self._make_handler("/demo-action", method="POST", body=self._demo_body())
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

    def test_demo_action_unauthorized_no_stacktrace(self):
        handler = self._make_handler("/demo-action", method="POST", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        body_str = json.dumps(body)
        self.assertNotIn("traceback", body_str.lower())
        self.assertNotIn("exception", body_str.lower())

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


class TestGl084LegacyMode(_BaseGl084):
    """Legacy-mode auth tests for POST /demo-action."""

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

        self._create_matching_grant()

    def _demo_body(self):
        return json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()

    def test_health_public(self):
        handler = self._make_handler("/health")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_public(self):
        handler = self._make_handler("/readiness")
        status, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))

    def test_demo_action_without_auth_returns_401(self):
        handler = self._make_handler("/demo-action", method="POST", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_demo_action_with_valid_admin_token_succeeds(self):
        handler = self._make_handler("/demo-action", method="POST", auth_header="Bearer legacy-admin-token", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIn("approved", body)
        self.assertTrue(body["approved"])
        self.assertIn("auditEventId", body)
        self.assertIn("executionId", body)
        self.assertIn("grantSignatureResult", body)

    def test_demo_action_unauthorized_safe_json(self):
        handler = self._make_handler("/demo-action", method="POST", body=self._demo_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self._assert_no_secrets_in_body(body)
        body_str = json.dumps(body)
        self.assertNotIn("legacy-admin-token", body_str)
        self.assertNotIn("Bearer", body_str)

    def test_gl083_grants_still_require_auth(self):
        handler = self._make_handler("/grants", auth_header=None)
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


class TestGl084OpenAPIContract(_BaseGl084):
    """Verify OpenAPI contract includes security and 401/403 for POST /demo-action."""

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

    def test_openapi_demo_action_has_security(self):
        text = self._openapi_text()
        section = self._section_between(text, "/demo-action:", "/demo/tamper-grant/")
        self.assertIn("security:", section)
        self.assertIn("LegacyAdminToken", section)
        self.assertIn("OperatorToken", section)

    def test_openapi_demo_action_has_401_403(self):
        text = self._openapi_text()
        section = self._section_between(text, "/demo-action:", "/demo/tamper-grant/")
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


class TestGl084NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-084 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-084-demo-action-auth-hardening":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-084 feature branch"
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
            "backend/tests/test_gl084_demo_action_auth_hardening.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-084 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
