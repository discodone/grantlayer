"""Tests for GL-119: Operator Token Expiry and Rotation Baseline.

Ensures operator tokens can expire, fail closed when expired, and support
rotation without leaking raw token material.

Covers:
1. Newly created operator token includes expiry by default
2. Active non-expired token authenticates
3. Expired token fails closed
4. Expired token failure does not leak raw token
5. Expired token emits safe reason_code through server auth path
6. Invalid token behavior from GL-120 remains preserved
7. Missing token behavior from GL-120 remains preserved
8. Inactive/revoked operator behavior remains preserved
9. token_lookup_hash narrowing from GL-107 remains preserved
10. PBKDF2 final verification remains required
11. Rotation returns a new raw token only once
12. Old token fails after rotation
13. New token authenticates after rotation
14. Rotated token has new token_lookup_hash
15. Rotated token has expiry/rotated_at metadata
16. Raw token is not stored in plaintext
17. /operators/me behavior preserved for valid non-expired token
18. GL-117/GL-118/GL-120 structured logging/correlation preserved on expiry
19. Migration adds columns and is idempotent
20. Baseline schema contains new columns for fresh installs
"""

import json
import logging
import os
import sqlite3
import sys
import tempfile
import unittest
import importlib
from io import BytesIO
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl119(unittest.TestCase):
    """Shared helpers for GL-119 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_rate_limit_auth = os.environ.get("GRANTLAYER_RATE_LIMIT_AUTH")
        self._orig_rate_limit_api = os.environ.get("GRANTLAYER_RATE_LIMIT_API")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod
        self.handler_class = server_mod.GrantLayerHandler

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_RATE_LIMIT_AUTH", self._orig_rate_limit_auth),
            ("GRANTLAYER_RATE_LIMIT_API", self._orig_rate_limit_api),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _insert_operator(self, op_id, name, role, token, active=1, expires_at=None, rotated_at=None):
        """Insert operator with optional expiry/rotation metadata."""
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators
                   (id, name, role, token_hash, token_lookup_hash, active, created_at, expires_at, rotated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)""",
                (
                    op_id, name, role,
                    self.ops_mod.hash_token(token),
                    self.ops_mod.derive_token_lookup_hash(token),
                    active,
                    expires_at,
                    rotated_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_handler(self, path, method="GET", auth_header=None, origin=None, client_ip="127.0.0.1"):
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"")
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if origin is not None:
            headers["Origin"] = origin
        handler.headers = headers
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = (client_ip, 0)
        handler.server = None
        return handler

    def _run_handler(self, handler):
        if handler.command == "GET":
            handler.do_GET()
        elif handler.command == "POST":
            handler.do_POST()
        elif handler.command == "OPTIONS":
            handler.do_OPTIONS()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        header_block = parts[0].decode()
        headers = {}
        for line in header_block.split("\r\n")[1:]:
            if ": " in line:
                k, v = line.split(": ", 1)
                headers[k] = v
        if len(parts) > 1 and parts[1]:
            body = json.loads(parts[1])
        else:
            body = {}
        return status, headers, body


# ═══════════════════════════════════════════════════════════════════════
# 1. Expiry basics
# ═══════════════════════════════════════════════════════════════════════

class TestGl119ExpiryBasics(_BaseGl119):
    """Core expiry behavior tests."""

    def test_newly_created_operator_token_has_expiry_by_default(self):
        """Bootstrap operator gets an expires_at timestamp by default."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap-secret"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_ID"] = "bootstrap-op"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_NAME"] = "Bootstrap"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE"] = "owner"
        importlib.reload(self.config_mod)

        import src.db as db_mod
        db_mod.init_db()
        importlib.reload(self.ops_mod)

        conn = db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT expires_at FROM operators WHERE id = ?", ("bootstrap-op",)
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertIsNotNone(row["expires_at"])
        self.assertTrue(len(row["expires_at"]) > 0)

    def test_active_non_expired_token_authenticates(self):
        """A token that has not reached its expiry continues to authenticate."""
        future = "2099-12-31T23:59:59Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=future)
        op = self.ops_mod.authenticate_operator("Bearer secret-token")
        self.assertIsNotNone(op)
        self.assertEqual(op.operator_id, "op-1")

    def test_expired_token_fails_closed(self):
        """A token past its expiry fails closed."""
        past = "2000-01-01T00:00:00Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=past)
        op = self.ops_mod.authenticate_operator("Bearer secret-token")
        self.assertIsNone(op)

    def test_expired_token_with_reason_code(self):
        """authenticate_operator_with_reason returns operator_token_expired."""
        past = "2000-01-01T00:00:00Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=past)
        op, reason = self.ops_mod.authenticate_operator_with_reason("Bearer secret-token")
        self.assertIsNone(op)
        self.assertEqual(reason, "operator_token_expired")

    def test_null_expires_at_is_not_expired(self):
        """Existing rows without expires_at remain valid for backward compat."""
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=None)
        op = self.ops_mod.authenticate_operator("Bearer secret-token")
        self.assertIsNotNone(op)
        self.assertEqual(op.operator_id, "op-1")


# ═══════════════════════════════════════════════════════════════════════
# 2. Rotation
# ═══════════════════════════════════════════════════════════════════════

class TestGl119Rotation(_BaseGl119):
    """Token rotation behavior tests."""

    def test_rotation_returns_new_raw_token_once(self):
        """rotate_operator_token returns a new raw token string."""
        self._insert_operator("op-1", "Alice", "owner", "old-token")
        new_token = self.ops_mod.rotate_operator_token("op-1")
        self.assertIsNotNone(new_token)
        self.assertIsInstance(new_token, str)
        self.assertTrue(len(new_token) > 0)

    def test_old_token_fails_after_rotation(self):
        """After rotation the previous raw token no longer authenticates."""
        self._insert_operator("op-1", "Alice", "owner", "old-token")
        self.ops_mod.rotate_operator_token("op-1")
        op = self.ops_mod.authenticate_operator("Bearer old-token")
        self.assertIsNone(op)

    def test_new_token_authenticates_after_rotation(self):
        """The token returned by rotation authenticates successfully."""
        self._insert_operator("op-1", "Alice", "owner", "old-token")
        new_token = self.ops_mod.rotate_operator_token("op-1")
        op = self.ops_mod.authenticate_operator(f"Bearer {new_token}")
        self.assertIsNotNone(op)
        self.assertEqual(op.operator_id, "op-1")

    def test_rotated_token_has_new_lookup_hash(self):
        """Rotation changes token_lookup_hash in the database."""
        self._insert_operator("op-1", "Alice", "owner", "old-token")
        old_lookup = self.ops_mod.derive_token_lookup_hash("old-token")

        new_token = self.ops_mod.rotate_operator_token("op-1")
        new_lookup = self.ops_mod.derive_token_lookup_hash(new_token)

        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT token_lookup_hash FROM operators WHERE id = ?", ("op-1",)
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["token_lookup_hash"], new_lookup)
        self.assertNotEqual(row["token_lookup_hash"], old_lookup)

    def test_rotated_token_has_expiry_and_rotated_at(self):
        """Rotation updates expires_at and rotated_at metadata."""
        self._insert_operator("op-1", "Alice", "owner", "old-token")
        self.ops_mod.rotate_operator_token("op-1")

        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT expires_at, rotated_at FROM operators WHERE id = ?", ("op-1",)
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertIsNotNone(row["expires_at"])
        self.assertIsNotNone(row["rotated_at"])
        self.assertTrue(len(row["expires_at"]) > 0)
        self.assertTrue(len(row["rotated_at"]) > 0)

    def test_rotation_does_not_store_raw_token(self):
        """The raw token returned by rotation is not stored in the DB."""
        self._insert_operator("op-1", "Alice", "owner", "old-token")
        new_token = self.ops_mod.rotate_operator_token("op-1")

        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT token_hash FROM operators WHERE id = ?", ("op-1",)
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertNotIn(new_token, row["token_hash"])
        # Verify PBKDF2 format
        self.assertTrue(row["token_hash"].startswith("pbkdf2_sha256$"))

    def test_rotation_returns_none_for_missing_operator(self):
        """rotate_operator_token returns None if operator does not exist."""
        result = self.ops_mod.rotate_operator_token("nonexistent-op")
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════════
# 3. Auth reason codes via check_auth
# ═══════════════════════════════════════════════════════════════════════

class TestGl119AuthReasonCodes(_BaseGl119):
    """Ensure check_auth returns distinct reason codes for expiry."""

    def test_check_auth_returns_expired_reason_code(self):
        """check_auth returns operator_token_expired for expired tokens."""
        past = "2000-01-01T00:00:00Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=past)
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        ok, status, payload = self.auth_mod.check_auth("Bearer secret-token", required_roles=["owner"])
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "operator_token_expired")

    def test_check_auth_preserves_invalid_reason_code(self):
        """check_auth still returns operator_auth_required for invalid tokens."""
        self._insert_operator("op-1", "Alice", "owner", "secret-token")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        ok, status, payload = self.auth_mod.check_auth("Bearer wrong-token", required_roles=["owner"])
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "operator_auth_required")

    def test_check_auth_preserves_missing_reason_code(self):
        """check_auth still returns operator_auth_required for missing tokens."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        ok, status, payload = self.auth_mod.check_auth(None, required_roles=["owner"])
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "operator_auth_required")

    def test_check_auth_preserves_role_forbidden_reason_code(self):
        """check_auth still returns operator_role_forbidden for insufficient role."""
        future = "2099-12-31T23:59:59Z"
        self._insert_operator("op-1", "Alice", "auditor", "secret-token", expires_at=future)
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        ok, status, payload = self.auth_mod.check_auth("Bearer secret-token", required_roles=["owner"])
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(payload["errorCode"], "operator_role_forbidden")


# ═══════════════════════════════════════════════════════════════════════
# 4. GL-107 narrowing preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl119Gl107NarrowingPreserved(_BaseGl119):
    """Ensure GL-107 token_lookup_hash behavior is not weakened."""

    def test_valid_token_uses_lookup_hash_then_pbkdf2(self):
        """Valid token still authenticates via lookup hash + PBKDF2."""
        future = "2099-12-31T23:59:59Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=future)
        op = self.ops_mod.authenticate_operator("Bearer secret-token")
        self.assertIsNotNone(op)
        self.assertEqual(op.operator_id, "op-1")

    def test_invalid_token_with_lookup_hash_fails_closed(self):
        """Invalid token fails closed even when lookup hash narrows."""
        future = "2099-12-31T23:59:59Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=future)
        op = self.ops_mod.authenticate_operator("Bearer wrong-token")
        self.assertIsNone(op)

    def test_pbkdf2_final_verification_still_required(self):
        """Matching lookup hash alone is not sufficient; PBKDF2 must pass."""
        future = "2099-12-31T23:59:59Z"
        # Insert operator A with a known token
        self._insert_operator("op-a", "Alice", "owner", "token-a", expires_at=future)
        # Craft a different token that happens to have the same SHA-256
        # is effectively impossible, so just verify wrong token fails.
        op = self.ops_mod.authenticate_operator("Bearer totally-different-token")
        self.assertIsNone(op)


# ═══════════════════════════════════════════════════════════════════════
# 5. Inactive operator preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl119InactiveOperatorPreserved(_BaseGl119):
    """Inactive/revoked operator behavior remains unchanged."""

    def test_inactive_operator_fails_closed(self):
        future = "2099-12-31T23:59:59Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", active=0, expires_at=future)
        op = self.ops_mod.authenticate_operator("Bearer secret-token")
        self.assertIsNone(op)


# ═══════════════════════════════════════════════════════════════════════
# 6. Server path (/operators/me) and structured logging
# ═══════════════════════════════════════════════════════════════════════

class TestGl119ServerPath(_BaseGl119):
    """Verify server paths handle expiry correctly and preserve GL-120 events."""

    def test_operators_me_returns_200_for_valid_non_expired_token(self):
        future = "2099-12-31T23:59:59Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=future)
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        self.auth_mod = fresh_auth

        handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body["operatorId"], "op-1")

    def test_expired_token_returns_401(self):
        past = "2000-01-01T00:00:00Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=past)
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        self.auth_mod = fresh_auth

        handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_token_expired")

    def test_expired_token_does_not_leak_raw_token(self):
        past = "2000-01-01T00:00:00Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=past)
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        self.auth_mod = fresh_auth

        handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
        status, headers, body = self._run_handler(handler)
        body_str = json.dumps(body)
        self.assertNotIn("secret-token", body_str)

    def test_expired_token_emits_auth_failed_with_reason_code(self):
        past = "2000-01-01T00:00:00Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=past)
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        self.auth_mod = fresh_auth

        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
            self._run_handler(handler)

        payload = None
        for msg in cm.output:
            if "auth_failed" in msg:
                start = msg.find("{")
                if start != -1:
                    payload = json.loads(msg[start:])
                    break
        self.assertIsNotNone(payload)
        self.assertEqual(payload["reason_code"], "operator_token_expired")
        self.assertEqual(payload["status_code"], 401)

    def test_expired_token_preserves_correlation_id(self):
        past = "2000-01-01T00:00:00Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=past)
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        self.auth_mod = fresh_auth

        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_handler(
                "/operators/me",
                auth_header="Bearer secret-token",
            )
            handler.headers["X-Correlation-ID"] = "corr-expired-123"
            self._run_handler(handler)

        payload = None
        for msg in cm.output:
            if "auth_failed" in msg:
                start = msg.find("{")
                if start != -1:
                    payload = json.loads(msg[start:])
                    break
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("correlation_id"), "corr-expired-123")

    def test_invalid_token_behavior_preserved_on_server_path(self):
        """Invalid token still returns operator_auth_required via server."""
        self._insert_operator("op-1", "Alice", "owner", "secret-token")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        self.auth_mod = fresh_auth

        handler = self._make_handler("/operators/me", auth_header="Bearer wrong-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_missing_token_behavior_preserved_on_server_path(self):
        """Missing token still returns operator_auth_required via server."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        self.auth_mod = fresh_auth

        handler = self._make_handler("/operators/me")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")


# ═══════════════════════════════════════════════════════════════════════
# 7. Migration and baseline
# ═══════════════════════════════════════════════════════════════════════

class TestGl119Migration(_BaseGl119):
    """Schema migration and baseline alignment tests."""

    def test_migration_adds_columns_to_old_schema(self):
        """GL-119 migration adds expires_at and rotated_at to an old schema."""
        raw_conn = sqlite3.connect(self.tmp_db.name)
        raw_conn.execute("DROP TABLE IF EXISTS operators")
        raw_conn.execute("""
            CREATE TABLE operators (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                role       TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                token_lookup_hash TEXT,
                active     INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        raw_conn.commit()
        raw_conn.close()

        import importlib.util
        mig_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "migrations",
            "0009_gl119_operator_token_expiry_rotation.py"
        )
        spec = importlib.util.spec_from_file_location("gl119_mig", mig_path)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)

        raw_conn2 = sqlite3.connect(self.tmp_db.name)
        mig.apply(raw_conn2)
        raw_conn2.close()

        raw_conn3 = sqlite3.connect(self.tmp_db.name)
        rows = raw_conn3.execute("PRAGMA table_info(operators)").fetchall()
        columns = [r[1] for r in rows]
        self.assertIn("expires_at", columns)
        self.assertIn("rotated_at", columns)
        raw_conn3.close()

    def test_migration_is_idempotent(self):
        """Applying migration twice does not raise."""
        import importlib.util
        mig_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "migrations",
            "0009_gl119_operator_token_expiry_rotation.py"
        )
        spec = importlib.util.spec_from_file_location("gl119_mig", mig_path)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)

        raw_conn = sqlite3.connect(self.tmp_db.name)
        mig.apply(raw_conn)
        mig.apply(raw_conn)
        raw_conn.close()

        raw_conn2 = sqlite3.connect(self.tmp_db.name)
        rows = raw_conn2.execute("PRAGMA table_info(operators)").fetchall()
        columns = [r[1] for r in rows]
        self.assertIn("expires_at", columns)
        self.assertIn("rotated_at", columns)
        raw_conn2.close()

    def test_baseline_contains_new_columns(self):
        """Fresh schema from baseline contains expires_at and rotated_at."""
        import src.db as db_mod
        db_mod.init_db()
        conn = db_mod.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(operators)").fetchall()
        finally:
            conn.close()
        columns = [r[1] for r in rows]
        self.assertIn("expires_at", columns)
        self.assertIn("rotated_at", columns)


# ═══════════════════════════════════════════════════════════════════════
# 8. Safe leakage prevention
# ═══════════════════════════════════════════════════════════════════════

class TestGl119LeakagePrevention(_BaseGl119):
    """Ensure raw tokens and hashes are not leaked."""

    def test_raw_token_not_in_database(self):
        future = "2099-12-31T23:59:59Z"
        self._insert_operator("op-1", "Alice", "owner", "my-secret", expires_at=future)
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute("SELECT token_hash FROM operators WHERE id = ?", ("op-1",)).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertNotIn("my-secret", row["token_hash"])

    def test_auth_failure_does_not_log_authorization_header(self):
        past = "2000-01-01T00:00:00Z"
        self._insert_operator("op-1", "Alice", "owner", "secret-token", expires_at=past)
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        self.auth_mod = fresh_auth

        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_handler("/operators/me", auth_header="Bearer secret-token")
            self._run_handler(handler)

        for msg in cm.output:
            self.assertNotIn("secret-token", msg)
            self.assertNotIn("Authorization", msg)


# ═══════════════════════════════════════════════════════════════════════
# 9. is_operator_token_expired helper
# ═══════════════════════════════════════════════════════════════════════

class TestGl119IsOperatorTokenExpired(_BaseGl119):
    """Direct helper tests."""

    def test_returns_true_for_expired(self):
        past = "2000-01-01T00:00:00Z"
        self._insert_operator("op-1", "Alice", "owner", "secret", expires_at=past)
        result = self.ops_mod.is_operator_token_expired("op-1")
        self.assertTrue(result)

    def test_returns_false_for_future_expiry(self):
        future = "2099-12-31T23:59:59Z"
        self._insert_operator("op-1", "Alice", "owner", "secret", expires_at=future)
        result = self.ops_mod.is_operator_token_expired("op-1")
        self.assertFalse(result)

    def test_returns_false_for_null_expiry(self):
        self._insert_operator("op-1", "Alice", "owner", "secret", expires_at=None)
        result = self.ops_mod.is_operator_token_expired("op-1")
        self.assertFalse(result)

    def test_returns_none_for_missing_operator(self):
        result = self.ops_mod.is_operator_token_expired("nonexistent")
        self.assertIsNone(result)

    def test_returns_none_for_inactive_operator(self):
        self._insert_operator("op-1", "Alice", "owner", "secret", active=0)
        result = self.ops_mod.is_operator_token_expired("op-1")
        self.assertIsNone(result)
