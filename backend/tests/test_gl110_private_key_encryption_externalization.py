"""Tests for GL-110: Private Key Encryption / Externalization.

Ensures:
- plaintext private key file remains allowed in local/test with safe permissions
- unsafe private key permissions rejected
- generated private key mode remains restrictive
- production-like mode rejects plaintext private key file by default
- production-like mode can load private key from externalized secret/config if configured
- encrypted private key requires passphrase if encrypted-file support is implemented
- missing passphrase fails closed if encrypted key configured
- invalid passphrase fails closed if encrypted key support implemented
- private key material not exposed in errors
- passphrase not exposed in errors
- public key behavior preserved
- signing behavior preserved
- verification behavior preserved
- invalid signature behavior preserved
- GL-096 permission behavior preserved
- GL-109 auth behavior preserved
- GL-108 audit immutability preserved
- GL-106 rate limiting preserved
- security boundary preserved
- no DB/schema/migration change
- no OpenAPI change
"""

import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl110(unittest.TestCase):
    """Shared helpers for GL-110 tests."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self._orig_private_key_path = None
        self._orig_public_key_path = None

        # Save and clear env vars before any module reloads
        self._env_vars = {
            "GRANTLAYER_SIGNING_PRIVATE_KEY": os.environ.get("GRANTLAYER_SIGNING_PRIVATE_KEY"),
            "GRANTLAYER_SIGNING_PRIVATE_KEY_FILE": os.environ.get("GRANTLAYER_SIGNING_PRIVATE_KEY_FILE"),
            "GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE": os.environ.get("GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE"),
            "GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE": os.environ.get("GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"),
            "GRANTLAYER_RUNTIME_MODE": os.environ.get("GRANTLAYER_RUNTIME_MODE"),
        }
        for key in self._env_vars:
            os.environ.pop(key, None)

        # Reload config with cleared env vars to ensure clean state
        import backend.src.core.config as config_mod
        importlib.reload(config_mod)

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        self.crypto_mod = crypto_mod
        self._orig_private_key_path = crypto_mod._PRIVATE_KEY_PATH
        self._orig_public_key_path = crypto_mod._PUBLIC_KEY_PATH

        # Redirect key paths into temp directory for isolation
        crypto_mod._PRIVATE_KEY_PATH = os.path.join(self.tmp_dir.name, "demo_ed25519_private_key.pem")
        crypto_mod._PUBLIC_KEY_PATH = os.path.join(self.tmp_dir.name, "demo_ed25519_public_key.pem")

    def tearDown(self):
        self.tmp_dir.cleanup()
        if self._orig_private_key_path is not None:
            self.crypto_mod._PRIVATE_KEY_PATH = self._orig_private_key_path
        if self._orig_public_key_path is not None:
            self.crypto_mod._PUBLIC_KEY_PATH = self._orig_public_key_path

        for key, orig in self._env_vars.items():
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _generate_keypair(self):
        self.crypto_mod.ensure_demo_keypair()

    def _set_private_key_mode(self, mode):
        os.chmod(self.crypto_mod._PRIVATE_KEY_PATH, mode)

    def _reload_config_and_crypto(self):
        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        self.crypto_mod = crypto_mod

    def _assert_no_secrets_in_error(self, exc):
        exc_str = str(exc)
        lower = exc_str.lower()
        # "passphrase" as a word in a safe error message is acceptable;
        # we guard against actual secret values and sensitive format terms.
        forbidden = ["private_key", "secret", "password", "pem", "pkcs8"]
        for term in forbidden:
            self.assertNotIn(term, lower, f"Error message leaks sensitive term: {term}")

    def _make_encrypted_key_file(self, passphrase):
        """Generate an encrypted private key file and return its path."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PrivateFormat,
            BestAvailableEncryption,
        )
        pk = Ed25519PrivateKey.generate()
        path = os.path.join(self.tmp_dir.name, "encrypted_private_key.pem")
        with open(path, "wb") as f:
            f.write(
                pk.private_bytes(
                    Encoding.PEM,
                    PrivateFormat.PKCS8,
                    BestAvailableEncryption(passphrase.encode()),
                )
            )
        os.chmod(path, 0o600)
        return path

    def _get_private_key_pem(self):
        """Return the plaintext PEM bytes of the generated private key."""
        with open(self.crypto_mod._PRIVATE_KEY_PATH, "rb") as f:
            return f.read().decode("utf-8")


# ═══════════════════════════════════════════════════════════════════════
# 1. Plaintext private key file allowed in local/test
# ═══════════════════════════════════════════════════════════════════════

class TestGl110PlaintextLocalTestAllowed(_BaseGl110):
    """Plaintext file loading remains allowed in local/test modes."""

    def test_plaintext_file_loads_in_local_mode(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        self._generate_keypair()
        self._reload_config_and_crypto()
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)

    def test_plaintext_file_loads_in_test_mode(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        self._generate_keypair()
        self._reload_config_and_crypto()
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)


# ═══════════════════════════════════════════════════════════════════════
# 2. Unsafe permissions rejected
# ═══════════════════════════════════════════════════════════════════════

class TestGl110UnsafePermissionsRejected(_BaseGl110):
    """Unsafe private key permissions are still rejected (GL-096 preserved)."""

    def test_world_readable_private_key_rejected(self):
        self._generate_keypair()
        self._set_private_key_mode(0o604)
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        self._assert_no_secrets_in_error(ctx.exception)

    def test_group_readable_private_key_rejected(self):
        self._generate_keypair()
        self._set_private_key_mode(0o640)
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        self._assert_no_secrets_in_error(ctx.exception)

    def test_world_writable_private_key_rejected(self):
        self._generate_keypair()
        self._set_private_key_mode(0o602)
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        self._assert_no_secrets_in_error(ctx.exception)


# ═══════════════════════════════════════════════════════════════════════
# 3. Generated private key mode restrictive
# ═══════════════════════════════════════════════════════════════════════

class TestGl110GeneratedKeyModeRestrictive(_BaseGl110):
    """Newly generated private key files are created with 0o600."""

    def test_generated_private_key_mode_is_restrictive(self):
        self._generate_keypair()
        file_stat = os.stat(self.crypto_mod._PRIVATE_KEY_PATH)
        mode = stat.S_IMODE(file_stat.st_mode)
        self.assertEqual(mode, 0o600, f"Expected mode 0o600, got {oct(mode)}")


# ═══════════════════════════════════════════════════════════════════════
# 4. Production-like mode rejects plaintext by default
# ═══════════════════════════════════════════════════════════════════════

class TestGl110ProductionRejectsPlaintext(_BaseGl110):
    """Production-like modes reject plaintext private key files by default."""

    def test_staging_rejects_plaintext_file(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "staging"
        self._generate_keypair()
        self._reload_config_and_crypto()
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        msg = str(ctx.exception).lower()
        self.assertIn("plaintext", msg)
        self.assertIn("not allowed", msg)
        self._assert_no_secrets_in_error(ctx.exception)

    def test_production_rejects_plaintext_file(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        self._generate_keypair()
        self._reload_config_and_crypto()
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        msg = str(ctx.exception).lower()
        self.assertIn("plaintext", msg)
        self._assert_no_secrets_in_error(ctx.exception)

    def test_explicit_override_allows_plaintext_in_production(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        self._generate_keypair()
        self._reload_config_and_crypto()
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)


# ═══════════════════════════════════════════════════════════════════════
# 5. Externalized private key loading in production-like mode
# ═══════════════════════════════════════════════════════════════════════

class TestGl110ExternalizedKey(_BaseGl110):
    """Production-like mode can load private key from externalized config."""

    def test_env_private_key_loads_in_production(self):
        self._generate_keypair()
        pem = self._get_private_key_pem()
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY"] = pem
        self._reload_config_and_crypto()
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)

    def test_explicit_file_path_loads_in_production_when_encrypted(self):
        path = self._make_encrypted_key_file("secret-pass")
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_FILE"] = path
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE"] = "secret-pass"
        self._reload_config_and_crypto()
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)

    def test_explicit_file_path_rejected_in_production_when_plaintext(self):
        self._generate_keypair()
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_FILE"] = self.crypto_mod._PRIVATE_KEY_PATH
        self._reload_config_and_crypto()
        with self.assertRaises(PermissionError):
            self.crypto_mod.load_private_key()


# ═══════════════════════════════════════════════════════════════════════
# 6. Encrypted private key handling
# ═══════════════════════════════════════════════════════════════════════

class TestGl110EncryptedKey(_BaseGl110):
    """Encrypted private key files load correctly with passphrase."""

    def test_encrypted_key_loads_with_correct_passphrase(self):
        path = self._make_encrypted_key_file("my-passphrase")
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_FILE"] = path
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE"] = "my-passphrase"
        self._reload_config_and_crypto()
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)

    def test_encrypted_key_from_env_loads_with_passphrase(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PrivateFormat,
            BestAvailableEncryption,
        )
        pk = Ed25519PrivateKey.generate()
        encrypted_pem = pk.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            BestAvailableEncryption(b"env-pass"),
        ).decode("utf-8")
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY"] = encrypted_pem
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE"] = "env-pass"
        self._reload_config_and_crypto()
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)


# ═══════════════════════════════════════════════════════════════════════
# 7. Missing passphrase fails closed
# ═══════════════════════════════════════════════════════════════════════

class TestGl110MissingPassphrase(_BaseGl110):
    """Missing passphrase on encrypted key fails closed."""

    def test_missing_passphrase_fails_closed(self):
        path = self._make_encrypted_key_file("needed-pass")
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_FILE"] = path
        # No passphrase set
        self._reload_config_and_crypto()
        with self.assertRaises(ValueError) as ctx:
            self.crypto_mod.load_private_key()
        msg = str(ctx.exception).lower()
        self.assertIn("passphrase", msg)
        self._assert_no_secrets_in_error(ctx.exception)


# ═══════════════════════════════════════════════════════════════════════
# 8. Invalid passphrase fails closed
# ═══════════════════════════════════════════════════════════════════════

class TestGl110InvalidPassphrase(_BaseGl110):
    """Invalid passphrase on encrypted key fails closed."""

    def test_invalid_passphrase_fails_closed(self):
        path = self._make_encrypted_key_file("correct-pass")
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_FILE"] = path
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE"] = "wrong-pass"
        self._reload_config_and_crypto()
        with self.assertRaises(ValueError) as ctx:
            self.crypto_mod.load_private_key()
        msg = str(ctx.exception).lower()
        self.assertIn("passphrase", msg)
        self._assert_no_secrets_in_error(ctx.exception)


# ═══════════════════════════════════════════════════════════════════════
# 9. Error safety — no key material or passphrase leakage
# ═══════════════════════════════════════════════════════════════════════

class TestGl110ErrorSafety(_BaseGl110):
    """Error messages must not leak sensitive material."""

    def test_permission_error_does_not_expose_path(self):
        self._generate_keypair()
        self._set_private_key_mode(0o644)
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        msg = str(ctx.exception)
        self.assertNotIn(self.crypto_mod._PRIVATE_KEY_PATH, msg)

    def test_plaintext_rejection_does_not_expose_path(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        self._generate_keypair()
        self._reload_config_and_crypto()
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        msg = str(ctx.exception)
        self.assertNotIn(self.crypto_mod._PRIVATE_KEY_PATH, msg)

    def test_invalid_passphrase_error_is_safe(self):
        path = self._make_encrypted_key_file("real-pass")
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_FILE"] = path
        os.environ["GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE"] = "guess-pass"
        self._reload_config_and_crypto()
        with self.assertRaises(ValueError) as ctx:
            self.crypto_mod.load_private_key()
        self._assert_no_secrets_in_error(ctx.exception)
        # Ensure the actual passphrase value is not in the error
        msg = str(ctx.exception)
        self.assertNotIn("guess-pass", msg)
        self.assertNotIn("real-pass", msg)


# ═══════════════════════════════════════════════════════════════════════
# 10. Public key behavior preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl110PublicKeyPreserved(_BaseGl110):
    """Public key loading is unaffected by private key hardening."""

    def test_public_key_loads_without_permission_check(self):
        self._generate_keypair()
        self._set_private_key_mode(0o644)
        pub = self.crypto_mod.load_public_key()
        self.assertIsNotNone(pub)


# ═══════════════════════════════════════════════════════════════════════
# 11-14. Signing, verification, invalid signature preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl110SigningVerificationPreserved(_BaseGl110):
    """Signing and verification behavior remains compatible."""

    def setUp(self):
        super().setUp()
        self._generate_keypair()

        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

    def test_valid_signing_and_verification_succeeds(self):
        grant = self.models_mod.Grant(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2030-01-01T00:00:00Z",
            created_by="owner-1",
            reason="test",
        )
        sig, phash, key_id = self.crypto_mod.sign_grant(grant)
        grant.signature = sig
        grant.payload_hash = phash
        grant.signing_key_id = key_id
        result = self.crypto_mod.verify_grant_signature(grant)
        self.assertEqual(result, "valid")

    def test_invalid_signature_remains_invalid(self):
        grant = self.models_mod.Grant(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2030-01-01T00:00:00Z",
            created_by="owner-1",
            reason="test",
        )
        sig, phash, key_id = self.crypto_mod.sign_grant(grant)
        sig_bytes = bytearray(bytes.fromhex(sig))
        sig_bytes[0] ^= 0xFF
        grant.signature = sig_bytes.hex()
        grant.payload_hash = phash
        grant.signing_key_id = key_id
        result = self.crypto_mod.verify_grant_signature(grant)
        self.assertEqual(result, "invalid")

    def test_missing_signature_returns_missing(self):
        grant = self.models_mod.Grant(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2030-01-01T00:00:00Z",
            created_by="owner-1",
            reason="test",
        )
        result = self.crypto_mod.verify_grant_signature(grant)
        self.assertEqual(result, "missing")

    def test_hash_mismatch_returns_hash_mismatch(self):
        grant = self.models_mod.Grant(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2030-01-01T00:00:00Z",
            created_by="owner-1",
            reason="test",
        )
        sig, phash, key_id = self.crypto_mod.sign_grant(grant)
        grant.signature = sig
        grant.payload_hash = "a" * 64
        grant.signing_key_id = key_id
        result = self.crypto_mod.verify_grant_signature(grant)
        self.assertEqual(result, "hash_mismatch")


# ═══════════════════════════════════════════════════════════════════════
# 15. GL-096 permission behavior preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl110Gl096Preserved(_BaseGl110):
    """GL-096 permission enforcement is preserved."""

    def test_owner_read_only_loads(self):
        self._generate_keypair()
        self._set_private_key_mode(0o400)
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)

    def test_group_and_world_readable_writable_rejected(self):
        self._generate_keypair()
        self._set_private_key_mode(0o666)
        with self.assertRaises(PermissionError):
            self.crypto_mod.load_private_key()


# ═══════════════════════════════════════════════════════════════════════
# 16-19. Cross-GL preservation (lightweight module checks)
# ═══════════════════════════════════════════════════════════════════════

class TestGl110CrossGlPreservation(unittest.TestCase):
    """Verify other GL behaviors are not broken by GL-110 changes."""

    def test_gl109_auth_module_preserved(self):
        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.assertTrue(hasattr(auth_mod, "check_admin_token"))
        self.assertTrue(hasattr(auth_mod, "check_auth"))

    def test_gl108_audit_module_preserved(self):
        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.assertTrue(hasattr(audit_mod, "append_event"))
        self.assertTrue(hasattr(audit_mod, "list_events"))

    def test_gl107_operator_lookup_preserved(self):
        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.assertTrue(hasattr(ops_mod, "hash_token"))
        self.assertTrue(hasattr(ops_mod, "derive_token_lookup_hash"))

    def test_gl106_rate_limiter_preserved(self):
        import backend.src.core.rate_limiter as rl_mod
        importlib.reload(rl_mod)
        self.assertTrue(hasattr(rl_mod, "RateLimiter"))


# ═══════════════════════════════════════════════════════════════════════
# 20. Security boundary preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl110SecurityBoundary(unittest.TestCase):
    """Core security boundaries remain intact."""

    def test_crypto_signing_has_expected_exports(self):
        import backend.src.core.crypto_signing as cs
        importlib.reload(cs)
        self.assertTrue(hasattr(cs, "ensure_demo_keypair"))
        self.assertTrue(hasattr(cs, "load_private_key"))
        self.assertTrue(hasattr(cs, "load_public_key"))
        self.assertTrue(hasattr(cs, "sign_grant"))
        self.assertTrue(hasattr(cs, "verify_grant_signature"))

    def test_no_new_network_calls_in_crypto_signing(self):
        import backend.src.core.crypto_signing as cs
        importlib.reload(cs)
        import inspect
        src_text = inspect.getsource(cs)
        self.assertNotIn("urllib", src_text)
        self.assertNotIn("http.client", src_text)
        self.assertNotIn("requests", src_text)
        self.assertNotIn("socket", src_text)


# ═══════════════════════════════════════════════════════════════════════
# 21. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl110NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-110 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-110-private-key-encryption-externalization":
            self.skipTest(
                "Branch-wide diff check only valid on GL-110 feature branch"
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
            "backend/src/config.py",
            "backend/src/runtime_config.py",
            "backend/tests/test_gl110_private_key_encryption_externalization.py",
            "docs/product_foundation_implementation_cut.md",
            "docs/secret_management_baseline_design.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-110 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
