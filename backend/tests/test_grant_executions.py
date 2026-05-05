"""Tests for GL-023 Grant Execution Audit & Usage Binding.

Covers:
1. Every protected action attempt creates a GrantExecution record
2. Success + denied + failed paths
3. Linkage to grant, grant_request, audit_event, challenge, operator
4. Read-only endpoints with proper authorization
"""

import os
import sys
import json
import unittest
import importlib
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGrantExecutionModel(unittest.TestCase):
    """Test GrantExecution record creation via handle_demo_action."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_req_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import src.challenges as ch_mod
        importlib.reload(ch_mod)
        self.ch_mod = ch_mod

        import src.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import src.grant_executions as exec_mod
        importlib.reload(exec_mod)
        self.exec_mod = exec_mod

        import src.crypto_signing as crypto_mod
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
        from src.models import Grant
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
        self.grants_mod.create_grant(g)
        return g

    # ──────────────────────────────────────────────
    # 1. Successful execution recorded
    # ──────────────────────────────────────────────
    def test_successful_execution_recorded(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
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
            "tech-01", "technician", "restart-service", "customer-env-a"
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
            "tech-01", "technician", "restart-service", "customer-env-a"
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
        c = self.ch_mod.create_challenge("tech-01", "restart-service", "customer-env-a")
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
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
                "tech-01", "technician", "restart-service", "customer-env-a"
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
        import src.grant_requests as gr_mod
        importlib.reload(gr_mod)
        from src.models import GrantRequest

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
        created_req = gr_mod.create_grant_request(req)
        updated_req, grant = gr_mod.approve_grant_request(created_req.id, "approver-1")

        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
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
            "tech-01", "technician", "restart-service", "customer-env-a"
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

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import src.grant_executions as exec_mod
        importlib.reload(exec_mod)
        self.exec_mod = exec_mod

        import src.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod
        self.handler_class = server_mod.GrantLayerHandler

        import src.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

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
        import src.db as db_mod
        conn = db_mod.get_conn()
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
        from src.models import Grant
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
        self.grants_mod.create_grant(g)
        return g

    def _http_get(self, path, auth_token=None):
        from io import BytesIO
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO()
        handler.wfile = BytesIO()
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        handler.headers = headers
        handler.path = path
        handler.command = "GET"
        handler.requestline = f"GET {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.do_GET()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        parts = response.split(b"\r\n\r\n", 1)
        return parts[0], json.loads(parts[1]) if len(parts) > 1 else {}

    # ──────────────────────────────────────────────
    # 8. GET /grant-executions returns list
    # ──────────────────────────────────────────────
    def test_list_grant_executions_endpoint(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        g = self._make_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )

        status_line, data = self._http_get("/grant-executions", auth_token="auditor-token")
        self.assertIn(b"200", status_line)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["grantId"], g.id)
        self.assertEqual(data[0]["result"], "succeeded")

    # ──────────────────────────────────────────────
    # 9. GET /grant-executions/:id returns single record
    # ──────────────────────────────────────────────
    def test_get_grant_execution_endpoint(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        execution_id = result["executionId"]

        status_line, data = self._http_get(
            f"/grant-executions/{execution_id}", auth_token="auditor-token"
        )
        self.assertIn(b"200", status_line)
        self.assertEqual(data["id"], execution_id)

    # ──────────────────────────────────────────────
    # 10. GET /grants/:id/executions returns executions for that grant
    # ──────────────────────────────────────────────
    def test_grant_executions_for_grant_endpoint(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        g = self._make_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )

        status_line, data = self._http_get(
            f"/grants/{g.id}/executions", auth_token="auditor-token"
        )
        self.assertIn(b"200", status_line)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["grantId"], g.id)

    # ──────────────────────────────────────────────
    # 11. GET /grant-executions filtered by grantId
    # ──────────────────────────────────────────────
    def test_grant_executions_filtered_by_grant_id(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        g1 = self._make_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )

        status_line, data = self._http_get(
            f"/grant-executions?grantId={g1.id}", auth_token="auditor-token"
        )
        self.assertIn(b"200", status_line)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["grantId"], g1.id)

    # ──────────────────────────────────────────────
    # 12. GET /grant-executions filtered by operatorId
    # ──────────────────────────────────────────────
    def test_grant_executions_filtered_by_operator_id(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        self._make_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            operator_id="op-123",
        )
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            operator_id="op-456",
        )

        status_line, data = self._http_get(
            "/grant-executions?operatorId=op-123", auth_token="auditor-token"
        )
        self.assertIn(b"200", status_line)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["operatorId"], "op-123")

    # ──────────────────────────────────────────────
    # 13. Unauthorized role cannot access executions
    # ──────────────────────────────────────────────
    def test_unauthorized_role_cannot_access_executions(self):
        self._insert_operator("viewer-1", "Viewer", "grant_admin", "viewer-token")
        # grant_admin is allowed, so use a different role
        self._insert_operator("nobody-1", "Nobody", "demo_operator", "nobody-token")
        status_line, data = self._http_get("/grant-executions", auth_token="nobody-token")
        self.assertIn(b"403", status_line)

    # ──────────────────────────────────────────────
    # 12. Non-existent execution returns 404
    # ──────────────────────────────────────────────
    def test_get_nonexistent_execution_returns_404(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        status_line, data = self._http_get(
            "/grant-executions/nonexistent-id", auth_token="auditor-token"
        )
        self.assertIn(b"404", status_line)

    # ──────────────────────────────────────────────
    # 13. Non-existent grant returns 404 for executions
    # ──────────────────────────────────────────────
    def test_get_executions_for_nonexistent_grant_returns_404(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        status_line, data = self._http_get(
            "/grants/nonexistent-id/executions", auth_token="auditor-token"
        )
        self.assertIn(b"404", status_line)

    # ──────────────────────────────────────────────
    # 14. Operator model disabled returns 404
    # ──────────────────────────────────────────────
    def test_executions_disabled_without_operator_model(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        importlib.reload(self.config_mod)
        importlib.reload(self.server_mod)
        self.handler_class = self.server_mod.GrantLayerHandler

        status_line, data = self._http_get("/grant-executions")
        self.assertIn(b"404", status_line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
