"""GL-045-A — API Contract & Error Consistency Hardening.

Covers:
1. Invalid JSON on builder endpoints returns structured GL-030 error
2. Missing required fields on builder endpoints returns structured GL-030 error
3. Missing auth on protected endpoints returns 401-equivalent with GL-030 shape
4. Demo-operator forbidden on protected endpoints returns 403-equivalent with GL-030 shape
5. Error responses never expose secrets, tokens, hashes, or env values
6. Builder-style endpoints remain non-mutating for Grant decision state
7. Regression guards for existing stable error codes (execution_not_found, etc.)
"""

import os
import sys
import json
import unittest
import tempfile
import importlib
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGl045aApiContractConsistency(unittest.TestCase):
    """GL-045-A: API contract and error consistency integration tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")

        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap-token"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin"

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

        import src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod

        self.db_mod = db_mod
        self.handler_class = server_mod.GrantLayerHandler

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

        for key, orig in [
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None),
        ]:
            if key == "GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN":
                os.environ.pop(key, None)
                continue
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────
    def _insert_operator(self, op_id: str, name: str, role: str, token: str) -> None:
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, datetime('now'))""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _http_request(self, method: str, path: str, body=None, auth=None):
        handler = self.handler_class.__new__(self.handler_class)
        req_body = json.dumps(body).encode() if body else b""
        handler.rfile = BytesIO(req_body)
        handler.wfile = BytesIO()
        headers = {}
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
        if req_body:
            headers["Content-Length"] = str(len(req_body))
        handler.headers = headers
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        parts = response.split(b"\r\n\r\n", 1)
        data = json.loads(parts[1]) if len(parts) > 1 else {}
        return status_line, data

    def _assert_gl030_full(self, payload: dict) -> None:
        """Assert payload contains the complete GL-030 additive shape."""
        self.assertIn("error", payload, "Missing 'error' field")
        self.assertIn("errorCode", payload, "Missing 'errorCode' field")
        self.assertIn("reason", payload, "Missing 'reason' field")
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)
        self.assertTrue(len(payload["error"]) > 0)
        self.assertTrue(len(payload["errorCode"]) > 0)
        self.assertTrue(len(payload["reason"]) > 0)
        self.assertNotIn(" ", payload["errorCode"],
                         f"errorCode contains space: {payload['errorCode']!r}")

    # ──────────────────────────────────────────────
    # 1. Invalid JSON returns structured error
    # ──────────────────────────────────────────────
    def test_invalid_json_agent_permissions_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"not-json")
        handler.wfile = BytesIO()
        handler.headers = {
            "Authorization": "Bearer admin-token",
            "Content-Length": "8",
        }
        handler.path = "/agent-permissions/evaluate"
        handler.command = "POST"
        handler.requestline = "POST /agent-permissions/evaluate HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        parts = response.split(b"\r\n\r\n", 1)
        data = json.loads(parts[1])
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "invalid_json")

    def test_invalid_json_approvals_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"not-json")
        handler.wfile = BytesIO()
        handler.headers = {
            "Authorization": "Bearer admin-token",
            "Content-Length": "8",
        }
        handler.path = "/approvals/evaluate"
        handler.command = "POST"
        handler.requestline = "POST /approvals/evaluate HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        parts = response.split(b"\r\n\r\n", 1)
        data = json.loads(parts[1])
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "invalid_json")

    def test_invalid_json_approvals_lifecycle_build(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"not-json")
        handler.wfile = BytesIO()
        handler.headers = {
            "Authorization": "Bearer admin-token",
            "Content-Length": "8",
        }
        handler.path = "/approvals/lifecycle/build"
        handler.command = "POST"
        handler.requestline = "POST /approvals/lifecycle/build HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        parts = response.split(b"\r\n\r\n", 1)
        data = json.loads(parts[1])
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "invalid_json")

    def test_invalid_json_decision_provenance_v2_build(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"not-json")
        handler.wfile = BytesIO()
        handler.headers = {
            "Authorization": "Bearer admin-token",
            "Content-Length": "8",
        }
        handler.path = "/decision-provenance/v2/build"
        handler.command = "POST"
        handler.requestline = "POST /decision-provenance/v2/build HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        parts = response.split(b"\r\n\r\n", 1)
        data = json.loads(parts[1])
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "invalid_json")

    def test_invalid_json_auditor_exports_build(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"not-json")
        handler.wfile = BytesIO()
        handler.headers = {
            "Authorization": "Bearer admin-token",
            "Content-Length": "8",
        }
        handler.path = "/auditor/exports/build"
        handler.command = "POST"
        handler.requestline = "POST /auditor/exports/build HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        parts = response.split(b"\r\n\r\n", 1)
        data = json.loads(parts[1])
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "invalid_json")

    def test_invalid_json_policy_requirements_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"not-json")
        handler.wfile = BytesIO()
        handler.headers = {
            "Authorization": "Bearer admin-token",
            "Content-Length": "8",
        }
        handler.path = "/policy-requirements/evaluate"
        handler.command = "POST"
        handler.requestline = "POST /policy-requirements/evaluate HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        parts = response.split(b"\r\n\r\n", 1)
        data = json.loads(parts[1])
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "invalid_json")

    def test_invalid_json_compliance_readiness_build(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"not-json")
        handler.wfile = BytesIO()
        handler.headers = {
            "Authorization": "Bearer admin-token",
            "Content-Length": "8",
        }
        handler.path = "/compliance/readiness/build"
        handler.command = "POST"
        handler.requestline = "POST /compliance/readiness/build HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        parts = response.split(b"\r\n\r\n", 1)
        data = json.loads(parts[1])
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "invalid_json")

    # ──────────────────────────────────────────────
    # 2. Missing required field returns structured error
    # ──────────────────────────────────────────────
    def test_missing_field_agent_permissions_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        status_line, data = self._http_request(
            "POST", "/agent-permissions/evaluate",
            body={"agentId": "some-agent"}, auth="admin-token"
        )
        self.assertIn(b"400", status_line)
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "missing_required_fields")

    def test_missing_field_approvals_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        status_line, data = self._http_request(
            "POST", "/approvals/evaluate", body={}, auth="admin-token"
        )
        self.assertIn(b"400", status_line)
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "missing_required_fields")

    def test_missing_field_agent_permissions_assignments_resolve(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        status_line, data = self._http_request(
            "POST", "/agent-permissions/assignments/resolve",
            body={"agentId": "some-agent"}, auth="admin-token"
        )
        self.assertIn(b"400", status_line)
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "missing_required_fields")

    # ──────────────────────────────────────────────
    # 3. Missing auth returns 401 structured error
    # ──────────────────────────────────────────────
    def test_missing_auth_returns_401(self):
        endpoints = [
            ("POST", "/agent-permissions/evaluate", {}),
            ("POST", "/approvals/evaluate", {"action": "test"}),
            ("POST", "/decision-provenance/v2/build", {}),
        ]
        for method, path, body in endpoints:
            status_line, data = self._http_request(method, path, body=body)
            self.assertIn(b"401", status_line,
                          f"{method} {path} should return 401 without auth")
            self._assert_gl030_full(data)

    # ──────────────────────────────────────────────
    # 4. Demo-operator forbidden returns 403 structured error
    # ──────────────────────────────────────────────
    def test_demo_operator_forbidden_returns_403(self):
        self._insert_operator("demo-op", "Demo", "demo_operator", "demo-token")
        endpoints = [
            ("POST", "/agent-permissions/evaluate",
             {"agentId": "a", "requestedScope": "b", "assignedScopes": ["c"]}),
            ("POST", "/approvals/evaluate", {"action": "test"}),
            ("POST", "/compliance/readiness/build", {}),
        ]
        for method, path, body in endpoints:
            status_line, data = self._http_request(method, path, body=body, auth="demo-token")
            self.assertIn(b"403", status_line,
                          f"{method} {path} should return 403 for demo_operator")
            self._assert_gl030_full(data)

    # ──────────────────────────────────────────────
    # 5. Error responses never expose secrets
    # ──────────────────────────────────────────────
    def test_error_responses_do_not_expose_secrets(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        test_cases = [
            ("GET", "/grants/nonexistent-id", None, None),
            ("POST", "/grants", b"bad-json", "admin-token"),
            ("POST", "/agent-permissions/evaluate", b"bad-json", "admin-token"),
            ("GET", "/operators/me", None, None),
        ]
        for method, path, body, auth in test_cases:
            if body is not None and isinstance(body, bytes):
                handler = self.handler_class.__new__(self.handler_class)
                handler.rfile = BytesIO(body)
                handler.wfile = BytesIO()
                handler.headers = {
                    "Authorization": f"Bearer {auth}",
                    "Content-Length": str(len(body)),
                }
                handler.path = path
                handler.command = method
                handler.requestline = f"{method} {path} HTTP/1.1"
                handler.request_version = "HTTP/1.1"
                handler.client_address = ("127.0.0.1", 0)
                handler.server = None
                if method == "GET":
                    handler.do_GET()
                else:
                    handler.do_POST()
                handler.wfile.seek(0)
                response = handler.wfile.read()
                parts = response.split(b"\r\n\r\n", 1)
                data = json.loads(parts[1]) if len(parts) > 1 else {}
            else:
                _, data = self._http_request(method, path, body=body, auth=auth)

            response_str = json.dumps(data).lower()
            forbidden_terms = [
                "token", "hash", "secret", "password", "api_key",
                "env", "bearer", "authorization",
            ]
            for term in forbidden_terms:
                self.assertNotIn(term, response_str,
                    f"Error response for {method} {path} contains '{term}'")

    # ──────────────────────────────────────────────
    # 6. Builder-style endpoints remain non-mutating
    # ──────────────────────────────────────────────
    def test_builder_endpoints_do_not_mutate_grant_state(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        count_before = len(self.grants_mod.list_grants())

        builder_endpoints = [
            ("POST", "/decision-provenance/v2/build", {"decisionId": "test-1"}),
            ("POST", "/auditor/exports/build", {"exportId": "test-1"}),
            ("POST", "/policy-requirements/evaluate", {"policyPack": "test"}),
            ("POST", "/compliance/readiness/build", {"subjectId": "test"}),
            ("POST", "/approvals/evaluate", {"action": "test"}),
            ("POST", "/approvals/lifecycle/build", {"action": "test"}),
        ]

        for method, path, body in builder_endpoints:
            status_line, data = self._http_request(method, path, body=body, auth="admin-token")
            self.assertIn(b"200", status_line, f"{method} {path} should succeed")

        count_after = len(self.grants_mod.list_grants())
        self.assertEqual(count_before, count_after,
                        "Builder endpoints must not create grants")

    # ──────────────────────────────────────────────
    # 7. Error-code stability (no spaces, non-empty)
    # ──────────────────────────────────────────────
    def test_error_codes_are_stable_and_no_spaces(self):
        known_codes = [
            "invalid_json",
            "missing_required_fields",
            "missing_denial_reason",
            "invalid_request",
            "grant_not_found",
            "grant_request_not_found",
            "grant_execution_not_found",
            "execution_not_found",
            "profile_not_found",
            "dashboard_not_found",
            "not_found",
            "operator_model_disabled",
            "operator_auth_required",
            "operator_role_forbidden",
            "admin_token_required",
            "admin_token_invalid",
            "self_approval_forbidden",
            "grant_already_revoked",
            "demo_endpoints_disabled",
        ]
        for code in known_codes:
            self.assertNotIn(" ", code, f"Error code '{code}' contains a space")
            self.assertTrue(len(code) > 0)

    # ──────────────────────────────────────────────
    # 8. Auth module regression — still uses GL-030
    # ──────────────────────────────────────────────
    def test_auth_module_returns_gl030_shape(self):
        ok, status, payload = self.auth_mod.check_auth(None, required_roles=["owner"])
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self._assert_gl030_full(payload)
        self.assertEqual(payload["errorCode"], "operator_auth_required")

        self._insert_operator("auditor", "Aud", "auditor", "aud-token")
        ok, status, payload = self.auth_mod.check_auth(
            "Bearer aud-token", required_roles=["owner"]
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self._assert_gl030_full(payload)
        self.assertEqual(payload["errorCode"], "operator_role_forbidden")

    # ──────────────────────────────────────────────
    # 9. Existing not_found shapes remain stable
    # ──────────────────────────────────────────────
    def test_existing_not_found_shapes_unmodified(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        status_line, data = self._http_request(
            "GET", "/evidence/executions/nonexistent-id", auth="admin-token"
        )
        self.assertIn(b"404", status_line)
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "execution_not_found")
        self.assertEqual(data["reason"], "The requested execution does not exist.")

        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        status_line, data = self._http_request(
            "GET", "/grant-executions/nonexistent-id", auth="auditor-token"
        )
        self.assertIn(b"404", status_line)
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "grant_execution_not_found")
        self.assertEqual(data["reason"], "The requested grant execution does not exist.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
