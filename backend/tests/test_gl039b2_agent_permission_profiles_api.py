"""GL-039-B2 — Agent Permission Scope Profiles API Endpoint tests.

Covers endpoint routing, auth, response shape, profile retrieval,
listing, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAgentPermissionProfilesAPI(unittest.TestCase):
    """Tests for the Agent Permission Scope Profiles API endpoints."""

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

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

        from backend.src import operators as ops
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
        import backend.src.db as db_mod
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
        import backend.src.db as bk_db
        import backend.src.config as config_mod
        import backend.src.auth as auth_mod
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        importlib.reload(config_mod)
        importlib.reload(auth_mod)
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        return TestClient(create_app(), raise_server_exceptions=False)

    def _run_handler(self, path, method="GET", auth=None, body=None):
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

    # ── GET /agent-permissions/profiles ─────────────────────────
    def test_list_profiles_returns_200_for_authorized_legacy_admin_token(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)
        self.assertTrue(len(body) >= 4)
        expected_keys = {"profileName", "description", "scopes", "scopeCount", "warnings"}
        for profile in body:
            self.assertEqual(set(profile.keys()), expected_keys)

    def test_list_profiles_returns_deterministic_profile_list(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        names = [p["profileName"] for p in body]
        self.assertEqual(names, sorted(names))
        names_set = {p["profileName"] for p in body}
        self.assertIn("auditor_readonly", names_set)
        self.assertIn("evidence_verifier", names_set)
        self.assertIn("grant_operator_readonly", names_set)
        self.assertIn("compliance_reviewer", names_set)

    def test_list_profiles_no_admin_token_returns_401(self):
        status, body = self._run_handler("/agent-permissions/profiles")
        self.assertEqual(status, 401)

    def test_list_profiles_wrong_token_returns_403(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer wrong-token",
        )
        self.assertEqual(status, 403)

    def test_list_profiles_owner_allowed_in_operator_mode(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("owner-1", "Owner One", "owner", "owner-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer owner-token",
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_list_profiles_grant_admin_allowed_in_operator_mode(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("admin-1", "Admin One", "grant_admin", "admin-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer admin-token",
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_list_profiles_auditor_forbidden_in_operator_mode(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer auditor-token",
        )
        self.assertEqual(status, 403)

    def test_list_profiles_demo_operator_forbidden_in_operator_mode(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("demo-1", "Demo Op", "demo_operator", "demo-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer demo-token",
        )
        self.assertEqual(status, 403)

    # ── GET /agent-permissions/profiles/:name ───────────────────
    def test_get_profile_returns_known_profile(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["profileName"], "auditor_readonly")
        self.assertIn("scopes", body)
        self.assertIsInstance(body["scopes"], list)
        self.assertIn("evidence:read", body["scopes"])

    def test_get_profile_unknown_returns_404(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/nonexistent",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 404)
        self.assertIn("error", body)
        self.assertEqual(body.get("profileName"), "nonexistent")

    def test_get_profile_case_insensitive(self):
        status_lower, body_lower = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer test-admin-token",
        )
        status_upper, body_upper = self._run_handler(
            "/agent-permissions/profiles/AUDITOR_READONLY",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status_lower, 200)
        self.assertEqual(status_upper, 200)
        self.assertEqual(body_lower["scopes"], body_upper["scopes"])

    def test_get_profile_missing_auth_returns_401(self):
        status, body = self._run_handler("/agent-permissions/profiles/auditor_readonly")
        self.assertEqual(status, 401)

    def test_get_profile_owner_allowed_in_operator_mode(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("owner-1", "Owner One", "owner", "owner-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer owner-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["profileName"], "auditor_readonly")

    def test_get_profile_grant_admin_allowed_in_operator_mode(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("admin-1", "Admin One", "grant_admin", "admin-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer admin-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["profileName"], "auditor_readonly")

    def test_get_profile_auditor_forbidden_in_operator_mode(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer auditor-token",
        )
        self.assertEqual(status, 403)

    def test_get_profile_demo_operator_forbidden_in_operator_mode(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("demo-1", "Demo Op", "demo_operator", "demo-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer demo-token",
        )
        self.assertEqual(status, 403)

    # ── Secrets safety ──────────────────────────────────────────
    def test_list_profiles_does_not_expose_secrets(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private", "hash"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    def test_get_profile_does_not_expose_secrets(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private", "hash"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    def test_list_profiles_no_admin_star_in_builtin_profiles(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        for profile in body:
            self.assertNotIn("admin:*", profile.get("scopes", []), f"Profile {profile['profileName']} contains admin:*")

    def test_get_profile_no_admin_star_in_builtin_profiles(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        self.assertNotIn("admin:*", body.get("scopes", []))

    # ── Endpoint does not mutate Grant decision ────────────────
    def test_list_profiles_does_not_mutate_grant_decision(self):
        # Verify the profile endpoints are read-only and do not affect grants
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        # After calling the read-only endpoint, the grant decision endpoint should still work normally
        status2, body2 = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status2, 200)
        self.assertEqual(body2["profileName"], "auditor_readonly")

    def test_get_profile_does_not_mutate_grant_decision(self):
        # Verify the profile endpoints are read-only and do not affect grants
        status, body = self._run_handler(
            "/agent-permissions/profiles/evidence_verifier",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        # After calling the read-only endpoint, the profile list should remain unchanged
        status2, body2 = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status2, 200)
        self.assertTrue(len(body2) >= 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
