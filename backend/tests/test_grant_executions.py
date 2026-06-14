"""Tests for GL-023 Grant Execution Audit & Usage Binding.

Covers:
1. Every protected action attempt creates a GrantExecution record
2. Success + denied + failed paths
3. Linkage to grant, grant_request, audit_event, challenge, operator
4. Read-only endpoints with proper authorization
"""

import os
import json
import unittest
import importlib
import tempfile


class TestGrantExecutionModel(unittest.TestCase):
    """Test GrantExecution record creation via handle_demo_action."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_req_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.auth.challenges as ch_mod
        importlib.reload(ch_mod)
        self.ch_mod = ch_mod

        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.grants.grant_executions as exec_mod
        importlib.reload(exec_mod)
        self.exec_mod = exec_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_req_challenge is not None:
            os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = self._orig_req_challenge
        else:
            os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)

    def _make_grant(self, **kwargs):
        from backend.src.core.models import Grant
        g = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Routine maintenance",
            **kwargs,
        )
        self.grants_mod.create_grant(g, tenant_id="demo")
        return g

    # ──────────────────────────────────────────────
    # 1. Successful execution recorded
    # ──────────────────────────────────────────────
    def test_successful_execution_recorded(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertTrue(result["approved"])
        self.assertIn("executionId", result)

        execs = self.exec_mod.list_grant_executions()
        self.assertEqual(len(execs), 1)
        ex = execs[0]
        self.assertEqual(ex.result, "succeeded")
        self.assertEqual(ex.grant_id, g.id)
        self.assertEqual(ex.action, "restart-service")
        self.assertEqual(ex.resource, "customer-env-a")
        self.assertIsNotNone(ex.audit_event_id)
        self.assertEqual(ex.audit_event_id, result["auditEventId"])

    # ──────────────────────────────────────────────
    # 2. Denied execution recorded (no grant)
    # ──────────────────────────────────────────────
    def test_denied_execution_recorded_no_grant(self):
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])
        self.assertIn("executionId", result)

        execs = self.exec_mod.list_grant_executions()
        self.assertEqual(len(execs), 1)
        ex = execs[0]
        self.assertEqual(ex.result, "denied")
        self.assertIsNone(ex.grant_id)
        self.assertIn("No grant found", ex.policy_result)
        self.assertIsNotNone(ex.audit_event_id)

    # ──────────────────────────────────────────────
    # 3. Denied execution with challenge required missing
    # ──────────────────────────────────────────────
    def test_denied_execution_challenge_required(self):
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        importlib.reload(self.demo_mod)
        self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])
        self.assertIn("executionId", result)

        execs = self.exec_mod.list_grant_executions()
        self.assertEqual(len(execs), 1)
        ex = execs[0]
        self.assertEqual(ex.result, "denied")
        self.assertEqual(ex.error_code, "challenge_required")
        self.assertEqual(ex.challenge_result, "required_missing")

    # ──────────────────────────────────────────────
    # 4. Successful execution with valid challenge
    # ──────────────────────────────────────────────
    def test_successful_execution_with_challenge(self):
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        importlib.reload(self.demo_mod)
        self._make_grant()
        c = self.ch_mod.create_challenge("tech-01", "restart-service", "customer-env-a", tenant_id="demo")
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
            tenant_id="demo",
        )
        self.assertTrue(result["approved"])
        execs = self.exec_mod.list_grant_executions()
        self.assertEqual(len(execs), 1)
        ex = execs[0]
        self.assertEqual(ex.result, "succeeded")
        self.assertEqual(ex.challenge_id, c.id)
        self.assertEqual(ex.challenge_result, "valid")

    # ──────────────────────────────────────────────
    # 5. Failed execution recorded (internal error)
    # ──────────────────────────────────────────────
    def test_failed_execution_recorded(self):
        self._make_grant()
        original_list_grants = self.grants_mod.list_grants

        def broken_list_grants():
            raise RuntimeError("simulated internal error")

        self.grants_mod.list_grants = broken_list_grants
        self.demo_mod.list_grants = broken_list_grants
        # Point the local reference inside demo_action to broken version
        self.demo_mod.list_grants = broken_list_grants
        try:
            result = self.demo_mod.handle_demo_action(
                "tech-01", "technician", "restart-service", "customer-env-a",
                tenant_id="demo",
            )
            self.assertFalse(result["approved"])
            self.assertIn("executionId", result)
            self.assertEqual(result["reason"], "internal_handler_error")
        finally:
            self.grants_mod.list_grants = original_list_grants
            self.demo_mod.list_grants = original_list_grants

        execs = self.exec_mod.list_grant_executions()
        self.assertEqual(len(execs), 1)
        ex = execs[0]
        self.assertEqual(ex.result, "failed")
        self.assertEqual(ex.error_code, "internal_handler_error")

    # ──────────────────────────────────────────────
    # 6. Execution links to grant_request_id
    # ──────────────────────────────────────────────
    def test_execution_links_grant_request_id(self):
        import backend.src.grants.grant_requests as gr_mod
        importlib.reload(gr_mod)
        from backend.src.core.models import GrantRequest

        req = GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Request test",
        )
        created_req = gr_mod.create_grant_request(req, tenant_id="demo")
        updated_req, grant = gr_mod.approve_grant_request(created_req.id, "approver-1", tenant_id="demo")

        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertTrue(result["approved"])

        execs = self.exec_mod.list_grant_executions()
        self.assertEqual(len(execs), 1)
        ex = execs[0]
        self.assertEqual(ex.grant_id, grant.id)
        self.assertEqual(ex.grant_request_id, updated_req.id)

    # ──────────────────────────────────────────────
    # 7. operator_id is recorded when provided
    # ──────────────────────────────────────────────
    def test_execution_records_operator_id(self):
        self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            operator_id="op-123",
            tenant_id="demo",
        )
        self.assertTrue(result["approved"])
        execs = self.exec_mod.list_grant_executions()
        self.assertEqual(execs[0].operator_id, "op-123")

    # ──────────────────────────────────────────────
    # 8. audit_event_id is linked to execution record
    # ──────────────────────────────────────────────
    def test_execution_audit_event_id_linked(self):
        self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertTrue(result["approved"])
        self.assertIn("auditEventId", result)
        self.assertIn("executionId", result)

        execution = self.exec_mod.get_grant_execution(result["executionId"])
        self.assertIsNotNone(execution)
        self.assertEqual(execution.audit_event_id, result["auditEventId"])


class TestGrantExecutionEndpoints(unittest.TestCase):
    """Test HTTP endpoints for grant executions."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.grants.grant_executions as exec_mod
        importlib.reload(exec_mod)
        self.exec_mod = exec_mod

        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        # Patch backend.src.db so TestClient uses the same temp DB
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        self._bk_db = db_mod

        # Create TestClient with operator model enabled
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        import backend.src.core.config as bk_cfg
        bk_cfg.ENABLE_OPERATOR_MODEL = True
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_enable_operator is not None:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = self._orig_enable_operator
        else:
            os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)

    def _insert_operator(self, op_id, name, role, token):
        conn = self._bk_db.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, datetime('now'))""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_grant(self):
        from backend.src.core.models import Grant
        g = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Routine maintenance",
        )
        self.grants_mod.create_grant(g, tenant_id="demo")
        return g

    def _http_get(self, path, auth_token=None):
        """Helper: GET request via TestClient."""
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        resp = self.client.get(path, headers=headers)
        return resp.status_code, resp.json()

    # ──────────────────────────────────────────────
    # 8. GET /grant-executions returns list
    # ──────────────────────────────────────────────
    def test_list_grant_executions_endpoint(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        g = self._make_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )

        status, data = self._http_get("/v1/grant-executions", auth_token="auditor-token")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["grantId"], g.id)
        self.assertEqual(data["items"][0]["result"], "succeeded")

    # ──────────────────────────────────────────────
    # 9. GET /grant-executions/:id returns single record
    # ──────────────────────────────────────────────
    def test_get_grant_execution_endpoint(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        execution_id = result["executionId"]

        status, data = self._http_get(
            f"/v1/grant-executions/{execution_id}", auth_token="auditor-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["id"], execution_id)

    # ──────────────────────────────────────────────
    # 10. GET /grants/:id/executions returns executions for that grant
    # ──────────────────────────────────────────────
    def test_grant_executions_for_grant_endpoint(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        g = self._make_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )

        status, data = self._http_get(
            f"/v1/grants/{g.id}/executions", auth_token="auditor-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["grantId"], g.id)

    # ──────────────────────────────────────────────
    # 11. GET /grant-executions filtered by grantId
    # ──────────────────────────────────────────────
    def test_grant_executions_filtered_by_grant_id(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        g1 = self._make_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )

        status, data = self._http_get(
            f"/v1/grant-executions?grantId={g1.id}", auth_token="auditor-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["grantId"], g1.id)

    # ──────────────────────────────────────────────
    # 12. GET /grant-executions filtered by operatorId
    # ──────────────────────────────────────────────
    def test_grant_executions_filtered_by_operator_id(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        self._make_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            operator_id="op-123",
            tenant_id="demo",
        )
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            operator_id="op-456",
            tenant_id="demo",
        )

        status, data = self._http_get(
            "/v1/grant-executions?operatorId=op-123", auth_token="auditor-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["operatorId"], "op-123")

    # ──────────────────────────────────────────────
    # 13. Unauthorized role cannot access executions
    # ──────────────────────────────────────────────
    def test_unauthorized_role_cannot_access_executions(self):
        self._insert_operator("viewer-1", "Viewer", "grant_admin", "viewer-token")
        # grant_admin is allowed, so use a different role
        self._insert_operator("nobody-1", "Nobody", "demo_operator", "nobody-token")
        status, data = self._http_get("/v1/grant-executions", auth_token="nobody-token")
        self.assertEqual(status, 403)

    # ──────────────────────────────────────────────
    # 12. Non-existent execution returns 404
    # ──────────────────────────────────────────────
    def test_get_nonexistent_execution_returns_404(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        status, data = self._http_get(
            "/v1/grant-executions/nonexistent-id", auth_token="auditor-token"
        )
        self.assertEqual(status, 404)
        self.assertEqual(data["error"], "Grant execution not found")
        self.assertEqual(data["errorCode"], "grant_execution_not_found")
        self.assertEqual(data["reason"], "The requested grant execution does not exist.")

    # ──────────────────────────────────────────────
    # 13. Non-existent grant returns 404 for executions
    # ──────────────────────────────────────────────
    def test_get_executions_for_nonexistent_grant_returns_404(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        status, data = self._http_get(
            "/v1/grants/nonexistent-id/executions", auth_token="auditor-token"
        )
        self.assertEqual(status, 404)

    # ──────────────────────────────────────────────
    # 14. Operator model disabled returns 404
    # ──────────────────────────────────────────────
    def test_executions_disabled_without_operator_model(self):
        import backend.src.core.config as bk_cfg
        orig = bk_cfg.ENABLE_OPERATOR_MODEL
        try:
            bk_cfg.ENABLE_OPERATOR_MODEL = False
            from fastapi.testclient import TestClient
            from backend.src.api.app import create_app
            client_no_op = TestClient(create_app(), raise_server_exceptions=False)
            resp = client_no_op.get("/v1/grant-executions")
            self.assertEqual(resp.status_code, 404)
        finally:
            bk_cfg.ENABLE_OPERATOR_MODEL = orig


if __name__ == "__main__":
    unittest.main(verbosity=2)
