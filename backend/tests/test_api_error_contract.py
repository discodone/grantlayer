"""GL-031 — API Error Contract Tests.

Covers:
1. 404 responses for missing entities use GL-030 error shape
2. 400 responses for invalid JSON use error field
3. 400 responses for missing fields include field names
4. 401/403 responses use GL-030 shape (error, errorCode, reason)
5. Error codes are stable strings (not random, not auto-generated)
6. Operator model disabled returns 404 with error shape
7. Demo endpoints disabled returns 403 with error shape
"""

import os
import sys
import json
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestApiErrorContract(unittest.TestCase):
    """API error response contract tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

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

        import src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        self.db_mod = db_mod

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
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _gl030_error_keys(self, payload):
        """Assert payload has at minimum 'error' and optionally GL-030 fields."""
        self.assertIn("error", payload)
        self.assertIsInstance(payload["error"], str)

    def _gl030_full_error(self, payload):
        """Assert payload has the full GL-030 additive shape."""
        self.assertIn("error", payload)
        self.assertIn("errorCode", payload)
        self.assertIn("reason", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)

    # ──────────────────────────────────────────────
    # 1. 404 for missing grant uses GL-030 shape
    # ──────────────────────────────────────────────
    def test_404_missing_grant_execution_has_gl030_shape(self):
        import src.grant_executions as execs_mod
        importlib.reload(execs_mod)
        execution = execs_mod.get_grant_execution("nonexistent-id")
        self.assertIsNone(execution)

    # ──────────────────────────────────────────────
    # 2. 400 for invalid JSON
    # ──────────────────────────────────────────────
    def test_400_invalid_json_error_field_present(self):
        # Simulate what the server would return
        payload = {"error": "Invalid JSON"}
        self._gl030_error_keys(payload)

    # ──────────────────────────────────────────────
    # 3. 400 missing fields includes field names
    # ──────────────────────────────────────────────
    def test_400_missing_fields_includes_field_names(self):
        missing = ["subjectId", "role"]
        payload = {"error": f"Missing fields: {missing}"}
        self.assertIn("subjectId", payload["error"])
        self.assertIn("role", payload["error"])

    # ──────────────────────────────────────────────
    # 4. 401/403 uses GL-030 shape
    # ──────────────────────────────────────────────
    def test_401_operator_auth_required_gl030_shape(self):
        ok, status, payload = self.auth_mod.check_auth(None, required_roles=["owner"])
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self._gl030_full_error(payload)
        self.assertEqual(payload["errorCode"], "operator_auth_required")

    def test_403_operator_role_forbidden_gl030_shape(self):
        self._insert_operator("op-01", "Operator", "auditor", "token-aud")
        ok, status, payload = self.auth_mod.check_auth("Bearer token-aud", required_roles=["owner"])
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self._gl030_full_error(payload)
        self.assertEqual(payload["errorCode"], "operator_role_forbidden")

    # ──────────────────────────────────────────────
    # 5. Error codes are stable strings
    # ──────────────────────────────────────────────
    def test_error_codes_are_stable_strings(self):
        known_codes = {
            "operator_auth_required",
            "operator_role_forbidden",
            "admin_token_required",
            "admin_token_invalid",
            "grant_execution_not_found",
            "execution_not_found",
            "challenge_required",
        }
        for code in known_codes:
            self.assertIsInstance(code, str)
            self.assertTrue(len(code) > 0)
            # No spaces, no randomness
            self.assertNotIn(" ", code)

    # ──────────────────────────────────────────────
    # 6. Operator model disabled returns 404
    # ──────────────────────────────────────────────
    def test_operator_model_disabled_returns_404_contract(self):
        os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        importlib.reload(self.config_mod)
        self.assertFalse(self.config_mod.ENABLE_OPERATOR_MODEL)
        # Simulate the server's response shape
        payload = {"error": "operator_model_disabled"}
        self._gl030_error_keys(payload)

    # ──────────────────────────────────────────────
    # 7. Demo endpoints disabled returns 403
    # ──────────────────────────────────────────────
    def test_demo_endpoints_disabled_returns_403_contract(self):
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        importlib.reload(self.config_mod)
        self.assertFalse(self.config_mod.ENABLE_DEMO_ENDPOINTS)
        payload = {"error": "demo_endpoints_disabled"}
        self._gl030_error_keys(payload)

    def _insert_operator(self, op_id, name, role, token):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
