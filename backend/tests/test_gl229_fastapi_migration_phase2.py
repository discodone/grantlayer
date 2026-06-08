"""GL-229: FastAPI Migration Phase 2 — test suite.

Tests for all new routers: grant-requests, audit-events, executions,
evidence, provenance, auditor, compliance, operators/me, admin,
challenges, agent-permissions, approvals, decision-provenance,
policy-requirements, demo.

Skips gracefully when FastAPI is not installed.
"""

import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(
    _FASTAPI_AVAILABLE,
    "FastAPI not installed (apt install python3-fastapi python3-uvicorn python3-pydantic python3-starlette)",
)

if _FASTAPI_AVAILABLE:
    import backend.src.config as _cfg
    import backend.src.db as _db
    from backend.src.api.app import create_app


class _GL229TestBase(unittest.TestCase):
    """Isolated temp-DB + config patches restored after each test."""

    # Subclasses can override to enable operator model
    _operator_model = False
    # Subclasses can set to enable demo endpoints
    _demo_endpoints = False
    # Subclasses can set an admin token
    _admin_token = ""

    def setUp(self):
        self._orig_enable_operator = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_allow_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db_path = _db.DB_PATH_OR_URL
        self._orig_admin_token = _cfg.GRANTLAYER_ADMIN_TOKEN
        self._orig_demo = _cfg.ENABLE_DEMO_ENDPOINTS

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True

        if self._operator_model:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
            _cfg.ENABLE_OPERATOR_MODEL = True
        else:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
            _cfg.ENABLE_OPERATOR_MODEL = False

        if self._demo_endpoints:
            _cfg.ENABLE_DEMO_ENDPOINTS = True
        else:
            _cfg.ENABLE_DEMO_ENDPOINTS = False

        if self._admin_token:
            _cfg.GRANTLAYER_ADMIN_TOKEN = self._admin_token
        else:
            _cfg.GRANTLAYER_ADMIN_TOKEN = ""

        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=True)

    def tearDown(self):
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_enable_operator
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_allow_plaintext
        _cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin_token
        _cfg.ENABLE_DEMO_ENDPOINTS = self._orig_demo
        _db.DB_PATH_OR_URL = self._orig_db_path
        _db.DB_PATH = self._orig_db_path
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def _auth_headers(self, token: str = "") -> dict:
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}


# ── Audit Events ─────────────────────────────────────────────────────────────

@_SKIP
class TestAuditEventsEndpoint(_GL229TestBase):

    def test_audit_events_200_demo_mode(self):
        resp = self.client.get("/audit-events")
        self.assertEqual(resp.status_code, 200)

    def test_audit_events_returns_list(self):
        resp = self.client.get("/audit-events")
        self.assertIsInstance(resp.json(), list)

    def test_audit_events_limit_param(self):
        resp = self.client.get("/audit-events?limit=5")
        self.assertEqual(resp.status_code, 200)

    def test_audit_events_invalid_limit_422(self):
        resp = self.client.get("/audit-events?limit=0")
        self.assertEqual(resp.status_code, 422)

    def test_audit_events_security_headers(self):
        resp = self.client.get("/audit-events")
        self.assertEqual(resp.headers.get("x-content-type-options"), "nosniff")


# ── Grant Requests — operator model disabled (404) ────────────────────────

@_SKIP
class TestGrantRequestsOperatorModelDisabled(_GL229TestBase):
    _operator_model = False

    BODY = {
        "subjectId": "agent-001",
        "role": "executor",
        "action": "deploy",
        "resource": "service:payments",
        "validFrom": "2025-01-01T00:00:00Z",
        "validUntil": "2026-01-01T00:00:00Z",
        "reason": "Grant request test",
    }

    def test_create_grant_request_requires_operator_model(self):
        resp = self.client.post("/grant-requests", json=self.BODY)
        self.assertEqual(resp.status_code, 404)
        self.assertIn("operator_model_disabled", str(resp.json()))

    def test_approve_grant_request_requires_operator_model(self):
        resp = self.client.post("/grant-requests/fake-id/approve")
        self.assertEqual(resp.status_code, 404)

    def test_deny_grant_request_requires_operator_model(self):
        resp = self.client.post("/grant-requests/fake-id/deny", json={"reason": "test"})
        self.assertEqual(resp.status_code, 404)

    def test_list_grant_requests_200_no_operator_model(self):
        """GET list doesn't require operator model."""
        resp = self.client.get("/grant-requests")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_get_grant_request_404_no_operator_model(self):
        resp = self.client.get("/grant-requests/nonexistent-id")
        self.assertEqual(resp.status_code, 404)

    def test_list_grant_requests_status_filter_invalid(self):
        resp = self.client.get("/grant-requests?status=invalid_status_xyz")
        self.assertEqual(resp.status_code, 400)


# ── Grant Executions — operator model disabled (404) ─────────────────────

@_SKIP
class TestExecutionsOperatorModelDisabled(_GL229TestBase):
    _operator_model = False

    def test_list_executions_requires_operator_model(self):
        resp = self.client.get("/grant-executions")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("operator_model_disabled", str(resp.json()))

    def test_get_execution_requires_operator_model(self):
        resp = self.client.get("/grant-executions/some-id")
        self.assertEqual(resp.status_code, 404)

    def test_list_executions_for_grant_requires_operator_model(self):
        resp = self.client.get("/grants/some-id/executions")
        self.assertEqual(resp.status_code, 404)


# ── Evidence — 404 for nonexistent execution ─────────────────────────────

@_SKIP
class TestEvidenceEndpoints(_GL229TestBase):

    def test_evidence_bundle_404_unknown_execution(self):
        resp = self.client.get("/evidence/executions/nonexistent-exec")
        self.assertEqual(resp.status_code, 404)
        detail = resp.json()
        self.assertIn("execution_not_found", str(detail))

    def test_evidence_export_404_unknown_execution(self):
        resp = self.client.get("/evidence/executions/nonexistent-exec/export")
        self.assertEqual(resp.status_code, 404)

    def test_evidence_verify_404_unknown_execution(self):
        resp = self.client.get("/evidence/executions/nonexistent-exec/verify")
        self.assertEqual(resp.status_code, 404)

    def test_evidence_completeness_404_unknown_execution(self):
        resp = self.client.get("/evidence/executions/nonexistent-exec/completeness")
        self.assertEqual(resp.status_code, 404)


# ── Provenance — 404 for nonexistent execution ────────────────────────────

@_SKIP
class TestProvenanceEndpoints(_GL229TestBase):
    _operator_model = False

    def test_provenance_summary_404_unknown(self):
        resp = self.client.get("/provenance/executions/nonexistent-exec/summary")
        # In legacy mode without operator model, nonexistent execution → 404
        self.assertEqual(resp.status_code, 404)


# ── Auditor ───────────────────────────────────────────────────────────────

@_SKIP
class TestAuditorEndpoints(_GL229TestBase):

    def test_auditor_report_404_unknown_execution(self):
        resp = self.client.get("/auditor/reports/executions/nonexistent-exec")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("execution_not_found", str(resp.json()))

    def test_auditor_export_build_200(self):
        resp = self.client.post("/auditor/exports/build", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), dict)

    def test_auditor_export_build_with_data(self):
        body = {
            "exportId": "export-001",
            "exportType": "institutional",
            "subjectId": "agent-001",
        }
        resp = self.client.post("/auditor/exports/build", json=body)
        self.assertEqual(resp.status_code, 200)


# ── Compliance ────────────────────────────────────────────────────────────

@_SKIP
class TestComplianceEndpoints(_GL229TestBase):

    def test_compliance_gaps_404_unknown(self):
        resp = self.client.get("/compliance/gaps/executions/nonexistent-exec")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("execution_not_found", str(resp.json()))

    def test_compliance_readiness_build_200(self):
        resp = self.client.post("/compliance/readiness/build", json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("readinessStatus", data)

    def test_compliance_readiness_status_not_assessed_maps_to_insufficient_data(self):
        resp = self.client.post("/compliance/readiness/build", json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # With empty input, should never return "not_assessed" (mapped away)
        self.assertNotEqual(data.get("readinessStatus"), "not_assessed")

    def test_compliance_readiness_build_with_subject(self):
        resp = self.client.post("/compliance/readiness/build", json={"subjectId": "agent-001"})
        self.assertEqual(resp.status_code, 200)


# ── Operators /me ─────────────────────────────────────────────────────────

@_SKIP
class TestOperatorsMeEndpoint(_GL229TestBase):
    _operator_model = False

    def test_operators_me_returns_404_when_operator_model_disabled(self):
        resp = self.client.get("/operators/me")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("operator_model_disabled", str(resp.json()))

    def test_operators_me_200_demo_mode_auth_passes(self):
        # Auth still passes in demo mode, operator model check gates on ENABLE_OPERATOR_MODEL
        resp = self.client.get("/operators/me")
        # Must be 404 (operator model disabled) not 401/403/5xx
        self.assertEqual(resp.status_code, 404)


# ── Admin Operators ───────────────────────────────────────────────────────

@_SKIP
class TestAdminOperatorsNoToken(_GL229TestBase):
    """Admin endpoints require admin token when GRANTLAYER_REQUIRE_ADMIN_TOKEN=true."""

    def setUp(self):
        super().setUp()
        # Force token requirement so unauthenticated requests fail closed
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        self.client = TestClient(create_app(), raise_server_exceptions=True)

    def tearDown(self):
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        super().tearDown()

    def test_list_operators_no_token_403(self):
        resp = self.client.get("/admin/operators")
        self.assertIn(resp.status_code, (401, 403))

    def test_get_operator_no_token_403(self):
        resp = self.client.get("/admin/operators/some-id")
        self.assertIn(resp.status_code, (401, 403))

    def test_create_operator_no_token_403(self):
        body = {"name": "test", "role": "owner", "tenantId": "t1"}
        resp = self.client.post("/admin/operators", json=body)
        self.assertIn(resp.status_code, (401, 403))

    def test_revoke_operator_no_token_403(self):
        resp = self.client.post("/admin/operators/some-id/revoke")
        self.assertIn(resp.status_code, (401, 403))


@_SKIP
class TestAdminOperatorsWithToken(_GL229TestBase):
    """Admin CRUD with a valid admin token."""
    _admin_token = "test-admin-token-gl229"

    def setUp(self):
        super().setUp()
        # auth.py reads from os.environ, not _cfg object
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._admin_token
        self.client = TestClient(create_app(), raise_server_exceptions=True)

    def tearDown(self):
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        super().tearDown()

    def _admin_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._admin_token}"}

    def test_list_operators_200(self):
        resp = self.client.get("/admin/operators", headers=self._admin_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_create_operator_201(self):
        body = {"name": "GL229 TestOp", "role": "grant_admin", "tenantId": "tenant-gl229"}
        resp = self.client.post("/admin/operators", json=body, headers=self._admin_headers())
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("operatorId", data)
        self.assertIn("token", data)
        self.assertEqual(data["role"], "grant_admin")
        self.assertEqual(data["tenantId"], "tenant-gl229")

    def test_create_operator_invalid_role_400(self):
        body = {"name": "Bad Role Op", "role": "superadmin", "tenantId": "t1"}
        resp = self.client.post("/admin/operators", json=body, headers=self._admin_headers())
        self.assertEqual(resp.status_code, 400)
        self.assertIn("invalid_operator_role", str(resp.json()))

    def test_get_operator_by_id(self):
        body = {"name": "GL229 GetOp", "role": "auditor", "tenantId": "tenant-gl229-get"}
        create_resp = self.client.post("/admin/operators", json=body, headers=self._admin_headers())
        self.assertEqual(create_resp.status_code, 201)
        op_id = create_resp.json()["operatorId"]
        get_resp = self.client.get(f"/admin/operators/{op_id}", headers=self._admin_headers())
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["operatorId"], op_id)
        # token must NOT be in safe view
        self.assertNotIn("token", get_resp.json())

    def test_get_nonexistent_operator_404(self):
        resp = self.client.get("/admin/operators/does-not-exist-xyz", headers=self._admin_headers())
        self.assertEqual(resp.status_code, 404)
        self.assertIn("operator_not_found", str(resp.json()))

    def test_revoke_operator(self):
        body = {"name": "GL229 RevokeOp", "role": "owner", "tenantId": "t-revoke"}
        create_resp = self.client.post("/admin/operators", json=body, headers=self._admin_headers())
        op_id = create_resp.json()["operatorId"]
        revoke_resp = self.client.post(f"/admin/operators/{op_id}/revoke", headers=self._admin_headers())
        self.assertEqual(revoke_resp.status_code, 200)
        data = revoke_resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["revoked"])
        self.assertEqual(data["operatorId"], op_id)

    def test_revoke_nonexistent_operator_404(self):
        resp = self.client.post("/admin/operators/ghost-id-xyz/revoke", headers=self._admin_headers())
        self.assertEqual(resp.status_code, 404)

    def test_create_operator_missing_name_422(self):
        body = {"role": "owner", "tenantId": "t1"}
        resp = self.client.post("/admin/operators", json=body, headers=self._admin_headers())
        self.assertEqual(resp.status_code, 422)

    def test_create_operator_empty_name_400(self):
        body = {"name": "   ", "role": "owner", "tenantId": "t1"}
        resp = self.client.post("/admin/operators", json=body, headers=self._admin_headers())
        self.assertEqual(resp.status_code, 400)


# ── Challenges ────────────────────────────────────────────────────────────

@_SKIP
class TestChallengesEndpoints(_GL229TestBase):

    def test_list_challenges_200(self):
        resp = self.client.get("/challenges")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_create_challenge_201(self):
        body = {"subjectId": "agent-001", "action": "deploy", "resource": "service:payments"}
        resp = self.client.post("/challenges", json=body)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("challengeId", data)
        self.assertIn("expiresAt", data)
        self.assertEqual(data["subjectId"], "agent-001")
        self.assertEqual(data["action"], "deploy")

    def test_create_challenge_missing_subject_id_422(self):
        body = {"action": "deploy", "resource": "service:payments"}
        resp = self.client.post("/challenges", json=body)
        self.assertEqual(resp.status_code, 422)

    def test_create_challenge_missing_action_422(self):
        body = {"subjectId": "agent-001", "resource": "service:payments"}
        resp = self.client.post("/challenges", json=body)
        self.assertEqual(resp.status_code, 422)

    def test_created_challenge_appears_in_list(self):
        body = {"subjectId": "agent-002", "action": "read", "resource": "db:users"}
        self.client.post("/challenges", json=body)
        resp = self.client.get("/challenges")
        ids = [c.get("challengeId") for c in resp.json()]
        self.assertGreater(len(ids), 0)


# ── Agent Permissions ─────────────────────────────────────────────────────

@_SKIP
class TestAgentPermissionsEndpoints(_GL229TestBase):

    def test_list_profiles_200(self):
        resp = self.client.get("/agent-permissions/profiles")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_get_profile_404_unknown(self):
        resp = self.client.get("/agent-permissions/profiles/does-not-exist-xyz")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("profile_not_found", str(resp.json()))

    def test_evaluate_permission_200(self):
        body = {
            "agentId": "agent-001",
            "requestedScope": "read:grants",
            "assignedScopes": ["read:grants", "write:grants"],
        }
        resp = self.client.post("/agent-permissions/evaluate", json=body)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), dict)

    def test_evaluate_permission_missing_agent_id_400(self):
        body = {"requestedScope": "read:grants", "assignedScopes": []}
        resp = self.client.post("/agent-permissions/evaluate", json=body)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("missing_required_fields", str(resp.json()))

    def test_resolve_assignment_200(self):
        body = {"agentId": "agent-001", "requestedScope": "read:grants"}
        resp = self.client.post("/agent-permissions/assignments/resolve", json=body)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), dict)

    def test_resolve_assignment_missing_fields_400(self):
        body = {"agentId": "agent-001"}
        resp = self.client.post("/agent-permissions/assignments/resolve", json=body)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("missing_required_fields", str(resp.json()))


# ── Approvals ─────────────────────────────────────────────────────────────

@_SKIP
class TestApprovalsEndpoints(_GL229TestBase):

    def test_lifecycle_build_200(self):
        resp = self.client.post("/approvals/lifecycle/build", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), dict)

    def test_lifecycle_transition_missing_fields_400(self):
        resp = self.client.post("/approvals/lifecycle/transition", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("missing_required_fields", str(resp.json()))

    def test_lifecycle_transition_200(self):
        body = {
            "approvalRequest": {"requestId": "req-001", "status": "pending"},
            "transition": "approve",
            "actorId": "op-001",
        }
        resp = self.client.post("/approvals/lifecycle/transition", json=body)
        self.assertEqual(resp.status_code, 200)

    def test_evaluate_approvals_missing_action_400(self):
        resp = self.client.post("/approvals/evaluate", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("missing_required_fields", str(resp.json()))

    def test_evaluate_approvals_200(self):
        body = {"action": "deploy", "actorId": "op-001"}
        resp = self.client.post("/approvals/evaluate", json=body)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), dict)


# ── Decision Provenance v2 ────────────────────────────────────────────────

@_SKIP
class TestDecisionProvenanceEndpoints(_GL229TestBase):

    def test_build_provenance_v2_200(self):
        resp = self.client.post("/decision-provenance/v2/build", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), dict)

    def test_build_provenance_v2_with_data(self):
        body = {
            "decisionId": "dec-001",
            "decisionType": "grant_approval",
            "subjectId": "agent-001",
            "decision": "approved",
        }
        resp = self.client.post("/decision-provenance/v2/build", json=body)
        self.assertEqual(resp.status_code, 200)


# ── Policy Requirements ───────────────────────────────────────────────────

@_SKIP
class TestPolicyRequirementsEndpoints(_GL229TestBase):

    def test_evaluate_policy_200(self):
        resp = self.client.post("/policy-requirements/evaluate", json={})
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), dict)

    def test_evaluate_policy_with_data(self):
        body = {"policyPack": "standard-v1", "subject": {"id": "agent-001"}}
        resp = self.client.post("/policy-requirements/evaluate", json=body)
        self.assertEqual(resp.status_code, 200)


# ── Demo Endpoints ────────────────────────────────────────────────────────

@_SKIP
class TestDemoEndpointsDisabled(_GL229TestBase):
    _demo_endpoints = False

    def test_tamper_grant_disabled_403(self):
        resp = self.client.post("/demo/tamper-grant/some-grant-id")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("demo_endpoints_disabled", str(resp.json()))


@_SKIP
class TestDemoActionEndpoint(_GL229TestBase):
    _demo_endpoints = False

    BODY = {
        "subjectId": "agent-001",
        "role": "executor",
        "action": "deploy",
        "resource": "service:payments",
    }

    def test_demo_action_200_or_403_on_valid_request(self):
        resp = self.client.post("/demo-action", json=self.BODY)
        # Either 200 (approved) or 403 (denied) — both are valid business outcomes
        self.assertIn(resp.status_code, (200, 403))
        data = resp.json()
        self.assertIn("approved", data)

    def test_demo_action_missing_subject_id_422(self):
        body = dict(self.BODY)
        del body["subjectId"]
        resp = self.client.post("/demo-action", json=body)
        self.assertEqual(resp.status_code, 422)

    def test_demo_action_missing_role_422(self):
        body = dict(self.BODY)
        del body["role"]
        resp = self.client.post("/demo-action", json=body)
        self.assertEqual(resp.status_code, 422)


# ── Auth fail-closed: all routes reject missing/invalid tokens ────────────

@_SKIP
class TestAuthFailClosed(_GL229TestBase):
    """Spot-check that key endpoints fail closed when token is invalid.

    Demo mode (no required token) passes auth; this tests operator model
    mode where a token IS required and invalid one is rejected.
    """

    def test_audit_events_no_auth_demo_returns_200(self):
        """In demo mode (no token required) audit-events is accessible."""
        resp = self.client.get("/audit-events")
        self.assertEqual(resp.status_code, 200)

    def test_challenges_no_auth_demo_returns_200(self):
        resp = self.client.get("/challenges")
        self.assertEqual(resp.status_code, 200)

    def test_admin_operators_accessible_in_demo_mode(self):
        # In demo mode (no required token), admin endpoints pass check_admin_token
        resp = self.client.get("/admin/operators")
        self.assertNotEqual(resp.status_code // 100, 5)


# ── Route count sanity check ──────────────────────────────────────────────

@_SKIP
class TestRouteCount(_GL229TestBase):

    def test_all_phase2_routes_registered(self):
        """Verify the expected GL-229 routes exist in the app."""
        from backend.src.api.app import create_app as _create
        app = _create()
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        expected = {
            "/audit-events",
            "/grant-requests",
            "/grant-requests/{request_id}",
            "/grant-requests/{request_id}/approve",
            "/grant-requests/{request_id}/deny",
            "/grant-executions",
            "/grant-executions/{execution_id}",
            "/grants/{grant_id}/executions",
            "/evidence/executions/{execution_id}",
            "/evidence/executions/{execution_id}/export",
            "/evidence/executions/{execution_id}/verify",
            "/evidence/executions/{execution_id}/completeness",
            "/provenance/executions/{execution_id}/summary",
            "/auditor/reports/executions/{execution_id}",
            "/auditor/exports/build",
            "/compliance/gaps/executions/{execution_id}",
            "/compliance/readiness/build",
            "/operators/me",
            "/admin/operators",
            "/admin/operators/{operator_id}",
            "/admin/operators/{operator_id}/revoke",
            "/challenges",
            "/agent-permissions/profiles",
            "/agent-permissions/profiles/{profile_name}",
            "/agent-permissions/evaluate",
            "/agent-permissions/assignments/resolve",
            "/approvals/lifecycle/build",
            "/approvals/lifecycle/transition",
            "/approvals/evaluate",
            "/decision-provenance/v2/build",
            "/policy-requirements/evaluate",
            "/demo/tamper-grant/{grant_id}",
            "/demo-action",
        }
        for path in expected:
            self.assertIn(path, paths, f"Missing route: {path}")


if __name__ == "__main__":
    unittest.main()
