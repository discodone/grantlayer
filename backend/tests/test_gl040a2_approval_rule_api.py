"""GL-040-A2 - Approval Rule Evaluation API Endpoint tests.

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


class TestApprovalRuleEvaluationAPI(unittest.TestCase):
    """Tests for POST /approvals/evaluate endpoint."""

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
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
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
        elif body is not None:
            resp = client.post(path, json=body, headers=headers)
        else:
            resp = client.post(path, headers=headers)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, None

    # Endpoint routing
    def test_endpoint_exists_and_returns_400_for_missing_fields(self):
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer test-admin-token",
            body={"actorId": "admin-1"},
        )
        self.assertEqual(status, 400)
        error_msg = body.get("error") or body.get("detail", {}).get("error", "")
        self.assertIn("Missing fields", error_msg)

    def test_endpoint_returns_200_for_valid_request(self):
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer test-admin-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["decision"], "no_approval_required")
        self.assertEqual(body["action"], "create-grant")
        self.assertEqual(body["actorId"], "admin-1")

    # Auth
    def test_endpoint_requires_admin_token_when_operator_disabled(self):
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
            },
        )
        self.assertEqual(status, 401)
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer wrong-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
            },
        )
        self.assertEqual(status, 403)

    def test_endpoint_accepts_owner_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("owner-1", "Owner One", "owner", "owner-token")

        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer owner-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["decision"], "no_approval_required")

    def test_endpoint_accepts_grant_admin_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("admin-1", "Admin One", "grant_admin", "admin-token")

        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer admin-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["decision"], "no_approval_required")

    def test_endpoint_rejects_auditor_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")

        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer auditor-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
            },
        )
        self.assertEqual(status, 403)

    def test_endpoint_rejects_demo_operator_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("demo-op-1", "Demo Op", "demo_operator", "demo-token")

        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer demo-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
            },
        )
        self.assertEqual(status, 403)

    # Response shape
    def test_response_contains_expected_keys(self):
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer test-admin-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
            },
        )
        self.assertEqual(status, 200)
        expected_keys = {
            "action",
            "actorId",
            "approvalRequired",
            "requiredApprovals",
            "requiredRoles",
            "decision",
            "reason",
            "blockers",
            "warnings",
            "riskLevel",
            "amount",
            "currency",
        }
        self.assertTrue(expected_keys.issubset(set(body.keys())))

    # Evaluation logic
    def test_endpoint_returns_blocked_for_missing_permission(self):
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer test-admin-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
                "permissionResult": {"allowed": False},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["decision"], "blocked")
        self.assertIn("permission_denied", body["blockers"])

    def test_endpoint_returns_four_eyes_for_high_risk(self):
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer test-admin-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "high",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["decision"], "four_eyes_required")
        self.assertEqual(body["requiredApprovals"], 2)

    def test_endpoint_passes_optional_fields(self):
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer test-admin-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "amount": 50000,
                "currency": "EUR",
                "riskLevel": "low",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
                "policyFlags": ["requires_approval"],
                "context": {"source": "test"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["amount"], 50000.0)
        self.assertEqual(body["currency"], "EUR")

    # Secrets safety
    def test_response_does_not_expose_secrets(self):
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer test-admin-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
                "context": {"api_key": "secret-key-123", "password": "hunter2"},
            },
        )
        self.assertEqual(status, 200)
        result_str = str(body)
        self.assertNotIn("secret-key-123", result_str)
        self.assertNotIn("hunter2", result_str)
        self.assertNotIn("api_key", result_str)
        self.assertNotIn("password", result_str)

    def test_include_details_false_omits_checks_and_inputs(self):
        status, body = self._run_handler(
            "/v1/approvals/evaluate",
            auth="Bearer test-admin-token",
            body={
                "action": "create-grant",
                "actorId": "admin-1",
                "riskLevel": "low",
                "permissionResult": {"allowed": True},
                "complianceReport": {"overallStatus": "clean", "severity": "low"},
                "evidenceCompleteness": {"complete": True},
                "includeDetails": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("checks", body)
        self.assertNotIn("inputs", body)
        self.assertIn("decision", body)
