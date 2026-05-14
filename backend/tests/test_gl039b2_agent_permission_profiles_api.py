"""GL-039-B2 — Agent Permission Scope Profiles API Endpoint tests.

Covers endpoint routing, auth, response shape, profile retrieval,
listing, expansion, and secrets safety.
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

    def _run_handler(self, path, method="GET", auth=None, body=None):
        """Simulate a server request and return (status, response_json)."""
        importlib.reload(self.config)
        from io import BytesIO

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

            def _send_html(inner_self, body):
                inner_self.send_response(200)
                inner_self._status = 200

        req = DummyRequest()
        if body is not None:
            req.rfile = BytesIO(json.dumps(body).encode("utf-8"))
            req.headers["Content-Length"] = str(len(json.dumps(body).encode("utf-8")))
        handler = TestHandler(req)
        if method == "GET":
            handler.do_GET()
        else:
            handler.do_POST()
        return handler._status, getattr(handler, "_json", None)

    # ── GET /agent-permissions/profiles ─────────────────────────
    def test_list_profiles_endpoint_exists_and_returns_200(self):
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

    def test_list_profiles_ordered_alphabetically(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        names = [p["profileName"] for p in body]
        self.assertEqual(names, sorted(names))

    def test_list_profiles_contains_known_built_ins(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        names = {p["profileName"] for p in body}
        self.assertIn("auditor_readonly", names)
        self.assertIn("evidence_verifier", names)
        self.assertIn("grant_operator_readonly", names)
        self.assertIn("compliance_reviewer", names)

    def test_list_profiles_no_admin_token_returns_401(self):
        status, body = self._run_handler("/agent-permissions/profiles")
        self.assertEqual(status, 401)

    def test_list_profiles_wrong_token_returns_403(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer wrong-token",
        )
        self.assertEqual(status, 403)

    def test_list_profiles_accepts_owner_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("owner-1", "Owner One", "owner", "owner-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer owner-token",
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_list_profiles_accepts_grant_admin_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("admin-1", "Admin One", "grant_admin", "admin-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer admin-token",
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_list_profiles_rejects_auditor_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer auditor-token",
        )
        self.assertEqual(status, 403)

    # ── GET /agent-permissions/profiles/:name ───────────────────
    def test_get_profile_returns_200_for_known_profile(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["profileName"], "auditor_readonly")
        self.assertIn("scopes", body)
        self.assertIsInstance(body["scopes"], list)
        self.assertIn("evidence:read", body["scopes"])

    def test_get_profile_returns_404_for_unknown_profile(self):
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

    def test_get_profile_no_admin_token_returns_401(self):
        status, body = self._run_handler("/agent-permissions/profiles/auditor_readonly")
        self.assertEqual(status, 401)

    # ── POST /agent-permissions/profiles/expand ─────────────────
    def test_expand_profiles_endpoint_exists_and_returns_200(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/expand",
            method="POST",
            auth="Bearer test-admin-token",
            body={"profileNames": ["auditor_readonly", "evidence_verifier"]},
        )
        self.assertEqual(status, 200)
        expected_keys = {"scopes", "scopeCount", "warnings", "resolvedProfiles"}
        self.assertEqual(set(body.keys()), expected_keys)

    def test_expand_profiles_deduplicates_scopes(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/expand",
            method="POST",
            auth="Bearer test-admin-token",
            body={"profileNames": ["auditor_readonly", "evidence_verifier"]},
        )
        self.assertEqual(status, 200)
        scopes = body["scopes"]
        self.assertEqual(len(scopes), len(set(scopes)))
        self.assertIn("evidence:read", scopes)
        self.assertIn("evidence:verify", scopes)

    def test_expand_profiles_unknown_profile_adds_warning(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/expand",
            method="POST",
            auth="Bearer test-admin-token",
            body={"profileNames": ["auditor_readonly", "unknown_xyz"]},
        )
        self.assertEqual(status, 200)
        self.assertIn("evidence:read", body["scopes"])
        self.assertTrue(
            any("unknown_xyz" in w for w in body.get("warnings", [])),
            f"Expected warning about unknown profile, got {body.get('warnings', [])}"
        )

    def test_expand_profiles_returns_400_for_missing_fields(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/expand",
            method="POST",
            auth="Bearer test-admin-token",
            body={},
        )
        self.assertEqual(status, 400)
        self.assertIn("Missing fields", body.get("error", ""))

    def test_expand_profiles_returns_400_for_non_list_profile_names(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/expand",
            method="POST",
            auth="Bearer test-admin-token",
            body={"profileNames": "not_a_list"},
        )
        self.assertEqual(status, 400)
        self.assertIn("profileNames must be a list", body.get("error", ""))

    def test_expand_profiles_empty_list_returns_empty_scopes(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/expand",
            method="POST",
            auth="Bearer test-admin-token",
            body={"profileNames": []},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["scopes"], [])
        self.assertEqual(body["scopeCount"], 0)
        self.assertEqual(body["warnings"], [])

    def test_expand_profiles_no_admin_token_returns_401(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/expand",
            method="POST",
            body={"profileNames": ["auditor_readonly"]},
        )
        self.assertEqual(status, 401)

    # ── Secrets safety ──────────────────────────────────────────
    def test_list_profiles_does_not_expose_secrets(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    def test_get_profile_does_not_expose_secrets(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/auditor_readonly",
            auth="Bearer test-admin-token",
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    def test_expand_profiles_does_not_expose_secrets(self):
        status, body = self._run_handler(
            "/agent-permissions/profiles/expand",
            method="POST",
            auth="Bearer test-admin-token",
            body={"profileNames": ["auditor_readonly"]},
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
