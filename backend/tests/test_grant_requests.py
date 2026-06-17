"""Tests for GL-022 Real Approval Workflow.

Covers:
1. Grant request lifecycle
2. Separate grant_requests table
3. Endpoints:
   POST /grant-requests
   GET /grant-requests
   GET /grant-requests/:id
   POST /grant-requests/:id/approve
   POST /grant-requests/:id/deny
4. Statuses:
   requested
   approved
   denied
   revoked
   expired
"""

import os
import unittest
import datetime
import tempfile
import importlib


class TestGrantRequests(unittest.TestCase):
    """Test the grant request lifecycle and API integration."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        # Save env vars
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")

        # Enable operator model for tests
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

        # Reset modules
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

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        # Patch backend.src.db so TestClient uses the same temp DB
        import backend.src.core.db as bk_db
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        self._bk_db = bk_db

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

        if self._orig_admin_token is not None:
            os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._orig_admin_token
        else:
            os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)

    # ─────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────
    def _insert_operator(self, op_id, name, role, token):
        """Helper to insert an operator into the database."""
        conn = self._bk_db.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

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
    
    # ─────────────────────────────────────────────────────
    # Grant Request CRUD Tests
    # ─────────────────────────────────────────────────────
    def test_create_grant_request(self):
        """Test creating a grant request."""
        from backend.src.core.models import GrantRequest
        req = GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
        )
        created = self.requests_mod.create_grant_request(req, tenant_id="demo")
        self.assertEqual(created.subject_id, "tech-01")
        self.assertEqual(created.role, "technician")
        self.assertEqual(created.status, "requested")
        self.assertIsNotNone(created.id)
        
        # Verify it's in the database
        retrieved = self.requests_mod.get_grant_request(created.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, created.id)
        self.assertEqual(retrieved.subject_id, "tech-01")
        self.assertEqual(retrieved.status, "requested")
    
    def test_get_nonexistent_grant_request(self):
        """Test getting a non-existent grant request."""
        retrieved = self.requests_mod.get_grant_request("non-existent-id")
        self.assertIsNone(retrieved)
    
    def test_list_grant_requests(self):
        """Test listing grant requests."""
        # Create a few requests
        r1 = self._create_request()
        r2 = self._create_request()
        r3 = self._create_request()
        
        # List all requests
        all_requests = self.requests_mod.list_grant_requests()
        self.assertEqual(len(all_requests), 3)
        
        # Check the IDs are all there
        ids = [r.id for r in all_requests]
        self.assertIn(r1.id, ids)
        self.assertIn(r2.id, ids)
        self.assertIn(r3.id, ids)
    
    def test_list_grant_requests_by_status(self):
        """Test filtering grant requests by status."""
        # Create a few requests with different statuses
        r1 = self._create_request()
        r2 = self._create_request()
        r3 = self._create_request()
        
        # Approve one request
        self.requests_mod.approve_grant_request(r1.id, "approver-1", tenant_id="demo")
        
        # Deny one request
        self.requests_mod.deny_grant_request(r2.id, "approver-1", "Denied for test", tenant_id="demo")
        
        # List by status
        requested = self.requests_mod.list_grant_requests(status_filter="requested")
        approved = self.requests_mod.list_grant_requests(status_filter="approved")
        denied = self.requests_mod.list_grant_requests(status_filter="denied")
        
        self.assertEqual(len(requested), 1)
        self.assertEqual(len(approved), 1)
        self.assertEqual(len(denied), 1)
        
        self.assertEqual(requested[0].id, r3.id)
        self.assertEqual(approved[0].id, r1.id)
        self.assertEqual(denied[0].id, r2.id)
    
    # ─────────────────────────────────────────────────────
    # Approval Workflow Tests
    # ─────────────────────────────────────────────────────
    def test_approve_grant_request(self):
        """Test approving a grant request creates a grant."""
        req = self._create_request()
        
        # Approve the request
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, "approver-1", tenant_id="demo")
        
        # Check the request was updated correctly
        self.assertEqual(updated_req.status, "approved")
        self.assertEqual(updated_req.approved_by, "approver-1")
        self.assertIsNotNone(updated_req.approved_at)
        self.assertEqual(updated_req.grant_id, grant.id)
        
        # Check the grant was created correctly
        self.assertEqual(grant.subject_id, req.subject_id)
        self.assertEqual(grant.role, req.role)
        self.assertEqual(grant.action, req.action)
        self.assertEqual(grant.resource, req.resource)
        self.assertEqual(grant.valid_from, req.valid_from)
        self.assertEqual(grant.valid_until, req.valid_until)
        
        # Check the grant exists in the grants table
        retrieved_grant = self.grants_mod.get_grant(grant.id)
        self.assertIsNotNone(retrieved_grant)
    
    def test_approve_nonexistent_grant_request(self):
        """Test approving a non-existent grant request."""
        with self.assertRaises(ValueError):
            self.requests_mod.approve_grant_request("non-existent-id", "approver-1", tenant_id="demo")
    
    def test_approve_non_requested_grant_request(self):
        """Test approving a grant request that's not in 'requested' state."""
        req = self._create_request()
        
        # Deny the request first
        self.requests_mod.deny_grant_request(req.id, "approver-1", "Denied for test", tenant_id="demo")
        
        # Try to approve it
        with self.assertRaises(ValueError):
            self.requests_mod.approve_grant_request(req.id, "approver-1", tenant_id="demo")
    
    def test_deny_grant_request(self):
        """Test denying a grant request."""
        req = self._create_request()
        
        # Deny the request
        updated_req = self.requests_mod.deny_grant_request(req.id, "approver-1", "Denied for test", tenant_id="demo")
        
        # Check the request was updated correctly
        self.assertEqual(updated_req.status, "denied")
        self.assertEqual(updated_req.denied_by, "approver-1")
        self.assertEqual(updated_req.denial_reason, "Denied for test")
        self.assertIsNotNone(updated_req.denied_at)
    
    def test_deny_nonexistent_grant_request(self):
        """Test denying a non-existent grant request."""
        with self.assertRaises(ValueError):
            self.requests_mod.deny_grant_request("non-existent-id", "approver-1", "Denied for test", tenant_id="demo")
    
    def test_deny_non_requested_grant_request(self):
        """Test denying a grant request that's not in 'requested' state."""
        req = self._create_request()
        
        # Approve the request first
        self.requests_mod.approve_grant_request(req.id, "approver-1", tenant_id="demo")
        
        # Try to deny it
        with self.assertRaises(ValueError):
            self.requests_mod.deny_grant_request(req.id, "approver-1", "Denied for test", tenant_id="demo")
    
    def test_revoke_approved_grant_request(self):
        """Test revoking an approved grant request also revokes the grant."""
        req = self._create_request()
        
        # Approve the request
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, "approver-1", tenant_id="demo")
        
        # Revoke the request
        revoked_req = self.requests_mod.revoke_grant_request(
            req.id, "admin-1", "Security concern",
            tenant_id="demo",
        )
        
        # Check the request was revoked
        self.assertEqual(revoked_req.status, "revoked")
        self.assertEqual(revoked_req.revoked_by, "admin-1")
        self.assertEqual(revoked_req.revoked_reason, "Security concern")
        self.assertIsNotNone(revoked_req.revoked_at)
        
        # Check the grant was also revoked
        revoked_grant = self.grants_mod.get_grant(grant.id)
        self.assertTrue(revoked_grant.revoked)
        self.assertEqual(revoked_grant.revoked_by, "admin-1")
        self.assertEqual(revoked_grant.revoked_reason, "Revoked from request: Security concern")
    
    def test_revoke_non_approved_grant_request(self):
        """Test revoking a grant request that's not approved."""
        req = self._create_request()  # Status is 'requested'
        
        # Try to revoke it
        with self.assertRaises(ValueError):
            self.requests_mod.revoke_grant_request(req.id, "admin-1", "Security concern", tenant_id="demo")
    
    def test_expire_stale_grant_requests(self):
        """Test expiring old grant requests."""
        # Create a request with a created_at time in the past
        from backend.src.core.models import GrantRequest
        old_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=25)).isoformat().replace("+00:00", "Z")
        req = GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
            created_at=old_time,
            updated_at=old_time
        )
        self.requests_mod.create_grant_request(req, tenant_id="demo")
        
        # Run the expiry function
        count = self.requests_mod.expire_old_requests()
        
        # Check that one request was expired
        self.assertEqual(count, 1)
        
        # Check that the request status was updated
        expired_req = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(expired_req.status, "expired")
    
    # ─────────────────────────────────────────────────────
    # API Endpoint Tests (FastAPI TestClient)
    # ─────────────────────────────────────────────────────
    def _make_client(self):
        """Create a FastAPI TestClient using the temp DB."""
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        import backend.src.core.config as bk_cfg
        bk_cfg.ENABLE_OPERATOR_MODEL = True
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_server_grant_requests_endpoints(self):
        """Integration test for the API endpoints via FastAPI TestClient."""
        # Set up operators
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")
        self._insert_operator("approver-1", "Approver", "grant_admin", "approver-token")

        client = self._make_client()

        req_data = {
            "subjectId": "tech-01",
            "role": "operator",
            "action": "restart-service",
            "resource": "customer-env-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2099-12-31T23:59:59Z",
            "reason": "API test request",
        }

        # 1. Create a grant request
        resp = client.post("/v1/grant-requests", json=req_data, headers={"Authorization": "Bearer admin-token"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["subjectId"], "tech-01")
        self.assertEqual(data["status"], "requested")
        self.assertEqual(data["requestedBy"], "admin-1")
        request_id = data["id"]

        # 2. List grant requests
        resp = client.get("/v1/grant-requests", headers={"Authorization": "Bearer approver-token"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["id"], request_id)

        # 3. Get a single grant request
        resp = client.get(f"/v1/grant-requests/{request_id}", headers={"Authorization": "Bearer approver-token"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], request_id)
        self.assertEqual(data["subjectId"], "tech-01")

        # 4. Approve the grant request
        resp = client.post(f"/v1/grant-requests/{request_id}/approve", headers={"Authorization": "Bearer approver-token"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["request"]["status"], "approved")
        self.assertEqual(data["request"]["approvedBy"], "approver-1")

        # 5. Try to approve again (already approved — expect error)
        resp = client.post(f"/v1/grant-requests/{request_id}/approve", headers={"Authorization": "Bearer admin-token"})
        self.assertIn(resp.status_code, (400, 403))
        body = resp.json()
        self.assertIn("error", body)

        # 6. Create another request and deny it
        resp = client.post("/v1/grant-requests", json=req_data, headers={"Authorization": "Bearer admin-token"})
        self.assertEqual(resp.status_code, 201)
        request2_id = resp.json()["id"]

        resp = client.post(f"/v1/grant-requests/{request2_id}/deny", json={"reason": "Denied for test"}, headers={"Authorization": "Bearer approver-token"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["request"]["status"], "denied")
        self.assertEqual(data["request"]["deniedBy"], "approver-1")
        self.assertEqual(data["request"]["denialReason"], "Denied for test")

    def test_operator_cannot_approve_own_request(self):
        """Test that an operator cannot approve their own request via FastAPI TestClient."""
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")

        client = self._make_client()

        req_data = {
            "subjectId": "tech-01",
            "role": "operator",
            "action": "restart-service",
            "resource": "customer-env-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2099-12-31T23:59:59Z",
            "reason": "API test request",
        }

        # Create a grant request as admin-1
        resp = client.post("/v1/grant-requests", json=req_data, headers={"Authorization": "Bearer admin-token"})
        self.assertEqual(resp.status_code, 201)
        request_id = resp.json()["id"]

        # Try to approve with the same token (self-approval)
        resp = client.post(f"/v1/grant-requests/{request_id}/approve", headers={"Authorization": "Bearer admin-token"})
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertEqual(data["error"], "Cannot approve your own request")
        self.assertEqual(data["requestedBy"], "admin-1")
        self.assertEqual(data["approverId"], "admin-1")
    
    def test_audit_events_for_grant_requests(self):
        """Test that audit events are created for grant request actions."""
        # Create and manipulate some grant requests
        req = self._create_request()
        
        # Approve one
        self.requests_mod.approve_grant_request(req.id, "approver-1", tenant_id="demo")
        
        # Create and deny another
        req2 = self._create_request()
        self.requests_mod.deny_grant_request(req2.id, "approver-1", "Denied for test", tenant_id="demo")
        
        # Check audit events
        events = self.audit_mod.list_events()
        
        # Find events related to our actions
        approve_events = [
            e for e in events 
            if e.action == "approve_grant_request" and f"grant_request/{req.id}" in e.resource
        ]
        deny_events = [
            e for e in events 
            if e.action == "deny_grant_request" and f"grant_request/{req2.id}" in e.resource
        ]
        
        # Verify they exist
        self.assertEqual(len(approve_events), 1)
        self.assertEqual(len(deny_events), 1)
        
        # Check event details
        self.assertEqual(approve_events[0].subject_id, "approver-1")
        self.assertEqual(deny_events[0].subject_id, "approver-1")
        
        # Approval: granted; Deny: not granted
        self.assertTrue(approve_events[0].approved)
        self.assertFalse(deny_events[0].approved)


if __name__ == "__main__":
    unittest.main()