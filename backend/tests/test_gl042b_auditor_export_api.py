"""GL-042-B — Institutional Auditor Export API Endpoint tests.

Covers endpoint:
- POST /auditor/exports/build
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAuditorExportAPI(unittest.TestCase):
    """Tests for auditor export API endpoint."""

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
        import json

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
                inner_self._json = None

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

        req = DummyRequest()
        if body is not None:
            if isinstance(body, dict):
                req.rfile = BytesIO(json.dumps(body).encode("utf-8"))
                req.headers["Content-Length"] = str(len(json.dumps(body).encode("utf-8")))
            else:
                req.rfile = BytesIO(body if isinstance(body, bytes) else body.encode())
                req.headers["Content-Length"] = str(len(req.rfile.getvalue()))
        handler = TestHandler(req)
        if method == "GET":
            handler.do_GET()
        else:
            handler.do_POST()
        return handler._status, getattr(handler, "_json", None)

    # /auditor/exports/build endpoint tests

    def test_build_endpoint_exists_and_returns_200_for_valid_request(self):
        """POST /auditor/exports/build returns 200 for valid request."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-123",
                "exportType": "institutional_audit",
                "subjectId": "sub-1",
                "decisionId": "dec-1",
                "generatedBy": "system",
                "auditorId": "auditor-1",
                "decisionProvenance": {
                    "decisionStatus": "approved",
                    "readiness": {"evidence": "ready", "compliance": "ready"},
                    "auditReadiness": {"status": "ready"},
                },
                "auditorReport": {"auditReady": True},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False, "decision": "approved"},
                "approvalLifecycle": {"status": "approved"},
                "policyResults": [{"passed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp["recordType"], "auditor_export")
        self.assertEqual(resp["recordVersion"], "gl-auditor-export-v1")
        self.assertEqual(resp["exportId"], "exp-123")
        self.assertEqual(resp["exportType"], "institutional_audit")
        self.assertEqual(resp["subjectId"], "sub-1")
        self.assertEqual(resp["decisionId"], "dec-1")
        self.assertEqual(resp["generatedBy"], "system")
        self.assertEqual(resp["auditorId"], "auditor-1")
        self.assertEqual(resp["exportStatus"], "ready")
        self.assertEqual(resp["auditReadiness"], "audit_ready")
        self.assertEqual(resp["blockers"], [])
        self.assertEqual(resp["warnings"], [])
        self.assertEqual(resp["missingSections"], [])
        self.assertIn("decisionProvenance", resp["sections"])
        self.assertIn("auditorReport", resp["sections"])
        self.assertIn("evidence", resp["sections"])
        self.assertIn("compliance", resp["sections"])
        self.assertIn("permission", resp["sections"])
        self.assertIn("approval", resp["sections"])
        self.assertIn("policy", resp["sections"])

    def test_build_endpoint_missing_auth_returns_401(self):
        """POST /auditor/exports/build without auth returns 401."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            body={},
        )
        self.assertEqual(status, 401)

    def test_build_endpoint_returns_400_for_invalid_json(self):
        """POST /auditor/exports/build with invalid JSON returns 400."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body=b"invalid json",
        )
        self.assertEqual(status, 400)
        self.assertIn("error", resp)
        self.assertIn("Invalid JSON", resp["error"])

    def test_build_endpoint_accepts_grant_admin_role_in_operator_mode(self):
        """POST /auditor/exports/build accepts grant_admin role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Admin", "grant_admin", "op-token-1")

        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer op-token-1",
            body={"exportId": "exp-123"},
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_build_endpoint_accepts_owner_role_in_operator_mode(self):
        """POST /auditor/exports/build accepts owner role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Owner", "owner", "op-token-1")

        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer op-token-1",
            body={"exportId": "exp-123"},
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_build_endpoint_accepts_auditor_role_in_operator_mode(self):
        """POST /auditor/exports/build accepts auditor role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Auditor", "auditor", "op-token-1")

        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer op-token-1",
            body={"exportId": "exp-123"},
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_build_endpoint_rejects_demo_operator_role_in_operator_mode(self):
        """POST /auditor/exports/build rejects demo_operator role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Demo", "demo_operator", "op-token-1")

        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer op-token-1",
            body={},
        )
        self.assertEqual(status, 403)

    def test_build_endpoint_requires_admin_token_when_operator_disabled(self):
        """POST /auditor/exports/build requires admin token when operator model disabled."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"

        # Missing auth should return 401
        status, resp = self._run_handler(
            "/auditor/exports/build",
            body={},
        )
        self.assertEqual(status, 401)

        # Wrong token should return 403
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer wrong-token",
            body={},
        )
        self.assertEqual(status, 403)

    def test_build_endpoint_returns_blocked_for_denied_permission(self):
        """POST /auditor/exports/build returns blocked when permission is denied."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-perm-block",
                "decisionProvenance": {
                    "decisionStatus": "approved",
                    "readiness": {"evidence": "ready"},
                    "auditReadiness": {"status": "ready"},
                },
                "auditorReport": {"auditReady": True},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": False},
                "approvalRequirement": {"required": False, "decision": "approved"},
                "policyResults": [{"passed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["exportStatus"], "blocked")
        self.assertIn("permission_denied", resp["blockers"])

    def test_build_endpoint_returns_incomplete_for_missing_sections(self):
        """POST /auditor/exports/build returns incomplete for missing sections."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={"exportId": "exp-incomplete"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["exportStatus"], "incomplete")
        self.assertEqual(resp["auditReadiness"], "insufficient_evidence")
        self.assertIn("decisionProvenance", resp["missingSections"])
        self.assertIn("auditorReport", resp["missingSections"])

    def test_build_endpoint_returns_needs_review_for_some_missing(self):
        """POST /auditor/exports/build returns needs_review when some sections missing."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-needs-review",
                "decisionProvenance": {"decisionStatus": "approved"},
                "auditorReport": {"auditReady": True},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False, "decision": "approved"},
                "policyResults": [{"passed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["exportStatus"], "needs_review")
        self.assertIn("evidence", resp["missingSections"])
        self.assertIn("compliance", resp["missingSections"])

    def test_build_endpoint_omits_details_when_include_details_false(self):
        """POST /auditor/exports/build omits details when includeDetails=False."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-no-details",
                "decisionProvenance": {"decisionStatus": "approved"},
                "auditorReport": {"auditReady": True},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False, "decision": "approved"},
                "policyResults": [{"passed": True}],
                "includeDetails": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("decisionProvenance", resp)
        self.assertNotIn("auditorReport", resp)
        self.assertNotIn("evidence", resp)
        self.assertNotIn("compliance", resp)
        self.assertNotIn("permission", resp)
        self.assertNotIn("approval", resp)
        self.assertNotIn("policy", resp)
        self.assertNotIn("metadata", resp)

    def test_build_endpoint_includes_details_when_include_details_true(self):
        """POST /auditor/exports/build includes details when includeDetails=True."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-with-details",
                "decisionProvenance": {"decisionStatus": "approved"},
                "auditorReport": {"auditReady": True},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False, "decision": "approved"},
                "policyResults": [{"passed": True}],
                "metadata": {"source": "test"},
                "context": {"env": "testing"},
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("decisionProvenance", resp)
        self.assertIn("auditorReport", resp)
        self.assertIn("evidence", resp)
        self.assertIn("compliance", resp)
        self.assertIn("permission", resp)
        self.assertIn("approval", resp)
        self.assertIn("policy", resp)
        self.assertIn("metadata", resp)
        self.assertIn("context", resp)

    def test_build_endpoint_returns_404_for_get(self):
        """GET /auditor/exports/build returns 404 (POST only)."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            method="GET",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 404)

    def test_build_endpoint_empty_body_returns_valid_export(self):
        """POST /auditor/exports/build with empty body returns valid export."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["recordType"], "auditor_export")
        self.assertEqual(resp["recordVersion"], "gl-auditor-export-v1")
        self.assertEqual(resp["exportStatus"], "incomplete")
        self.assertEqual(resp["auditReadiness"], "insufficient_evidence")

    def test_build_endpoint_handles_all_optional_fields(self):
        """POST /auditor/exports/build handles all optional fields."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-full",
                "exportType": "institutional_audit",
                "subjectId": "sub-1",
                "decisionId": "dec-1",
                "generatedBy": "system",
                "auditorId": "auditor-1",
                "decisionProvenance": {
                    "decisionStatus": "approved",
                    "readiness": {"evidence": "ready", "compliance": "ready"},
                    "auditReadiness": {"status": "ready"},
                },
                "auditorReport": {"auditReady": True, "warnings": []},
                "evidenceCompleteness": {"complete": True, "missing": [], "present": ["ev1"]},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True, "reason": "All permissions granted"},
                "approvalRequirement": {"required": False, "decision": "approved"},
                "approvalLifecycle": {"status": "approved", "currentStep": 1, "totalSteps": 1},
                "policyResults": [{"passed": True, "name": "policy1"}],
                "createdAt": "2026-01-01T00:00:00Z",
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["exportId"], "exp-full")
        self.assertEqual(resp["createdAt"], "2026-01-01T00:00:00Z")
        self.assertEqual(resp["exportStatus"], "ready")
        self.assertEqual(resp["auditReadiness"], "audit_ready")

    def test_build_endpoint_no_secrets_at_top_level(self):
        """POST /auditor/exports/build does not expose secrets at top level."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-secrets",
                "decisionProvenance": {"decisionStatus": "approved"},
                "metadata": {"api_key": "secret123", "token": "bearer-token"},
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("api_key", resp)
        self.assertNotIn("token", resp)
        # metadata is in the detail section
        self.assertIn("metadata", resp)

    def test_build_endpoint_returns_blocked_for_policy_failed(self):
        """POST /auditor/exports/build returns blocked when policy fails."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-policy-fail",
                "decisionProvenance": {
                    "decisionStatus": "approved",
                    "readiness": {"evidence": "ready"},
                    "auditReadiness": {"status": "ready"},
                },
                "auditorReport": {"auditReady": True},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False, "decision": "approved"},
                "policyResults": [{"failed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("policy_failed", resp["blockers"])
        self.assertEqual(resp["exportStatus"], "blocked")

    def test_build_endpoint_returns_warning_for_approval_pending(self):
        """POST /auditor/exports/build returns warning when approval pending."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-approval-pending",
                "decisionProvenance": {
                    "decisionStatus": "approved",
                    "readiness": {"evidence": "ready"},
                    "auditReadiness": {"status": "ready"},
                },
                "auditorReport": {"auditReady": True},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"decision": "pending"},
                "policyResults": [{"passed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["exportStatus"], "needs_review")
        self.assertIn("approval_requirement_pending", resp["warnings"])

    def test_build_endpoint_returns_blocked_for_critical_findings(self):
        """POST /auditor/exports/build returns blocked for critical auditor findings."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-critical",
                "decisionProvenance": {
                    "decisionStatus": "approved",
                    "readiness": {"evidence": "ready"},
                    "auditReadiness": {"status": "ready"},
                },
                "auditorReport": {
                    "auditReady": True,
                    "criticalFindings": [{"id": "f1", "severity": "critical"}],
                },
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {"overallStatus": "complete"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False, "decision": "approved"},
                "policyResults": [{"passed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["exportStatus"], "blocked")
        self.assertIn("auditor_report_critical_findings", resp["blockers"])

    def test_build_endpoint_returns_blocked_for_compliance_critical_gaps(self):
        """POST /auditor/exports/build returns blocked for critical compliance gaps."""
        status, resp = self._run_handler(
            "/auditor/exports/build",
            auth="Bearer test-admin-token",
            body={
                "exportId": "exp-compliance-critical",
                "decisionProvenance": {
                    "decisionStatus": "approved",
                    "readiness": {"evidence": "ready"},
                    "auditReadiness": {"status": "ready"},
                },
                "auditorReport": {"auditReady": True},
                "evidenceCompleteness": {"complete": True},
                "complianceGapReport": {
                    "overallStatus": "complete",
                    "criticalGaps": [{"id": "g1", "severity": "critical"}],
                },
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False, "decision": "approved"},
                "policyResults": [{"passed": True}],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["exportStatus"], "blocked")
        self.assertIn("compliance_critical_gaps", resp["blockers"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
