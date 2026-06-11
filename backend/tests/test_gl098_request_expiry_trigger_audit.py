"""Tests for GL-098 Request Expiry Trigger + Expiry Audit Trail.

Ensures:
1. expire_old_requests() transitions expired pending requests to expired.
2. Non-expired pending requests are not expired.
3. Approved/denied/revoked requests are not incorrectly expired.
4. Expired pending requests cannot be approved.
5. Approval path handles expired pending requests safely.
6. Expiry creates an audit event with expiry semantics.
7. Expiry audit event does not use approved=True.
8. Expiry audit is distinguishable from approve/deny/revoke.
9. Repeated expiry does not duplicate audit events.
10. Valid non-expired approvals still succeed.
11. GL-097 self-approval guard remains intact.
12. GL-097 denial reason length remains intact.
13. GL-092 deny/revoke audit semantics preserved.
14. Safe deterministic errors, no internals leaked.
15. Health/readiness remain public.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))



class _BaseGl098(unittest.TestCase):
    """Shared helpers for GL-098 tests."""

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
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.grant_requests as requests_mod
        importlib.reload(requests_mod)
        self.requests_mod = requests_mod

        import backend.src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        self.db_mod = db_mod

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=False)

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
        return (path, method, auth_header, body)

    def _run_handler(self, req):
        path, method, auth_header, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    body_dict = json.loads(body)
                    resp = self.client.post(path, json=body_dict, headers=headers)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    resp = self.client.post(path, content=body, headers=headers)
            else:
                resp = self.client.post(path, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("detail"), dict):
            data = data["detail"]
        return resp.status_code, data

    def _assert_gl030_full(self, payload):
        self.assertIn("error", payload)
        self.assertIn("errorCode", payload)
        self.assertIn("reason", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)


# ═══════════════════════════════════════════════════════════════════════
# 1. expire_old_requests transitions expired pending requests
# ═══════════════════════════════════════════════════════════════════════

class TestGl098ExpireOldRequests(_BaseGl098):
    """Tests for expire_old_requests() behavior."""

    def test_expire_old_requests_transitions_expired_pending(self):
        """expire_old_requests must transition old pending requests to expired."""
        req = self._create_old_request()
        count = self.requests_mod.expire_old_requests()
        self.assertEqual(count, 1)
        expired_req = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(expired_req.status, "expired")

    def test_non_expired_pending_not_expired(self):
        """Recent pending requests must not be expired."""
        req = self._create_request()
        count = self.requests_mod.expire_old_requests()
        self.assertEqual(count, 0)
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")

    def test_approved_requests_not_incorrectly_expired(self):
        """Approved requests must not be transitioned to expired."""
        req = self._create_request()
        self.requests_mod.approve_grant_request(req.id, "approver-1")
        count = self.requests_mod.expire_old_requests()
        self.assertEqual(count, 0)
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "approved")

    def test_denied_requests_not_incorrectly_expired(self):
        """Denied requests must not be transitioned to expired."""
        req = self._create_old_request()
        self.requests_mod.deny_grant_request(req.id, "denier-1", "Not allowed")
        count = self.requests_mod.expire_old_requests()
        self.assertEqual(count, 0)
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "denied")

    def test_revoked_requests_not_incorrectly_expired(self):
        """Revoked requests must not be transitioned to expired."""
        req = self._create_request()
        self.requests_mod.approve_grant_request(req.id, "approver-1")
        self.requests_mod.revoke_grant_request(req.id, "revoker-1", "Security concern")
        count = self.requests_mod.expire_old_requests()
        self.assertEqual(count, 0)
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "revoked")


# ═══════════════════════════════════════════════════════════════════════
# 2. Expired pending requests cannot be approved
# ═══════════════════════════════════════════════════════════════════════

class TestGl098ExpiredRequestCannotBeApproved(_BaseGl098):
    """Tests ensuring expired requests are rejected at approval time."""

    def test_expired_pending_request_cannot_be_approved(self):
        """An expired pending request must be rejected by approve_grant_request."""
        req = self._create_old_request()
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.approve_grant_request(req.id, "approver-1")
        self.assertIn("expired", str(ctx.exception).lower())

    def test_approval_of_expired_leaves_state_unchanged(self):
        """Approval rejection of expired request must not mutate state."""
        req = self._create_old_request()
        try:
            self.requests_mod.approve_grant_request(req.id, "approver-1")
        except ValueError:
            pass
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")
        self.assertIsNone(req_after.approved_by)
        self.assertIsNone(req_after.grant_id)

    def test_approval_of_expired_does_not_create_approval_audit(self):
        """Approval rejection of expired request must not create misleading audit."""
        req = self._create_old_request()
        try:
            self.requests_mod.approve_grant_request(req.id, "approver-1")
        except ValueError:
            pass
        events = self.audit_mod.list_events(limit=10)
        approve_events = [e for e in events if e.action == "approve_grant_request"]
        self.assertEqual(len(approve_events), 0)

    def test_valid_non_expired_approval_still_succeeds(self):
        """Non-expired requests must still be approvable."""
        req = self._create_request()
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, "approver-1")
        self.assertEqual(updated_req.status, "approved")
        self.assertEqual(updated_req.approved_by, "approver-1")
        self.assertIsNotNone(grant)

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
# 3. Server-layer approval path handles expired requests safely
# ═══════════════════════════════════════════════════════════════════════

class TestGl098ServerApprovalPath(_BaseGl098):
    """Tests ensuring the server layer safely handles expired requests."""

    def test_server_rejects_approval_of_expired_request(self):
        """Server must return safe 400 when approving an expired request."""
        self._insert_operator("approver-1", "Approver", "grant_admin", "approver-token")
        req = self._create_old_request()
        approval_body = json.dumps({"comment": "Approved"}).encode()
        http_req = self._make_handler(
            f"/grant-requests/{req.id}/approve",
            method="POST",
            auth_header="Bearer approver-token",
            body=approval_body,
        )
        status, data = self._run_handler(http_req)
        self.assertEqual(status, 400)
        self._assert_gl030_full(data)
        self.assertIn("expired", data.get("reason", "").lower())


# ═══════════════════════════════════════════════════════════════════════
# 4. Expiry audit event semantics
# ═══════════════════════════════════════════════════════════════════════

class TestGl098ExpiryAuditSemantics(_BaseGl098):
    """Tests for expiry audit event semantics."""

    def test_expiry_creates_audit_event(self):
        """expire_old_requests must create an audit event for each expiry."""
        req = self._create_old_request()
        self.requests_mod.expire_old_requests()
        events = self.audit_mod.list_events(limit=10)
        expire_events = [e for e in events if e.action == "expire_grant_request"]
        self.assertEqual(len(expire_events), 1)
        self.assertIn(req.id, expire_events[0].resource)

    def test_expiry_audit_not_approved_true(self):
        """Expiry audit event must never contain approved=True."""
        req = self._create_old_request()
        self.requests_mod.expire_old_requests()
        events = self.audit_mod.list_events(limit=10)
        for e in events:
            if e.action == "expire_grant_request":
                self.assertFalse(e.approved, "Expiry audit must have approved=False")

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

    def test_no_state_change_means_no_audit_event(self):
        """If no requests are expired, no audit events should be created."""
        self._create_request()  # Recent, not expired
        before = len(self.audit_mod.list_events(limit=10))
        self.requests_mod.expire_old_requests()
        after = len(self.audit_mod.list_events(limit=10))
        self.assertEqual(before, after)


# ═══════════════════════════════════════════════════════════════════════
# 5. GL-097 protections preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl098Gl097Preserved(_BaseGl098):
    """Regression tests ensuring GL-097 protections remain intact."""

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

    def test_denial_reason_length_still_works(self):
        """Overlong denial reason must still be rejected."""
        req = self._create_request()
        reason = "x" * (self.requests_mod.MAX_DENIAL_REASON_LENGTH + 1)
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.deny_grant_request(req.id, "denier-1", reason)
        self.assertIn("exceeds maximum length", str(ctx.exception))

    def test_denial_reason_length_leaves_state_unchanged(self):
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


# ═══════════════════════════════════════════════════════════════════════
# 6. GL-092 deny/revoke audit semantics preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl098Gl092Preserved(_BaseGl098):
    """Regression tests ensuring GL-092 audit semantics remain intact."""

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
# 7. Prior GL protection regressions
# ═══════════════════════════════════════════════════════════════════════

class TestGl098PriorGLRegressions(_BaseGl098):
    """Regression tests for prior GL protections."""

    def test_health_public(self):
        """GET /health remains public."""
        req = self._make_handler("/health")
        status, data = self._run_handler(req)
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ok")

    def test_readiness_public(self):
        """GET /readiness remains public."""
        req = self._make_handler("/readiness")
        status, data = self._run_handler(req)
        self.assertIn(status, (200, 503))

    def test_gl091_signature_auth_cache_hardening_intact(self):
        """Operator token lookup still uses SHA-256 hex."""
        import hashlib
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.operators as fresh_ops
        importlib.reload(fresh_ops)

        digest = fresh_ops.derive_token_lookup_hash("owner-token")
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, hashlib.sha256("owner-token".encode("utf-8")).hexdigest())

    @unittest.skip("Legacy GrantLayerHandler body-size guard is not exposed by the FastAPI test surface")
    def test_gl090_request_body_json_hardening_intact(self):
        """Oversized body still returns 413."""
        self.fail("Legacy GrantLayerHandler-only assertion")

    def test_gl088_post_challenges_still_protected(self):
        """POST /challenges still requires auth."""
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        valid_body = json.dumps({
            "subjectId": "sub-1", "action": "read", "resource": "repo-a"
        }).encode()
        req = self._make_handler("/challenges", method="POST", body=valid_body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 401)
        self._assert_gl030_full(data)
        self.assertEqual(data.get("errorCode"), "operator_auth_required")

    def test_gl087_auth_error_response_consistency_intact(self):
        """Auth error response format remains consistent."""
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        req = self._make_handler("/grants")
        status, data = self._run_handler(req)
        self.assertEqual(status, 401)
        self.assertEqual(data.get("errorCode"), "operator_auth_required")
        self.assertEqual(data.get("reason"), "Operator authentication is required.")

    def test_gl089_auth_default_fail_closed_intact(self):
        """Without operator model + empty admin token + require_admin=true, endpoints fail closed."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = ""
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        import backend.src.db as bk_db
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/grants")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "admin_token_required")


# ═══════════════════════════════════════════════════════════════════════
# 8. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl098NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-098 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-098-request-expiry-trigger-audit":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-098 feature branch"
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
            "backend/src/server.py",
            "backend/tests/test_gl098_request_expiry_trigger_audit.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-098 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
