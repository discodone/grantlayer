"""The anchor fold must consume EXACTLY what the public export produces.

Two code paths build the per-entry dict that gets folded into a chain head:

  * anchor  : audit_compliance._load_workspace_entries  (hand-built row dict
              -> _row_to_audit_event -> to_dict)
  * public  : audit_log.list_events (SELECT * -> _row_to_audit_event -> to_dict)

Both then fold through recompute_head_from_records / _entry_canonical. If the
hand-built anchor dict omits any column the public SELECT * carries, the same
event canonicalises two different ways and the anchored head stops matching the
public export — a publicly-unverifiable anchor.

These tests are DATA-LEVEL (a real chain in a real DB), so they cannot go
vacuous. Test (b) compares the FULL entry dict field-by-field, so a future
column added to the model but not propagated by _load_workspace_entries breaks
THIS test instead of a paid on-chain anchor.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest

from backend.src.api.routers.audit_compliance import (
    _load_workspace_entries,
    recompute_head_from_records,
)

_TENANT = "t-parity"
_WS = "ws-parity"


class TestAnchorPublicFoldParity(unittest.TestCase):
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
        self.db = db_mod
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

    def _append(self, **kw):
        base = dict(
            subject_id="s1", role="agent", action="read", resource="res/1",
            approved=True, reason="access granted", workspace_id=_WS,
            tenant_id=_TENANT, scope="tenant",
        )
        base.update(kw)
        ev = self.AuditEvent(**base)
        self.audit.append_event(ev)
        return ev

    # --- shared helpers: the two entry-building paths, both in seq ASC order ---

    def _anchor_entries(self):
        from sqlalchemy.orm import Session
        with Session(self.db.get_engine()) as session:
            return _load_workspace_entries(session, _WS)

    def _public_entries(self):
        # list_events IS the public /export data source (SELECT *). It returns
        # newest-first; re-sort to the anchor's seq-ASC determinism order so the
        # ONLY variable under test is per-entry canonicalisation, not order.
        evs = self.audit.list_events(tenant_id=_TENANT, workspace_id=_WS)
        evs = sorted(evs, key=lambda e: e.seq)
        return [e.to_dict() for e in evs]

    # ── (a) fold-parity: heads must be byte-identical ──────────────────────────
    def test_a_head_parity_with_mixed_reason_codes(self):
        """A chain containing BOTH a None and a non-None reason_code must fold to
        the same head on the anchor path and the public path."""
        self._append(action="none-rc", reason_code=None)
        self._append(action="set-rc", reason_code="access_granted")

        anchor = recompute_head_from_records(self._anchor_entries())
        public = recompute_head_from_records(self._public_entries())

        self.assertEqual(anchor["entry_count"], public["entry_count"])
        self.assertEqual(
            anchor["final_hash"], public["final_hash"],
            "anchor fold head != public export fold head — a non-None reason_code "
            "is folded by the public export but dropped by the anchor path",
        )

    # ── (b) generalised: FULL per-entry column parity ──────────────────────────
    def test_b_full_column_parity_per_event(self):
        """Every field of every event's entry dict must be identical between the
        two paths. This does NOT special-case reason_code: it compares the whole
        dict, so any column the public SELECT * carries but the hand-built anchor
        dict omits (reason_code today, any future column tomorrow) fails here."""
        self._append(
            action="rich", reason="richest reason", reason_code="grant_expired",
            matched_grant_id="g-xyz", challenge_id="ch-1", challenge_present=True,
            challenge_result="passed", grant_signature_result="valid",
        )
        anchor_by_id = {e["id"]: e for e in self._anchor_entries()}
        public_by_id = {e["id"]: e for e in self._public_entries()}

        self.assertEqual(set(anchor_by_id), set(public_by_id))
        for eid, ae in anchor_by_id.items():
            pe = public_by_id[eid]
            self.assertEqual(
                set(ae.keys()), set(pe.keys()),
                f"entry {eid}: anchor keys {set(ae) ^ set(pe)} differ from public",
            )
            for k in sorted(ae):
                self.assertEqual(
                    ae[k], pe[k],
                    f"entry {eid}: field {k!r} differs — anchor={ae[k]!r} public={pe[k]!r}",
                )


if __name__ == "__main__":
    unittest.main()
