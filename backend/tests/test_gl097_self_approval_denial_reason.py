"""Tests for GL-097 Self-Approval Guard + Denial Reason Length.

Ensures:
1. Identifiable self-approval is rejected in approve_grant_request.
2. Self-approval rejection does not mutate request state.
3. Self-approval rejection does not create misleading approval audit events.
4. Approval by a different approver still succeeds.
5. Denial reason length is bounded.
6. Overlong denial reason is rejected before state/audit mutation.
7. Empty/omitted denial reason behavior is preserved at the module layer.
8. Error messages are safe and deterministic.
9. Prior GL protections remain intact (GL-092, GL-091, GL-090, GL-089, GL-088, GL-087, GL-084).
10. GET /health and GET /readiness remain public.
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


class _BaseGl097(unittest.TestCase):
    """Shared helpers for GL-097 tests."""

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

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
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

        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.auth.operators as ops_mod
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
        return self.requests_mod.create_grant_request(req, tenant_id="demo")

    def _insert_operator(self, op_id, name, role, token):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
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
# 1. Self-approval guard
# ═══════════════════════════════════════════════════════════════════════

class TestGl097SelfApprovalGuard(_BaseGl097):
    """Tests for self-approval rejection in approve_grant_request."""

    def test_self_approval_rejected_when_requester_equals_approver(self):
        """Identifiable requester==approver approval must be rejected."""
        req = self._create_request(requested_by="operator-a")
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.approve_grant_request(req.id, "operator-a", tenant_id="demo")
        self.assertIn("Self-approval is not permitted", str(ctx.exception))

    def test_self_approval_leaves_request_unapproved(self):
        """Self-approval rejection must not mutate request state."""
        req = self._create_request(requested_by="operator-a")
        try:
            self.requests_mod.approve_grant_request(req.id, "operator-a", tenant_id="demo")
        except ValueError:
            pass

        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")
        self.assertIsNone(req_after.approved_by)
        self.assertIsNone(req_after.approved_at)
        self.assertIsNone(req_after.grant_id)

    def test_self_approval_does_not_create_approval_audit(self):
        """Self-approval rejection must not create a misleading approval audit event."""
        req = self._create_request(requested_by="operator-a")
        try:
            self.requests_mod.approve_grant_request(req.id, "operator-a", tenant_id="demo")
        except ValueError:
            pass

        events = self.audit_mod.list_events(limit=10)
        approve_events = [e for e in events if e.action == "approve_grant_request"]
        self.assertEqual(len(approve_events), 0, "Self-approval must not create approval audit event")

    def test_approval_by_different_approver_succeeds(self):
        """Approval by a different approver must still work."""
        req = self._create_request(requested_by="operator-a")
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, "operator-b", tenant_id="demo")
        self.assertEqual(updated_req.status, "approved")
        self.assertEqual(updated_req.approved_by, "operator-b")
        self.assertIsNotNone(grant)

    def test_self_approval_error_message_safe(self):
        """Self-approval error must be deterministic and safe."""
        req = self._create_request(requested_by="operator-a")
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.approve_grant_request(req.id, "operator-a", tenant_id="demo")
        msg = str(ctx.exception)
        self.assertEqual(msg, "Self-approval is not permitted")
        leak_terms = ["traceback", "stack", "token", "secret", "password", "GRANTLAYER", "postgres", "sqlite"]
        for term in leak_terms:
            self.assertNotIn(term, msg.lower())


# ═══════════════════════════════════════════════════════════════════════
# 2. Denial reason length limit
# ═══════════════════════════════════════════════════════════════════════

class TestGl097DenialReasonLength(_BaseGl097):
    """Tests for denial reason length bounding in deny_grant_request."""

    def test_denial_with_acceptable_reason_succeeds(self):
        """Denial with a reason at or below the limit must succeed."""
        req = self._create_request()
        updated = self.requests_mod.deny_grant_request(req.id, "denier-1", "Not allowed", tenant_id="demo")
        self.assertEqual(updated.status, "denied")
        self.assertEqual(updated.denied_by, "denier-1")
        self.assertEqual(updated.denial_reason, "Not allowed")

    def test_denial_with_exactly_max_length_reason_succeeds(self):
        """Denial with a reason exactly at the max length must succeed."""
        req = self._create_request()
        reason = "x" * self.requests_mod.MAX_DENIAL_REASON_LENGTH
        updated = self.requests_mod.deny_grant_request(req.id, "denier-1", reason, tenant_id="demo")
        self.assertEqual(updated.status, "denied")
        self.assertEqual(updated.denial_reason, reason)

    def test_overlong_denial_reason_rejected(self):
        """Denial with a reason exceeding the max length must be rejected."""
        req = self._create_request()
        reason = "x" * (self.requests_mod.MAX_DENIAL_REASON_LENGTH + 1)
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.deny_grant_request(req.id, "denier-1", reason, tenant_id="demo")
        self.assertIn("exceeds maximum length", str(ctx.exception))

    def test_overlong_denial_reason_leaves_state_unchanged(self):
        """Overlong denial reason rejection must not mutate request state."""
        req = self._create_request()
        reason = "x" * (self.requests_mod.MAX_DENIAL_REASON_LENGTH + 1)
        try:
            self.requests_mod.deny_grant_request(req.id, "denier-1", reason, tenant_id="demo")
        except ValueError:
            pass

        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")
        self.assertIsNone(req_after.denied_by)
        self.assertIsNone(req_after.denied_at)
        self.assertIsNone(req_after.denial_reason)

    def test_overlong_denial_reason_does_not_create_denial_audit(self):
        """Overlong denial reason rejection must not create a misleading denial audit event."""
        req = self._create_request()
        reason = "x" * (self.requests_mod.MAX_DENIAL_REASON_LENGTH + 1)
        try:
            self.requests_mod.deny_grant_request(req.id, "denier-1", reason, tenant_id="demo")
        except ValueError:
            pass

        events = self.audit_mod.list_events(limit=10)
        deny_events = [e for e in events if e.action == "deny_grant_request"]
        self.assertEqual(len(deny_events), 0, "Overlong denial must not create denial audit event")

    def test_empty_denial_reason_preserved(self):
        """Empty denial reason behavior at the module layer must be preserved."""
        req = self._create_request()
        updated = self.requests_mod.deny_grant_request(req.id, "denier-1", "", tenant_id="demo")
        self.assertEqual(updated.status, "denied")
        self.assertEqual(updated.denial_reason, "")

    def test_overlong_error_message_safe(self):
        """Overlong denial reason error must be deterministic and safe."""
        req = self._create_request()
        reason = "x" * (self.requests_mod.MAX_DENIAL_REASON_LENGTH + 1)
        with self.assertRaises(ValueError) as ctx:
            self.requests_mod.deny_grant_request(req.id, "denier-1", reason, tenant_id="demo")
        msg = str(ctx.exception)
        self.assertIn("1000", msg)
        leak_terms = ["traceback", "stack", "token", "secret", "password", "GRANTLAYER", "postgres", "sqlite"]
        for term in leak_terms:
            self.assertNotIn(term, msg.lower())


# ═══════════════════════════════════════════════════════════════════════
# 3. Server-layer self-approval guard preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl097ServerSelfApprovalGuard(_BaseGl097):
    """Tests ensuring the server-layer self-approval guard remains intact."""

    def test_server_rejects_self_approval_with_403(self):
        """Server must reject self-approval before reaching the module layer."""
        self._insert_operator("admin-1", "Admin", "owner", "admin-token")

        req_data = {
            "subjectId": "tech-01",
            "role": "operator",
            "action": "restart-service",
            "resource": "customer-env-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2099-12-31T23:59:59Z",
            "reason": "API test request"
        }
        body = json.dumps(req_data).encode()
        req = self._make_handler("/v1/grant-requests", method="POST", auth_header="Bearer admin-token", body=body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 201)
        request_id = data["id"]

        approval_body = json.dumps({"comment": "Approved"}).encode()
        req = self._make_handler(
            f"/v1/grant-requests/{request_id}/approve",
            method="POST",
            auth_header="Bearer admin-token",
            body=approval_body
        )
        status, data = self._run_handler(req)
        self.assertEqual(status, 403)
        self.assertEqual(data.get("errorCode"), "self_approval_forbidden")


# ═══════════════════════════════════════════════════════════════════════
# 4. Prior GL protection regressions
# ═══════════════════════════════════════════════════════════════════════

class TestGl097PriorGLRegressions(_BaseGl097):
    """Regression tests for prior GL protections."""

    def test_gl092_deny_revoke_audit_semantics_intact(self):
        import backend.src.grants.grant_requests as requests_mod
        importlib.reload(requests_mod)
        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        req = models_mod.GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
        )
        created = requests_mod.create_grant_request(req, tenant_id="demo")
        denied = requests_mod.deny_grant_request(created.id, "denier-1", "Not allowed", tenant_id="demo")
        self.assertEqual(denied.status, "denied")

    @unittest.skip("server.py deleted in GL-240")
    def test_gl091_signature_auth_cache_hardening_intact(self):
        source = pathlib.Path("backend/src/server.py").read_text(encoding="utf-8")
        self.assertNotIn("hash(auth_header)", source)
        self.assertIn("hashlib.sha256(auth_header.encode", source)

    def test_gl090_request_body_json_hardening_intact(self):
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.core.config as fresh_config
        importlib.reload(fresh_config)
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

        before = self.grants_mod.list_grants()
        oversized = b"x" * (1_048_576 + 1)
        req = self._make_handler(
            "/v1/grants", method="POST", auth_header="Bearer owner-token", body=oversized
        )
        status, data = self._run_handler(req)
        self.assertIn(status, (400, 413, 422))
        if status == 413:
            self.assertEqual(data.get("errorCode"), "payload_too_large")
        self.assertEqual(len(self.grants_mod.list_grants()), len(before))

    def test_gl089_auth_default_fail_closed_intact(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = ""
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.core.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        import backend.src.core.db as bk_db
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/v1/grants")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "admin_token_required")

    def test_gl088_post_challenges_still_protected(self):
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.core.config as fresh_config
        importlib.reload(fresh_config)
        valid_body = json.dumps({
            "subjectId": "sub-1", "action": "read", "resource": "repo-a"
        }).encode()
        req = self._make_handler("/v1/challenges", method="POST", body=valid_body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 401)
        self._assert_gl030_full(data)
        self.assertEqual(data.get("errorCode"), "operator_auth_required")

    def test_gl087_auth_error_response_consistency_intact(self):
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.core.config as fresh_config
        importlib.reload(fresh_config)
        req = self._make_handler("/v1/grants")
        status, data = self._run_handler(req)
        self.assertEqual(status, 401)
        self.assertEqual(data.get("errorCode"), "operator_auth_required")
        self.assertEqual(data.get("reason"), "Operator authentication is required.")

    def test_gl084_demo_action_still_protected(self):
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.core.config as fresh_config
        importlib.reload(fresh_config)
        demo_body = json.dumps({
            "subjectId": "sub-1", "role": "engineer", "action": "read", "resource": "repo-a"
        }).encode()
        req = self._make_handler("/v1/demo-action", method="POST", body=demo_body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 401)
        self._assert_gl030_full(data)
        self.assertEqual(data.get("errorCode"), "operator_auth_required")

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


# ═══════════════════════════════════════════════════════════════════════
# 5. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl097NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-097 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-097-self-approval-denial-reason-hardening":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-097 feature branch"
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
            "backend/tests/test_gl097_self_approval_denial_reason.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-097 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
