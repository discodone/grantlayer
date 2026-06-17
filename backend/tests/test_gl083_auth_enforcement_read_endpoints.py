"""Tests for GL-083 Auth Enforcement for Read Endpoints.

Ensures sensitive read endpoints require authentication/authorization using
existing GrantLayer auth patterns. Public endpoints (/health, /readiness)
remain accessible without auth.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

try:
    import backend.src.core.db as _db
    import backend.src.core.config as _cfg
    import backend.src.auth.operators as _ops
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    _SKIP = lambda cls: cls  # noqa: E731
except ImportError:
    _SKIP = unittest.skip("FastAPI/backend not available")


class _BaseGl083(unittest.TestCase):
    """Shared helpers for GL-083 tests (FastAPI TestClient)."""

    _operator_model: bool = True
    _admin_token: str = ""
    _require_admin: bool = False

    def setUp(self):
        self._orig_enable_operator = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_admin_token_cfg = _cfg.GRANTLAYER_ADMIN_TOKEN
        self._orig_require_admin_cfg = _cfg.REQUIRE_ADMIN_TOKEN
        self._orig_allow_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db_path = _db.DB_PATH_OR_URL
        self._orig_env = {k: os.environ.get(k) for k in (
            "GRANTLAYER_JWT_SECRET",
            "GRANTLAYER_ENABLE_OPERATOR_MODEL",
            "GRANTLAYER_ADMIN_TOKEN",
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
            "GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE",
        )}

        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True

        _cfg.ENABLE_OPERATOR_MODEL = self._operator_model
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true" if self._operator_model else "false"

        _cfg.GRANTLAYER_ADMIN_TOKEN = self._admin_token
        _cfg.REQUIRE_ADMIN_TOKEN = self._require_admin
        if self._admin_token:
            os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._admin_token
        else:
            os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        if self._require_admin:
            os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        else:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_enable_operator
        _cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin_token_cfg
        _cfg.REQUIRE_ADMIN_TOKEN = self._orig_require_admin_cfg
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_allow_plaintext
        _db.DB_PATH_OR_URL = self._orig_db_path
        _db.DB_PATH = self._orig_db_path
        for k, v in self._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def _insert_operator(self, op_id, name, role, token):
        conn = _db.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, token_lookup_hash, active, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
                (op_id, name, role, _ops.hash_token(token), _ops.derive_token_lookup_hash(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _auth(self, token):
        return {"Authorization": f"Bearer {token}"}

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


@_SKIP
class TestGl083OperatorMode(_BaseGl083):
    """Operator-model auth tests for sensitive read endpoints."""

    _operator_model = True

    def setUp(self):
        super().setUp()
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("admin-1", "Grant Admin", "grant_admin", "admin-token")
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        self._insert_operator("demo-1", "Demo", "demo_operator", "demo-token")
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def test_health_public(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "ok")

    def test_readiness_public(self):
        resp = self.client.get("/readiness")
        self.assertIn(resp.status_code, (200, 503))
        self.assertIn(resp.json().get("status"), ("ready", "not_ready"))

    def test_grants_without_auth_returns_401(self):
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_grant_detail_without_auth_returns_401(self):
        resp = self.client.get("/v1/grants/nonexistent-id")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_audit_events_without_auth_returns_401(self):
        resp = self.client.get("/v1/audit-events")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_challenges_without_auth_returns_401(self):
        resp = self.client.get("/v1/challenges")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_grant_executions_without_auth_returns_401(self):
        resp = self.client.get("/v1/grant-executions")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_grant_executions_for_grant_without_auth_returns_401(self):
        resp = self.client.get("/v1/grants/nonexistent-id/executions")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_evidence_without_auth_returns_401(self):
        resp = self.client.get("/v1/evidence/executions/nonexistent-id")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_grants_owner_succeeds(self):
        resp = self.client.get("/v1/grants", headers=self._auth("owner-token"))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json().get("items"), list)

    def test_grants_grant_admin_succeeds(self):
        resp = self.client.get("/v1/grants", headers=self._auth("admin-token"))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json().get("items"), list)

    def test_grants_auditor_succeeds(self):
        resp = self.client.get("/v1/grants", headers=self._auth("auditor-token"))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json().get("items"), list)

    def test_grants_demo_operator_forbidden(self):
        resp = self.client.get("/v1/grants", headers=self._auth("demo-token"))
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    def test_grant_detail_demo_operator_forbidden(self):
        resp = self.client.get("/v1/grants/nonexistent-id", headers=self._auth("demo-token"))
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    def test_audit_events_demo_operator_forbidden(self):
        resp = self.client.get("/v1/audit-events", headers=self._auth("demo-token"))
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")

    def test_error_responses_safe_json(self):
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self._assert_no_secrets_in_body(body)
        body_str = json.dumps(body)
        self.assertNotIn("owner-token", body_str)
        self.assertNotIn("admin-token", body_str)
        self.assertNotIn("auditor-token", body_str)
        self.assertNotIn("demo-token", body_str)
        self.assertNotIn("Bearer", body_str)

    def test_error_responses_no_stacktrace(self):
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 401)
        body_str = json.dumps(resp.json())
        self.assertNotIn("traceback", body_str.lower())
        self.assertNotIn("exception", body_str.lower())

    def test_authorized_grant_detail_returns_404_for_missing(self):
        resp = self.client.get("/v1/grants/nonexistent-id", headers=self._auth("owner-token"))
        self.assertEqual(resp.status_code, 404)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "grant_not_found")


@_SKIP
class TestGl083LegacyMode(_BaseGl083):
    """Legacy-mode auth tests for sensitive read endpoints."""

    _operator_model = False
    _admin_token = "legacy-admin-token"
    _require_admin = True

    def test_health_public(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "ok")

    def test_readiness_public(self):
        resp = self.client.get("/readiness")
        self.assertIn(resp.status_code, (200, 503))

    def test_grants_without_auth_returns_401(self):
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_grant_detail_without_auth_returns_401(self):
        resp = self.client.get("/v1/grants/nonexistent-id")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_audit_events_without_auth_returns_401(self):
        resp = self.client.get("/v1/audit-events")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_challenges_without_auth_returns_401(self):
        resp = self.client.get("/v1/challenges")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_grants_with_valid_admin_token_succeeds(self):
        resp = self.client.get("/v1/grants", headers=self._auth("legacy-admin-token"))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json().get("items"), list)

    def test_grant_detail_with_valid_admin_token_succeeds(self):
        resp = self.client.get("/v1/grants/nonexistent-id", headers=self._auth("legacy-admin-token"))
        self.assertEqual(resp.status_code, 404)
        self._assert_gl030_full(resp.json())

    def test_evidence_without_auth_returns_401(self):
        resp = self.client.get("/v1/evidence/executions/nonexistent-id")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_error_responses_safe_json(self):
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self._assert_gl030_full(body)
        self._assert_no_secrets_in_body(body)
        body_str = json.dumps(body)
        self.assertNotIn("legacy-admin-token", body_str)
        self.assertNotIn("Bearer", body_str)


class TestGl083OpenAPIContract(_BaseGl083):
    """Verify OpenAPI contract includes security and 401/403 for affected endpoints."""

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

    def test_openapi_grants_has_security(self):
        text = self._openapi_text()
        section = self._section_between(text, "/v1/grants:", "/v1/grants/{id}:")
        self.assertIn("security:", section)
        self.assertIn("LegacyAdminToken", section)
        self.assertIn("OperatorToken", section)

    def test_openapi_grants_has_401_403(self):
        text = self._openapi_text()
        section = self._section_between(text, "/v1/grants:", "/v1/grants/{id}:")
        self.assertIn('"401"', section)
        self.assertIn('"403"', section)

    def test_openapi_grant_detail_has_security(self):
        text = self._openapi_text()
        section = self._section_between(text, "/v1/grants/{id}:", "/v1/grants/{id}/revoke:")
        self.assertIn("security:", section)
        self.assertIn("LegacyAdminToken", section)
        self.assertIn("OperatorToken", section)

    def test_openapi_grant_detail_has_401_403(self):
        text = self._openapi_text()
        section = self._section_between(text, "/v1/grants/{id}:", "/v1/grants/{id}/revoke:")
        self.assertIn('"401"', section)
        self.assertIn('"403"', section)

    def test_openapi_audit_events_has_security(self):
        text = self._openapi_text()
        section = self._section_between(text, "/v1/audit-events:", "/v1/evidence/")
        self.assertIn("security:", section)
        self.assertIn("LegacyAdminToken", section)
        self.assertIn("OperatorToken", section)

    def test_openapi_audit_events_has_401_403(self):
        text = self._openapi_text()
        section = self._section_between(text, "/v1/audit-events:", "/v1/evidence/")
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

    def test_openapi_grant_requests_has_security(self):
        text = self._openapi_text()
        section = self._section_between(text, "/v1/grant-requests:", "/v1/grant-requests/{id}:")
        self.assertIn("security:", section)
        self.assertIn("OperatorToken", section)

    def test_openapi_grant_executions_has_security(self):
        text = self._openapi_text()
        section = self._section_between(text, "/v1/grant-executions:", "/v1/grant-executions/{id}:")
        self.assertIn("security:", section)
        self.assertIn("OperatorToken", section)

    def test_openapi_no_longer_claims_grant_reads_are_unauthenticated(self):
        text = self._openapi_text()
        info_section = text[text.find("info:"):text.find("paths:")]
        self.assertNotIn("GET /grants", info_section)
        self.assertNotIn("GET /grants/{id}", info_section)
        self.assertNotIn("GET /audit-events", info_section)


class TestGl083NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-083 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-083-auth-enforcement-read-endpoints":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-083 feature branch"
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
            "backend/tests/test_gl083_auth_enforcement_read_endpoints.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-083 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
