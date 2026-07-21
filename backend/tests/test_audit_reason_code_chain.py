"""reason_code is additive-and-forward-only in the anchored export chain.

The machine reason_code is added to decision events going forward. The
externally-anchored head folds `_entry_canonical` over each event's full dict
(AuditEvent.to_dict()), so a naive addition would put `"reason_code": null`
into EVERY historical event's canonical and change every anchored head —
invalidating the recomputation of every past on-chain anchor.

These tests pin the forward-only invariant: a reason_code that is None (every
pre-change event, and every non-decision event) must be INVISIBLE to the fold,
so historical heads recompute byte-identically; a reason_code that is SET must
be covered by the fold going forward.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest

from backend.src.api.routers.audit_compliance import recompute_head_from_records


def _chain(reason_code_key: bool, reason_code_value=None):
    """Two hash-linked events shaped like real audit rows. When reason_code_key
    is True, the reason_code column is present (value = reason_code_value)."""
    rows = [
        {
            "id": "e1", "timestamp": "2026-01-01T00:00:00Z", "subject_id": "s1",
            "role": "agent", "action": "read", "resource": "res/1",
            "approved": True, "reason": "access granted", "matched_grant_id": "g1",
            "challenge_id": None, "challenge_present": False,
            "challenge_result": "legacy_mode", "grant_signature_result": "valid",
            "tenant_id": "t1", "workspace_id": "w1", "scope": "tenant", "seq": 1,
            "row_hash": "a" * 64, "prev_hash": None,
        },
        {
            "id": "e2", "timestamp": "2026-01-01T00:00:01Z", "subject_id": "s1",
            "role": "agent", "action": "write", "resource": "res/2",
            "approved": False, "reason": "grant expired", "matched_grant_id": None,
            "challenge_id": None, "challenge_present": False,
            "challenge_result": "legacy_mode", "grant_signature_result": "not_checked",
            "tenant_id": "t1", "workspace_id": "w1", "scope": "tenant", "seq": 2,
            "row_hash": "b" * 64, "prev_hash": "a" * 64,
        },
    ]
    if reason_code_key:
        for r in rows:
            r["reason_code"] = reason_code_value
    return rows


class TestReasonCodeForwardOnly(unittest.TestCase):
    def test_none_reason_code_is_invisible_to_the_fold(self):
        """A present-but-None reason_code must NOT change the anchored head —
        this is what keeps every past on-chain anchor recomputable."""
        head_without = recompute_head_from_records(_chain(reason_code_key=False))
        head_with_none = recompute_head_from_records(_chain(reason_code_key=True, reason_code_value=None))
        self.assertEqual(head_without["final_hash"], head_with_none["final_hash"])
        self.assertEqual(head_without["entry_count"], head_with_none["entry_count"])

    def test_set_reason_code_is_covered_by_the_fold(self):
        """A non-None reason_code IS folded in, so new decision events are
        anchored with their machine code."""
        head_without = recompute_head_from_records(_chain(reason_code_key=False))
        head_with_code = recompute_head_from_records(_chain(reason_code_key=True, reason_code_value="grant_expired"))
        self.assertNotEqual(head_without["final_hash"], head_with_code["final_hash"])


class TestReasonCodePersistence(unittest.TestCase):
    """End-to-end: a decision event stores the machine code and keeps the
    free-text reason; a legacy event has NULL reason_code and the row_hash
    chain still verifies (reason_code is deliberately not in the row_hash
    whitelist — it rides the anchored export chain)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp.name
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit = audit_mod
        from backend.src.core.models import AuditEvent
        self.AuditEvent = AuditEvent

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass
        if self._orig_db is None:
            os.environ.pop("GRANTLAYER_DB", None)
        else:
            os.environ["GRANTLAYER_DB"] = self._orig_db

    def _event(self, **kw):
        base = dict(
            subject_id="s1", role="agent", action="read", resource="res/1",
            approved=True, reason="access granted", workspace_id="w1",
            tenant_id="t1", scope="tenant",
        )
        base.update(kw)
        return self.AuditEvent(**base)

    def _read_back(self, event_id):
        rows = self.audit.list_events(tenant_id="t1", workspace_id="w1")
        matches = [e for e in rows if e.id == event_id]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_decision_event_stores_machine_code_and_retains_reason(self):
        ev = self._event(reason="access granted", reason_code="access_granted")
        self.audit.append_event(ev)
        got = self._read_back(ev.id)
        self.assertEqual(got.reason_code, "access_granted")
        self.assertEqual(got.reason, "access granted")

    def test_legacy_event_null_reason_code_and_chain_verifies(self):
        ev = self._event()  # no reason_code -> NULL
        self.audit.append_event(ev)
        got = self._read_back(ev.id)
        self.assertIsNone(got.reason_code)
        self.assertTrue(self.audit.verify_audit_hash_chain()["valid"])


if __name__ == "__main__":
    unittest.main()
