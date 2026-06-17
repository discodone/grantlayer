"""GL-039-C2 — Agent Permission Assignment Resolver API Endpoint tests.

Covers endpoint routing, auth, response shape, assignment resolution logic,
profile integration, includeDetails flag, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAgentPermissionAssignmentsAPI(unittest.TestCase):
    """Tests for POST /agent-permissions/assignments/resolve endpoint."""

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

    # ── Endpoint routing ────────────────────────────────────────
    def test_endpoint_exists_and_returns_400_for_missing_fields(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={"agentId": "agent-1"},
        )
        self.assertEqual(status, 400)
        error_msg = body.get("error") or body.get("detail", {}).get("error", "")
        self.assertIn("Missing fields", error_msg)

    def test_endpoint_returns_200_for_valid_request_with_scopes(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])
        self.assertEqual(body["agentId"], "agent-1")
        self.assertEqual(body["requestedScope"], "evidence:read")
        self.assertEqual(body["matchedScope"], "evidence:read")
        self.assertEqual(body["reason"], "scope_matched")

    def test_endpoint_returns_200_for_valid_request_with_profiles(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedProfiles": ["auditor_readonly"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])
        self.assertEqual(body["matchedScope"], "evidence:read")
        self.assertEqual(body["reason"], "scope_matched")

    def test_endpoint_returns_200_with_both_scopes_and_profiles(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:verify",
                "assignedScopes": ["evidence:read"],
                "assignedProfiles": ["evidence_verifier"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])
        self.assertEqual(body["matchedScope"], "evidence:verify")
        self.assertIn("evidence:read", body["resolvedScopes"])
        self.assertIn("evidence:verify", body["resolvedScopes"])

    # ── Auth ────────────────────────────────────────────────────
    def test_endpoint_requires_admin_token_when_operator_disabled(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 401)
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer wrong-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 403)

    def test_endpoint_accepts_owner_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("owner-1", "Owner One", "owner", "owner-token")

        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer owner-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])

    def test_endpoint_accepts_grant_admin_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("admin-1", "Admin One", "grant_admin", "admin-token")

        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])

    def test_endpoint_rejects_auditor_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")

        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer auditor-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 403)

    def test_endpoint_rejects_demo_operator_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("demo-op-1", "Demo Op", "demo_operator", "demo-token")

        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer demo-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 403)

    # ── Response shape ──────────────────────────────────────────
    def test_response_contains_expected_keys(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
                "resourceType": "bundle",
                "resourceId": "bundle-123",
                "includeDetails": False,
            },
        )
        self.assertEqual(status, 200)
        expected_keys = {
            "allowed",
            "agentId",
            "requestedScope",
            "assignedScopes",
            "assignedProfiles",
            "resolvedScopes",
            "matchedScope",
            "resourceType",
            "resourceId",
            "reason",
            "warnings",
        }
        self.assertEqual(set(body.keys()), expected_keys)
        self.assertEqual(body["resourceType"], "bundle")
        self.assertEqual(body["resourceId"], "bundle-123")

    def test_response_with_details_includes_profile_resolution_and_evaluation(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedProfiles": ["auditor_readonly"],
                "includeDetails": True,
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("profileResolution", body)
        self.assertIn("evaluation", body)
        self.assertEqual(body["profileResolution"]["resolvedProfiles"], ["auditor_readonly"])

    def test_response_without_details_omits_profile_resolution_and_evaluation(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedProfiles": ["auditor_readonly"],
                "includeDetails": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("profileResolution", body)
        self.assertNotIn("evaluation", body)
        self.assertIn("resolvedScopes", body)
        self.assertIn("matchedScope", body)

    # ── Evaluation logic ────────────────────────────────────────
    def test_endpoint_denies_unknown_scope(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:frobnicate",
                "assignedProfiles": ["auditor_readonly"],
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertEqual(body["reason"], "requested_scope_unknown")
        self.assertIn("evidence:read", body["resolvedScopes"])

    def test_endpoint_denies_empty_assignment(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": [],
                "assignedProfiles": [],
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertEqual(body["reason"], "scope_not_matched")
        self.assertEqual(body["resolvedScopes"], [])

    def test_endpoint_allows_wildcard_read(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["*:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])
        self.assertEqual(body["matchedScope"], "*:read")

    def test_endpoint_denies_malformed_requested_scope(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertEqual(body["reason"], "requested_scope_malformed")

    def test_endpoint_allows_admin_star(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["admin:*"],
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])
        self.assertEqual(body["matchedScope"], "admin:*")

    def test_endpoint_denies_scope_not_matched(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:write",
                "assignedScopes": ["evidence:read"],
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertEqual(body["reason"], "scope_not_matched")

    def test_endpoint_passes_context_optional(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["evidence:read"],
                "context": {"ip": "127.0.0.1"},
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["allowed"])

    def test_endpoint_warns_on_unknown_profile(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedProfiles": ["unknown_profile"],
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertTrue(any("unknown" in w.lower() for w in body["warnings"]))
        self.assertEqual(body["resolvedScopes"], [])

    def test_endpoint_with_neither_scopes_nor_profiles_denies(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["allowed"])
        self.assertEqual(body["reason"], "scope_not_matched")

    # ── Determinism and ordering ────────────────────────────────
    def test_combined_scopes_are_sorted(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedScopes": ["provenance:read", "evidence:verify"],
                "assignedProfiles": ["auditor_readonly"],
            },
        )
        self.assertEqual(status, 200)
        resolved = body["resolvedScopes"]
        sorted_resolved = sorted(resolved)
        self.assertEqual(resolved, sorted_resolved)

    # ── Secrets safety ──────────────────────────────────────────
    def test_response_does_not_expose_secrets(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedProfiles": ["auditor_readonly"],
            },
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    def test_no_admin_star_in_resolved_scopes_from_builtin_profiles(self):
        status, body = self._run_handler(
            "/v1/agent-permissions/assignments/resolve",
            auth="Bearer test-admin-token",
            body={
                "agentId": "agent-1",
                "requestedScope": "evidence:read",
                "assignedProfiles": ["auditor_readonly", "evidence_verifier"],
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("admin:*", body["resolvedScopes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
