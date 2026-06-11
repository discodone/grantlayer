"""Tests for GL-103: Audit Hash Chain / Tamper-Evidence Fields.

Ensures:
1.  Migration adds row_hash and prev_hash columns.
2.  Existing audit insertion still works.
3.  New audit event receives row_hash.
4.  First new audit event has expected genesis prev_hash behavior.
5.  Second new audit event prev_hash equals first event row_hash.
6.  row_hash is deterministic SHA-256-like hex string.
7.  Different event contents produce different row_hash.
8.  Hash payload excludes row_hash itself.
9.  Audit event list/select preserves row_hash and prev_hash.
10. GL-102 UPDATE immutability still blocks mutation.
11. GL-102 DELETE immutability still blocks mutation.
12. INSERT remains allowed after GL-102 + GL-103 migrations.
13. Fresh DB migration path works.
14. Repeated migration/idempotency remains safe.
15. No audit verification endpoint added.
16. GL-099 transactional audit consistency preserved.
17. GL-098 expiry audit behavior preserved.
18. GL-092 deny/revoke semantics preserved.
19. GL-100 grant lifecycle/tamper guard preserved.
20. Diff scope limited to allowed files.
"""

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))



class _BaseGl103(unittest.TestCase):
    """Shared helpers for GL-103 tests."""

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

    def _append_audit_event(self, event_id, action="test_action", approved=True, reason="test reason"):
        event = self.models_mod.AuditEvent(
            id=event_id,
            timestamp="2026-01-01T00:00:00Z",
            subject_id="test-subject",
            role="tester",
            action=action,
            resource="test-resource",
            approved=approved,
            reason=reason,
            matched_grant_id=None,
            challenge_id=None,
            challenge_present=False,
            challenge_result="legacy_mode",
            grant_signature_result="not_checked",
        )
        self.audit_mod.append_event(event)
        return event


# ═══════════════════════════════════════════════════════════════════════
# 1. Migration adds row_hash and prev_hash columns
# ═══════════════════════════════════════════════════════════════════════

class TestGl103MigrationAddsColumns(_BaseGl103):
    """Verify the migration creates the expected columns."""

    def test_row_hash_column_exists(self):
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(audit_events)").fetchall()
            names = {r[1] for r in rows}
            self.assertIn("row_hash", names)
        finally:
            conn.close()

    def test_prev_hash_column_exists(self):
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(audit_events)").fetchall()
            names = {r[1] for r in rows}
            self.assertIn("prev_hash", names)
        finally:
            conn.close()

    def test_columns_are_nullable(self):
        """row_hash and prev_hash should allow NULL for pre-existing rows
        and for genesis events."""
        conn = self.db_mod.get_conn()
        try:
            # Insert a minimal row with NULLs
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource,
                    approved, reason, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-null", "2026-01-01T00:00:00Z", "s", "r", "a", "res", 1, "r", None, None)
            )
            conn.commit()
            row = conn.execute(
                "SELECT row_hash, prev_hash FROM audit_events WHERE id = ?", ("evt-null",)
            ).fetchone()
            self.assertIsNone(row["row_hash"])
            self.assertIsNone(row["prev_hash"])
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 2. Existing audit insertion still works
# ═══════════════════════════════════════════════════════════════════════

class TestGl103AuditInsertPreserved(_BaseGl103):
    """INSERT into audit_events must still work via append_event."""

    def test_append_event_inserts_row(self):
        self._append_audit_event("evt-001")
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].id, "evt-001")

    def test_append_event_with_conn_parameter(self):
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
# 3. New audit event receives row_hash
# ═══════════════════════════════════════════════════════════════════════

class TestGl103RowHashPopulated(_BaseGl103):
    """New audit events must receive a row_hash."""

    def test_new_event_has_row_hash(self):
        event = self._append_audit_event("evt-rh-1")
        self.assertIsNotNone(event.row_hash)
        self.assertEqual(len(event.row_hash), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in event.row_hash))

    def test_row_hash_stored_in_db(self):
        self._append_audit_event("evt-rh-2")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT row_hash FROM audit_events WHERE id = ?", ("evt-rh-2",)
            ).fetchone()
            self.assertIsNotNone(row["row_hash"])
            self.assertEqual(len(row["row_hash"]), 64)
        finally:
            conn.close()

    def test_row_hash_on_retrieved_event(self):
        self._append_audit_event("evt-rh-3")
        event = self.audit_mod.get_event("evt-rh-3")
        self.assertIsNotNone(event.row_hash)
        self.assertEqual(len(event.row_hash), 64)

    def test_row_hash_on_listed_event(self):
        self._append_audit_event("evt-rh-4")
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 1)
        self.assertIsNotNone(events[0].row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 4. First new audit event has expected genesis prev_hash behavior
# ═══════════════════════════════════════════════════════════════════════

class TestGl103GenesisPrevHash(_BaseGl103):
    """First event after migration must have NULL prev_hash."""

    def test_first_event_prev_hash_is_none(self):
        event = self._append_audit_event("evt-gen-1")
        self.assertIsNone(event.prev_hash)

    def test_first_event_prev_hash_in_db(self):
        self._append_audit_event("evt-gen-2")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT prev_hash FROM audit_events WHERE id = ?", ("evt-gen-2",)
            ).fetchone()
            self.assertIsNone(row["prev_hash"])
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 5. Second new audit event prev_hash equals first event row_hash
# ═══════════════════════════════════════════════════════════════════════

class TestGl103HashChain(_BaseGl103):
    """Consecutive events must chain via prev_hash."""

    def test_second_event_prev_hash_equals_first_row_hash(self):
        first = self._append_audit_event("evt-chain-1")
        second = self._append_audit_event("evt-chain-2")
        self.assertEqual(second.prev_hash, first.row_hash)

    def test_third_event_chains_too(self):
        first = self._append_audit_event("evt-chain-3")
        second = self._append_audit_event("evt-chain-4")
        third = self._append_audit_event("evt-chain-5")
        self.assertEqual(second.prev_hash, first.row_hash)
        self.assertEqual(third.prev_hash, second.row_hash)

    def test_chain_preserved_in_db(self):
        first = self._append_audit_event("evt-chain-6")
        second = self._append_audit_event("evt-chain-7")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT prev_hash FROM audit_events WHERE id = ?", ("evt-chain-7",)
            ).fetchone()
            self.assertEqual(row["prev_hash"], first.row_hash)
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 6. row_hash is deterministic SHA-256-like hex string
# ═══════════════════════════════════════════════════════════════════════

class TestGl103RowHashDeterministic(_BaseGl103):
    """row_hash must be deterministic."""

    def test_row_hash_is_sha256_hex(self):
        event = self._append_audit_event("evt-det-1")
        self.assertEqual(len(event.row_hash), 64)
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", event.row_hash))

    def test_same_fields_produce_same_hash(self):
        """Two events with identical fields (and same prev_hash context)
        should produce the same row_hash because prev_hash is based on the
        chain state, but we can test determinism by computing manually."""
        event1 = self.models_mod.AuditEvent(
            id="evt-same",
            timestamp="2026-01-01T00:00:00Z",
            subject_id="sub",
            role="r",
            action="a",
            resource="res",
            approved=True,
            reason="reason",
        )
        self.audit_mod.append_event(event1)
        hash1 = event1.row_hash

        # Re-compute directly
        canonical = json.dumps({
            "id": "evt-same",
            "timestamp": "2026-01-01T00:00:00Z",
            "subject_id": "sub",
            "role": "r",
            "action": "a",
            "resource": "res",
            "approved": True,
            "reason": "reason",
            "matched_grant_id": None,
            "challenge_id": None,
            "challenge_present": False,
            "challenge_result": "legacy_mode",
            "grant_signature_result": "not_checked",
            "prev_hash": None,
        }, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertEqual(hash1, expected)


# ═══════════════════════════════════════════════════════════════════════
# 7. Different event contents produce different row_hash
# ═══════════════════════════════════════════════════════════════════════

class TestGl103DifferentContentDifferentHash(_BaseGl103):
    """Different audit contents must yield different row_hash."""

    def test_different_action_different_hash(self):
        e1 = self._append_audit_event("evt-diff-1", action="action_a")
        e2 = self._append_audit_event("evt-diff-2", action="action_b")
        self.assertNotEqual(e1.row_hash, e2.row_hash)

    def test_different_reason_different_hash(self):
        e1 = self._append_audit_event("evt-diff-3", reason="reason_a")
        e2 = self._append_audit_event("evt-diff-4", reason="reason_b")
        self.assertNotEqual(e1.row_hash, e2.row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 8. Hash payload excludes row_hash itself
# ═══════════════════════════════════════════════════════════════════════

class TestGl103HashPayloadExcludesRowHash(_BaseGl103):
    """row_hash must not be part of its own hash payload."""

    def test_payload_excludes_row_hash(self):
        """If row_hash were included in the payload, the hash would not
        be verifiable later. We verify by checking that the hash function
        only uses the helper that does not include row_hash."""
        event = self._append_audit_event("evt-exc-1")
        # Manual re-computation must match
        canonical = json.dumps({
            "id": event.id,
            "timestamp": event.timestamp,
            "subject_id": event.subject_id,
            "role": event.role,
            "action": event.action,
            "resource": event.resource,
            "approved": event.approved,
            "reason": event.reason,
            "matched_grant_id": event.matched_grant_id,
            "challenge_id": event.challenge_id,
            "challenge_present": event.challenge_present,
            "challenge_result": event.challenge_result,
            "grant_signature_result": event.grant_signature_result,
            "prev_hash": event.prev_hash,
        }, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertEqual(event.row_hash, expected)


# ═══════════════════════════════════════════════════════════════════════
# 9. Audit event list/select preserves row_hash and prev_hash
# ═══════════════════════════════════════════════════════════════════════

class TestGl103SelectPreservesHashes(_BaseGl103):
    """SELECT/list must return row_hash and prev_hash."""

    def test_get_event_preserves_hashes(self):
        self._append_audit_event("evt-sel-1")
        event = self.audit_mod.get_event("evt-sel-1")
        self.assertIsNotNone(event.row_hash)
        self.assertIsNotNone(event)
        self.assertTrue(hasattr(event, "row_hash"))
        self.assertTrue(hasattr(event, "prev_hash"))

    def test_list_events_preserves_hashes(self):
        self._append_audit_event("evt-sel-2")
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 1)
        self.assertIsNotNone(events[0].row_hash)

    def test_list_events_by_grant_preserves_hashes(self):
        event = self.models_mod.AuditEvent(
            id="evt-sel-3",
            timestamp="2026-01-01T00:00:00Z",
            subject_id="sub",
            role="r",
            action="a",
            resource="res",
            approved=True,
            reason="r",
            matched_grant_id="grant-123",
        )
        self.audit_mod.append_event(event)
        events = self.audit_mod.list_events_by_grant("grant-123")
        self.assertEqual(len(events), 1)
        self.assertIsNotNone(events[0].row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 10. GL-102 UPDATE immutability still blocks mutation
# ═══════════════════════════════════════════════════════════════════════

class TestGl103UpdateImmutabilityPreserved(_BaseGl103):
    """UPDATE on audit_events must still raise an error."""

    def test_direct_update_fails(self):
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
# 11. GL-102 DELETE immutability still blocks mutation
# ═══════════════════════════════════════════════════════════════════════

class TestGl103DeleteImmutabilityPreserved(_BaseGl103):
    """DELETE on audit_events must still raise an error."""

    def test_direct_delete_fails(self):
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
# 12. INSERT remains allowed after GL-102 + GL-103 migrations
# ═══════════════════════════════════════════════════════════════════════

class TestGl103InsertAllowed(_BaseGl103):
    """INSERT must still work after both migrations."""

    def test_multiple_inserts_succeed(self):
        for i in range(5):
            self._append_audit_event(f"evt-ins-{i}")
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 5)


# ═══════════════════════════════════════════════════════════════════════
# 13. Fresh DB migration path works
# ═══════════════════════════════════════════════════════════════════════

class TestGl103FreshDbMigration(_BaseGl103):
    """Fresh database initialization must apply GL-103 columns."""

    def test_fresh_db_has_hash_columns(self):
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(audit_events)").fetchall()
            names = {r[1] for r in rows}
            self.assertIn("row_hash", names)
            self.assertIn("prev_hash", names)
        finally:
            conn.close()

    def test_fresh_db_can_insert_and_chain(self):
        self._append_audit_event("evt-fresh-1")
        self._append_audit_event("evt-fresh-2")
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 2)
        # Ordered DESC by timestamp
        second = [e for e in events if e.id == "evt-fresh-2"][0]
        first = [e for e in events if e.id == "evt-fresh-1"][0]
        self.assertIsNone(first.prev_hash)
        self.assertEqual(second.prev_hash, first.row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 14. Repeated migration/idempotency remains safe
# ═══════════════════════════════════════════════════════════════════════

class TestGl103MigrationIdempotency(_BaseGl103):
    """Re-running the migration must not fail."""

    def test_repeated_apply_does_not_raise(self):
        import backend.src.migrations.runner as runner_mod
        importlib.reload(runner_mod)

        conn = self.db_mod.get_conn()
        try:
            runner_mod.run_migrations(conn)
        finally:
            conn.close()

        # Verify columns still exist and INSERT still works
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(audit_events)").fetchall()
            names = {r[1] for r in rows}
            self.assertIn("row_hash", names)
            self.assertIn("prev_hash", names)
        finally:
            conn.close()

        self._append_audit_event("evt-idem-1")
        events = self.audit_mod.list_events(limit=10)
        ids = [e.id for e in events]
        self.assertIn("evt-idem-1", ids)


# ═══════════════════════════════════════════════════════════════════════
# 15. No audit verification endpoint added
# ═══════════════════════════════════════════════════════════════════════

class TestGl103NoVerificationEndpoint(_BaseGl103):
    """Ensure no audit verification endpoint was added."""

    def test_no_verify_audit_route(self):
        req = self._make_handler("/audit/verify")
        status, data = self._run_handler(req)
        self.assertEqual(status, 404)

    def test_no_verify_hash_route(self):
        req = self._make_handler("/audit/verify-hash")
        status, data = self._run_handler(req)
        self.assertEqual(status, 404)


# ═══════════════════════════════════════════════════════════════════════
# 16. GL-099 transactional audit consistency preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl103Gl099Preserved(_BaseGl103):
    """GL-099 transactional audit consistency must remain intact."""

    def test_approval_audit_failure_rolls_back_state(self):
        req = self.models_mod.GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
        )
        req = self.requests_mod.create_grant_request(req)

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

    def test_valid_approval_still_succeeds_and_emits_audit(self):
        req = self.models_mod.GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
        )
        req = self.requests_mod.create_grant_request(req)
        updated_req, grant = self.requests_mod.approve_grant_request(req.id, "approver-1")

        self.assertEqual(updated_req.status, "approved")
        self.assertIsNotNone(grant)

        events = self.audit_mod.list_events(limit=10)
        approve_events = [e for e in events if e.action == "approve_grant_request"]
        self.assertEqual(len(approve_events), 1)
        self.assertTrue(approve_events[0].approved)
        self.assertIsNotNone(approve_events[0].row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 17. GL-098 expiry audit behavior preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl103Gl098Preserved(_BaseGl103):
    """GL-098 expiry audit behavior must remain intact."""

    def test_expiry_creates_audit_event(self):
        import datetime
        old_time = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=25)
        ).isoformat().replace("+00:00", "Z")
        req = self.models_mod.GrantRequest(
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
        req = self.requests_mod.create_grant_request(req)
        count = self.requests_mod.expire_old_requests()
        self.assertEqual(count, 1)
        events = self.audit_mod.list_events(limit=10)
        expire_events = [e for e in events if e.action == "expire_grant_request"]
        self.assertEqual(len(expire_events), 1)
        self.assertIsNotNone(expire_events[0].row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 18. GL-092 deny/revoke audit semantics preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl103Gl092Preserved(_BaseGl103):
    """GL-092 deny/revoke audit semantics must remain intact."""

    def test_deny_audit_still_approved_false(self):
        req = self.models_mod.GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
        )
        req = self.requests_mod.create_grant_request(req)
        self.requests_mod.deny_grant_request(req.id, "denier-1", "Not allowed")
        events = self.audit_mod.list_events(limit=10)
        deny_events = [e for e in events if e.action == "deny_grant_request"]
        self.assertEqual(len(deny_events), 1)
        self.assertFalse(deny_events[0].approved)
        self.assertIsNotNone(deny_events[0].row_hash)

    def test_revoke_audit_still_approved_false(self):
        req = self.models_mod.GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
        )
        req = self.requests_mod.create_grant_request(req)
        self.requests_mod.approve_grant_request(req.id, "approver-1")
        self.requests_mod.revoke_grant_request(req.id, "revoker-1", "Security concern")
        events = self.audit_mod.list_events(limit=10)
        revoke_events = [e for e in events if e.action == "revoke_grant_request"]
        self.assertEqual(len(revoke_events), 1)
        self.assertFalse(revoke_events[0].approved)
        self.assertIsNotNone(revoke_events[0].row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 19. GL-100 grant lifecycle/tamper guard preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl103Gl100Preserved(_BaseGl103):
    """GL-100 grant lifecycle and tamper guard must remain intact."""

    def test_tamper_grant_direct_call_works(self):
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
        import backend.src.demo_action as demo_mod
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
        self.assertIsNotNone(events[0].row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 20. Server safety / boundary checks
# ═══════════════════════════════════════════════════════════════════════

class TestGl103ServerSafety(_BaseGl103):
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
# 21. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl103NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-103 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-103-audit-hash-chain-tamper-evidence":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-103 feature branch"
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
            "backend/src/models.py",
            "backend/src/migrations/0006_gl103_audit_hash_chain.py",
            "backend/src/migrations/runner.py",
            "backend/tests/test_gl103_audit_hash_chain.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-103 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
