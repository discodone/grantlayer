"""GL-040-C - Approval Lifecycle API Endpoint tests.

Covers endpoints:
- POST /approvals/lifecycle/build
- POST /approvals/lifecycle/transition
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestApprovalLifecycleAPI(unittest.TestCase):
    """Tests for approval lifecycle API endpoints."""

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

    # /approvals/lifecycle/build endpoint tests

    def test_build_endpoint_exists_and_returns_200_for_valid_request(self):
        """POST /approvals/lifecycle/build returns 200 for valid request."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                    "requiredApprovals": 1,
                    "requiredRoles": ["grant_admin"],
                },
                "requestId": "req-123",
                "action": "create",
                "actorId": "actor-1",
                "subjectId": "subject-1",
                "requestedBy": "requester",
                "approvers": [],
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)
        self.assertIn("status", resp)
        self.assertEqual(resp["status"], "pending")
        self.assertEqual(resp["requiredApprovals"], 1)
        self.assertEqual(resp["requiredRoles"], ["grant_admin"])

    def test_build_endpoint_missing_auth_returns_401(self):
        """POST /approvals/lifecycle/build without auth returns 401."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            body={},
        )
        self.assertEqual(status, 401)

    def test_build_endpoint_returns_400_for_invalid_json(self):
        """POST /approvals/lifecycle/build with invalid JSON returns 400."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body=b"invalid json",
        )
        self.assertIn(status, [400, 422])

    def test_build_endpoint_accepts_grant_admin_role_in_operator_mode(self):
        """POST /approvals/lifecycle/build accepts grant_admin role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Admin", "grant_admin", "op-token-1")

        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer op-token-1",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_build_endpoint_rejects_auditor_role_in_operator_mode(self):
        """POST /approvals/lifecycle/build rejects auditor role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Auditor", "auditor", "op-token-1")

        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer op-token-1",
            body={},
        )
        self.assertEqual(status, 403)

    def test_build_endpoint_accepts_owner_role_in_operator_mode(self):
        """POST /approvals/lifecycle/build accepts owner role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Owner", "owner", "op-token-1")

        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer op-token-1",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_build_endpoint_requires_admin_token_when_operator_disabled(self):
        """POST /approvals/lifecycle/build requires admin token when operator model disabled."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"

        # Missing auth should return 401
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            body={},
        )
        self.assertEqual(status, 401)

        # Wrong token should return 403
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer wrong-token",
            body={},
        )
        self.assertEqual(status, 403)

    def test_build_endpoint_returns_blocked_for_missing_approval_requirement(self):
        """POST /approvals/lifecycle/build returns blocked status for missing approvalRequirement."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "requestId": "req-123",
                "action": "create",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "blocked")
        self.assertEqual(resp["decision"], "blocked")
        self.assertEqual(resp["reason"], "missing_approval_requirement")
        self.assertIn("approval_requirement_missing", resp["blockers"])

    def test_build_endpoint_returns_not_required_for_no_approval_required(self):
        """POST /approvals/lifecycle/build returns not_required for no_approval_required decision."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "no_approval_required",
                    "reason": "low_risk",
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "not_required")
        self.assertEqual(resp["decision"], "no_approval_required")
        self.assertEqual(resp["reason"], "low_risk")

    def test_build_endpoint_returns_pending_for_approval_required(self):
        """POST /approvals/lifecycle/build returns pending for approval_required decision."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "medium_risk",
                    "requiredApprovals": 2,
                    "requiredRoles": ["grant_admin", "owner"],
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "pending")
        self.assertEqual(resp["requiredApprovals"], 2)
        self.assertEqual(resp["requiredRoles"], ["grant_admin", "owner"])

    def test_build_endpoint_returns_pending_for_four_eyes_required(self):
        """POST /approvals/lifecycle/build returns pending for four_eyes_required decision."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "four_eyes_required",
                    "reason": "high_risk",
                    "requiredApprovals": 2,
                    "requiredRoles": ["grant_admin", "owner"],
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "pending")
        self.assertGreaterEqual(resp["requiredApprovals"], 2)

    def test_build_endpoint_returns_blocked_for_blocked_decision(self):
        """POST /approvals/lifecycle/build returns blocked for blocked decision."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "blocked",
                    "reason": "policy_violation",
                    "blockers": ["missing_evidence"],
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "blocked")
        self.assertEqual(resp["decision"], "blocked")
        self.assertEqual(resp["reason"], "policy_violation")
        self.assertIn("missing_evidence", resp["blockers"])

    def test_build_endpoint_handles_optional_fields(self):
        """POST /approvals/lifecycle/build handles all optional fields."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
                "requestId": "req-123",
                "action": "create",
                "actorId": "actor-1",
                "subjectId": "subject-1",
                "requestedBy": "requester",
                "approvers": [{"role": "grant_admin", "id": "user1"}],
                "context": {"note": "test context"},
                "includeDetails": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["requestId"], "req-123")
        self.assertEqual(resp["action"], "create")
        self.assertEqual(resp["actorId"], "actor-1")
        self.assertEqual(resp["subjectId"], "subject-1")
        self.assertEqual(resp["requestedBy"], "requester")
        self.assertEqual(len(resp["approvers"]), 1)
        self.assertNotIn("context", resp)  # includeDetails=False

    def test_build_endpoint_includes_context_when_include_details_true(self):
        """POST /approvals/lifecycle/build includes context when includeDetails=True."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
                "context": {"note": "test context", "api_key": "secret-key"},
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("context", resp)
        self.assertEqual(resp["context"]["note"], "test context")
        self.assertEqual(resp["context"]["api_key"], "[REDACTED]")  # secrets redacted

    # /approvals/lifecycle/transition endpoint tests

    def test_transition_endpoint_exists_and_returns_200_for_valid_request(self):
        """POST /approvals/lifecycle/transition returns 200 for valid request."""
        # First create a pending approval request
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                    "requiredApprovals": 1,
                    "requiredRoles": ["grant_admin"],
                },
                "requestId": "req-123",
                "action": "create",
            },
        )
        self.assertEqual(status, 200)

        # Now transition it
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "create",
                "actorId": "actor-1",
                "reason": "created",
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp["status"], "pending")
        self.assertEqual(resp["decision"], "approval_required")
        self.assertEqual(resp["reason"], "created")

    def test_transition_endpoint_missing_auth_returns_401(self):
        """POST /approvals/lifecycle/transition without auth returns 401."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            body={
                "approvalRequest": {},
                "transition": "create",
            },
        )
        self.assertEqual(status, 401)

    def test_transition_endpoint_returns_400_for_invalid_json(self):
        """POST /approvals/lifecycle/transition with invalid JSON returns 400."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body=b"invalid json",
        )
        self.assertIn(status, [400, 422])

    def test_transition_endpoint_returns_400_for_missing_required_fields(self):
        """POST /approvals/lifecycle/transition returns 400 for missing approvalRequest or transition."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={},
        )
        self.assertEqual(status, 400)
        error_msg = (resp or {}).get("error") or str((resp or {}).get("detail", {}).get("error", ""))
        self.assertIn("Missing fields", error_msg)

    def test_transition_endpoint_accepts_grant_admin_role_in_operator_mode(self):
        """POST /approvals/lifecycle/transition accepts grant_admin role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Admin", "grant_admin", "op-token-1")

        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer op-token-1",
            body={
                "approvalRequest": {
                    "status": "pending",
                    "decision": "approval_required",
                    "requiredApprovals": 1,
                    "requiredRoles": ["grant_admin"],
                },
                "transition": "create",
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_transition_endpoint_rejects_auditor_role_in_operator_mode(self):
        """POST /approvals/lifecycle/transition rejects auditor role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Auditor", "auditor", "op-token-1")

        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer op-token-1",
            body={
                "approvalRequest": {},
                "transition": "create",
            },
        )
        self.assertEqual(status, 403)

    def test_transition_endpoint_accepts_owner_role_in_operator_mode(self):
        """POST /approvals/lifecycle/transition accepts owner role in operator mode."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("op-1", "Test Owner", "owner", "op-token-1")

        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer op-token-1",
            body={
                "approvalRequest": {
                    "status": "pending",
                    "decision": "approval_required",
                    "requiredApprovals": 1,
                    "requiredRoles": ["grant_admin"],
                },
                "transition": "create",
            },
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(resp, dict)

    def test_transition_endpoint_requires_admin_token_when_operator_disabled(self):
        """POST /approvals/lifecycle/transition requires admin token when operator model disabled."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"

        # Missing auth should return 401
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            body={
                "approvalRequest": {},
                "transition": "create",
            },
        )
        self.assertEqual(status, 401)

        # Wrong token should return 403
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer wrong-token",
            body={
                "approvalRequest": {},
                "transition": "create",
            },
        )
        self.assertEqual(status, 403)

    def test_transition_endpoint_handles_create_transition(self):
        """POST /approvals/lifecycle/transition handles create transition."""
        # Build a not_required request
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "no_approval_required",
                    "reason": "low_risk",
                },
            },
        )
        self.assertEqual(build_resp["status"], "not_required")

        # Transition to pending
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "create",
                "actorId": "actor-1",
                "reason": "created",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "pending")
        self.assertEqual(resp["reason"], "created")

    def test_transition_endpoint_handles_approve_transition(self):
        """POST /approvals/lifecycle/transition handles approve transition."""
        # Build a pending request
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                    "requiredApprovals": 1,
                    "requiredRoles": ["grant_admin"],
                },
                "approvers": [{"role": "grant_admin", "id": "user1"}],
            },
        )
        self.assertEqual(build_resp["status"], "pending")

        # Transition to approved
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "approve",
                "actorId": "actor-1",
                "reason": "approved",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "approved")
        self.assertEqual(resp["decision"], "approved")
        self.assertEqual(resp["reason"], "approved")
        self.assertEqual(resp["receivedApprovals"], 1)
        self.assertEqual(resp["approvedByRoles"], ["grant_admin"])

    def test_transition_endpoint_handles_reject_transition(self):
        """POST /approvals/lifecycle/transition handles reject transition."""
        # Build a pending request
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )

        # Transition to rejected
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "reject",
                "actorId": "actor-1",
                "reason": "rejected",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "rejected")
        self.assertEqual(resp["decision"], "rejected")
        self.assertEqual(resp["reason"], "rejected")

    def test_transition_endpoint_handles_expire_transition(self):
        """POST /approvals/lifecycle/transition handles expire transition."""
        # Build a pending request
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )

        # Transition to expired
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "expire",
                "actorId": "actor-1",
                "reason": "expired",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "expired")
        self.assertEqual(resp["decision"], "expired")
        self.assertEqual(resp["reason"], "expired")

    def test_transition_endpoint_handles_cancel_transition(self):
        """POST /approvals/lifecycle/transition handles cancel transition."""
        # Build a pending request
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )

        # Transition to cancelled
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "cancel",
                "actorId": "actor-1",
                "reason": "cancelled",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "cancelled")
        self.assertEqual(resp["decision"], "cancelled")
        self.assertEqual(resp["reason"], "cancelled")

    def test_transition_endpoint_handles_block_transition(self):
        """POST /approvals/lifecycle/transition handles block transition."""
        # Build a pending request
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )

        # Transition to blocked
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "block",
                "actorId": "actor-1",
                "reason": "blocked",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "blocked")
        self.assertEqual(resp["decision"], "blocked")
        self.assertEqual(resp["reason"], "blocked")

    def test_transition_endpoint_handles_reopen_transition(self):
        """POST /approvals/lifecycle/transition handles reopen transition."""
        # Build a rejected request
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )
        # First reject it
        status, rejected_resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "reject",
                "actorId": "actor-1",
                "reason": "rejected",
            },
        )
        self.assertEqual(rejected_resp["status"], "rejected")

        # Now reopen it
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": rejected_resp,
                "transition": "reopen",
                "actorId": "actor-2",
                "reason": "reopened",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "pending")
        self.assertEqual(resp["reason"], "reopened")

    def test_transition_endpoint_returns_blocked_for_invalid_transition(self):
        """POST /approvals/lifecycle/transition returns blocked for invalid transition."""
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )

        # Try invalid transition
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "invalid_transition",
                "actorId": "actor-1",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "pending")  # Status unchanged
        self.assertIn("invalid_transition", resp["blockers"][0])

    def test_transition_endpoint_handles_optional_fields(self):
        """POST /approvals/lifecycle/transition handles all optional fields."""
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )

        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "create",
                "actorId": "actor-1",
                "reason": "created with context",
                "at": "2024-01-01T00:00:00Z",
                "context": {"note": "test context"},
                "includeDetails": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "pending")
        self.assertEqual(resp["reason"], "created with context")
        self.assertNotIn("context", resp)  # includeDetails=False

    def test_transition_endpoint_includes_context_when_include_details_true(self):
        """POST /approvals/lifecycle/transition includes context when includeDetails=True."""
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
            },
        )

        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "create",
                "context": {"note": "test context", "api_key": "secret-key"},
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("context", resp)
        self.assertEqual(resp["context"]["note"], "test context")
        self.assertEqual(resp["context"]["api_key"], "[REDACTED]")  # secrets redacted

    def test_transition_endpoint_handles_blocked_to_reopen_with_flag(self):
        """POST /approvals/lifecycle/transition allows blocked->reopen with allowBlockedReopen flag."""
        # Build a blocked request
        status, build_resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "blocked",
                    "reason": "policy_violation",
                },
            },
        )
        self.assertEqual(build_resp["status"], "blocked")

        # Try to reopen without flag (should fail)
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "reopen",
                "actorId": "actor-1",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "blocked")  # Still blocked
        self.assertIn("blocked_cannot_reopen_without_explicit_flag", resp["blockers"][0])

        # Try to reopen with flag (should succeed)
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/transition",
            auth="Bearer test-admin-token",
            body={
                "approvalRequest": build_resp,
                "transition": "reopen",
                "actorId": "actor-1",
                "context": {"allowBlockedReopen": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "pending")  # Now pending

    def test_response_does_not_expose_secrets(self):
        """Response does not expose secrets, tokens, or auth hashes."""
        status, resp = self._run_handler(
            "/v1/approvals/lifecycle/build",
            auth="Bearer test-admin-token",
            body={
                "approvalRequirement": {
                    "decision": "approval_required",
                    "reason": "test",
                },
                "context": {
                    "note": "test",
                    "password": "secret123",
                    "api_key": "sk-12345",
                    "authorization": "Bearer token",
                    "normal_field": "ok",
                },
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("context", resp)
        self.assertEqual(resp["context"]["note"], "test")
        self.assertEqual(resp["context"]["password"], "[REDACTED]")
        self.assertEqual(resp["context"]["api_key"], "[REDACTED]")
        self.assertEqual(resp["context"]["authorization"], "[REDACTED]")
        self.assertEqual(resp["context"]["normal_field"], "ok")
