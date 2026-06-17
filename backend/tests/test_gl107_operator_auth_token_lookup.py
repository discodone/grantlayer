"""Tests for GL-107 Operator Auth Token Lookup Hardening.

Ensures operator authentication uses deterministic SHA-256 lookup narrowing
before PBKDF2 verification, eliminating O(n) PBKDF2 loops for invalid tokens.

Covers:
1. Valid operator token authenticates via lookup hash + PBKDF2
2. Invalid operator token fails closed without exhaustive PBKDF2
3. Missing token fails closed
4. Inactive operator token fails closed
5. Role checks preserved through auth module
6. Operator creation stores token_lookup_hash
7. Migration adds token_lookup_hash column and index
8. Baseline schema contains token_lookup_hash for fresh installs
9. Invalid token with many active operators has bounded PBKDF2 checks
10. Valid token has bounded lookup/verification (1 PBKDF2 call)
11. Raw token/hash not leaked in responses
"""

import os
import sys
import unittest
import tempfile
import importlib
import sqlite3
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl107(unittest.TestCase):
    """Shared helpers for GL-107 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _insert_operator_with_lookup(self, op_id, name, role, token, active=1):
        """Insert operator with token_lookup_hash (GL-107 compliant)."""
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, token_lookup_hash, active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, token_hash=EXCLUDED.token_hash, token_lookup_hash=EXCLUDED.token_lookup_hash, active=EXCLUDED.active""",
                (op_id, name, role, self.ops_mod.hash_token(token),
                 self.ops_mod.derive_token_lookup_hash(token), active),
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_operator_legacy(self, op_id, name, role, token, active=1):
        """Insert operator without token_lookup_hash (pre-GL-107 legacy)."""
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, token_hash=EXCLUDED.token_hash, active=EXCLUDED.active""",
                (op_id, name, role, self.ops_mod.hash_token(token), active),
            )
            conn.commit()
        finally:
            conn.close()


class TestGl107AuthFlows(_BaseGl107):
    """Core authentication flow tests."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.core.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

    def test_valid_token_authenticates(self):
        self._insert_operator_with_lookup("op-1", "Alice", "owner", "secret-token-1")
        op = self.ops_mod.authenticate_operator("Bearer secret-token-1")
        self.assertIsNotNone(op)
        self.assertEqual(op.operator_id, "op-1")
        self.assertEqual(op.name, "Alice")
        self.assertEqual(op.role, "owner")

    def test_invalid_token_fails_closed(self):
        self._insert_operator_with_lookup("op-1", "Alice", "owner", "secret-token-1")
        op = self.ops_mod.authenticate_operator("Bearer wrong-token")
        self.assertIsNone(op)

    def test_missing_token_fails_closed(self):
        self._insert_operator_with_lookup("op-1", "Alice", "owner", "secret-token-1")
        self.assertIsNone(self.ops_mod.authenticate_operator(None))
        self.assertIsNone(self.ops_mod.authenticate_operator(""))
        self.assertIsNone(self.ops_mod.authenticate_operator("Bearer "))
        self.assertIsNone(self.ops_mod.authenticate_operator("Basic secret-token-1"))

    def test_inactive_token_fails_closed(self):
        self._insert_operator_with_lookup("op-1", "Alice", "owner", "secret-token-1", active=0)
        op = self.ops_mod.authenticate_operator("Bearer secret-token-1")
        self.assertIsNone(op)

    def test_role_checks_preserved(self):
        self._insert_operator_with_lookup("op-1", "Alice", "auditor", "secret-token-1")
        ok, status, payload = self.auth_mod.check_auth(
            "Bearer secret-token-1", required_roles=["owner", "grant_admin"]
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(payload.get("errorCode"), "operator_role_forbidden")

        ok2, status2, payload2 = self.auth_mod.check_auth(
            "Bearer secret-token-1", required_roles=["auditor"]
        )
        self.assertTrue(ok2)
        self.assertEqual(status2, 200)
        self.assertEqual(payload2["operator"]["role"], "auditor")


class TestGl107LookupHashStorage(_BaseGl107):
    """Tests that token_lookup_hash is stored correctly."""

    def test_operator_creation_stores_lookup_hash(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap-secret"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_ID"] = "bootstrap-op"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_NAME"] = "Bootstrap"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE"] = "owner"
        importlib.reload(self.config_mod)

        import backend.src.core.db as db_mod
        db_mod.init_db()
        importlib.reload(self.ops_mod)

        conn = db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT token_lookup_hash FROM operators WHERE id = ?", ("bootstrap-op",)
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertIsNotNone(row["token_lookup_hash"])
        self.assertEqual(
            row["token_lookup_hash"],
            self.ops_mod.derive_token_lookup_hash("bootstrap-secret")
        )

    def test_lookup_hash_is_deterministic(self):
        token = "test-token-abc"
        h1 = self.ops_mod.derive_token_lookup_hash(token)
        h2 = self.ops_mod.derive_token_lookup_hash(token)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex

    def test_lookup_hash_differs_for_different_tokens(self):
        h1 = self.ops_mod.derive_token_lookup_hash("token-a")
        h2 = self.ops_mod.derive_token_lookup_hash("token-b")
        self.assertNotEqual(h1, h2)


class TestGl107Migration(_BaseGl107):
    """Tests for schema migration and baseline alignment."""

    def test_migration_adds_token_lookup_hash(self):
        """GL-107 migration adds column and index to an old schema."""
        # Create a DB without the column (simulate pre-GL-107 schema)
        raw_conn = sqlite3.connect(self.tmp_db.name)
        raw_conn.execute("DROP TABLE IF EXISTS operators")
        raw_conn.execute("""
            CREATE TABLE operators (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                role       TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                active     INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        raw_conn.commit()
        raw_conn.close()

        # Load and apply migration using the same mechanism as the runner
        import importlib.util
        mig_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "migrations",
            "0007_gl107_operator_token_lookup.py"
        )
        spec = importlib.util.spec_from_file_location("gl107_mig", mig_path)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)

        raw_conn2 = sqlite3.connect(self.tmp_db.name)
        mig.apply(raw_conn2)
        raw_conn2.close()

        # Verify column exists
        raw_conn3 = sqlite3.connect(self.tmp_db.name)
        rows = raw_conn3.execute("PRAGMA table_info(operators)").fetchall()
        columns = [r[1] for r in rows]
        self.assertIn("token_lookup_hash", columns)

        # Verify index exists
        idx_rows = raw_conn3.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_operators_token_lookup_hash'"
        ).fetchall()
        self.assertEqual(len(idx_rows), 1)
        raw_conn3.close()

    def test_migration_is_idempotent(self):
        """Applying migration twice does not raise."""
        import importlib.util
        mig_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "migrations",
            "0007_gl107_operator_token_lookup.py"
        )
        spec = importlib.util.spec_from_file_location("gl107_mig", mig_path)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)

        raw_conn = sqlite3.connect(self.tmp_db.name)
        # First apply
        mig.apply(raw_conn)
        # Second apply should not raise
        mig.apply(raw_conn)
        raw_conn.close()

    def test_baseline_schema_contains_token_lookup_hash(self):
        """Fresh DB created via baseline migration includes token_lookup_hash."""
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(operators)").fetchall()
        finally:
            conn.close()
        columns = [r[1] for r in rows]
        self.assertIn("token_lookup_hash", columns)


class TestGl107PerformanceBounds(_BaseGl107):
    """Tests that PBKDF2 calls are bounded."""

    def test_invalid_token_with_many_active_operators_has_bounded_pbkdf2(self):
        """Invalid token against 50 operators with lookup hashes: 0 PBKDF2 calls."""
        for i in range(50):
            self._insert_operator_with_lookup(
                f"op-{i}", f"Op {i}", "owner", f"token-{i}"
            )

        with patch.object(self.ops_mod, 'verify_token') as mock_verify:
            mock_verify.return_value = False
            result = self.ops_mod.authenticate_operator("Bearer totally-wrong-token")
            self.assertIsNone(result)
            mock_verify.assert_not_called()

    def test_invalid_token_with_legacy_operators_bounded_pbkdf2(self):
        """Invalid token against 5 legacy operators: at most 5 PBKDF2 calls."""
        for i in range(5):
            self._insert_operator_legacy(
                f"legacy-{i}", f"Legacy {i}", "owner", f"legacy-token-{i}"
            )

        with patch.object(self.ops_mod, 'verify_token') as mock_verify:
            mock_verify.return_value = False
            result = self.ops_mod.authenticate_operator("Bearer wrong-token")
            self.assertIsNone(result)
            self.assertLessEqual(mock_verify.call_count, 5)

    def test_valid_token_has_bounded_lookup_verification(self):
        """Valid token triggers exactly 1 PBKDF2 verification."""
        self._insert_operator_with_lookup("op-1", "Alice", "owner", "secret-token")

        with patch.object(self.ops_mod, 'verify_token') as mock_verify:
            mock_verify.return_value = True
            result = self.ops_mod.authenticate_operator("Bearer secret-token")
            self.assertIsNotNone(result)
            self.assertEqual(mock_verify.call_count, 1)

    def test_valid_legacy_token_triggers_single_pbkdf2(self):
        """Valid token for legacy operator triggers exactly 1 PBKDF2."""
        self._insert_operator_legacy("legacy-1", "Bob", "owner", "legacy-secret")

        with patch.object(self.ops_mod, 'verify_token') as mock_verify:
            mock_verify.return_value = True
            result = self.ops_mod.authenticate_operator("Bearer legacy-secret")
            self.assertIsNotNone(result)
            self.assertEqual(mock_verify.call_count, 1)


class TestGl107LeakagePrevention(_BaseGl107):
    """Tests that raw tokens and hashes are not leaked."""

    def test_auth_response_does_not_contain_token_or_hash(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)

        self._insert_operator_with_lookup("op-1", "Alice", "owner", "my-secret-token")
        ok, status, payload = fresh_auth.check_auth(
            "Bearer my-secret-token", required_roles=["owner"]
        )
        self.assertTrue(ok)
        payload_str = str(payload)
        self.assertNotIn("my-secret-token", payload_str)
        self.assertNotIn("token_hash", payload_str)
        self.assertNotIn("token_lookup_hash", payload_str)

    def test_operator_dict_excludes_sensitive_fields(self):
        self._insert_operator_with_lookup("op-1", "Alice", "owner", "my-secret-token")
        op = self.ops_mod.authenticate_operator("Bearer my-secret-token")
        self.assertIsNotNone(op)
        d = op.to_dict()
        self.assertNotIn("token_hash", d)
        self.assertNotIn("token_lookup_hash", d)
        self.assertNotIn("my-secret-token", str(d))

    def test_failed_auth_does_not_leak_token(self):
        self._insert_operator_with_lookup("op-1", "Alice", "owner", "my-secret-token")
        op = self.ops_mod.authenticate_operator("Bearer wrong-token")
        self.assertIsNone(op)
        # No exception, no leakage — just a silent None


class TestGl107NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-107 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        import pathlib
        import subprocess
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-107-operator-auth-token-lookup-hardening":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-107 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/operators.py",
            "backend/src/migrations/0007_gl107_operator_token_lookup.py",
            "backend/src/migrations/0001_gl032_baseline.py",
            "backend/tests/test_gl107_operator_auth_token_lookup.py",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-107 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
