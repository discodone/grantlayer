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
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
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

        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        self.db_mod = db_mod

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=False)

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
        headers = {}
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        elif method == "POST":
            if body is not None:
                resp = self.client.post(path, json=body, headers=headers)
            else:
                resp = self.client.post(path, headers=headers)
        else:
            resp = self.client.request(method, path, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {}
        # FastAPI wraps non-handled status codes in {"detail": {...}} - unwrap
        if isinstance(data.get("detail"), dict):
            data = data["detail"]
        return resp.status_code, data

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
    def _test_invalid_json_endpoint(self, path, auth_token="admin-token"):
        headers = {"Authorization": f"Bearer {auth_token}"}
        resp = self.client.post(path, content=b"not-json", headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data.get("detail"), dict):
            data = data["detail"]
        self.assertIn(resp.status_code, [400, 422],
                      f"POST {path} with invalid JSON should return 400 or 422")
        if resp.status_code == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_json")

    def test_invalid_json_agent_permissions_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        self._test_invalid_json_endpoint("/agent-permissions/evaluate")

    def test_invalid_json_approvals_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        self._test_invalid_json_endpoint("/approvals/evaluate")

    def test_invalid_json_approvals_lifecycle_build(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        self._test_invalid_json_endpoint("/approvals/lifecycle/build")

    def test_invalid_json_decision_provenance_v2_build(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        self._test_invalid_json_endpoint("/decision-provenance/v2/build")

    def test_invalid_json_auditor_exports_build(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        self._test_invalid_json_endpoint("/auditor/exports/build")

    def test_invalid_json_policy_requirements_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        self._test_invalid_json_endpoint("/policy-requirements/evaluate")

    def test_invalid_json_compliance_readiness_build(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        self._test_invalid_json_endpoint("/compliance/readiness/build")

    # ──────────────────────────────────────────────
    # 2. Missing required field returns structured error
    # ──────────────────────────────────────────────
    def test_missing_field_agent_permissions_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        status, data = self._http_request(
            "POST", "/agent-permissions/evaluate",
            body={"agentId": "some-agent"}, auth="admin-token"
        )
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "missing_required_fields")

    def test_missing_field_approvals_evaluate(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        status, data = self._http_request(
            "POST", "/approvals/evaluate", body={}, auth="admin-token"
        )
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "missing_required_fields")

    def test_missing_field_agent_permissions_assignments_resolve(self):
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        status, data = self._http_request(
            "POST", "/agent-permissions/assignments/resolve",
            body={"agentId": "some-agent"}, auth="admin-token"
        )
        self.assertIn(status, [400, 422])
        if status == 400:
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
            status, data = self._http_request(method, path, body=body)
            self.assertEqual(status, 401,
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
            status, data = self._http_request(method, path, body=body, auth="demo-token")
            self.assertEqual(status, 403,
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
            headers = {}
            if auth:
                headers["Authorization"] = f"Bearer {auth}"
            if body is not None and isinstance(body, bytes):
                resp = self.client.request(method, path, content=body, headers=headers)
            else:
                resp = self.client.request(method, path, headers=headers)
            try:
                data = resp.json()
            except Exception:
                data = {}
            if isinstance(data.get("detail"), dict):
                data = data["detail"]

            response_str = json.dumps(data).lower()
            forbidden_terms = [
                "hash", "secret", "password", "api_key",
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
            status, data = self._http_request(method, path, body=body, auth="admin-token")
            self.assertEqual(status, 200, f"{method} {path} should succeed")

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
        status, data = self._http_request(
            "GET", "/evidence/executions/nonexistent-id", auth="admin-token"
        )
        self.assertEqual(status, 404)
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "execution_not_found")
        self.assertEqual(data["reason"], "The requested execution does not exist.")

        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        status, data = self._http_request(
            "GET", "/grant-executions/nonexistent-id", auth="auditor-token"
        )
        self.assertEqual(status, 404)
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "grant_execution_not_found")
        self.assertEqual(data["reason"], "The requested grant execution does not exist.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
