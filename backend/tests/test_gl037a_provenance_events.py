"""GL-037-A — Provenance Event Model & Persistence tests.

Covers migration, model, record, get, list, filtering, validation,
metadata_json round-trip, and append-only contract.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestProvenanceEvents(unittest.TestCase):
    """Provenance event persistence tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")

        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        if self._orig_url is not None:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

        from backend.src.policy.provenance import (
            record_provenance_event,
            get_provenance_event,
            list_provenance_events,
            _VALID_ACTOR_TYPES,
            _VALID_EVENT_TYPES,
        )
        self.record = record_provenance_event
        self.get = get_provenance_event
        self.list = list_provenance_events
        self.valid_actor_types = _VALID_ACTOR_TYPES
        self.valid_event_types = _VALID_EVENT_TYPES

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_url is not None:
            os.environ["GRANTLAYER_DATABASE_URL"] = self._orig_url
        else:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    # ── Migration ───────────────────────────────────────────────
    def test_migration_creates_provenance_events_table(self):
        conn = self.db.get_conn()
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            self.assertIn("provenance_events", tables)
        finally:
            conn.close()

    def test_migration_creates_all_indexes(self):
        conn = self.db.get_conn()
        try:
            indexes = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='provenance_events'"
            ).fetchall()}
            self.assertIn("idx_provenance_events_execution_id", indexes)
            self.assertIn("idx_provenance_events_grant_id", indexes)
            self.assertIn("idx_provenance_events_actor_type", indexes)
            self.assertIn("idx_provenance_events_occurred_at", indexes)
            self.assertIn("idx_provenance_events_resource_type_resource_id", indexes)
        finally:
            conn.close()

    def test_migration_columns_exist(self):
        conn = self.db.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(provenance_events)").fetchall()
            columns = {r[1] for r in rows}
            required = {
                "id", "event_type", "actor_type", "actor_id", "action",
                "occurred_at", "created_at", "resource_type", "resource_id",
                "execution_id", "grant_id", "evidence_hash",
                "verification_status", "metadata_json",
            }
            for col in required:
                self.assertIn(col, columns, f"Missing column: {col}")
        finally:
            conn.close()

    # ── Record / Get ───────────────────────────────────────────
    def test_event_can_be_saved_and_read(self):
        event = self.record(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="policy-engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
        )
        self.assertIsNotNone(event.id)
        self.assertRegex(event.id, r"^[0-9a-f]{8}-")

        fetched = self.get(event.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.event_type, "policy_evaluated")
        self.assertEqual(fetched.actor_type, "system")
        self.assertEqual(fetched.actor_id, "policy-engine-1")
        self.assertEqual(fetched.action, "evaluate")
        self.assertEqual(fetched.occurred_at, "2026-05-11T10:00:00Z")
        self.assertIsNotNone(fetched.created_at)

    def test_event_with_all_fields(self):
        event = self.record(
            event_type="grant_executed",
            actor_type="agent",
            actor_id="agent-42",
            action="approve",
            occurred_at="2026-05-11T11:00:00Z",
            resource_type="grant",
            resource_id="g-1",
            execution_id="ex-1",
            grant_id="g-1",
            evidence_hash="sha256:abc123",
            verification_status="valid",
            metadata_json='{"reason": "test"}',
        )
        fetched = self.get(event.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.resource_type, "grant")
        self.assertEqual(fetched.resource_id, "g-1")
        self.assertEqual(fetched.execution_id, "ex-1")
        self.assertEqual(fetched.grant_id, "g-1")
        self.assertEqual(fetched.evidence_hash, "sha256:abc123")
        self.assertEqual(fetched.verification_status, "valid")
        self.assertEqual(fetched.metadata_json, '{"reason": "test"}')

    def test_get_missing_returns_none(self):
        fetched = self.get("00000000-0000-0000-0000-000000000000")
        self.assertIsNone(fetched)

    # ── Filter by execution_id ─────────────────────────────────
    def test_filter_by_execution_id(self):
        e1 = self.record(
            event_type="grant_executed",
            actor_type="system",
            actor_id="sys-1",
            action="run",
            occurred_at="2026-05-11T12:00:00Z",
            execution_id="ex-a",
        )
        self.record(
            event_type="grant_executed",
            actor_type="system",
            actor_id="sys-1",
            action="run",
            occurred_at="2026-05-11T12:01:00Z",
            execution_id="ex-b",
        )
        results = self.list(execution_id="ex-a")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, e1.id)

    # ── Filter by grant_id ─────────────────────────────────────
    def test_filter_by_grant_id(self):
        e1 = self.record(
            event_type="grant_issued",
            actor_type="user",
            actor_id="user-1",
            action="issue",
            occurred_at="2026-05-11T13:00:00Z",
            grant_id="g-1",
        )
        self.record(
            event_type="grant_issued",
            actor_type="user",
            actor_id="user-2",
            action="issue",
            occurred_at="2026-05-11T13:01:00Z",
            grant_id="g-2",
        )
        results = self.list(grant_id="g-1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, e1.id)

    # ── metadata_json round-trip ───────────────────────────────
    def test_metadata_json_roundtrip(self):
        payload = {"nested": {"key": "value"}, "list": [1, 2, 3], "bool": True}
        event = self.record(
            event_type="evidence_created",
            actor_type="agent",
            actor_id="agent-1",
            action="create",
            occurred_at="2026-05-11T14:00:00Z",
            metadata_json=json.dumps(payload),
        )
        fetched = self.get(event.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(json.loads(fetched.metadata_json), payload)

    def test_invalid_metadata_json_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.record(
                event_type="evidence_created",
                actor_type="agent",
                actor_id="agent-1",
                action="create",
                occurred_at="2026-05-11T14:00:00Z",
                metadata_json="not valid json",
            )
        self.assertIn("valid JSON", str(ctx.exception))

    # ── Validation ─────────────────────────────────────────────
    def test_invalid_actor_type_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.record(
                event_type="policy_evaluated",
                actor_type="hacker",
                actor_id="bad",
                action="eval",
                occurred_at="2026-05-11T10:00:00Z",
            )
        self.assertIn("Invalid actor_type", str(ctx.exception))

    def test_invalid_event_type_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.record(
                event_type="mystery_event",
                actor_type="system",
                actor_id="sys-1",
                action="eval",
                occurred_at="2026-05-11T10:00:00Z",
            )
        self.assertIn("Invalid event_type", str(ctx.exception))

    def test_list_invalid_actor_type_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.list(actor_type="hacker")
        self.assertIn("Invalid actor_type", str(ctx.exception))

    # ── Append-only contract ───────────────────────────────────
    def test_no_update_function_exists(self):
        """Append-only: module must not expose update / delete functions."""
        import backend.src.policy.provenance as prov_mod
        self.assertFalse(hasattr(prov_mod, "update_provenance_event"))
        self.assertFalse(hasattr(prov_mod, "delete_provenance_event"))

    # ── Ordering / limit ───────────────────────────────────────
    def test_list_orders_by_occurred_at_desc(self):
        self.record(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="sys-1",
            action="a",
            occurred_at="2026-05-11T09:00:00Z",
        )
        self.record(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="sys-1",
            action="b",
            occurred_at="2026-05-11T11:00:00Z",
        )
        e3 = self.record(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="sys-1",
            action="c",
            occurred_at="2026-05-11T10:00:00Z",
        )
        results = self.list(limit=2)
        self.assertEqual(len(results), 2)
        # Most recent first
        self.assertEqual(results[0].action, "b")
        self.assertEqual(results[1].action, "c")

    def test_list_limit_bounds(self):
        for i in range(5):
            self.record(
                event_type="policy_evaluated",
                actor_type="system",
                actor_id="sys-1",
                action=f"a{i}",
                occurred_at=f"2026-05-11T{i:02d}:00:00Z",
            )
        results = self.list(limit=3)
        self.assertEqual(len(results), 3)

    def test_list_limit_clamped_at_1000(self):
        # Just verify it doesn't crash with a very large limit
        results = self.list(limit=99999)
        self.assertEqual(len(results), 0)

    # ── Grant logic untouched ──────────────────────────────────
    def test_grant_logic_unchanged(self):
        """Confirm grants table still works independently."""
        from backend.src.grants.grants import create_grant
        from backend.src.core.models import Grant

        grant = Grant(
            subject_id="sub-1",
            role="admin",
            action="read",
            resource="doc-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2027-01-01T00:00:00Z",
            created_by="test",
            reason="test",
        )
        create_grant(grant)
        self.assertIsNotNone(grant.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
