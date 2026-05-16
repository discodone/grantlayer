"""GL-044-B — Compliance Readiness Dashboard API Endpoint tests.

Covers POST /compliance/readiness/build endpoint:
auth, response shape, readiness status logic, includeDetails,
missing inputs, blockers, warnings, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestComplianceReadinessDashboardAPI(unittest.TestCase):
    """Tests for POST /compliance/readiness/build endpoint."""

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

    # ── Endpoint routing ────────────────────────────────────────
    def test_endpoint_returns_200_for_authorized_legacy_admin(self):
        status, resp = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={},
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp["recordType"], "compliance_readiness_summary")
        self.assertEqual(resp["recordVersion"], "gl-compliance-readiness-v1")

    # ── Auth ────────────────────────────────────────────────────
    def test_endpoint_requires_admin_token_when_operator_disabled(self):
        status, body = self._run_handler("/compliance/readiness/build", body={})
        self.assertEqual(status, 401)
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer wrong-token",
            body={},
        )
        self.assertEqual(status, 403)

    def test_endpoint_accepts_operator_roles_when_operator_enabled(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")

        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer auditor-token",
            body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["recordType"], "compliance_readiness_summary")

    def test_endpoint_rejects_demo_operator_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("demo-op-1", "Demo Op", "demo_operator", "demo-token")

        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer demo-token",
            body={},
        )
        self.assertEqual(status, 403)

    # ── Response shape ──────────────────────────────────────────
    def test_response_contains_minimum_fields(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={},
        )
        self.assertEqual(status, 200)
        required_fields = {
            "recordType", "recordVersion", "subjectId", "workflowId",
            "readinessStatus", "readinessScore",
            "evidenceStatus", "complianceStatus", "permissionStatus",
            "approvalStatus", "provenanceStatus", "auditorExportStatus", "policyStatus",
            "blockers", "warnings", "missingInputs", "recommendedActions",
            "createdAt",
        }
        self.assertTrue(required_fields.issubset(body.keys()))

    def test_response_preserves_subject_id_and_workflow_id(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={"subjectId": "sub-123", "workflowId": "wf-456"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["subjectId"], "sub-123")
        self.assertEqual(body["workflowId"], "wf-456")

    # ── Readiness logic ─────────────────────────────────────────
    def test_all_clean_ready_signals_returns_ready(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "evidenceCompleteness": {"completenessStatus": "complete"},
                "complianceGapReport": {"overallStatus": "clear"},
                "permissionResult": {"allowed": True},
                "approvalRequirement": {"required": False},
                "approvalLifecycle": {"status": "approved"},
                "decisionProvenance": {"events": [{"id": "e1"}]},
                "auditorExport": {"auditReady": True, "conclusion": "clean"},
                "policyRequirementEvaluation": {"passed": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "ready")
        self.assertEqual(body["readinessScore"], 100)
        self.assertEqual(body["evidenceStatus"], "ready")
        self.assertEqual(body["complianceStatus"], "ready")
        self.assertEqual(body["permissionStatus"], "ready")
        self.assertEqual(body["approvalStatus"], "ready")
        self.assertEqual(body["provenanceStatus"], "ready")
        self.assertEqual(body["auditorExportStatus"], "ready")
        self.assertEqual(body["policyStatus"], "ready")

    def test_missing_all_signals_returns_insufficient_data(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "insufficient_data")
        self.assertIn("permission_result", body["missingInputs"])
        self.assertIn("approval_requirement", body["missingInputs"])
        self.assertIn("policy_results", body["missingInputs"])

    def test_compliance_high_critical_gaps_block_result(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "complianceGapReport": {"overallStatus": "blocked", "complianceGaps": [{"gapId": "g1", "severity": "critical"}]},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "blocked")
        self.assertEqual(body["complianceStatus"], "blocked")
        self.assertIn("compliance_blocked", body["blockers"])

    def test_permission_result_allowed_false_blocks(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "permissionResult": {"allowed": False},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "blocked")
        self.assertEqual(body["permissionStatus"], "blocked")
        self.assertIn("permission_denied", body["blockers"])

    def test_approval_requirement_decision_blocked_blocks(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {"decision": "blocked"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "blocked")
        self.assertEqual(body["approvalStatus"], "blocked")
        self.assertIn("approval_requirement_blocked", body["blockers"])

    def test_approval_lifecycle_status_blocked_blocks(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "approvalLifecycle": {"status": "blocked"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "blocked")
        self.assertEqual(body["approvalStatus"], "blocked")
        self.assertIn("approval_lifecycle_blocked", body["blockers"])

    def test_decision_provenance_decision_status_blocked_blocks(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "decisionProvenance": {"decisionStatus": "blocked"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "blocked")
        self.assertEqual(body["provenanceStatus"], "blocked")
        self.assertIn("decision_provenance_blocked", body["blockers"])

    def test_auditor_export_export_status_blocked_blocks(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "auditorExport": {"exportStatus": "blocked"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "blocked")
        self.assertEqual(body["auditorExportStatus"], "blocked")
        self.assertIn("auditor_export_blocked", body["blockers"])

    def test_policy_requirement_evaluation_status_blocked_blocks(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "policyRequirementEvaluation": {"evaluationStatus": "blocked"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "blocked")
        self.assertEqual(body["policyStatus"], "blocked")
        self.assertIn("policy_evaluation_blocked", body["blockers"])

    def test_warning_level_signals_create_warnings(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "evidenceCompleteness": {"completenessStatus": "incomplete"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "needs_review")
        self.assertEqual(body["evidenceStatus"], "needs_review")
        self.assertIn("evidence_incomplete", body["warnings"])

    def test_blockers_force_readiness_status_blocked(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "evidenceCompleteness": {"completenessStatus": "complete"},
                "permissionResult": {"allowed": False},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "blocked")
        self.assertEqual(body["evidenceStatus"], "ready")
        self.assertEqual(body["permissionStatus"], "blocked")

    def test_warnings_without_blockers_create_needs_review(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "evidenceCompleteness": {"completenessStatus": "incomplete"},
                "complianceGapReport": {"overallStatus": "gaps_detected"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["readinessStatus"], "needs_review")
        self.assertNotEqual(len(body["warnings"]), 0)
        self.assertEqual(body["blockers"], [])

    def test_readiness_score_deterministic_between_0_and_100(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={},
        )
        self.assertEqual(status, 200)
        score = body["readinessScore"]
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    # ── includeDetails flag ─────────────────────────────────────
    def test_include_details_true_includes_nested_objects(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "evidenceCompleteness": {"completenessStatus": "complete"},
                "complianceGapReport": {"overallStatus": "clear"},
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("evidenceCompleteness", body)
        self.assertIn("complianceGapReport", body)

    def test_include_details_false_omits_detail_objects(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "evidenceCompleteness": {"completenessStatus": "complete"},
                "complianceGapReport": {"overallStatus": "clear"},
                "includeDetails": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("evidenceCompleteness", body)
        self.assertNotIn("complianceGapReport", body)
        self.assertNotIn("permissionResult", body)
        self.assertNotIn("approvalRequirement", body)
        self.assertNotIn("approvalLifecycle", body)
        self.assertNotIn("decisionProvenance", body)
        self.assertNotIn("auditorExport", body)
        self.assertNotIn("policyRequirementEvaluation", body)
        # Core fields remain
        self.assertIn("readinessStatus", body)
        self.assertIn("readinessScore", body)
        self.assertIn("blockers", body)
        self.assertIn("warnings", body)

    # ── Secrets safety ──────────────────────────────────────────
    def test_response_does_not_expose_secrets(self):
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={
                "context": {"note": "safe"},
                "evidenceCompleteness": {"completenessStatus": "complete"},
            },
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    def test_endpoint_does_not_mutate_grant_decision_state(self):
        """POST /compliance/readiness/build is read-only and does not mutate DB state."""
        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        # Count grants before
        conn = db_mod.get_conn()
        before = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        conn.close()
        # Call endpoint
        status, body = self._run_handler(
            "/compliance/readiness/build",
            auth="Bearer test-admin-token",
            body={"evidenceCompleteness": {"completenessStatus": "complete"}},
        )
        self.assertEqual(status, 200)
        # Count grants after
        conn = db_mod.get_conn()
        after = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        conn.close()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
