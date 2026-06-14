"""Tests for GL-080 revoke_grant_request atomicity.

Ensures that revoke_grant_request(, tenant_id="demo") performs linked grant revoke and
grant request status update atomically in a single transaction.
"""

import os
import sys
import unittest
import datetime
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestRevokeGrantRequestAtomicity(unittest.TestCase):
    """Test atomicity of revoke_grant_request."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.grants.grant_requests as requests_mod
        importlib.reload(requests_mod)
        self.requests_mod = requests_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

        if self._orig_enable_operator is not None:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = self._orig_enable_operator
        else:
            os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)

    def _create_request(self, **kwargs):
        """Helper to create a grant request with defaults."""
        from backend.src.core.models import GrantRequest
        defaults = dict(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
        )
        defaults.update(kwargs)
        req = GrantRequest(**defaults)
        return self.requests_mod.create_grant_request(req, tenant_id="demo")

    def _create_and_approve_request(self, operator_id="approver-1"):
        """Create and approve a request, returning (request, grant)."""
        req = self._create_request()
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, operator_id, tenant_id="demo")
        return updated_req, grant

    # ------------------------------------------------------------------
    # A. Successful atomic revoke
    # ------------------------------------------------------------------
    def test_successful_atomic_revoke(self):
        """Revoking an approved request revokes both request and linked grant."""
        req, grant = self._create_and_approve_request()
        revoked_req = self.requests_mod.revoke_grant_request(
            req.id, "admin-1", "Security concern",
            tenant_id="demo",
        )

        self.assertEqual(revoked_req.status, "revoked")
        self.assertEqual(revoked_req.revoked_by, "admin-1")
        self.assertEqual(revoked_req.revoked_reason, "Security concern")
        self.assertIsNotNone(revoked_req.revoked_at)

        revoked_grant = self.grants_mod.get_grant(grant.id)
        self.assertTrue(revoked_grant.revoked)
        self.assertEqual(revoked_grant.revoked_by, "admin-1")
        self.assertEqual(
            revoked_grant.revoked_reason, "Revoked from request: Security concern"
        )

    # ------------------------------------------------------------------
    # B. Rollback if request update fails after linked grant revoke attempt
    # ------------------------------------------------------------------
    def test_rollback_if_request_update_fails(self):
        """If the request status update fails, the linked grant revoke must roll back."""
        req, grant = self._create_and_approve_request()

        import backend.src.core.db as db_mod
        original_get_engine = db_mod.get_engine

        def patched_get_engine():
            engine = original_get_engine()
            orig_connect = engine.connect

            def patched_connect():
                conn = orig_connect()
                orig_execute = conn.execute

                def patched_execute(sql, params=None, **kwargs):
                    sql_str = sql
                    if hasattr(sql, "text"):
                        sql_str = sql.text
                    if isinstance(sql_str, str) and "UPDATE grant_requests" in sql_str:
                        raise RuntimeError("Simulated request update failure")
                    return orig_execute(sql, params, **kwargs)

                conn.execute = patched_execute
                return conn

            engine.connect = patched_connect
            return engine

        # Patch get_engine in the module where it is actually imported
        self.requests_mod.get_engine = patched_get_engine
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.revoke_grant_request(
                    req.id, "admin-1", "Security concern",
                    tenant_id="demo",
                )
        finally:
            self.requests_mod.get_engine = original_get_engine

        # Linked grant must NOT be revoked
        grant_after = self.grants_mod.get_grant(grant.id)
        self.assertFalse(grant_after.revoked)

        # Request must remain approved
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "approved")
        self.assertIsNone(req_after.revoked_by)
        self.assertIsNone(req_after.revoked_at)

    # ------------------------------------------------------------------
    # C. Rollback if linked grant revoke fails
    # ------------------------------------------------------------------
    def test_rollback_if_linked_grant_revoke_fails(self):
        """If the linked grant revoke fails, the request must remain unchanged."""
        req, grant = self._create_and_approve_request()

        original_revoke_grant = self.grants_mod.revoke_grant

        def failing_revoke_grant(*args, **kwargs):
            raise RuntimeError("Simulated grant revoke failure")

        self.grants_mod.revoke_grant = failing_revoke_grant
        # Ensure grant_requests also sees the patched function
        self.requests_mod.grants.revoke_grant = failing_revoke_grant
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.revoke_grant_request(
                    req.id, "admin-1", "Security concern",
                    tenant_id="demo",
                )
        finally:
            self.grants_mod.revoke_grant = original_revoke_grant
            self.requests_mod.grants.revoke_grant = original_revoke_grant

        # Linked grant must NOT be revoked
        grant_after = self.grants_mod.get_grant(grant.id)
        self.assertFalse(grant_after.revoked)

        # Request must remain approved
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "approved")
        self.assertIsNone(req_after.revoked_by)

    # ------------------------------------------------------------------
    # D. Standalone grants.revoke_grant compatibility
    # ------------------------------------------------------------------
    def test_standalone_revoke_grant_compatibility(self):
        """Calling revoke_grant without a connection still commits independently."""
        req, grant = self._create_and_approve_request()

        result = self.grants_mod.revoke_grant(grant.id, "admin-1", "Standalone revoke")
        self.assertTrue(result)

        revoked_grant = self.grants_mod.get_grant(grant.id)
        self.assertTrue(revoked_grant.revoked)
        self.assertEqual(revoked_grant.revoked_reason, "Standalone revoke")

    # ------------------------------------------------------------------
    # E. Shared connection behavior
    # ------------------------------------------------------------------
    def test_shared_connection_does_not_commit_independently(self):
        """Using revoke_grant with an outer connection must not commit on its own."""
        req, grant = self._create_and_approve_request()

        import backend.src.core.db as db_mod
        conn = db_mod.get_conn()
        try:
            conn.execute("BEGIN TRANSACTION")
            result = self.grants_mod.revoke_grant(
                grant.id, "admin-1", "Shared conn revoke", conn=conn
            )
            self.assertTrue(result)
            conn.rollback()
        finally:
            conn.close()

        # Grant must NOT be revoked because outer transaction rolled back
        grant_after = self.grants_mod.get_grant(grant.id)
        self.assertFalse(grant_after.revoked)

    # ------------------------------------------------------------------
    # F. Regression: approve_grant_request atomicity still works
    # ------------------------------------------------------------------
    def test_approve_grant_request_regression(self):
        """Existing approve_grant_request atomic behavior remains intact."""
        req = self._create_request()
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, "approver-1", tenant_id="demo")

        self.assertEqual(updated_req.status, "approved")
        self.assertEqual(updated_req.grant_id, grant.id)

        retrieved_grant = self.grants_mod.get_grant(grant.id)
        self.assertIsNotNone(retrieved_grant)
        self.assertEqual(retrieved_grant.subject_id, req.subject_id)


if __name__ == "__main__":
    unittest.main()
