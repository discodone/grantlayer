"""Tests for GL-099 Transactional Audit Consistency.

Ensures:
1. Approval state transition and approval audit event are consistent.
2. If approval audit write fails, approval state must not remain committed where
   rollback is supported.
3. Valid approval still succeeds and emits audit.
4. Revoke state transition and revoke audit event are consistent.
5. If revoke audit write fails, revoke state must not remain committed where
   rollback is supported.
6. Valid revoke still succeeds and emits audit.
7. Expiry state transition and expiry audit event are consistent.
8. If expiry audit write fails, expiry state must not remain committed where
   rollback is supported.
9. Expiry audit does not use approved=True.
10. Expiry audit is distinguishable from approve/deny/revoke.
11. Repeated expiry does not duplicate audit events.
12. GL-092 deny/revoke audit semantics preserved.
13. GL-097 self-approval guard preserved.
14. GL-097 denial reason length preserved.
15. GL-098 expired request approval rejection preserved.
16. Safe deterministic errors, no internals leaked.
17. Health/readiness remain public.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl099(unittest.TestCase):
    """Shared helpers for GL-099 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import src.grant_requests as requests_mod
        importlib.reload(requests_mod)
        self.requests_mod = requests_mod

        import src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod

        self.db_mod = db_mod
        self.handler_class = server_mod.GrantLayerHandler

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

    def _create_request(self, **kwargs):
        """Helper to create a grant request with defaults."""
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
        req = self.models_mod.GrantRequest(**defaults)
        return self.requests_mod.create_grant_request(req)

    def _create_old_request(self, **kwargs):
        """Helper to create a grant request with a created_at in the past."""
        import datetime
        old_time = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=25)
        ).isoformat().replace("+00:00", "Z")
        defaults = dict(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
            created_at=old_time,
            updated_at=old_time,
        )
        defaults.update(kwargs)
        req = self.models_mod.GrantRequest(**defaults)
        return self.requests_mod.create_grant_request(req)

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

    def _make_handler(self, path, method="GET", auth_header=None, body=b"", content_length=None):
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if body or content_length is not None:
            headers["Content-Length"] = str(content_length) if content_length is not None else str(len(body))
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


# ═══════════════════════════════════════════════════════════════════════
# 1. Approval transactional audit consistency
# ═══════════════════════════════════════════════════════════════════════

class TestGl099ApprovalTransactionalConsistency(_BaseGl099):
    """Tests ensuring approval and audit are atomic."""

    def test_approval_audit_failure_prevents_committed_state(self):
        """If approval audit write fails, request must remain requested."""
        req = self._create_request()

        original_append = self.audit_mod.append_event
        def failing_append(event, conn=None):
            raise RuntimeError("Simulated audit log failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.approve_grant_request(req.id, "approver-1")
        finally:
            self.audit_mod.append_event = original_append

        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")
        self.assertIsNone(req_after.approved_by)
        self.assertIsNone(req_after.approved_at)
        self.assertIsNone(req_after.grant_id)

    def test_approval_audit_failure_does_not_create_grant(self):
        """If approval audit write fails, no grant must be created."""
        req = self._create_request()

        def failing_append(event, conn=None):
            raise RuntimeError("Simulated audit log failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.approve_grant_request(req.id, "approver-1")
        finally:
            self.audit_mod.append_event = self.audit_mod.append_event

        grants = self.grants_mod.list_grants()
        self.assertEqual(len(grants), 0)

    def test_valid_approval_still_succeeds_and_emits_audit(self):
        """Successful approval must create request, grant, and audit event."""
        req = self._create_request()
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, "approver-1")

        self.assertEqual(updated_req.status, "approved")
        self.assertEqual(updated_req.approved_by, "approver-1")
        self.assertIsNotNone(grant)

        events = self.audit_mod.list_events(limit=10)
        approve_events = [e for e in events if e.action == "approve_grant_request"]
        self.assertEqual(len(approve_events), 1)
        self.assertTrue(approve_events[0].approved)
        self.assertEqual(approve_events[0].subject_id, "approver-1")

    def test_approval_failure_is_surfaced(self):
        """Approval failure must propagate the exception."""
        req = self._create_request()

        def failing_append(event, conn=None):
            raise RuntimeError("audit failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError) as ctx:
                self.requests_mod.approve_grant_request(req.id, "approver-1")
            self.assertIn("audit failure", str(ctx.exception))
        finally:
            self.audit_mod.append_event = self.audit_mod.append_event

    def test_approval_error_safe_no_internals_leaked(self):
        """Approval error must be deterministic and safe."""
        req = self._create_request()

        def failing_append(event, conn=None):
            raise RuntimeError("audit failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError) as ctx:
                self.requests_mod.approve_grant_request(req.id, "approver-1")
            msg = str(ctx.exception)
            leak_terms = ["traceback", "stack", "token", "secret", "password", "GRANTLAYER", "postgres", "sqlite"]
            for term in leak_terms:
                self.assertNotIn(term, msg.lower())
        finally:
            self.audit_mod.append_event = self.audit_mod.append_event


# ═══════════════════════════════════════════════════════════════════════
# 2. Revoke transactional audit consistency
# ═══════════════════════════════════════════════════════════════════════

class TestGl099RevokeTransactionalConsistency(_BaseGl099):
    """Tests ensuring revoke and audit are atomic."""

    def test_revoke_audit_failure_prevents_committed_state(self):
        """If revoke audit write fails, request must remain approved."""
        req = self._create_request()
        self.requests_mod.approve_grant_request(req.id, "approver-1")

        original_append = self.audit_mod.append_event
        def failing_append(event, conn=None):
            raise RuntimeError("Simulated audit log failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.revoke_grant_request(req.id, "revoker-1", "Security concern")
        finally:
            self.audit_mod.append_event = original_append

        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "approved")
        self.assertIsNone(req_after.revoked_by)
        self.assertIsNone(req_after.revoked_at)
        self.assertIsNone(req_after.revoked_reason)

    def test_revoke_audit_failure_does_not_revoke_grant(self):
        """If revoke audit write fails, linked grant must not be revoked."""
        req = self._create_request()
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, "approver-1")

        def failing_append(event, conn=None):
            raise RuntimeError("Simulated audit log failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.revoke_grant_request(req.id, "revoker-1", "Security concern")
        finally:
            self.audit_mod.append_event = self.audit_mod.append_event

        grant_after = self.grants_mod.get_grant(grant.id)
        self.assertFalse(grant_after.revoked)

    def test_valid_revoke_still_succeeds_and_emits_audit(self):
        """Successful revoke must update state and emit audit event."""
        req = self._create_request()
        self.requests_mod.approve_grant_request(req.id, "approver-1")
        updated = self.requests_mod.revoke_grant_request(req.id, "revoker-1", "Security concern")

        self.assertEqual(updated.status, "revoked")
        self.assertEqual(updated.revoked_by, "revoker-1")

        events = self.audit_mod.list_events(limit=10)
        revoke_events = [e for e in events if e.action == "revoke_grant_request"]
        self.assertEqual(len(revoke_events), 1)
        self.assertFalse(revoke_events[0].approved)
        self.assertEqual(revoke_events[0].subject_id, "revoker-1")

    def test_revoke_failure_is_surfaced(self):
        """Revoke failure must propagate the exception."""
        req = self._create_request()
        self.requests_mod.approve_grant_request(req.id, "approver-1")

        def failing_append(event, conn=None):
            raise RuntimeError("audit failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError) as ctx:
                self.requests_mod.revoke_grant_request(req.id, "revoker-1", "Security concern")
            self.assertIn("audit failure", str(ctx.exception))
        finally:
            self.audit_mod.append_event = self.audit_mod.append_event


# ═══════════════════════════════════════════════════════════════════════
# 3. Expiry transactional audit consistency
# ═══════════════════════════════════════════════════════════════════════

class TestGl099ExpiryTransactionalConsistency(_BaseGl099):
    """Tests ensuring expiry and audit are atomic where supported."""

    def test_expiry_audit_failure_prevents_committed_state(self):
        """If expiry audit write fails, request must remain requested."""
        req = self._create_old_request()

        original_append = self.audit_mod.append_event
        def failing_append(event, conn=None):
            raise RuntimeError("Simulated audit log failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.expire_old_requests()
        finally:
            self.audit_mod.append_event = original_append

        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")

    def test_valid_expiry_still_expires_and_emits_audit(self):
        """Successful expiry must transition state and emit audit event."""
        req = self._create_old_request()
        count = self.requests_mod.expire_old_requests()

        self.assertEqual(count, 1)
        expired_req = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(expired_req.status, "expired")

        events = self.audit_mod.list_events(limit=10)
        expire_events = [e for e in events if e.action == "expire_grant_request"]
        self.assertEqual(len(expire_events), 1)

    def test_expiry_audit_not_approved_true(self):
        """Expiry audit event must never contain approved=True."""
        req = self._create_old_request()
        self.requests_mod.expire_old_requests()
        events = self.audit_mod.list_events(limit=10)
        for e in events:
            if e.action == "expire_grant_request":
                self.assertFalse(e.approved)

    def test_expiry_audit_distinguishable_from_approve_deny_revoke(self):
        """Expiry audit must be distinguishable from approve/deny/revoke."""
        req = self._create_old_request()
        self.requests_mod.expire_old_requests()
        events = self.audit_mod.list_events(limit=10)
        expire_events = [e for e in events if e.action == "expire_grant_request"]
        self.assertEqual(len(expire_events), 1)
        self.assertEqual(expire_events[0].subject_id, "system")
        self.assertEqual(expire_events[0].role, "system")

    def test_repeated_expiry_does_not_duplicate_audit(self):
        """Running expire_old_requests again must not create duplicate audit events."""
        req = self._create_old_request()
        self.requests_mod.expire_old_requests()
        self.requests_mod.expire_old_requests()
        events = self.audit_mod.list_events(limit=10)
        expire_events = [e for e in events if e.action == "expire_grant_request"]
        self.assertEqual(len(expire_events), 1)


# ═══════════════════════════════════════════════════════════════════════
# 4. GL-092 deny/revoke audit semantics preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl099Gl092SemanticsPreserved(_BaseGl099):
    """Tests ensuring GL-092 deny/revoke audit semantics remain intact."""

    def test_deny_audit_still_approved_false(self):
        """Deny audit must still have approved=False."""
        req = self._create_request()
        self.requests_mod.deny_grant_request(req.id, "denier-1", "Not allowed")
        events = self.audit_mod.list_events(limit=10)
        deny_events = [e for e in events if e.action == "deny_grant_request"]
        self.assertEqual(len(deny_events), 1)
        self.assertFalse(deny_events[0].approved)

    def test_revoke_audit_still_approved_false(self):
        """Revoke audit must still have approved=False."""
        req = self._create_request()
        self.requests_mod.approve_grant_request(req.id, "approver-1")
        self.requests_mod.revoke_grant_request(req.id, "revoker-1", "Security concern")
        events = self.audit_mod.list_events(limit=10)
        revoke_events = [e for e in events if e.action == "revoke_grant_request"]
        self.assertEqual(len(revoke_events), 1)
        self.assertFalse(revoke_events[0].approved)

    def test_approve_audit_still_approved_true(self):
        """Approve audit must still have approved=True."""
        req = self._create_request()
        self.requests_mod.approve_grant_request(req.id, "approver-1")
        events = self.audit_mod.list_events(limit=10)
        approve_events = [e for e in events if e.action == "approve_grant_request"]
        self.assertEqual(len(approve_events), 1)
        self.assertTrue(approve_events[0].approved)


# ═══════════════════════════════════════════════════════════════════════
# 5. GL-097 self-approval and denial reason length preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl099Gl097Preserved(_BaseGl099):
    """Tests ensuring GL-097 protections remain intact."""

    def test_self_approval_guard_still_works(self):
        """Self-approval must still be rejected."""
        req = self._create_request(requested_by="operator-a")
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.approve_grant_request(req.id, "operator-a")
        self.assertIn("Self-approval is not permitted", str(ctx.exception))

    def test_self_approval_leaves_request_unapproved(self):
        """Self-approval rejection must not mutate request state."""
        req = self._create_request(requested_by="operator-a")
        try:
            self.requests_mod.approve_grant_request(req.id, "operator-a")
        except ValueError:
            pass
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")
        self.assertIsNone(req_after.approved_by)

    def test_self_approval_does_not_create_approval_audit(self):
        """Self-approval rejection must not create a misleading approval audit event."""
        req = self._create_request(requested_by="operator-a")
        try:
            self.requests_mod.approve_grant_request(req.id, "operator-a")
        except ValueError:
            pass
        events = self.audit_mod.list_events(limit=10)
        approve_events = [e for e in events if e.action == "approve_grant_request"]
        self.assertEqual(len(approve_events), 0)

    def test_denial_reason_length_still_works(self):
        """Overlong denial reason must still be rejected."""
        req = self._create_request()
        reason = "x" * (self.requests_mod.MAX_DENIAL_REASON_LENGTH + 1)
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.deny_grant_request(req.id, "denier-1", reason)
        self.assertIn("exceeds maximum length", str(ctx.exception))

    def test_overlong_denial_leaves_state_unchanged(self):
        """Overlong denial rejection must not mutate request state."""
        req = self._create_request()
        reason = "x" * (self.requests_mod.MAX_DENIAL_REASON_LENGTH + 1)
        try:
            self.requests_mod.deny_grant_request(req.id, "denier-1", reason)
        except ValueError:
            pass
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")
        self.assertIsNone(req_after.denied_by)

    def test_overlong_denial_does_not_create_audit(self):
        """Overlong denial rejection must not create a misleading denial audit event."""
        req = self._create_request()
        reason = "x" * (self.requests_mod.MAX_DENIAL_REASON_LENGTH + 1)
        try:
            self.requests_mod.deny_grant_request(req.id, "denier-1", reason)
        except ValueError:
            pass
        events = self.audit_mod.list_events(limit=10)
        deny_events = [e for e in events if e.action == "deny_grant_request"]
        self.assertEqual(len(deny_events), 0)


# ═══════════════════════════════════════════════════════════════════════
# 6. GL-098 expired request approval rejection preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl099Gl098Preserved(_BaseGl099):
    """Tests ensuring GL-098 expiry behavior remains intact."""

    def test_expired_request_approval_rejection_preserved(self):
        """Expired pending requests must still be rejected at approval time."""
        req = self._create_old_request()
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.approve_grant_request(req.id, "approver-1")
        self.assertIn("expired", str(ctx.exception).lower())

    def test_expired_approval_leaves_state_unchanged(self):
        """Approval rejection of expired request must not mutate state."""
        req = self._create_old_request()
        try:
            self.requests_mod.approve_grant_request(req.id, "approver-1")
        except ValueError:
            pass
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")
        self.assertIsNone(req_after.approved_by)

    def test_expired_approval_does_not_create_approval_audit(self):
        """Approval rejection of expired request must not create misleading audit."""
        req = self._create_old_request()
        try:
            self.requests_mod.approve_grant_request(req.id, "approver-1")
        except ValueError:
            pass
        events = self.audit_mod.list_events(limit=10)
        approve_events = [e for e in events if e.action == "approve_grant_request"]
        self.assertEqual(len(approve_events), 0)

    def test_expired_approval_error_safe(self):
        """Expired approval error must be deterministic and safe."""
        req = self._create_old_request()
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.approve_grant_request(req.id, "approver-1")
        msg = str(ctx.exception)
        self.assertEqual(msg, "Grant request has expired")
        leak_terms = ["traceback", "stack", "token", "secret", "password", "GRANTLAYER", "postgres", "sqlite"]
        for term in leak_terms:
            self.assertNotIn(term, msg.lower())


# ═══════════════════════════════════════════════════════════════════════
# 7. Server-layer safety
# ═══════════════════════════════════════════════════════════════════════

class TestGl099ServerSafety(_BaseGl099):
    """Server-layer tests for audit consistency and prior GL protections."""

    def test_server_rejects_self_approval(self):
        """Server must reject self-approval before reaching module layer."""
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")

        req_data = {
            "subjectId": "tech-01",
            "role": "technician",
            "action": "restart-service",
            "resource": "customer-env-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2099-12-31T23:59:59Z",
            "reason": "API test request"
        }
        body = json.dumps(req_data).encode()
        handler = self._make_handler("/grant-requests", method="POST", auth_header="Bearer admin-token", body=body)
        status, data = self._run_handler(handler)
        self.assertEqual(status, 201)
        request_id = data["id"]

        approval_body = json.dumps({"comment": "Approved"}).encode()
        handler = self._make_handler(
            f"/grant-requests/{request_id}/approve",
            method="POST",
            auth_header="Bearer admin-token",
            body=approval_body
        )
        status, data = self._run_handler(handler)
        self.assertEqual(status, 403)
        self.assertEqual(data.get("errorCode"), "self_approval_forbidden")

    def test_server_rejects_approval_of_expired(self):
        """Server must return safe 400 when approving an expired request."""
        self._insert_operator("approver-1", "Approver", "grant_admin", "approver-token")
        req = self._create_old_request()
        approval_body = json.dumps({"comment": "Approved"}).encode()
        handler = self._make_handler(
            f"/grant-requests/{req.id}/approve",
            method="POST",
            auth_header="Bearer approver-token",
            body=approval_body,
        )
        status, data = self._run_handler(handler)
        self.assertEqual(status, 400)
        self._assert_gl030_full(data)
        self.assertIn("expired", data.get("reason", "").lower())

    def test_health_public(self):
        """GET /health remains public."""
        handler = self._make_handler("/health")
        status, data = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ok")

    def test_readiness_public(self):
        """GET /readiness remains public."""
        handler = self._make_handler("/readiness")
        status, data = self._run_handler(handler)
        self.assertIn(status, (200, 503))


# ═══════════════════════════════════════════════════════════════════════
# 8. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl099NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-099 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-099-transactional-audit-consistency":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-099 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/grant_requests.py",
            "backend/src/audit_log.py",
            "backend/tests/test_gl099_transactional_audit_consistency.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-099 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
