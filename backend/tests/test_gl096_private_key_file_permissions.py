"""Tests for GL-096 Private Key File Permission Enforcement.

Ensures:
- Generated private key files are created with restrictive owner-only permissions.
- Existing private key files with safe permissions load successfully.
- World-readable private key files are rejected.
- Group-readable private key files are rejected.
- Group/world-writable private key files are rejected.
- Public key behavior is preserved (no permission checks on public keys).
- Valid signing and verification still succeed.
- Invalid signature behavior remains unchanged.
- Error messages do not expose key material, secrets, or raw stack traces.
"""

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl096(unittest.TestCase):
    """Shared helpers for GL-096 tests."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self._orig_private_key_path = None
        self._orig_public_key_path = None

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

    def _generate_keypair(self):
        self.crypto_mod.ensure_demo_keypair()

    def _set_private_key_mode(self, mode):
        os.chmod(self.crypto_mod._PRIVATE_KEY_PATH, mode)

    def _assert_no_secrets_in_error(self, exc):
        exc_str = str(exc)
        lower = exc_str.lower()
        forbidden = ["private_key", "secret", "password", "pem", "pkcs8"]
        for term in forbidden:
            self.assertNotIn(term, lower, f"Error message leaks sensitive term: {term}")


class TestGl096GeneratedKeyPermissions(_BaseGl096):
    """Tests for newly generated private key file permissions."""

    def test_generated_private_key_mode_is_restrictive(self):
        self._generate_keypair()
        file_stat = os.stat(self.crypto_mod._PRIVATE_KEY_PATH)
        mode = stat.S_IMODE(file_stat.st_mode)
        self.assertEqual(mode, 0o600, f"Expected mode 0o600, got {oct(mode)}")


class TestGl096SafeExistingKeyLoads(_BaseGl096):
    """Tests that safe existing private key files load successfully."""

    def test_safe_existing_private_key_loads(self):
        self._generate_keypair()
        # Default is 0o600 after generation
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)

    def test_owner_read_only_loads(self):
        self._generate_keypair()
        self._set_private_key_mode(0o400)
        key = self.crypto_mod.load_private_key()
        self.assertIsNotNone(key)


class TestGl096UnsafePermissionsRejected(_BaseGl096):
    """Tests that unsafe private key permissions are rejected."""

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

    def test_group_writable_private_key_rejected(self):
        self._generate_keypair()
        self._set_private_key_mode(0o620)
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        self._assert_no_secrets_in_error(ctx.exception)

    def test_world_writable_private_key_rejected(self):
        self._generate_keypair()
        self._set_private_key_mode(0o602)
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        self._assert_no_secrets_in_error(ctx.exception)

    def test_group_and_world_readable_writable_rejected(self):
        self._generate_keypair()
        self._set_private_key_mode(0o666)
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        self._assert_no_secrets_in_error(ctx.exception)

    def test_error_message_is_safe(self):
        self._generate_keypair()
        self._set_private_key_mode(0o644)
        with self.assertRaises(PermissionError) as ctx:
            self.crypto_mod.load_private_key()
        msg = str(ctx.exception)
        self.assertIn("unsafe permissions", msg.lower())
        self.assertNotIn(self.crypto_mod._PRIVATE_KEY_PATH, msg)


class TestGl096PublicKeyBehaviorPreserved(_BaseGl096):
    """Tests that public key loading is unaffected by permission hardening."""

    def test_public_key_loads_without_permission_check(self):
        self._generate_keypair()
        # Even if private key has unsafe permissions, public key should still load
        self._set_private_key_mode(0o644)
        pub = self.crypto_mod.load_public_key()
        self.assertIsNotNone(pub)


class TestGl096SigningVerificationPreserved(_BaseGl096):
    """Tests that signing and verification behavior remains compatible."""

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


class TestGl096NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-096 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-096-private-key-file-permissions":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-096 feature branch"
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
            "backend/tests/test_gl096_private_key_file_permissions.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-096 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
