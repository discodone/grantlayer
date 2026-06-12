"""Tests for GL-102: Audit Log Database Immutability.

Ensures:
1. Migration creates immutability guard (triggers preventing UPDATE/DELETE).
2. Audit helper can insert audit_events.
3. Selecting/listing audit_events still works.
4. Direct UPDATE audit_events fails.
5. Direct DELETE audit_events fails.
6. Failed UPDATE leaves row unchanged.
7. Failed DELETE leaves row present.
8. Multiple audit inserts still work.
9. Fresh DB migration path works.
10. Repeated migration/idempotency behavior remains safe.
11. GL-099 transactional audit consistency preserved.
12. GL-098 expiry audit behavior preserved.
13. GL-092 deny/revoke audit semantics preserved.
14. GL-100 grant lifecycle/tamper guard preserved.
15. Diff scope limited to allowed files.
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



class _BaseGl102(unittest.TestCase):
    """Shared helpers for GL-102 tests."""

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

    def _create_request(self, **kwargs):
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

    def _append_audit_event(self, event_id, action="test_action", approved=True):
        event = self.models_mod.AuditEvent(
            id=event_id,
            timestamp="2026-01-01T00:00:00Z",
            subject_id="test-subject",
            role="tester",
            action=action,
            resource="test-resource",
            approved=approved,
            reason="test reason",
            matched_grant_id=None,
            challenge_id=None,
            challenge_present=False,
            challenge_result="legacy_mode",
            grant_signature_result="not_checked",
        )
        self.audit_mod.append_event(event)
        return event


# ═══════════════════════════════════════════════════════════════════════
# 1. Migration creates immutability guard
# ═══════════════════════════════════════════════════════════════════════

class TestGl102MigrationCreatesGuard(_BaseGl102):
    """Verify the migration creates the expected triggers."""

    def test_triggers_exist_after_migration(self):
        """Both BEFORE UPDATE and BEFORE DELETE triggers must exist."""
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='audit_events'"
            ).fetchall()
            names = {r["name"] if isinstance(r, dict) else r[0] for r in rows}
            self.assertIn("trg_audit_events_no_update", names)
            self.assertIn("trg_audit_events_no_delete", names)
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 2. Audit helper can insert audit_events
# ═══════════════════════════════════════════════════════════════════════

class TestGl102AuditInsertPreserved(_BaseGl102):
    """INSERT into audit_events must still work."""

    def test_append_event_inserts_row(self):
        """append_event must create a row."""
        self._append_audit_event("evt-001")
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].id, "evt-001")

    def test_append_event_with_conn_parameter(self):
        """append_event with explicit conn must still work."""
        conn = self.db_mod.get_conn()
        try:
            event = self.models_mod.AuditEvent(
                id="evt-conn-001",
                timestamp="2026-01-01T00:00:00Z",
                subject_id="sub",
                role="r",
                action="a",
                resource="res",
                approved=True,
                reason="reason",
                matched_grant_id=None,
                challenge_id=None,
                challenge_present=False,
                challenge_result="legacy_mode",
                grant_signature_result="not_checked",
            )
            self.audit_mod.append_event(event, conn=conn)
            conn.commit()
        finally:
            conn.close()
        events = self.audit_mod.list_events(limit=10)
        ids = [e.id for e in events]
        self.assertIn("evt-conn-001", ids)


# ═══════════════════════════════════════════════════════════════════════
# 3. Selecting/listing audit_events still works
# ═══════════════════════════════════════════════════════════════════════

class TestGl102AuditSelectPreserved(_BaseGl102):
    """SELECT/list operations on audit_events must still work."""

    def test_list_events_returns_rows(self):
        """list_events must return inserted rows."""
        self._append_audit_event("evt-s1", action="action_a")
        self._append_audit_event("evt-s2", action="action_b")
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 2)

    def test_get_event_by_id(self):
        """get_event must retrieve a single row by ID."""
        self._append_audit_event("evt-g1")
        event = self.audit_mod.get_event("evt-g1")
        self.assertIsNotNone(event)
        self.assertEqual(event.id, "evt-g1")

    def test_list_events_by_grant(self):
        """list_events_by_grant must still work."""
        event = self.models_mod.AuditEvent(
            id="evt-grant-1",
            timestamp="2026-01-01T00:00:00Z",
            subject_id="sub",
            role="r",
            action="a",
            resource="res",
            approved=True,
            reason="r",
            matched_grant_id="grant-123",
            challenge_id=None,
            challenge_present=False,
            challenge_result="legacy_mode",
            grant_signature_result="not_checked",
        )
        self.audit_mod.append_event(event)
        events = self.audit_mod.list_events_by_grant("grant-123")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].matched_grant_id, "grant-123")

    def test_list_events_limit_and_order(self):
        """list_events respects limit and ordering."""
        for i in range(3):
            self._append_audit_event(f"evt-lo-{i}")
        events = self.audit_mod.list_events(limit=2)
        self.assertEqual(len(events), 2)


# ═══════════════════════════════════════════════════════════════════════
# 4. Direct UPDATE audit_events fails
# ═══════════════════════════════════════════════════════════════════════

class TestGl102UpdateBlocked(_BaseGl102):
    """UPDATE on audit_events must raise an error."""

    def test_direct_update_fails(self):
        """Direct UPDATE must be rejected by the trigger."""
        self._append_audit_event("evt-upd-1")
        conn = self.db_mod.get_conn()
        try:
            with self.assertRaises(Exception) as ctx:
                conn.execute(
                    "UPDATE audit_events SET reason = 'tampered' WHERE id = ?",
                    ("evt-upd-1",),
                )
            msg = str(ctx.exception).lower()
            self.assertIn("immutable", msg)
            self.assertIn("update", msg)
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 5. Direct DELETE audit_events fails
# ═══════════════════════════════════════════════════════════════════════

class TestGl102DeleteBlocked(_BaseGl102):
    """DELETE on audit_events must raise an error."""

    def test_direct_delete_fails(self):
        """Direct DELETE must be rejected by the trigger."""
        self._append_audit_event("evt-del-1")
        conn = self.db_mod.get_conn()
        try:
            with self.assertRaises(Exception) as ctx:
                conn.execute(
                    "DELETE FROM audit_events WHERE id = ?",
                    ("evt-del-1",),
                )
            msg = str(ctx.exception).lower()
            self.assertIn("immutable", msg)
            self.assertIn("delete", msg)
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 6. Failed UPDATE leaves row unchanged
# ═══════════════════════════════════════════════════════════════════════

class TestGl102FailedUpdateLeavesRowUnchanged(_BaseGl102):
    """A blocked UPDATE must not mutate the row."""

    def test_failed_update_preserves_original_reason(self):
        """Original reason must remain after a rejected UPDATE."""
        self._append_audit_event("evt-upd-preserve", action="original_action")
        conn = self.db_mod.get_conn()
        try:
            try:
                conn.execute(
                    "UPDATE audit_events SET action = 'tampered' WHERE id = ?",
                    ("evt-upd-preserve",),
                )
            except Exception:
                pass
        finally:
            conn.close()
        event = self.audit_mod.get_event("evt-upd-preserve")
        self.assertEqual(event.action, "original_action")


# ═══════════════════════════════════════════════════════════════════════
# 7. Failed DELETE leaves row present
# ═══════════════════════════════════════════════════════════════════════

class TestGl102FailedDeleteLeavesRowPresent(_BaseGl102):
    """A blocked DELETE must not remove the row."""

    def test_failed_delete_preserves_row(self):
        """Row must remain after a rejected DELETE."""
        self._append_audit_event("evt-del-preserve")
        conn = self.db_mod.get_conn()
        try:
            try:
                conn.execute(
                    "DELETE FROM audit_events WHERE id = ?",
                    ("evt-del-preserve",),
                )
            except Exception:
                pass
        finally:
            conn.close()
        event = self.audit_mod.get_event("evt-del-preserve")
        self.assertIsNotNone(event)


# ═══════════════════════════════════════════════════════════════════════
# 8. Multiple audit inserts still work
# ═══════════════════════════════════════════════════════════════════════

class TestGl102MultipleInserts(_BaseGl102):
    """Many INSERTs must succeed sequentially."""

    def test_many_inserts_succeed(self):
        """Inserting many audit events must all succeed."""
        for i in range(10):
            self._append_audit_event(f"evt-batch-{i}")
        events = self.audit_mod.list_events(limit=20)
        self.assertEqual(len(events), 10)


# ═══════════════════════════════════════════════════════════════════════
# 9. Fresh DB migration path works
# ═══════════════════════════════════════════════════════════════════════

class TestGl102FreshDbMigration(_BaseGl102):
    """Fresh database initialization must apply the migration."""

    def test_fresh_db_has_triggers(self):
        """After init_db(), immutability triggers must exist."""
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='audit_events'"
            ).fetchall()
            names = {r["name"] if isinstance(r, dict) else r[0] for r in rows}
            self.assertIn("trg_audit_events_no_update", names)
            self.assertIn("trg_audit_events_no_delete", names)
        finally:
            conn.close()

    def test_fresh_db_can_insert_and_select(self):
        """Fresh DB must allow insert and select on audit_events."""
        self._append_audit_event("evt-fresh-1")
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].id, "evt-fresh-1")


# ═══════════════════════════════════════════════════════════════════════
# 10. Repeated migration/idempotency safe
# ═══════════════════════════════════════════════════════════════════════

class TestGl102MigrationIdempotency(_BaseGl102):
    """Re-running the migration must not fail."""

    def test_repeated_apply_does_not_raise(self):
        """Applying the migration twice must be safe."""
        import backend.src.migrations.runner as runner_mod
        importlib.reload(runner_mod)

        conn = self.db_mod.get_conn()
        try:
            # Running migrations again should not raise
            runner_mod.run_migrations(conn)
        finally:
            conn.close()

        # Verify triggers still exist and INSERT still works
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='audit_events'"
            ).fetchall()
            names = {r["name"] if isinstance(r, dict) else r[0] for r in rows}
            self.assertIn("trg_audit_events_no_update", names)
            self.assertIn("trg_audit_events_no_delete", names)
        finally:
            conn.close()

        self._append_audit_event("evt-idem-1")
        events = self.audit_mod.list_events(limit=10)
        ids = [e.id for e in events]
        self.assertIn("evt-idem-1", ids)


# ═══════════════════════════════════════════════════════════════════════
# 11. GL-099 transactional audit consistency preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl102Gl099Preserved(_BaseGl102):
    """GL-099 transactional audit consistency must remain intact."""

    def test_approval_audit_failure_rolls_back_state(self):
        """If audit append fails during approval, request must stay requested."""
        req = self._create_request()
        original_append = self.audit_mod.append_event

        def failing_append(event, conn=None):
            raise RuntimeError("Simulated audit failure")

        self.audit_mod.append_event = failing_append
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.approve_grant_request(req.id, "approver-1")
        finally:
            self.audit_mod.append_event = original_append

        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "requested")
        self.assertIsNone(req_after.approved_by)
        grants = self.grants_mod.list_grants()
        self.assertEqual(len(grants), 0)

    def test_revoke_audit_failure_rolls_back_state(self):
        """If audit append fails during revoke, request must stay approved."""
        req = self._create_request()
        self.requests_mod.approve_grant_request(req.id, "approver-1")

        original_append = self.audit_mod.append_event

        def failing_revoke_append(event, conn=None):
            if event.action == "revoke_grant_request":
                raise RuntimeError("Simulated revoke audit failure")
            return original_append(event, conn=conn)

        self.audit_mod.append_event = failing_revoke_append
        try:
            with self.assertRaises(RuntimeError):
                self.requests_mod.revoke_grant_request(req.id, "approver-1", "Test")
        finally:
            self.audit_mod.append_event = original_append

        req_after = self.requests_mod.get_grant_request(req.id)
        self.assertEqual(req_after.status, "approved")

    def test_valid_approval_still_succeeds_and_emits_audit(self):
        """Successful approval must create request, grant, and audit event."""
        req = self._create_request()
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, "approver-1")

        self.assertEqual(updated_req.status, "approved")
        self.assertIsNotNone(grant)

        events = self.audit_mod.list_events(limit=10)
        approve_events = [e for e in events if e.action == "approve_grant_request"]
        self.assertEqual(len(approve_events), 1)
        self.assertTrue(approve_events[0].approved)


# ═══════════════════════════════════════════════════════════════════════
# 12. GL-098 expiry audit behavior preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl102Gl098Preserved(_BaseGl102):
    """GL-098 expiry audit behavior must remain intact."""

    def test_expiry_creates_audit_event(self):
        """expire_old_requests must create an audit event."""
        import datetime
        old_time = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=25)
        ).isoformat().replace("+00:00", "Z")
        req = self._create_request(created_at=old_time, updated_at=old_time)
        count = self.requests_mod.expire_old_requests()
        self.assertEqual(count, 1)
        events = self.audit_mod.list_events(limit=10)
        expire_events = [e for e in events if e.action == "expire_grant_request"]
        self.assertEqual(len(expire_events), 1)

    def test_repeated_expiry_does_not_duplicate_audit(self):
        """Running expire_old_requests again must not create duplicate audit events."""
        import datetime
        old_time = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=25)
        ).isoformat().replace("+00:00", "Z")
        self._create_request(created_at=old_time, updated_at=old_time)
        self.requests_mod.expire_old_requests()
        self.requests_mod.expire_old_requests()
        events = self.audit_mod.list_events(limit=10)
        expire_events = [e for e in events if e.action == "expire_grant_request"]
        self.assertEqual(len(expire_events), 1)


# ═══════════════════════════════════════════════════════════════════════
# 13. GL-092 deny/revoke audit semantics preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl102Gl092Preserved(_BaseGl102):
    """GL-092 deny/revoke audit semantics must remain intact."""

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
# 14. GL-100 grant lifecycle/tamper guard preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl102Gl100Preserved(_BaseGl102):
    """GL-100 grant lifecycle and tamper guard must remain intact."""

    def test_tamper_grant_direct_call_works(self):
        """tamper_grant() must still be callable for test/simulation."""
        g = self.models_mod.Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Direct grant for testing",
        )
        self.grants_mod.create_grant(g)
        result = self.grants_mod.tamper_grant(g.id)
        self.assertIsNotNone(result)
        self.assertTrue(result.get("ok"))

    def test_demo_action_audit_with_matched_grant_id(self):
        """demo_action must still create audit with matched_grant_id."""
        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)

        g = self.models_mod.Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Direct grant for testing",
        )
        self.grants_mod.create_grant(g)
        demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].approved)
        self.assertEqual(events[0].matched_grant_id, g.id)


# ═══════════════════════════════════════════════════════════════════════
# 15. Server safety / boundary checks
# ═══════════════════════════════════════════════════════════════════════

class TestGl102ServerSafety(_BaseGl102):
    """Server-layer safety checks."""

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

    def test_protected_endpoint_requires_auth(self):
        """GET /grants requires operator auth."""
        req = self._make_handler("/grants")
        status, data = self._run_handler(req)
        self.assertIn(status, (401, 403))


# ═══════════════════════════════════════════════════════════════════════
# 16. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl102NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-102 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-102-audit-log-db-immutability":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-102 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/audit_log.py",
            "backend/src/db.py",
            "backend/src/migrations/0005_gl102_audit_log_immutability.py",
            "backend/src/migrations/runner.py",
            "backend/tests/test_gl102_audit_log_db_immutability.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-102 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
