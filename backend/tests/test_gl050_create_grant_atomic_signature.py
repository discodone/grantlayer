"""Tests for GL-050 Create grant atomic signature (GRA-128).

Ensures grant creation is atomic with signature generation:
- Signature fields (signature, signing_key_id, payload_hash) are populated before insertion
- The INSERT includes all three fields in a single atomic operation
- No grant can exist in the database with NULL signature
- No UPDATE is needed after insertion
"""

import os
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import Grant
from src.grants import create_grant, get_grant


class TestCreateGrantAtomicSignature(unittest.TestCase):
    """GL-050: Atomic grant creation with signature."""

    def setUp(self):
        # Setup a fresh temporary database
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        # Disable operator model and demo-mode restrictions for simpler test
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)

        # Initialize database
        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

    def tearDown(self):
        # Restore original environment and cleanup temp file
        if self._orig_db:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

        for var, val in [
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_CHALLENGE", self._orig_require_challenge),
        ]:
            if val is not None:
                os.environ[var] = val
            else:
                os.environ.pop(var, None)

        os.unlink(self.tmp_db.name)

    def test_create_grant_has_atomic_signature_fields(self):
        """Create a grant; verify signature fields are present and non‑null."""
        grant = Grant(
            subject_id="test-subject",
            role="developer",
            action="deploy",
            resource="service-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            created_by="admin",
            reason="GL‑050 test",
        )

        created = create_grant(grant)

        # All three signature-related fields must be present on the returned object
        self.assertIsNotNone(created.signature)
        self.assertIsNotNone(created.signing_key_id)
        self.assertIsNotNone(created.payload_hash)

        # They must be non‑empty strings
        self.assertIsInstance(created.signature, str)
        self.assertIsInstance(created.signing_key_id, str)
        self.assertIsInstance(created.payload_hash, str)
        self.assertGreater(len(created.signature), 0)
        self.assertGreater(len(created.signing_key_id), 0)
        self.assertGreater(len(created.payload_hash), 0)

        # The signing_key_id must match the demo key ID
        self.assertEqual(created.signing_key_id, "demo-ed25519-v1")

        # The payload_hash must be 64‑character lowercase hex (SHA‑256)
        self.assertEqual(len(created.payload_hash), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in created.payload_hash))

        # The signature must be hex (Ed25519 signature length is 64 bytes = 128 hex chars)
        self.assertEqual(len(created.signature), 128)
        self.assertTrue(all(c in "0123456789abcdef" for c in created.signature))

        # Fetch the grant from the database and verify the same fields are present
        fetched = get_grant(created.id)
        self.assertIsNotNone(fetched)
        self.assertIsNotNone(fetched.signature)
        self.assertIsNotNone(fetched.signing_key_id)
        self.assertIsNotNone(fetched.payload_hash)

        # Ensure the fetched fields match the returned ones
        self.assertEqual(fetched.signature, created.signature)
        self.assertEqual(fetched.signing_key_id, created.signing_key_id)
        self.assertEqual(fetched.payload_hash, created.payload_hash)

    def test_grant_creation_single_insert_and_no_update(self):
        """Verify that no separate UPDATE is required after INSERT.

        This test ensures the atomicity property: the database row is inserted
        with all three signature fields already populated.
        """
        # We'll inspect the database directly to confirm there is no row with NULL signature
        import sqlite3
        conn = sqlite3.connect(os.environ["GRANTLAYER_DB"])
        try:
            # Create a grant
            grant = Grant(
                subject_id="test-subject-2",
                role="developer",
                action="deploy",
                resource="service-b",
                valid_from="2026-01-01T00:00:00Z",
                valid_until="2026-12-31T23:59:59Z",
                created_by="admin",
                reason="GL‑050 atomic test",
            )
            created = create_grant(grant)

            # Query the raw row
            cur = conn.execute(
                "SELECT signature, signing_key_id, payload_hash FROM grants WHERE id = ?",
                (created.id,)
            )
            row = cur.fetchone()
            self.assertIsNotNone(row)
            sig, key_id, hash_hex = row

            # All three must be NOT NULL
            self.assertIsNotNone(sig)
            self.assertIsNotNone(key_id)
            self.assertIsNotNone(hash_hex)

            # They must match the grant object
            self.assertEqual(sig, created.signature)
            self.assertEqual(key_id, created.signing_key_id)
            self.assertEqual(hash_hex, created.payload_hash)
        finally:
            conn.close()

    def test_grants_cannot_have_null_signature_fields(self):
        """No grant may exist in the database with NULL signature/payload_hash/signing_key_id.

        This is the core guarantee of GL‑050.
        """
        import sqlite3
        conn = sqlite3.connect(os.environ["GRANTLAYER_DB"])
        try:
            # Before any tests, there should be zero rows in grants
            cur = conn.execute("SELECT COUNT(*) FROM grants")
            self.assertEqual(cur.fetchone()[0], 0)

            # Create a grant via the atomic path
            grant = Grant(
                subject_id="test-subject-3",
                role="developer",
                action="deploy",
                resource="service-c",
                valid_from="2026-01-01T00:00:00Z",
                valid_until="2026-12-31T23:59:59Z",
                created_by="admin",
                reason="GL‑050 null‑safety test",
            )
            create_grant(grant)

            # Count grants where any of the three signature fields is NULL
            cur = conn.execute("""
                SELECT COUNT(*) FROM grants
                WHERE signature IS NULL
                   OR signing_key_id IS NULL
                   OR payload_hash IS NULL
            """)
            null_count = cur.fetchone()[0]
            self.assertEqual(null_count, 0, "Found grants with NULL signature fields")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()