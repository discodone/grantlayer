"""GL-041-B — Decision Provenance v2 API Endpoint tests.

Covers endpoint:
- POST /decision-provenance/v2/build
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDecisionProvenanceV2API(unittest.TestCase):
    """Tests for decision provenance v2 API endpoint."""

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

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

        from backend.src.auth import operators as ops
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
        import backend.src.core.db as db_mod
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

    def _run_handler(self, path, method="POST", auth=None, body=None):
        headers = {}
        if auth:
            headers["Authorization"] = auth
        client = self._make_client()
        if method == "GET":
            resp = client.get(path, headers=headers)
        elif isinstance(body, (bytes, bytearray)):
            resp = client.post(path, content=body, headers=headers)
        elif body is not None:
            resp = client.post(path, json=body, headers=headers)
        else:
            resp = client.post(path, headers=headers)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, None

    # /decision-provenance/v2/build endpoint tests

    def test_build_endpoint_exists_and_returns_200_for_valid_request(self):
        """POST /decision-provenance/v2/build returns 200 for valid request."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decisionId": "dec-123",
                "decisionType": "grant_request",
                "subjectId": "sub-1",
                "actorId": "agent-1",
                "action": "read",
                "decision": "approved",
                "reason": "All checks passed",
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False},
                "approvalLifecycle": {"status": "approved"},
                "provenanceSummary": {"events": [{"id": "evt-1"}]},
                "auditorReport": {"auditReady": True},
                "policyResults": [{"passed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp["recordType"], "decision_provenance")
        self.assertEqual(resp["recordVersion"], "gl-decision-provenance-v2")
        self.assertEqual(resp["decisionId"], "dec-123")
        self.assertEqual(resp["decision"], "approved")
        self.assertEqual(resp["decisionStatus"], "approved")
        self.assertEqual(resp["signals"]["evidence"], "complete")
        self.assertEqual(resp["signals"]["compliance"], "complete")
        self.assertEqual(resp["signals"]["permission"], "allowed")
        self.assertEqual(resp["signals"]["approval"], "approved")
        self.assertEqual(resp["signals"]["provenance"], "present")
        self.assertEqual(resp["signals"]["auditor"], "ready")
        self.assertEqual(resp["signals"]["policy"], "passed")
        self.assertEqual(resp["readiness"]["evidence"], "ready")
        self.assertEqual(resp["readiness"]["compliance"], "ready")
        self.assertEqual(resp["readiness"]["permission"], "ready")
        self.assertEqual(resp["readiness"]["approval"], "ready")
        self.assertEqual(resp["readiness"]["provenance"], "ready")
        self.assertEqual(resp["readiness"]["policy"], "ready")
        self.assertEqual(resp["blockers"], [])
        self.assertEqual(resp["warnings"], [])
        self.assertEqual(resp["missingInputs"], [])

    def test_build_endpoint_missing_auth_returns_401(self):
        """POST /decision-provenance/v2/build without auth returns 401."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            body={},
        )
        self.assertEqual(status, 401)

    def test_build_endpoint_returns_400_for_invalid_json(self):
        """POST /decision-provenance/v2/build with invalid JSON returns 400."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body=b"invalid json",
        )
        self.assertIn(status, [400, 422])

    def test_build_endpoint_accepts_grant_admin_role_in_operator_mode(self):
        """POST /decision-provenance/v2/build accepts grant_admin role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Admin", "grant_admin", "op-token-1")

        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer op-token-1",
            body={
                "decisionId": "dec-123",
                "decision": "approved",
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_build_endpoint_accepts_owner_role_in_operator_mode(self):
        """POST /decision-provenance/v2/build accepts owner role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Owner", "owner", "op-token-1")

        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer op-token-1",
            body={
                "decisionId": "dec-123",
                "decision": "approved",
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_build_endpoint_accepts_auditor_role_in_operator_mode(self):
        """POST /decision-provenance/v2/build accepts auditor role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Auditor", "auditor", "op-token-1")

        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer op-token-1",
            body={
                "decisionId": "dec-123",
                "decision": "approved",
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_build_endpoint_rejects_demo_operator_role_in_operator_mode(self):
        """POST /decision-provenance/v2/build rejects demo_operator role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Demo", "demo_operator", "op-token-1")

        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer op-token-1",
            body={},
        )
        self.assertEqual(status, 403)

    def test_build_endpoint_requires_admin_token_when_operator_disabled(self):
        """POST /decision-provenance/v2/build requires admin token when operator model disabled."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"

        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            body={},
        )
        self.assertEqual(status, 401)

        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer wrong-token",
            body={},
        )
        self.assertEqual(status, 403)

    def test_build_endpoint_returns_blocked_for_denied_permission(self):
        """POST /decision-provenance/v2/build returns blocked when permission is denied."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decisionId": "dec-perm-block",
                "decision": "approved",
                "permissionResult": {"allowed": False},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["decisionStatus"], "blocked")
        self.assertIn("permission_denied", resp["blockers"])
        self.assertEqual(resp["signals"]["permission"], "denied")

    def test_build_endpoint_returns_incomplete_for_missing_decision(self):
        """POST /decision-provenance/v2/build returns incomplete for missing decision."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decisionId": "dec-789",
                "decisionType": "unknown",
                "subjectId": "sub-3",
                "evidenceCompleteness": {"complete": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertIsNone(resp["decision"])
        self.assertEqual(resp["decisionStatus"], "incomplete")
        self.assertIn("decision", resp["missingInputs"])

    def test_build_endpoint_omits_details_when_include_details_false(self):
        """POST /decision-provenance/v2/build omits details when includeDetails=False."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decisionId": "test-details",
                "decision": "approved",
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False},
                "approvalLifecycle": {"status": "approved"},
                "provenanceSummary": {"events": [{"id": "evt-1"}]},
                "auditorReport": {"auditReady": True},
                "policyResults": [{"passed": True}],
                "inputs": {"param1": "value1"},
                "context": {"env": "test"},
                "includeDetails": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertIsNone(resp.get("evidence"))
        self.assertIsNone(resp.get("compliance"))
        self.assertIsNone(resp.get("permission"))
        self.assertIsNone(resp.get("approval"))
        self.assertIsNone(resp.get("provenance"))
        self.assertIsNone(resp.get("auditor"))
        self.assertIsNone(resp.get("policy"))
        self.assertIsNone(resp.get("inputs"))

    def test_build_endpoint_includes_details_when_include_details_true(self):
        """POST /decision-provenance/v2/build includes details when includeDetails=True."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decisionId": "test-details-true",
                "decision": "approved",
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False},
                "provenanceSummary": {"events": [{"id": "evt-1"}]},
                "auditorReport": {"auditReady": True},
                "policyResults": [{"passed": True}],
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIsNotNone(resp.get("evidence"))
        self.assertIsNotNone(resp.get("compliance"))
        self.assertIsNotNone(resp.get("permission"))
        self.assertIsNotNone(resp.get("provenance"))
        self.assertIsNotNone(resp.get("auditor"))
        self.assertIsNotNone(resp.get("policy"))

    def test_build_endpoint_redacts_secrets_in_inputs(self):
        """POST /decision-provenance/v2/build redacts secrets in inputs."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decision": "approved",
                "inputs": {
                    "token": "secret-token-123",
                    "password": "mypassword",
                    "apiKey": "key-456",
                    "safeParam": "normal_value",
                },
                "context": {
                    "authHeader": "Bearer secret-token",
                    "normalData": "safe_value",
                },
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        inputs_out = resp["inputs"]
        self.assertIsNotNone(inputs_out)
        self.assertEqual(inputs_out["token"], "[REDACTED]")
        self.assertEqual(inputs_out["password"], "[REDACTED]")
        self.assertEqual(inputs_out["apiKey"], "[REDACTED]")
        self.assertEqual(inputs_out["authHeader"], "[REDACTED]")
        self.assertEqual(inputs_out["safeParam"], "normal_value")
        self.assertEqual(inputs_out["normalData"], "safe_value")

    def test_build_endpoint_returns_404_for_get(self):
        """GET /decision-provenance/v2/build returns 404 or 405 (POST only)."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            method="GET",
            auth="Bearer test-admin-token",
        )
        self.assertIn(status, [404, 405])

    def test_build_endpoint_empty_body_returns_valid_provenance(self):
        """POST /decision-provenance/v2/build with empty body returns valid provenance."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["recordType"], "decision_provenance")
        self.assertEqual(resp["recordVersion"], "gl-decision-provenance-v2")
        self.assertIsNone(resp["decision"])
        self.assertEqual(resp["decisionStatus"], "incomplete")
        self.assertEqual(resp["signals"]["evidence"], "missing")
        self.assertEqual(resp["signals"]["compliance"], "missing")
        self.assertEqual(resp["signals"]["permission"], "missing")
        self.assertEqual(resp["signals"]["approval"], "missing")
        self.assertEqual(resp["signals"]["provenance"], "missing")
        self.assertEqual(resp["signals"]["auditor"], "missing")
        self.assertEqual(resp["signals"]["policy"], "missing")

    def test_build_endpoint_handles_all_optional_fields(self):
        """POST /decision-provenance/v2/build handles all optional fields."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decisionId": "dec-full",
                "decisionType": "grant_request",
                "subjectId": "sub-1",
                "actorId": "agent-1",
                "action": "read",
                "decision": "approved",
                "reason": "All checks passed",
                "evidenceCompleteness": {"complete": True, "missing": [], "present": ["evidence1"]},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True, "reason": "All permissions granted"},
                "approvalRequirement": {"required": False, "decision": "not_required"},
                "approvalLifecycle": {"status": "approved", "currentStep": 1, "totalSteps": 1},
                "provenanceSummary": {"events": [{"id": "evt-1", "type": "test"}], "decisionId": "dec-full"},
                "auditorReport": {"auditReady": True, "warnings": []},
                "policyResults": [{"passed": True, "name": "policy1"}],
                "createdAt": "2026-01-01T00:00:00Z",
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["decisionId"], "dec-full")
        self.assertEqual(resp["createdAt"], "2026-01-01T00:00:00Z")
        self.assertEqual(resp["signals"]["evidence"], "complete")
        self.assertEqual(resp["signals"]["compliance"], "complete")
        self.assertEqual(resp["signals"]["permission"], "allowed")
        self.assertEqual(resp["signals"]["approval"], "approved")
        self.assertEqual(resp["signals"]["provenance"], "present")
        self.assertEqual(resp["signals"]["auditor"], "ready")
        self.assertEqual(resp["signals"]["policy"], "passed")

    def test_build_endpoint_returns_warning_for_provenance_decision_id_mismatch(self):
        """POST /decision-provenance/v2/build returns warning when provenance decisionId mismatches."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decisionId": "dec-A",
                "provenanceSummary": {"decisionId": "dec-B"},
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("provenance_decision_id_mismatch", resp["warnings"])

    def test_build_endpoint_returns_blocked_for_policy_failed(self):
        """POST /decision-provenance/v2/build returns blocked when policy fails."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decision": "approved",
                "policyResults": [{"failed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("policy_failed", resp["blockers"])
        self.assertEqual(resp["signals"]["policy"], "failed")

    def test_build_endpoint_returns_warning_for_policy_partial(self):
        """POST /decision-provenance/v2/build returns warning for partial policy."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decision": "approved",
                "policyResults": [{"passed": False}, {"passed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["signals"]["policy"], "partial")
        self.assertIn("policy_partial", resp["warnings"])

    def test_build_endpoint_no_secrets_in_response(self):
        """POST /decision-provenance/v2/build does not expose secrets in response."""
        status, resp = self._run_handler(
            "/decision-provenance/v2/build",
            auth="Bearer test-admin-token",
            body={
                "decision": "approved",
                "inputs": {
                    "token": "secret-token",
                    "password": "secret-password",
                    "apiKey": "secret-key",
                    "safeField": "safe-value",
                },
                "context": {
                    "authHeader": "Bearer token123",
                    "normalField": "normal-value",
                },
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("inputs", resp)
        self.assertEqual(resp["inputs"]["token"], "[REDACTED]")
        self.assertEqual(resp["inputs"]["password"], "[REDACTED]")
        self.assertEqual(resp["inputs"]["apiKey"], "[REDACTED]")
        self.assertEqual(resp["inputs"]["authHeader"], "[REDACTED]")
        self.assertEqual(resp["inputs"]["safeField"], "safe-value")
        self.assertEqual(resp["inputs"]["normalField"], "normal-value")


if __name__ == "__main__":
    unittest.main(verbosity=2)
