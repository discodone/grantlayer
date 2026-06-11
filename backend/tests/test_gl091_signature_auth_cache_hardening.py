"""Tests for GL-091 Signature Verification Broad-Except Hardening + Auth Cache Key Hardening.

Ensures:
- verify_grant_signature does not catch broad Exception.
- InvalidSignature and ValueError still return "invalid".
- Unexpected infrastructure/key-load/programming errors are not silently swallowed.
- Python hash(auth_header) is not used for auth cache keying.
- Stable cryptographic digest (SHA-256 hex) is used for auth header cache key.
- Raw Authorization header/token is not stored directly as cache key.
- Existing auth success/failure behavior is preserved.
- Missing auth still returns 401 safe JSON on protected endpoints.
- Valid auth still succeeds on representative endpoints.
- All prior GL protections remain intact (GL-090, GL-089, GL-088, GL-087, GL-084).
- GET /health and GET /readiness remain public.
"""

import json
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl091(unittest.TestCase):
    """Shared helpers for GL-091 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.challenges as challenges_mod
        importlib.reload(challenges_mod)
        self.challenges_mod = challenges_mod

        import backend.src.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        self.crypto_mod = crypto_mod

        import backend.src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

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

    def _make_grant(self):
        return self.models_mod.Grant(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2030-01-01T00:00:00Z",
            created_by="owner-1",
            reason="test",
        )

    def _make_handler(self, path, method="GET", auth_header=None, body=b""):
        import backend.src.server as server_mod
        importlib.reload(server_mod)
        handler_class = server_mod.GrantLayerHandler
        from io import BytesIO

        handler = handler_class.__new__(handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if body:
            headers["Content-Length"] = str(len(body))
        handler.headers = headers
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        return handler

    def _run_handler(self, handler):
        if handler.command == "GET":
            handler.do_GET()
        elif handler.command == "POST":
            handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        body = json.loads(parts[1]) if len(parts) > 1 else {}
        return status, body

    def _assert_gl030_full(self, payload):
        self.assertIn("error", payload)
        self.assertIn("errorCode", payload)
        self.assertIn("reason", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)

    def _assert_no_secrets_in_body(self, body):
        body_str = json.dumps(body).lower()
        forbidden_terms = [
            "password", "api_key", "traceback", "exception",
            "postgresql://", "db_url", "secret_value", "private_key",
        ]
        for term in forbidden_terms:
            self.assertNotIn(term, body_str, f"Error response contains forbidden term: {term}")

    def _valid_challenge_body(self):
        return json.dumps({
            "subjectId": "sub-1",
            "action": "read",
            "resource": "repo-a",
        }).encode()

    def _grant_body(self):
        return json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2020-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "owner-1",
            "reason": "test",
        }).encode()


class TestGl091SignatureVerificationHardening(_BaseGl091):
    """Tests for signature verification broad-except removal."""

    def setUp(self):
        super().setUp()
        self.crypto_mod.ensure_demo_keypair()

    def test_valid_signature_verifies_successfully(self):
        grant = self._make_grant()
        sig, phash, key_id = self.crypto_mod.sign_grant(grant)
        grant.signature = sig
        grant.payload_hash = phash
        grant.signing_key_id = key_id
        result = self.crypto_mod.verify_grant_signature(grant)
        self.assertEqual(result, "valid")

    def test_invalid_signature_returns_invalid(self):
        grant = self._make_grant()
        sig, phash, key_id = self.crypto_mod.sign_grant(grant)
        # XOR first byte — guaranteed different regardless of signature value
        sig_bytes = bytearray(bytes.fromhex(sig))
        sig_bytes[0] ^= 0xFF
        grant.signature = sig_bytes.hex()
        grant.payload_hash = phash
        grant.signing_key_id = key_id
        result = self.crypto_mod.verify_grant_signature(grant)
        self.assertEqual(result, "invalid")

    def test_missing_signature_returns_missing(self):
        grant = self._make_grant()
        result = self.crypto_mod.verify_grant_signature(grant)
        self.assertEqual(result, "missing")

    def test_hash_mismatch_returns_hash_mismatch(self):
        grant = self._make_grant()
        sig, phash, key_id = self.crypto_mod.sign_grant(grant)
        grant.signature = sig
        grant.payload_hash = "a" * 64
        grant.signing_key_id = key_id
        result = self.crypto_mod.verify_grant_signature(grant)
        self.assertEqual(result, "hash_mismatch")

    def test_unexpected_key_load_error_not_swallowed(self):
        """Infrastructure errors from load_public_key must propagate, not return 'invalid'."""
        grant = self._make_grant()
        sig, phash, key_id = self.crypto_mod.sign_grant(grant)
        grant.signature = sig
        grant.payload_hash = phash
        grant.signing_key_id = key_id

        original_load = self.crypto_mod.load_public_key
        def _failing_load():
            raise RuntimeError("simulated key load failure")

        self.crypto_mod.load_public_key = _failing_load
        try:
            with self.assertRaises(RuntimeError) as ctx:
                self.crypto_mod.verify_grant_signature(grant)
            self.assertIn("simulated key load failure", str(ctx.exception))
        finally:
            self.crypto_mod.load_public_key = original_load

    def test_unexpected_permission_error_not_swallowed(self):
        """Permissions/OSError from file access must propagate, not return 'invalid'."""
        grant = self._make_grant()
        sig, phash, key_id = self.crypto_mod.sign_grant(grant)
        grant.signature = sig
        grant.payload_hash = phash
        grant.signing_key_id = key_id

        original_load = self.crypto_mod.load_public_key
        def _failing_load():
            raise PermissionError("simulated permission denied")

        self.crypto_mod.load_public_key = _failing_load
        try:
            with self.assertRaises(PermissionError) as ctx:
                self.crypto_mod.verify_grant_signature(grant)
            self.assertIn("simulated permission denied", str(ctx.exception))
        finally:
            self.crypto_mod.load_public_key = original_load

    def test_verify_grant_signature_no_broad_exception(self):
        """The source code must not contain a bare Exception catch in verify_grant_signature."""
        source = inspect.getsource(self.crypto_mod.verify_grant_signature)
        # Ensure broad Exception is not in the except clause
        lines = source.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("except") and "Exception" in stripped:
                # Allow specific exception types like InvalidSignature, ValueError
                # but not bare Exception
                self.assertNotIn(
                    "Exception",
                    stripped,
                    f"verify_grant_signature still catches broad Exception: {stripped}",
                )


class TestGl091AuthCacheKeyHardening(_BaseGl091):
    """Tests for auth cache key hardening."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_hash_auth_header_not_used_in_source(self):
        """The server source must not call Python built-in hash() on auth_header."""
        source = inspect.getsource(self.server_mod)
        for line in source.splitlines():
            self.assertNotIn("hash(auth_header)", line, f"Found hash(auth_header) in server.py: {line.strip()}")

    def test_stable_cryptographic_digest_used_for_admin_cache(self):
        handler = self._make_handler("/grants", auth_header="Bearer owner-token")
        # Trigger auth via _require_admin path (legacy mode)
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "owner-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server

        handler = self._make_handler("/grants", auth_header="Bearer owner-token")
        handler.do_GET()
        auth_cache = getattr(handler, "_auth_cache", {})
        # Cache key should be ("admin", <hex digest>) not ("admin", <int hash>)
        for key in auth_cache:
            self.assertEqual(key[0], "admin")
            digest = key[1]
            self.assertIsNotNone(digest)
            self.assertIsInstance(digest, str)
            self.assertEqual(len(digest), 64)  # SHA-256 hex is 64 chars
            # Verify it's a valid hex string
            try:
                int(digest, 16)
            except ValueError:
                self.fail(f"Cache key digest is not valid hex: {digest}")
            # Verify it matches expected SHA-256
            expected = hashlib.sha256("Bearer owner-token".encode("utf-8")).hexdigest()
            self.assertEqual(digest, expected)

    def test_stable_cryptographic_digest_used_for_operator_cache(self):
        handler = self._make_handler("/grants", auth_header="Bearer owner-token")
        handler.do_GET()
        auth_cache = getattr(handler, "_auth_cache", {})
        for key in auth_cache:
            self.assertEqual(key[0], "operator")
            digest = key[2]
            self.assertIsNotNone(digest)
            self.assertIsInstance(digest, str)
            self.assertEqual(len(digest), 64)
            try:
                int(digest, 16)
            except ValueError:
                self.fail(f"Cache key digest is not valid hex: {digest}")
            expected = hashlib.sha256("Bearer owner-token".encode("utf-8")).hexdigest()
            self.assertEqual(digest, expected)

    def test_raw_auth_token_not_stored_in_cache_key(self):
        handler = self._make_handler("/grants", auth_header="Bearer owner-token")
        handler.do_GET()
        auth_cache = getattr(handler, "_auth_cache", {})
        for key in auth_cache:
            key_str = json.dumps(key)
            self.assertNotIn("owner-token", key_str)
            self.assertNotIn("Bearer", key_str)

    def test_none_auth_header_cache_key_is_none(self):
        handler = self._make_handler("/grants", auth_header=None)
        handler.do_GET()
        auth_cache = getattr(handler, "_auth_cache", {})
        for key in auth_cache:
            if key[0] == "operator":
                self.assertIsNone(key[2])
            elif key[0] == "admin":
                self.assertIsNone(key[1])

    def test_auth_cache_is_request_local(self):
        handler1 = self._make_handler("/grants", auth_header="Bearer owner-token")
        handler2 = self._make_handler("/grants", auth_header="Bearer owner-token")
        handler1.do_GET()
        handler2.do_GET()
        self.assertTrue(hasattr(handler1, "_auth_cache"))
        self.assertTrue(hasattr(handler2, "_auth_cache"))
        # Each handler should have its own cache dict
        self.assertIsNot(handler1._auth_cache, handler2._auth_cache)


class TestGl091AuthBehaviorPreserved(_BaseGl091):
    """Tests ensuring existing auth behavior is preserved after hardening."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("demo-1", "Demo", "demo_operator", "demo-token")

    def test_missing_auth_returns_401_safe_json(self):
        handler = self._make_handler("/grants")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_valid_auth_succeeds(self):
        handler = self._make_handler("/grants", auth_header="Bearer owner-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_invalid_role_returns_403_safe_json(self):
        handler = self._make_handler("/grants", auth_header="Bearer demo-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_role_forbidden")


class TestGl091PriorGLProtections(_BaseGl091):
    """Regression tests ensuring prior GL protections stay intact."""

    def test_gl090_request_body_json_hardening_intact(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

        # Oversized body should still return 413
        oversized = b"x" * (self.server_mod.MAX_JSON_BODY_BYTES + 1)
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token",
            body=oversized,
        )
        handler.headers["Content-Length"] = str(len(oversized))
        status, body = self._run_handler(handler)
        self.assertEqual(status, 413)
        self.assertEqual(body.get("errorCode"), "payload_too_large")

    def test_gl088_post_challenges_still_protected(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

        handler = self._make_handler("/challenges", method="POST", body=self._valid_challenge_body())
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_gl087_auth_error_response_consistency_intact(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

        handler = self._make_handler("/grants")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")
        self.assertEqual(body.get("reason"), "Operator authentication is required.")

    def test_gl084_demo_action_still_protected(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("demo-1", "Demo", "demo_operator", "demo-token")

        demo_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/demo-action", method="POST", body=demo_body)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_health_public(self):
        handler = self._make_handler("/health")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_public(self):
        handler = self._make_handler("/readiness")
        status, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))


class TestGl091LegacyMode(_BaseGl091):
    """Auth cache key hardening in legacy admin-token mode."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-admin-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.auth_mod = fresh_auth

    def test_legacy_admin_cache_uses_sha256(self):
        handler = self._make_handler("/grants", auth_header="Bearer legacy-admin-token")
        handler.do_GET()
        auth_cache = getattr(handler, "_auth_cache", {})
        for key in auth_cache:
            self.assertEqual(key[0], "admin")
            digest = key[1]
            self.assertIsNotNone(digest)
            self.assertIsInstance(digest, str)
            self.assertEqual(len(digest), 64)
            expected = hashlib.sha256("Bearer legacy-admin-token".encode("utf-8")).hexdigest()
            self.assertEqual(digest, expected)

    def test_legacy_missing_auth_returns_401(self):
        handler = self._make_handler("/grants")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_legacy_valid_auth_succeeds(self):
        handler = self._make_handler("/grants", auth_header="Bearer legacy-admin-token")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)


class TestGl091NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-091 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-091-signature-auth-cache-hardening":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-091 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/crypto_signing.py",
            "backend/src/server.py",
            "backend/tests/test_gl091_signature_auth_cache_hardening.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-091 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
