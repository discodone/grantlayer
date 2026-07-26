"""Canonical-insert guard on audit_events (hash hygiene, gl-412 fix A).

Both hash layers (row_hash scheme and anchor fold) hash NORMALIZED values
(approved -> bool, challenge_result/'' -> "legacy_mode",
grant_signature_result/'' -> "not_checked"), so a raw column whose
normalized form is unchanged (approved 1 vs 5, challenge_result NULL vs '')
is bound one-to-many to its hashed form. The app write path already stores
the canonical form and UPDATE/DELETE are trigger-blocked (0005/0008); the
open flank is a direct raw INSERT. Migration 0024 closes it with
BEFORE-INSERT canonical-guard triggers (same pattern as 0005/0008):
a new row must store exactly the form the hashes bind.

Existing rows are untouched — no stored value, canonical, or hash changes,
so anchored bytes cannot move.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid


def _mk_event_row(**overrides):
    """Raw column dict for a direct INSERT, canonical by default."""
    row = {
        "id": str(uuid.uuid4()),
        "timestamp": "2026-07-26T12:00:00Z",
        "subject_id": "raw-writer",
        "role": "agent",
        "action": "raw_insert",
        "resource": "res",
        "approved": 1,
        "reason": "raw",
        "matched_grant_id": None,
        "challenge_id": None,
        "challenge_present": 0,
        "challenge_result": "legacy_mode",
        "grant_signature_result": "not_checked",
        "row_hash": "0" * 64,  # content irrelevant for the guard
        "prev_hash": None,
        "tenant_id": "demo",
        "workspace_id": "default",
        "scope": "tenant",
        "seq": None,
        "reason_code": None,
        "constraint_violation": None,
    }
    row.update(overrides)
    return row


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        self.db_path = self.tmp_db.name

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

    def _raw_insert(self, row):
        cols = ", ".join(row)
        marks = ", ".join(f":{c}" for c in row)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"INSERT INTO audit_events ({cols}) VALUES ({marks})", row
            )
            conn.commit()


class TestNonCanonicalInsertRejected(_Base):
    """Each non-canonical raw form must be REJECTED at insert.

    RED before the guard exists: these inserts succeed, silently creating a
    raw row whose stored bytes differ from what both hash layers bind.
    """

    def _assert_rejected(self, **overrides):
        with self.assertRaises(
            sqlite3.IntegrityError,
            msg=f"non-canonical insert must be rejected: {overrides}",
        ):
            self._raw_insert(_mk_event_row(**overrides))

    def test_approved_out_of_range_rejected(self):
        self._assert_rejected(approved=5)

    def test_approved_null_rejected(self):
        # NULL approved would hash as bool(None)=False while storing NULL.
        # (Also blocked by NOT NULL — the guard makes the intent explicit.)
        self._assert_rejected(approved=None)

    def test_challenge_present_out_of_range_rejected(self):
        self._assert_rejected(challenge_present=7)

    def test_challenge_present_null_rejected(self):
        self._assert_rejected(challenge_present=None)

    def test_challenge_result_null_rejected(self):
        self._assert_rejected(challenge_result=None)

    def test_challenge_result_empty_rejected(self):
        self._assert_rejected(challenge_result="")

    def test_grant_signature_result_null_rejected(self):
        self._assert_rejected(grant_signature_result=None)

    def test_grant_signature_result_empty_rejected(self):
        self._assert_rejected(grant_signature_result="")


class TestCanonicalWritesStillWork(_Base):
    """Control: canonical inserts (raw AND app-path) remain accepted."""

    def test_canonical_raw_insert_accepted(self):
        self._raw_insert(_mk_event_row())
        with sqlite3.connect(self.db_path) as conn:
            n = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        self.assertEqual(n, 1)

    def test_app_append_path_unaffected(self):
        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        from backend.src.core.models import AuditEvent

        audit_mod.append_event(AuditEvent(
            subject_id="app-writer", role="agent", action="a", resource="r",
            approved=True, reason="ok", tenant_id="demo",
            workspace_id="default", scope="tenant",
        ))
        report = audit_mod.verify_audit_hash_chain()
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["checked"], 1)


if __name__ == "__main__":
    unittest.main()
