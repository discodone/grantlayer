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

# audit_events columns that the anchor fold intentionally does NOT carry. Each
# entry MUST have a justification. Empty today: _load_workspace_entries folds
# every audit_events column, so a NEW column is a bug until it is either folded
# there or added here with a reason.
_FOLD_EXCLUDED_COLUMNS: dict[str, str] = {}


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

    def _append_full(self, **overrides):
        """Append an event with EVERY optional/nullable column set to a distinct
        non-None value, so a column dropped by the fold surfaces as None."""
        kw = dict(
            subject_id="s-full", role="agent", action="exercise", resource="res/full",
            approved=True, reason="full reason", matched_grant_id="g-full",
            challenge_id="ch-full", challenge_present=True, challenge_result="passed",
            grant_signature_result="valid", workspace_id=_WS, tenant_id=_TENANT,
            scope="tenant", reason_code="access_granted",
        )
        kw.update(overrides)
        ev = self.AuditEvent(**kw)
        self.audit.append_event(ev)  # sets row_hash / prev_hash / seq
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

    # ── (b) schema-anchored coverage + full per-entry parity ───────────────────
    def test_b_schema_anchored_and_full_parity(self):
        """Two assertions:

        (1) SCHEMA ANCHOR — every audit_events column (minus a justified
            exclusion list) must be carried into the fold with its value, not
            silently dropped to None. Anchored on AuditEvent.__table__.columns,
            so it does NOT depend on list_events staying `SELECT *`: a future
            column dropped by _load_workspace_entries fails HERE (data-level)
            instead of at a paid on-chain anchor.
        (2) The existing anchor-vs-public-export full-field parity — I want both.
        """
        from backend.src.core.orm import AuditEvent as OrmAuditEvent

        self._append_full(action="first")
        ev2 = self._append_full(action="second")  # 2nd event => prev_hash non-None too

        anchor_entries = self._anchor_entries()
        entry2 = next(e for e in anchor_entries if e["id"] == ev2.id)

        # (1) schema-anchored coverage
        for col in (c.name for c in OrmAuditEvent.__table__.columns):
            if col in _FOLD_EXCLUDED_COLUMNS:
                continue
            self.assertIsNotNone(
                entry2.get(col),
                f"anchor fold drops audit_events column {col!r}: it is defined on "
                f"the ORM table but arrives as None in the folded entry",
            )

        # (2) anchor path vs public export path — full field-by-field parity
        public_by_id = {e["id"]: e for e in self._public_entries()}
        for eid, ae in {e["id"]: e for e in anchor_entries}.items():
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
