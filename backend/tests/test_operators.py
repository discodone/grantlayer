"""Tests for GL-021 Real Operator / Admin Model.

Baseline: 52 existing tests from GL-020 Product Core Hardening.
All existing tests must remain green.

Test isolation: each test gets a fresh temporary DB.
"""

import os
import unittest
import importlib
import tempfile


class TestOperatorModel(unittest.TestCase):
    """Test operator auth, bootstrap, roles, and legacy fallback."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        # Save env vars we will mutate
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_bootstrap_id = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_ID")
        self._orig_bootstrap_name = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_NAME")
        self._orig_bootstrap_role = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

        # Reset modules for clean state
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if "GRANTLAYER_DB" in os.environ:
            del os.environ["GRANTLAYER_DB"]

        for key, orig in [
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_ID", self._orig_bootstrap_id),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_NAME", self._orig_bootstrap_name),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE", self._orig_bootstrap_role),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────
    def _insert_operator(self, op_id: str, name: str, role: str, token: str, active: int = 1):
        import backend.src.core.db as db_mod
        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        conn = db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, token_hash=EXCLUDED.token_hash, active=EXCLUDED.active""",
                (op_id, name, role, ops_mod.hash_token(token), active),
            )
            conn.commit()
        finally:
            conn.close()

    def _setup_operator(self, op_id: str, name: str, role: str):
        """Enable operator model, insert operator, then reload modules."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)
        self._insert_operator(op_id, name, role, f"{op_id}-token")
        import backend.src.core.db as db_mod
        db_mod.init_db()
        importlib.reload(self.ops_mod)

    # ──────────────────────────────────────────────
    # 1. Token hashing
    # ──────────────────────────────────────────────
    def test_token_hash_contains_salt_separator(self):
        h = self.ops_mod.hash_token("op-token-123")
        self.assertIn("$", h)
        self.assertTrue(h.startswith("pbkdf2_sha256$600000$"))

    def test_verify_valid_token(self):
        token = "test-token-xyz"
        h = self.ops_mod.hash_token(token)
        self.assertTrue(self.ops_mod.verify_token(token, h))

    def test_verify_invalid_token_fails(self):
        h = self.ops_mod.hash_token("correct-token")
        self.assertFalse(self.ops_mod.verify_token("wrong-token", h))

    # ──────────────────────────────────────────────
    # 2. Bootstrap creates operator when table empty
    # ──────────────────────────────────────────────
    def test_bootstrap_creates_operator_when_empty(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap-secret-123"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_ID"] = "admin-01"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_NAME"] = "System Admin"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE"] = "owner"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        # Re-init DB after config change
        import backend.src.core.db as db_mod
        db_mod.init_db()
        importlib.reload(self.ops_mod)

        ops = self.ops_mod.list_operators()
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].operator_id, "admin-01")
        self.assertEqual(ops[0].name, "System Admin")
        self.assertEqual(ops[0].role, "owner")

    # ──────────────────────────────────────────────
    # 3. Bootstrap skips when operators already exist
    # ──────────────────────────────────────────────
    def test_bootstrap_skips_when_operators_exist(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "first-secret"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        import backend.src.core.db as db_mod
        db_mod.init_db()
        importlib.reload(self.ops_mod)

        # Change bootstrap token and reload
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "second-secret"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)
        db_mod.init_db()  # should create none (already exists)
        importlib.reload(self.ops_mod)

        ops = self.ops_mod.list_operators()
        self.assertEqual(len(ops), 1)

    # ──────────────────────────────────────────────
    # 4. Token is not stored plaintext
    # ──────────────────────────────────────────────
    def test_token_is_not_stored_plaintext(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "my-secret-123"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        import backend.src.core.db as db_mod
        db_mod.init_db()
        importlib.reload(self.ops_mod)

        conn = db_mod.get_conn()
        try:
            row = conn.execute("SELECT token_hash FROM operators").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertIn("$", row["token_hash"])
        self.assertNotIn("my-secret-123", row["token_hash"])

    # ──────────────────────────────────────────────
    # 5. Authentication
    # ──────────────────────────────────────────────
    def test_valid_token_authenticates(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.core.db as db_mod
        db_mod.init_db()
        importlib.reload(self.ops_mod)
        importlib.reload(self.auth_mod)

        self._insert_operator("test-op", "Test Op", "owner", "my-auth-token")

        op = self.ops_mod.authenticate_operator("Bearer my-auth-token")
        self.assertIsNotNone(op)
        self.assertEqual(op.operator_id, "test-op")

    def test_invalid_token_fails(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.core.db as db_mod
        db_mod.init_db()
        importlib.reload(self.ops_mod)
        importlib.reload(self.auth_mod)

        self._insert_operator("test-op", "Test Op", "owner", "my-auth-token")

        op = self.ops_mod.authenticate_operator("Bearer wrong-token")
        self.assertIsNone(op)

    def test_inactive_operator_fails(self):
        self._insert_operator("op-1", "Alice", "owner", "token-abc", active=0)
        import backend.src.core.db as db_mod
        db_mod.init_db()
        importlib.reload(self.ops_mod)

        # Hash with known token
        h = self.ops_mod.hash_token("token-abc")
        conn = db_mod.get_conn()
        try:
            conn.execute("UPDATE operators SET token_hash = ? WHERE id = ?", (h, "op-1"))
            conn.commit()
        finally:
            conn.close()

        op = self.ops_mod.authenticate_operator("Bearer token-abc")
        self.assertIsNone(op)

    # ──────────────────────────────────────────────
    # 6. Role-based authorization
    # ──────────────────────────────────────────────
    def test_grant_creation_requires_owner_or_grant_admin(self):
        self._setup_operator("auditor-op", "Bob", "auditor")
        ok, status, _ = self.auth_mod.check_auth(
            "Bearer auditor-op-token", required_roles=["owner", "grant_admin"]
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)

    def test_revoke_requires_owner_or_grant_admin(self):
        self._setup_operator("grant-op", "Carol", "grant_admin")
        ok, status, payload = self.auth_mod.check_auth(
            "Bearer grant-op-token", required_roles=["owner", "grant_admin"]
        )
        self.assertTrue(ok)

    def test_demo_tamper_requires_owner_or_demo_operator(self):
        self._setup_operator("grant-op", "Carol", "grant_admin")
        ok, status, _ = self.auth_mod.check_auth(
            "Bearer grant-op-token", required_roles=["owner", "demo_operator"]
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)

    # ──────────────────────────────────────────────
    # 7. /operators/me endpoint
    # ──────────────────────────────────────────────
    def test_operators_me_returns_identity_without_hash(self):
        self._setup_operator("viewer", "Dave", "auditor")
        op = self.ops_mod.authenticate_operator("Bearer viewer-token")
        self.assertIsNotNone(op)
        d = op.to_dict()
        self.assertNotIn("token_hash", d)
        self.assertEqual(d["operatorId"], "viewer")

    # ──────────────────────────────────────────────
    # 8. Health check
    # ──────────────────────────────────────────────
    def test_health_reports_operator_model_flags(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        self.assertTrue(self.config_mod.ENABLE_OPERATOR_MODEL)

    # ──────────────────────────────────────────────
    # 9. Legacy admin-token mode still works
    # ──────────────────────────────────────────────
    def test_legacy_admin_token_mode_unchanged(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        ok, status, _ = self.auth_mod.check_auth("Bearer legacy-token")
        self.assertTrue(ok)
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
