"""GL-043-B — Policy Requirement / Grant Rule Pack API Endpoint tests.

Covers endpoint:
- POST /policy-requirements/evaluate
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPolicyRequirementsAPI(unittest.TestCase):
    """Tests for POST /policy-requirements/evaluate endpoint."""

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

    # /policy-requirements/evaluate endpoint tests

    def test_evaluate_endpoint_exists_and_returns_200_for_valid_request(self):
        """POST /policy-requirements/evaluate returns 200 for valid request."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "grant-policy-2026",
                    "policyPackVersion": "v1",
                    "name": "Example Grant Policy",
                    "requiredEvidence": [
                        {"type": "budget_plan", "required": True},
                        {"type": "eligibility_statement", "required": True},
                    ],
                    "exclusions": [
                        {"code": "sanctioned_entity", "severity": "blocking"},
                    ],
                    "deadlines": [
                        {"name": "submission_deadline", "dueAt": "2099-12-31T23:59:59Z", "required": True}
                    ],
                    "amountLimits": {"maxAmount": 50000, "currency": "EUR"},
                    "requiredRoles": ["grant_admin"],
                    "approvalPolicy": {"minimumApprovals": 1, "fourEyesAboveAmount": 50000},
                },
                "subject": {
                    "subjectId": "grant-request-123",
                    "amount": 25000,
                    "currency": "EUR",
                    "evidenceTypes": ["budget_plan", "eligibility_statement"],
                    "exclusionCodes": [],
                },
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"decision": "approved"},
                "approvalLifecycle": {"status": "approved"},
                "decisionProvenance": {"decisionStatus": "approved"},
                "auditorExport": {"exportStatus": "ready"},
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp["recordType"], "policy_requirement_evaluation")
        self.assertEqual(resp["recordVersion"], "gl-policy-requirements-v1")
        self.assertEqual(resp["policyPackId"], "grant-policy-2026")
        self.assertEqual(resp["policyPackVersion"], "v1")
        self.assertEqual(resp["evaluationStatus"], "passed")
        self.assertEqual(resp["readiness"], "ready")
        self.assertEqual(resp["missingEvidence"], [])
        self.assertEqual(resp["exclusionViolations"], [])
        self.assertEqual(resp["deadlineStatus"], "on_time")
        self.assertEqual(resp["amountStatus"], "within_limit")
        self.assertIn("policyPack", resp)
        self.assertIn("subject", resp)
        self.assertIn("evidenceCompleteness", resp)
        self.assertIn("complianceGapReport", resp)
        self.assertIn("permissionResult", resp)
        self.assertIn("approvalRequirement", resp)
        self.assertIn("approvalLifecycle", resp)
        self.assertIn("decisionProvenance", resp)
        self.assertIn("auditorExport", resp)

    def test_evaluate_endpoint_missing_auth_returns_401(self):
        """POST /policy-requirements/evaluate without auth returns 401."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            body={},
        )
        self.assertEqual(status, 401)

    def test_evaluate_endpoint_returns_400_for_invalid_json(self):
        """POST /policy-requirements/evaluate with invalid JSON returns 400."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body=b"invalid json",
        )
        self.assertIn(status, [400, 422])

    def test_evaluate_endpoint_accepts_grant_admin_role_in_operator_mode(self):
        """POST /policy-requirements/evaluate accepts grant_admin role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Admin", "grant_admin", "op-token-1")

        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer op-token-1",
            body={"policyPack": {"policyPackId": "pp-1"}},
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_evaluate_endpoint_accepts_owner_role_in_operator_mode(self):
        """POST /policy-requirements/evaluate accepts owner role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Owner", "owner", "op-token-1")

        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer op-token-1",
            body={"policyPack": {"policyPackId": "pp-1"}},
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_evaluate_endpoint_accepts_auditor_role_in_operator_mode(self):
        """POST /policy-requirements/evaluate accepts auditor role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Auditor", "auditor", "op-token-1")

        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer op-token-1",
            body={"policyPack": {"policyPackId": "pp-1"}},
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_evaluate_endpoint_rejects_demo_operator_role_in_operator_mode(self):
        """POST /policy-requirements/evaluate rejects demo_operator role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Demo", "demo_operator", "op-token-1")

        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer op-token-1",
            body={},
        )
        self.assertEqual(status, 403)

    def test_evaluate_endpoint_requires_admin_token_when_operator_disabled(self):
        """POST /policy-requirements/evaluate requires admin token when operator model disabled."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"

        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            body={},
        )
        self.assertEqual(status, 401)

        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer wrong-token",
            body={},
        )
        self.assertEqual(status, 403)

    def test_evaluate_endpoint_missing_policy_pack_returns_blocked(self):
        """POST /policy-requirements/evaluate returns blocked when policy pack missing."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={"subject": {"subjectId": "sub-1"}},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertEqual(resp["readiness"], "blocked")
        self.assertIn("policy_pack_missing", resp["blockers"])
        self.assertIn("policy_pack", resp["missingInputs"])

    def test_evaluate_endpoint_malformed_policy_pack_returns_blocked(self):
        """POST /policy-requirements/evaluate returns blocked when policy pack malformed."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={"policyPack": "not-a-dict"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertIn("policy_pack_malformed", resp["blockers"])

    def test_evaluate_endpoint_empty_body_returns_valid_evaluation(self):
        """POST /policy-requirements/evaluate with empty body returns valid evaluation."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["recordType"], "policy_requirement_evaluation")
        self.assertEqual(resp["recordVersion"], "gl-policy-requirements-v1")
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertEqual(resp["readiness"], "blocked")
        self.assertIn("policy_pack_missing", resp["blockers"])

    def test_evaluate_endpoint_missing_subject_recorded(self):
        """POST /policy-requirements/evaluate records missing subject."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {"policyPackId": "pp-1"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("subject", resp["missingInputs"])

    def test_evaluate_endpoint_omits_details_when_include_details_false(self):
        """POST /policy-requirements/evaluate omits details when includeDetails=False."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [],
                    "deadlines": [],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
                "includeDetails": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("policyPack", resp)
        self.assertNotIn("subject", resp)
        self.assertNotIn("evidenceCompleteness", resp)
        self.assertNotIn("complianceGapReport", resp)
        self.assertNotIn("permissionResult", resp)
        self.assertNotIn("approvalRequirement", resp)
        self.assertNotIn("approvalLifecycle", resp)
        self.assertNotIn("decisionProvenance", resp)
        self.assertNotIn("auditorExport", resp)
        self.assertNotIn("context", resp)
        self.assertIn("recordType", resp)
        self.assertIn("evaluationStatus", resp)
        self.assertIn("blockers", resp)
        self.assertIn("warnings", resp)

    def test_evaluate_endpoint_includes_details_when_include_details_true(self):
        """POST /policy-requirements/evaluate includes details when includeDetails=True."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [],
                    "deadlines": [],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"decision": "approved"},
                "approvalLifecycle": {"status": "approved"},
                "decisionProvenance": {"decisionStatus": "approved"},
                "auditorExport": {"exportStatus": "ready"},
                "context": {"env": "testing"},
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("policyPack", resp)
        self.assertIn("subject", resp)
        self.assertIn("evidenceCompleteness", resp)
        self.assertIn("complianceGapReport", resp)
        self.assertIn("permissionResult", resp)
        self.assertIn("approvalRequirement", resp)
        self.assertIn("approvalLifecycle", resp)
        self.assertIn("decisionProvenance", resp)
        self.assertIn("auditorExport", resp)
        self.assertIn("context", resp)

    def test_evaluate_endpoint_no_secrets_at_top_level(self):
        """POST /policy-requirements/evaluate does not expose secrets at top level."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {"policyPackId": "pp-1"},
                "context": {"api_key": "secret123", "password": "hunter2", "token": "bearer-token"},
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        resp_str = json.dumps(resp)
        self.assertNotIn("secret123", resp_str)
        self.assertNotIn("hunter2", resp_str)
        self.assertNotIn("bearer-token", resp_str)
        self.assertIn("[REDACTED]", resp_str)

    def test_evaluate_endpoint_returns_blocked_for_denied_permission(self):
        """POST /policy-requirements/evaluate returns blocked when permission denied."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [],
                    "deadlines": [],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": False},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertIn("permission_denied", resp["blockers"])

    def test_evaluate_endpoint_returns_blocked_for_compliance_critical(self):
        """POST /policy-requirements/evaluate returns blocked for critical compliance gaps."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [],
                    "deadlines": [],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {
                    "overallStatus": "blocked",
                    "severity": "critical",
                    "blockingGaps": [{"gapId": "g1", "severity": "critical"}],
                },
                "permissionResult": {"allowed": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertTrue(any("compliance" in b for b in resp["blockers"]))

    def test_evaluate_endpoint_returns_blocked_for_approval_lifecycle_blocked(self):
        """POST /policy-requirements/evaluate returns blocked when approval lifecycle blocked."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [],
                    "deadlines": [],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"decision": "approved"},
                "approvalLifecycle": {"status": "blocked"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertIn("approval_lifecycle_blocked", resp["blockers"])

    def test_evaluate_endpoint_returns_blocked_for_decision_provenance_blocked(self):
        """POST /policy-requirements/evaluate returns blocked when decision provenance blocked."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [],
                    "deadlines": [],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"decision": "approved"},
                "approvalLifecycle": {"status": "approved"},
                "decisionProvenance": {"decisionStatus": "blocked"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertIn("decision_provenance_blocked", resp["blockers"])

    def test_evaluate_endpoint_returns_blocked_for_auditor_export_blocked(self):
        """POST /policy-requirements/evaluate returns blocked when auditor export blocked."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [],
                    "deadlines": [],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"decision": "approved"},
                "approvalLifecycle": {"status": "approved"},
                "decisionProvenance": {"decisionStatus": "approved"},
                "auditorExport": {"exportStatus": "blocked"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertIn("auditor_export_blocked", resp["blockers"])

    def test_evaluate_endpoint_returns_blocked_for_exclusion(self):
        """POST /policy-requirements/evaluate returns blocked for blocking exclusion."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [{"code": "sanctioned_entity", "severity": "blocking"}],
                    "deadlines": [],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1", "exclusionCodes": ["sanctioned_entity"]},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertIn("sanctioned_entity", resp["exclusionViolations"])
        self.assertTrue(any("exclusion:sanctioned_entity" in b for b in resp["blockers"]))

    def test_evaluate_endpoint_returns_404_for_get(self):
        """GET /policy-requirements/evaluate returns 404 or 405 (POST only)."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            method="GET",
            auth="Bearer test-admin-token",
        )
        self.assertIn(status, [404, 405])

    def test_evaluate_endpoint_handles_all_optional_fields(self):
        """POST /policy-requirements/evaluate handles all optional fields."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-full",
                    "policyPackVersion": "v2",
                    "name": "Full Policy",
                    "requiredEvidence": [
                        {"type": "budget_plan", "required": True},
                    ],
                    "exclusions": [],
                    "deadlines": [
                        {"name": "submission", "dueAt": "2099-12-31T23:59:59Z", "required": True}
                    ],
                    "amountLimits": {"maxAmount": 100000, "currency": "USD"},
                    "requiredRoles": ["owner"],
                    "approvalPolicy": {"minimumApprovals": 2, "fourEyesAboveAmount": 50000},
                },
                "subject": {
                    "subjectId": "sub-full",
                    "amount": 25000,
                    "currency": "USD",
                    "evidenceTypes": ["budget_plan"],
                    "exclusionCodes": [],
                },
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"decision": "approved"},
                "approvalLifecycle": {"status": "approved"},
                "decisionProvenance": {"decisionStatus": "approved"},
                "auditorExport": {"exportStatus": "ready"},
                "context": {"env": "test"},
                "createdAt": "2026-01-01T00:00:00Z",
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["policyPackId"], "pp-full")
        self.assertEqual(resp["policyPackVersion"], "v2")
        self.assertEqual(resp["subjectId"], "sub-full")
        self.assertEqual(resp["createdAt"], "2026-01-01T00:00:00Z")
        self.assertEqual(resp["evaluationStatus"], "passed")
        self.assertEqual(resp["readiness"], "ready")

    def test_evaluate_endpoint_returns_needs_review_for_warnings(self):
        """POST /policy-requirements/evaluate returns needs_review when only warnings."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [
                        {"type": "optional_statement", "required": False},
                    ],
                    "exclusions": [],
                    "deadlines": [],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1", "evidenceTypes": []},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "needs_review")
        self.assertTrue(any("missing_optional_evidence" in w for w in resp["warnings"]))

    def test_evaluate_endpoint_returns_blocked_for_amount_above_max(self):
        """POST /policy-requirements/evaluate returns blocked when amount above max."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [],
                    "deadlines": [],
                    "amountLimits": {"maxAmount": 10000, "currency": "EUR"},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1", "amount": 20000, "currency": "EUR"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertIn("amount_above_max", resp["blockers"])
        self.assertEqual(resp["amountStatus"], "above_limit")

    def test_evaluate_endpoint_returns_blocked_for_expired_deadline(self):
        """POST /policy-requirements/evaluate returns blocked for expired required deadline."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {
                    "policyPackId": "pp-1",
                    "name": "Test Policy",
                    "requiredEvidence": [],
                    "exclusions": [],
                    "deadlines": [
                        {"name": "submission_deadline", "dueAt": "2020-01-01T00:00:00Z", "required": True}
                    ],
                    "amountLimits": {},
                    "requiredRoles": [],
                    "approvalPolicy": {},
                },
                "subject": {"subjectId": "sub-1"},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "clear", "severity": "low"},
                "permissionResult": {"allowed": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["evaluationStatus"], "blocked")
        self.assertTrue(any("deadline_expired" in b for b in resp["blockers"]))
        self.assertEqual(resp["deadlineStatus"], "expired")

    def test_evaluate_endpoint_field_preservation(self):
        """POST /policy-requirements/evaluate preserves policy pack id, version and subject id."""
        status, resp = self._run_handler(
            "/policy-requirements/evaluate",
            auth="Bearer test-admin-token",
            body={
                "policyPack": {"policyPackId": "pp-123", "policyPackVersion": "v3"},
                "subject": {"subjectId": "sub-456"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["policyPackId"], "pp-123")
        self.assertEqual(resp["policyPackVersion"], "v3")
        self.assertEqual(resp["subjectId"], "sub-456")


if __name__ == "__main__":
    unittest.main(verbosity=2)
