"""Tests for GL-051 approve_grant_request transaction consistency.

Ensures approve_grant_request(, tenant_id="demo") is atomic:
- Grant creation and grant request approval/update/linking must succeed together
  or both must roll back
- No orphan grant may remain if approval flow fails
- No approved grant request may point to a non-existing or failed grant
- GL-050 signature behavior is preserved on successfully created grants
"""

import os
import sys
import sqlite3
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.src.core.models import GrantRequest


class TestApproveGrantRequestTransaction(unittest.TestCase):
    """GL-051: Atomic approve_grant_request transaction."""

    def setUp(self):
        # Fresh temporary database
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

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.grants.grant_requests as requests_mod
        importlib.reload(requests_mod)
        self.requests_mod = requests_mod

    def tearDown(self):
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

    def _create_request(self):
        req = GrantRequest(
            subject_id="subj-01",
            role="developer",
            action="deploy",
            resource="svc-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="req-01",
            reason="GL-051 test",
        )
        return self.requests_mod.create_grant_request(req, tenant_id="demo")

    def _count_grants(self):
        db_path = os.environ["GRANTLAYER_DB"]
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.execute("SELECT COUNT(*) FROM grants")
            return cur.fetchone()[0]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 1. Successful approval still creates and links grant correctly
    # ------------------------------------------------------------------
    def test_successful_approval_creates_and_links_grant(self):
        req = self._create_request()
        updated_req, grant = self.requests_mod.approve_grant_request(
            req.id, "approver-1",
            tenant_id="demo",
        )

        self.assertEqual(updated_req.status, "approved")
        self.assertEqual(updated_req.approved_by, "approver-1")
        self.assertIsNotNone(updated_req.approved_at)
        self.assertEqual(updated_req.grant_id, grant.id)

        # Grant must exist and match request data
        fetched_grant = self.grants_mod.get_grant(grant.id)
        self.assertIsNotNone(fetched_grant)
        self.assertEqual(fetched_grant.subject_id, req.subject_id)
        self.assertEqual(fetched_grant.role, req.role)
        self.assertEqual(fetched_grant.action, req.action)
        self.assertEqual(fetched_grant.resource, req.resource)

        # Only one grant in DB
        self.assertEqual(self._count_grants(), 1)

    # ------------------------------------------------------------------
    # 2. Grant creation failure leaves request not approved
    # ------------------------------------------------------------------
    def test_grant_creation_failure_leaves_request_not_approved(self):
        req = self._create_request()

        original_sign_grant = self.grants_mod._sign_grant

        def failing_sign_grant(grant):
            raise RuntimeError("Simulated signing failure")

        self.grants_mod._sign_grant = failing_sign_grant
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.approve_grant_request(req.id, "approver-1", tenant_id="demo")
        finally:
            self.grants_mod._sign_grant = original_sign_grant

        # Request must still be in 'requested' state
        fetched_req = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(fetched_req.status, "requested")
        self.assertIsNone(fetched_req.approved_by)
        self.assertIsNone(fetched_req.grant_id)

        # No grant should have been committed
        self.assertEqual(self._count_grants(), 0)

    # ------------------------------------------------------------------
    # 3. Failure after grant creation attempt rolls back grant and request
    # ------------------------------------------------------------------
    def test_failure_after_grant_creation_rolls_back_everything(self):
        req = self._create_request()

        gr_mod = self.requests_mod
        original_datetime_class = gr_mod.datetime.datetime

        class FailingDateTime:
            @staticmethod
            def now(tz=None):
                raise RuntimeError("Simulated failure after grant creation")

        gr_mod.datetime.datetime = FailingDateTime
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.approve_grant_request(req.id, "approver-1", tenant_id="demo")
        finally:
            gr_mod.datetime.datetime = original_datetime_class

        # Request must still be in 'requested' state
        fetched_req = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(fetched_req.status, "requested")
        self.assertIsNone(fetched_req.approved_by)
        self.assertIsNone(fetched_req.grant_id)

        # No grant should remain
        self.assertEqual(self._count_grants(), 0)

    # ------------------------------------------------------------------
    # 4. GL-050 signature fields remain present on successfully created grant
    # ------------------------------------------------------------------
    def test_approved_grant_has_signature_fields(self):
        req = self._create_request()
        updated_req, grant = self.requests_mod.approve_grant_request(
            req.id, "approver-1",
            tenant_id="demo",
        )

        # Returned grant must have signature fields populated
        self.assertIsNotNone(grant.signature)
        self.assertIsNotNone(grant.payload_hash)
        self.assertIsNotNone(grant.signing_key_id)

        self.assertIsInstance(grant.signature, str)
        self.assertIsInstance(grant.payload_hash, str)
        self.assertIsInstance(grant.signing_key_id, str)

        self.assertGreater(len(grant.signature), 0)
        self.assertGreater(len(grant.payload_hash), 0)
        self.assertGreater(len(grant.signing_key_id), 0)

        # Signature should be hex (Ed25519 = 64 bytes = 128 hex chars)
        self.assertEqual(len(grant.signature), 128)
        self.assertTrue(all(c in "0123456789abcdef" for c in grant.signature))

        # Payload hash should be 64-char hex (SHA-256)
        self.assertEqual(len(grant.payload_hash), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in grant.payload_hash))

        # signing_key_id is the signing key's fingerprint id
        self.assertTrue(grant.signing_key_id.startswith("ed25519-"))

        # Persisted grant must also have fields
        fetched_grant = self.grants_mod.get_grant(grant.id)
        self.assertIsNotNone(fetched_grant)
        self.assertEqual(fetched_grant.signature, grant.signature)
        self.assertEqual(fetched_grant.payload_hash, grant.payload_hash)
        self.assertEqual(fetched_grant.signing_key_id, grant.signing_key_id)

        # No NULL signature fields in DB
        db_path = os.environ["GRANTLAYER_DB"]
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.execute(
                """
                SELECT COUNT(*) FROM grants
                WHERE signature IS NULL
                   OR signing_key_id IS NULL
                   OR payload_hash IS NULL
                """
            )
            self.assertEqual(cur.fetchone()[0], 0)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
