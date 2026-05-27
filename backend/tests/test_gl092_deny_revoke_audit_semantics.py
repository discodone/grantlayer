"""Tests for GL-092 deny_grant_request rollback + deny/revoke audit semantics.

Ensures:
1. If deny_grant_request updates request state and then required audit/logging step
   fails, the state update is rolled back.
2. Deny audit event does not include approved=True.
3. Revoke audit event does not include approved=True.
4. Approval audit semantics remain correct (approved=True).
5. Prior GL protections remain intact (GL-080, GL-091, GL-090, GL-089, GL-088, GL-087, GL-084).
6. GET /health and GET /readiness remain public.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import importlib
import pathlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl092(unittest.TestCase):
    """Shared helpers for GL-092 tests."""

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

    def _create_and_approve_request(self, operator_id="approver-1"):
        """Create and approve a request, returning (request, grant)."""
        req = self._create_request()
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, operator_id)
        return updated_req, grant

    def _make_handler(self, path, method="GET", auth_header=None, body=b""):
        import src.server as server_mod
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


# ═══════════════════════════════════════════════════════════════════════
# 1. Deny rollback hardening
# ═══════════════════════════════════════════════════════════════════════

class TestGl092DenyRollbackHardening(_BaseGl092):
    """Tests for deny_grant_request rollback behavior."""

    def test_deny_audit_failure_rolls_back_request_state(self):
        """If audit log insert fails during deny, request must remain requested."""
        req = self._create_request()

        original_append = self.audit_mod.append_event
        def failing_append(event, conn=None):
            raise RuntimeError("Simulated audit log failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.deny_grant_request(req.id, "denier-1", "Not allowed")
        finally:
            self.audit_mod.append_event = original_append

        # Request must remain in requested state
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")
        self.assertIsNone(req_after.denied_by)
        self.assertIsNone(req_after.denied_at)
        self.assertIsNone(req_after.denial_reason)

    def test_deny_failure_is_surfaced(self):
        """Deny failure must propagate the exception, not silently ignore."""
        req = self._create_request()

        def failing_append(event, conn=None):
            raise RuntimeError("audit failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError) as ctx:
                self.requests_mod.deny_grant_request(req.id, "denier-1", "Not allowed")
            self.assertIn("audit failure", str(ctx.exception))
        finally:
            self.audit_mod.append_event = self.audit_mod.append_event

    def test_successful_denies_create_correct_audit_semantics(self):
        """Successful deny must create audit event with approved=False."""
        req = self._create_request()
        updated = self.requests_mod.deny_grant_request(req.id, "denier-1", "Not allowed")

        self.assertEqual(updated.status, "denied")
        self.assertEqual(updated.denied_by, "denier-1")

        events = self.audit_mod.list_events(limit=10)
        deny_events = [e for e in events if e.action == "deny_grant_request"]
        self.assertEqual(len(deny_events), 1)
        self.assertFalse(deny_events[0].approved)


# ═══════════════════════════════════════════════════════════════════════
# 2. Deny audit semantics
# ═══════════════════════════════════════════════════════════════════════

class TestGl092DenyAuditSemantics(_BaseGl092):
    """Tests for deny audit event semantics."""

    def test_deny_audit_no_approved_true(self):
        """Deny audit event must never contain approved=True."""
        req = self._create_request()
        self.requests_mod.deny_grant_request(req.id, "denier-1", "Not allowed")

        events = self.audit_mod.list_events(limit=10)
        for e in events:
            if e.action == "deny_grant_request":
                self.assertFalse(e.approved, "Deny audit event must have approved=False")

    def test_deny_audit_distinguishable_from_approval(self):
        """Deny audit event must be distinguishable from approval."""
        req = self._create_request()
        denied = self.requests_mod.deny_grant_request(req.id, "denier-1", "Not allowed")
        req2 = self._create_request(subject_id="tech-02")
        approved, grant = self.requests_mod.approve_grant_request(req2.id, "approver-1")

        events = self.audit_mod.list_events(limit=10)
        deny = [e for e in events if e.action == "deny_grant_request"]
        approve = [e for e in events if e.action == "approve_grant_request"]

        self.assertEqual(len(deny), 1)
        self.assertEqual(len(approve), 1)
        self.assertFalse(deny[0].approved)
        self.assertTrue(approve[0].approved)


# ═══════════════════════════════════════════════════════════════════════
# 3. Revoke audit semantics
# ═══════════════════════════════════════════════════════════════════════

class TestGl092RevokeAuditSemantics(_BaseGl092):
    """Tests for revoke audit event semantics."""

    def test_revoke_audit_no_approved_true(self):
        """Revoke audit event must never contain approved=True."""
        req, grant = self._create_and_approve_request()
        self.requests_mod.revoke_grant_request(req.id, "revoker-1", "Security concern")

        events = self.audit_mod.list_events(limit=10)
        for e in events:
            if e.action == "revoke_grant_request":
                self.assertFalse(e.approved, "Revoke audit event must have approved=False")

    def test_revoke_audit_distinguishable_from_approval(self):
        """Revoke audit event must be distinguishable from approval."""
        req, grant = self._create_and_approve_request()
        self.requests_mod.revoke_grant_request(req.id, "revoker-1", "Security concern")

        events = self.audit_mod.list_events(limit=10)
        revoke = [e for e in events if e.action == "revoke_grant_request"]
        approve = [e for e in events if e.action == "approve_grant_request"]

        # _create_and_approve_request creates exactly 1 approval event
        self.assertEqual(len(revoke), 1)
        self.assertEqual(len(approve), 1)
        self.assertFalse(revoke[0].approved)
        self.assertTrue(approve[0].approved)


# ═══════════════════════════════════════════════════════════════════════
# 4. Approval audit semantics preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl092ApprovalAuditSemanticsPreserved(_BaseGl092):
    """Tests ensuring approval audit semantics are not broken."""

    def test_approval_audit_still_approved_true(self):
        """Approve audit must still have approved=True."""
        req = self._create_request()
        self.requests_mod.approve_grant_request(req.id, "approver-1")

        events = self.audit_mod.list_events(limit=10)
        approve = [e for e in events if e.action == "approve_grant_request"]
        self.assertEqual(len(approve), 1)
        self.assertTrue(approve[0].approved)


# ═══════════════════════════════════════════════════════════════════════
# 5. GL-080 revoke atomicity preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl092RevokeAtomicityPreserved(_BaseGl092):
    """Regression tests ensuring GL-080 atomicity stays intact."""

    def test_atomic_revoke_still_works(self):
        """Successful revoke must update both grant and request."""
        req, grant = self._create_and_approve_request()
        revoked = self.requests_mod.revoke_grant_request(req.id, "admin-1", "Security concern")

        self.assertEqual(revoked.status, "revoked")
        grant_after = self.grants_mod.get_grant(grant.id)
        self.assertTrue(grant_after.revoked)

    def test_revoke_rollback_if_request_update_fails(self):
        """If request update fails during revoke, grant must not be revoked."""
        req, grant = self._create_and_approve_request()

        original_get_conn = self.db_mod.get_conn

        def patched_get_conn():
            conn = original_get_conn()
            orig_execute = conn.execute

            def patched_execute(sql, params=None):
                if isinstance(sql, str) and "UPDATE grant_requests" in sql:
                    raise RuntimeError("Simulated request update failure")
                return orig_execute(sql, params)

            conn.execute = patched_execute
            return conn

        self.db_mod.get_conn = patched_get_conn
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.revoke_grant_request(req.id, "admin-1", "Security concern")
        finally:
            self.db_mod.get_conn = original_get_conn

        grant_after = self.grants_mod.get_grant(grant.id)
        self.assertFalse(grant_after.revoked)
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "approved")

    def test_revoke_rollback_if_linked_grant_revoke_fails(self):
        """If linked grant revoke fails, request must remain approved."""
        req, grant = self._create_and_approve_request()

        original_revoke_grant = self.grants_mod.revoke_grant
        def failing_revoke_grant(*args, **kwargs):
            raise RuntimeError("Simulated grant revoke failure")

        self.grants_mod.revoke_grant = failing_revoke_grant
        self.requests_mod.grants.revoke_grant = failing_revoke_grant
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.revoke_grant_request(req.id, "admin-1", "Security concern")
        finally:
            self.grants_mod.revoke_grant = original_revoke_grant
            self.requests_mod.grants.revoke_grant = original_revoke_grant

        grant_after = self.grants_mod.get_grant(grant.id)
        self.assertFalse(grant_after.revoked)
        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "approved")


# ═══════════════════════════════════════════════════════════════════════
# 6. Prior GL protection regressions
# ═══════════════════════════════════════════════════════════════════════

class TestGl092PriorGLRegressions(_BaseGl092):
    """Regression tests for prior GL protections."""

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

    def test_gl091_signature_auth_cache_hardening_intact(self):
        """Auth cache still uses SHA-256 hex, not Python hash()."""
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

        handler = self._make_handler("/grants", auth_header="Bearer owner-token")
        handler.do_GET()
        auth_cache = getattr(handler, "_auth_cache", {})
        for key in auth_cache:
            if key[0] == "operator":
                import hashlib
                digest = key[2]
                self.assertEqual(len(digest), 64)
                expected = hashlib.sha256("Bearer owner-token".encode("utf-8")).hexdigest()
                self.assertEqual(digest, expected)

    def test_gl090_request_body_json_hardening_intact(self):
        """Oversized body still returns 413."""
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.server as fresh_server
        importlib.reload(fresh_server)
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

        oversized = b"x" * (fresh_server.MAX_JSON_BODY_BYTES + 1)
        handler = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token", body=oversized,
        )
        handler.headers["Content-Length"] = str(len(oversized))
        status, body = self._run_handler(handler)
        self.assertEqual(status, 413)
        self.assertEqual(body.get("errorCode"), "payload_too_large")

    def test_gl088_post_challenges_still_protected(self):
        """POST /challenges still requires auth."""
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.server as fresh_server
        importlib.reload(fresh_server)

        valid_body = json.dumps({
            "subjectId": "sub-1", "action": "read", "resource": "repo-a"
        }).encode()
        handler = self._make_handler("/challenges", method="POST", body=valid_body)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_gl087_auth_error_response_consistency_intact(self):
        """Auth error response format remains consistent."""
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.server as fresh_server
        importlib.reload(fresh_server)

        handler = self._make_handler("/grants")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")
        self.assertEqual(body.get("reason"), "Operator authentication is required.")

    def test_gl084_demo_action_still_protected(self):
        """POST /demo-action still requires auth."""
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.server as fresh_server
        importlib.reload(fresh_server)

        demo_body = json.dumps({
            "subjectId": "sub-1", "role": "engineer", "action": "read", "resource": "repo-a"
        }).encode()
        handler = self._make_handler("/demo-action", method="POST", body=demo_body)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")

    def test_gl089_auth_default_fail_closed_intact(self):
        """Without operator model + empty admin token + require_admin=true, endpoints fail closed."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = ""
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        import src.server as fresh_server
        importlib.reload(fresh_server)

        handler = self._make_handler("/grants")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_health_public(self):
        """GET /health remains public."""
        handler = self._make_handler("/health")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_public(self):
        """GET /readiness remains public."""
        handler = self._make_handler("/readiness")
        status, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))


# ═══════════════════════════════════════════════════════════════════════
# 7. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl092NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-092 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-092-deny-revoke-audit-semantics":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-092 feature branch"
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
            "backend/tests/test_gl092_deny_revoke_audit_semantics.py",
            "backend/tests/test_grant_requests.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-092 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
