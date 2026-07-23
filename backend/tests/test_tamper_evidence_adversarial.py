"""Adversarial tamper-evidence suite for the audit chain.

GrantLayer claims its audit chain is tamper-evident. Every prior test EXERCISED
that claim on the happy path (append, then verify a clean chain). This suite
ATTACKS it: for each attack we apply the mutation directly at the storage layer
(raw SQL, bypassing the API — the posture of a real attacker who has DB access),
then assert that a SPECIFIC, NAMED detection mechanism fires. "Something failed"
is never good enough — each assertion message names the mechanism.

Three defence layers exist, and this suite pins the boundary between them:

  1. IMMUTABILITY TRIGGERS (SQLite trg_audit_events_no_update / _no_delete,
     migration 0005). A naive UPDATE/DELETE is aborted at the storage engine.
     A sophisticated attacker DROPs the triggers first — so every attack below
     that needs UPDATE/DELETE first proves the trigger blocks the naive attempt,
     THEN drops the triggers and proves the cryptographic layer still catches it.

  2. THE ROW-HASH CHAIN (audit_log.verify_audit_hash_chain). Each event's
     row_hash is SHA-256 over its canonical payload + the previous row_hash;
     verification recomputes both the row_hash and the prev_hash linkage.
     Catches deletions, in-place field mutation, partial re-hashing, fabricated
     inserts, and duplication — anything that leaves the forward links broken.

  3. THE ON-CHAIN ANCHORED HEAD (audit_compliance.anchor_head, published to
     Cardano). The head is a left-fold over the FULL workspace chain whose
     per-entry canonical includes EVERY column (seq, reason_code, row_hash, ...).
     Catches the three attacks the row-hash chain alone is BLIND to: tail
     truncation, a fully re-linked chain, and reason_code mutation — because each
     changes the recomputed head so it no longer equals the head published on
     chain.

The honest limits (which attacks NO layer catches without a *fresh* anchor) are
documented in the module docstring of the report and asserted where relevant:
attacks 2, 6 and 9 are invisible to the local chain and rely ENTIRELY on the
anchored head, so any tamper of events NOT YET covered by an anchor is caught by
nothing until the next anchor is published. reason_code specifically is NEVER in
the row-hash payload, so even on an anchored event it is invisible to
verify_audit_hash_chain and only the fold/anchor sees it.

SQLite-only, self-provisioning (temp DB per test). No PostgreSQL, no Cardano
network, no mainnet. Registered in SQLITE_ONLY_MODULES.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from typing import Any, Optional
from unittest import mock

# Imported once at module load. These are pure functions or take an explicit
# session, so they are unaffected by the per-test reload of the db/audit modules
# (same pattern as test_anchor_public_fold_parity / test_anchor_export_determinism).
from backend.src.api.routers import audit_compliance as ac

_WS = "ws-adversarial"
_TENANT = "tenant-adversarial"
# All seeded events share ONE timestamp so ``seq`` is the sole total order — the
# stable insertion-order tiebreak migration 0013 exists for. Both the row-hash
# chain (ORDER BY timestamp ASC, seq ASC) and the anchor fold (seq ASC, id ASC)
# then agree on order, so a seq swap is a genuine reorder, not a no-op.
_TS = "2026-01-01T00:00:00Z"

_NO_UPDATE_TRIGGER = "trg_audit_events_no_update"
_NO_DELETE_TRIGGER = "trg_audit_events_no_delete"


class _BaseChainAttack(unittest.TestCase):
    """Fresh temp SQLite DB per test with a known-good 5-event chain."""

    def setUp(self) -> None:
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        import backend.src.core.db as db_mod

        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()
        self.db = db_mod

        import backend.src.core.models as models_mod

        importlib.reload(models_mod)
        self.models = models_mod

        import backend.src.audit.audit_log as audit_mod

        importlib.reload(audit_mod)
        self.audit = audit_mod

        self.events = self._seed(5)

    def tearDown(self) -> None:
        try:
            os.unlink(self.tmp_db.name)
        except OSError:
            pass
        if self._orig_db is None:
            os.environ.pop("GRANTLAYER_DB", None)
        else:
            os.environ["GRANTLAYER_DB"] = self._orig_db

    # ── seeding & inspection ────────────────────────────────────────────────

    def _seed(self, n: int, reason_code: Optional[str] = None) -> list:
        events = []
        for i in range(n):
            ev = self.models.AuditEvent(
                subject_id=f"subj-{i}",
                role="agent",
                action=f"action-{i}",
                resource=f"res-{i}",
                approved=(i % 2 == 0),
                reason=f"reason-{i}",
                timestamp=_TS,
                tenant_id=_TENANT,
                workspace_id=_WS,
                scope="tenant",
                reason_code=reason_code,
            )
            self.audit.append_event(ev)
            events.append(ev)
        return events

    def _append_one(self, **kw) -> Any:
        base = dict(
            subject_id="subj-x",
            role="agent",
            action="action-x",
            resource="res-x",
            approved=True,
            reason="reason-x",
            timestamp=_TS,
            tenant_id=_TENANT,
            workspace_id=_WS,
            scope="tenant",
        )
        base.update(kw)
        ev = self.models.AuditEvent(**base)
        self.audit.append_event(ev)
        return ev

    def _rows(self) -> list[dict]:
        """Raw storage rows in the chain's total order (seq ASC)."""
        return self.db.query_all(
            "SELECT * FROM audit_events ORDER BY seq ASC, id ASC"
        )

    # ── the three detection layers ──────────────────────────────────────────

    def _verify(self) -> dict:
        """Layer 2: the row-hash chain verifier (row_hash + prev_hash linkage)."""
        return self.audit.verify_audit_hash_chain()

    def _anchor_head(self) -> dict:
        """Layer 3: the fold head that gets published on chain."""
        session = self.db.get_session()
        try:
            return ac.anchor_head(session, _WS)
        finally:
            session.close()

    def _public_export_head(self) -> dict:
        """The head an external auditor recomputes from the public export
        (list_events -> to_dict), re-sorted to the anchor's seq-ASC order. The
        anchored head MUST equal this or the anchor is publicly unverifiable."""
        evs = self.audit.list_events(
            limit=10000, tenant_id=_TENANT, workspace_id=_WS
        )
        evs = sorted(evs, key=lambda e: e.seq)
        return ac.recompute_head_from_records([e.to_dict() for e in evs])

    def _publish(self) -> dict:
        """Snapshot the current anchored head — the value committed on chain."""
        return self._anchor_head()

    # ── attacker capabilities (raw storage layer) ───────────────────────────

    def _disable_immutability(self) -> None:
        """A DB-access attacker DROPs the append-only triggers before mutating."""
        self.db.execute(f"DROP TRIGGER {_NO_UPDATE_TRIGGER}", {})
        self.db.execute(f"DROP TRIGGER {_NO_DELETE_TRIGGER}", {})

    def _assert_trigger_blocks(self, sql: str, params: dict) -> None:
        """The naive attempt must be aborted by the immutability trigger."""
        with self.assertRaises(Exception) as ctx:
            self.db.execute(sql, params)
        self.assertIn(
            "immutable",
            str(ctx.exception).lower(),
            "immutability trigger did not fire: append-only UPDATE/DELETE guard "
            f"(migration 0005) failed to abort {sql!r}",
        )

    def _recompute_forward(self, mutate_seq: int, **field_overrides) -> None:
        """Re-link the WHOLE chain forward from a mutation (attack 6). Rewrites
        every row_hash and prev_hash so the chain is internally consistent — the
        strongest local attack. Requires triggers already dropped."""
        prev = None
        for row in self._rows():
            ev = self.audit._row_to_audit_event(row)
            is_target = ev.seq == mutate_seq
            if is_target:
                for k, v in field_overrides.items():
                    setattr(ev, k, v)
            new_hash = self.audit._compute_row_hash(ev, prev)
            # Only the mutated row's payload field is rewritten; every other row
            # keeps its original payload and just gets re-linked (new row_hash /
            # prev_hash). Writing the override to non-target rows would desync the
            # stored payload from the hashed payload and defeat the point.
            if is_target:
                sets = "".join(f"{k}=:{k}, " for k in field_overrides)
                params = {**field_overrides, "h": new_hash, "p": prev, "s": ev.seq}
            else:
                sets = ""
                params = {"h": new_hash, "p": prev, "s": ev.seq}
            self.db.execute(
                f"UPDATE audit_events SET {sets}row_hash=:h, prev_hash=:p "
                "WHERE seq=:s",
                params,
            )
            prev = new_hash


class TestTamperEvidenceAdversarial(_BaseChainAttack):
    """One attack per test. Each asserts a NAMED mechanism fired."""

    # ── Attack 1 — delete a middle event ────────────────────────────────────
    def test_attack_01_delete_middle_event(self) -> None:
        mid = self._rows()[2]
        # Naive DELETE is aborted by the immutability trigger.
        self._assert_trigger_blocks(
            "DELETE FROM audit_events WHERE seq=:s", {"s": mid["seq"]}
        )
        # Sophisticated attacker drops the trigger, then deletes.
        self._disable_immutability()
        self.db.execute("DELETE FROM audit_events WHERE seq=:s", {"s": mid["seq"]})

        result = self._verify()
        self.assertFalse(
            result["valid"],
            "MECHANISM row-hash chain: deleting a middle event left the chain "
            "verifying valid — the prev_hash linkage did not detect the gap",
        )
        reasons = " | ".join(f["reason"] for f in result["failures"])
        self.assertIn(
            "prev_hash mismatch", reasons,
            "MECHANISM prev_hash linkage: expected a broken forward link at the "
            f"event after the deleted one; got failures: {reasons}",
        )

    # ── Attack 2 — delete the most recent event (truncation) ────────────────
    def test_attack_02_delete_recent_truncation(self) -> None:
        published = self._publish()
        last = self._rows()[-1]
        self._assert_trigger_blocks(
            "DELETE FROM audit_events WHERE seq=:s", {"s": last["seq"]}
        )
        self._disable_immutability()
        self.db.execute("DELETE FROM audit_events WHERE seq=:s", {"s": last["seq"]})

        # HONEST GAP: the row-hash chain is BLIND to tail truncation — a shorter
        # prefix is still internally consistent.
        self.assertTrue(
            self._verify()["valid"],
            "the row-hash chain is expected to be BLIND to tail truncation; if "
            "this now fails the finding in the report is stale",
        )
        # Only the anchored head catches it: fewer entries, different final_hash.
        head = self._anchor_head()
        self.assertNotEqual(
            head["entry_count"], published["entry_count"],
            "MECHANISM on-chain anchored head (entry_count): truncation did not "
            "change the entry count vs the published head",
        )
        self.assertNotEqual(
            head["final_hash"], published["final_hash"],
            "MECHANISM on-chain anchored head (final_hash): truncation left the "
            "recomputed head equal to the head published on chain",
        )

    # ── Attack 3 — reorder two events ───────────────────────────────────────
    def test_attack_03_reorder_two_events(self) -> None:
        published = self._publish()
        rows = self._rows()
        a, b = rows[1], rows[2]
        self._assert_trigger_blocks(
            "UPDATE audit_events SET seq=:x WHERE id=:i",
            {"x": b["seq"], "i": a["id"]},
        )
        self._disable_immutability()
        # Swap the two events' seq — a genuine reorder (seq is the total order).
        self.db.execute(
            "UPDATE audit_events SET seq=:x WHERE id=:i",
            {"x": b["seq"], "i": a["id"]},
        )
        self.db.execute(
            "UPDATE audit_events SET seq=:x WHERE id=:i",
            {"x": a["seq"], "i": b["id"]},
        )

        result = self._verify()
        self.assertFalse(
            result["valid"],
            "MECHANISM row-hash chain: reordering two events left the chain valid",
        )
        reasons = " | ".join(f["reason"] for f in result["failures"])
        self.assertIn(
            "prev_hash mismatch", reasons,
            "MECHANISM prev_hash linkage: a reorder must break the forward links "
            f"at the swapped positions; got: {reasons}",
        )
        # The anchored head (seq-ASC fold) also diverges.
        self.assertNotEqual(
            self._anchor_head()["final_hash"], published["final_hash"],
            "MECHANISM on-chain anchored head: reorder did not change the head",
        )

    # ── Attack 4 — mutate a payload field, leave hashes untouched ───────────
    def test_attack_04_mutate_payload_leave_hashes(self) -> None:
        mid = self._rows()[2]
        self._assert_trigger_blocks(
            "UPDATE audit_events SET action=:a WHERE seq=:s",
            {"a": "TAMPERED", "s": mid["seq"]},
        )
        self._disable_immutability()
        # 'action' is inside the row-hash payload; leave row_hash/prev_hash as-is.
        self.db.execute(
            "UPDATE audit_events SET action=:a WHERE seq=:s",
            {"a": "TAMPERED", "s": mid["seq"]},
        )

        result = self._verify()
        self.assertFalse(
            result["valid"],
            "MECHANISM row-hash recomputation: an in-place field edit with the "
            "stored hash untouched must not verify",
        )
        reasons = " | ".join(f["reason"] for f in result["failures"])
        self.assertIn(
            "row_hash mismatch", reasons,
            "MECHANISM row_hash recomputation: the recomputed hash of the edited "
            f"event must differ from the stored hash; got: {reasons}",
        )

    # ── Attack 5 — mutate a field AND recompute that entry's own hash ───────
    def test_attack_05_mutate_and_recompute_own_hash(self) -> None:
        """Attacker who understands the format but cannot re-link forward: fixes
        the mutated event's OWN row_hash, but the next event's prev_hash still
        points at the pre-mutation hash."""
        rows = self._rows()
        mid = rows[2]
        self._disable_immutability()
        ev = self.audit._row_to_audit_event(mid)
        ev.action = "SMART-TAMPER"
        # Recompute this event's row_hash correctly against its real prev_hash.
        correct_own_hash = self.audit._compute_row_hash(ev, mid["prev_hash"])
        self.db.execute(
            "UPDATE audit_events SET action=:a, row_hash=:h WHERE seq=:s",
            {"a": "SMART-TAMPER", "h": correct_own_hash, "s": mid["seq"]},
        )

        result = self._verify()
        self.assertFalse(
            result["valid"],
            "MECHANISM forward prev_hash linkage: re-hashing only the mutated "
            "event must still break the link to the NEXT event",
        )
        reasons = " | ".join(f["reason"] for f in result["failures"])
        self.assertIn(
            "prev_hash mismatch", reasons,
            "MECHANISM forward prev_hash linkage: the event after the mutation "
            f"must report a prev_hash mismatch; got: {reasons}",
        )

    # ── Attack 6 — recompute the ENTIRE chain forward (full re-link) ────────
    def test_attack_06_full_relink_caught_only_by_anchor(self) -> None:
        """Attacker who re-links everything. The local chain is fully consistent
        and CANNOT catch this — only the anchored head, published before the
        tamper, still commits to the original head."""
        published = self._publish()
        self._disable_immutability()
        self._recompute_forward(self._rows()[1]["seq"], action="RELINKED")

        # The row-hash chain is DEFEATED — a fully re-linked chain verifies valid.
        self.assertTrue(
            self._verify()["valid"],
            "a full forward re-link is expected to defeat the local chain; if "
            "this now fails the finding in the report is stale",
        )
        # The anchored head is the ONLY thing that catches it.
        self.assertNotEqual(
            self._anchor_head()["final_hash"], published["final_hash"],
            "MECHANISM on-chain anchored head: a fully re-linked chain recomputed "
            "to the same head published on chain — the anchor failed to detect "
            "the tamper",
        )

    # ── Attack 7 — insert a fabricated event with a plausible seq ───────────
    def test_attack_07_insert_fabricated_event(self) -> None:
        published = self._publish()
        rows = self._rows()
        last = rows[-1]
        next_seq = int(last["seq"]) + 1
        # INSERT is NOT guarded by the append-only triggers (they only block
        # UPDATE/DELETE) — the fabricated row lands at the storage layer.
        self.db.execute(
            """INSERT INTO audit_events
               (id, timestamp, subject_id, role, action, resource, approved,
                reason, challenge_present, challenge_result,
                grant_signature_result, row_hash, prev_hash, tenant_id,
                workspace_id, scope, seq)
               VALUES (:id, :ts, :subj, 'agent', 'FABRICATED', 'res-x', 1,
                'fabricated', 0, 'legacy_mode', 'not_checked', :rh, :ph,
                :tenant, :ws, 'tenant', :seq)""",
            {
                "id": "fabricated-evt",
                "ts": _TS,
                "subj": "attacker",
                # a plausible-looking but forged 64-hex hash pair
                "rh": "f" * 64,
                "ph": last["row_hash"],
                "tenant": _TENANT,
                "ws": _WS,
                "seq": next_seq,
            },
        )
        self.assertEqual(
            len(self._rows()), 6,
            "the fabricated INSERT should not be blocked (append-only triggers "
            "guard UPDATE/DELETE only) — it must reach the storage layer",
        )

        result = self._verify()
        self.assertFalse(
            result["valid"],
            "MECHANISM row-hash recomputation: a fabricated event's forged hash "
            "must not recompute to itself",
        )
        reasons = " | ".join(f["reason"] for f in result["failures"])
        self.assertIn(
            "row_hash mismatch", reasons,
            f"MECHANISM row_hash recomputation: expected a row_hash mismatch on "
            f"the fabricated event; got: {reasons}",
        )
        self.assertNotEqual(
            self._anchor_head()["entry_count"], published["entry_count"],
            "MECHANISM on-chain anchored head (entry_count): the fabricated event "
            "did not change the anchored count",
        )

    # ── Attack 8 — duplicate an event ───────────────────────────────────────
    def test_attack_08_duplicate_event(self) -> None:
        mid = self._rows()[2]
        # (a) An EXACT duplicate (same id) is blocked by the primary key.
        with self.assertRaises(Exception) as ctx:
            self.db.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, challenge_present, challenge_result,
                    grant_signature_result, row_hash, prev_hash, tenant_id,
                    workspace_id, scope, seq)
                   VALUES (:id, :ts, 's', 'agent', 'a', 'r', 1, 'x', 0,
                    'legacy_mode', 'not_checked', :rh, :ph, :tn, :ws, 'tenant',
                    :seq)""",
                {
                    "id": mid["id"], "ts": _TS, "rh": mid["row_hash"],
                    "ph": mid["prev_hash"], "tn": _TENANT, "ws": _WS,
                    "seq": 999,
                },
            )
        self.assertIn(
            "unique", str(ctx.exception).lower(),
            "MECHANISM primary-key uniqueness: an exact-id duplicate must be "
            f"rejected by the PK constraint; got: {ctx.exception}",
        )

        # (b) A content duplicate under a NEW id, appended with the copied hash,
        # is caught by the chain: its prev_hash does not link to the real tail.
        last = self._rows()[-1]
        self.db.execute(
            """INSERT INTO audit_events
               (id, timestamp, subject_id, role, action, resource, approved,
                reason, challenge_present, challenge_result,
                grant_signature_result, row_hash, prev_hash, tenant_id,
                workspace_id, scope, seq)
               VALUES (:id, :ts, :subj, :role, :action, :res, :appr, :reason, 0,
                'legacy_mode', 'not_checked', :rh, :ph, :tn, :ws, 'tenant',
                :seq)""",
            {
                "id": "dup-of-mid", "ts": _TS, "subj": mid["subject_id"],
                "role": mid["role"], "action": mid["action"],
                "res": mid["resource"], "appr": mid["approved"],
                "reason": mid["reason"],
                # copy the duplicated event's OWN hashes verbatim
                "rh": mid["row_hash"], "ph": mid["prev_hash"],
                "tn": _TENANT, "ws": _WS, "seq": int(last["seq"]) + 1,
            },
        )
        result = self._verify()
        self.assertFalse(
            result["valid"],
            "MECHANISM row-hash chain: a duplicated event appended to the tail "
            "must not verify",
        )
        reasons = " | ".join(f["reason"] for f in result["failures"])
        self.assertIn(
            "prev_hash mismatch", reasons,
            "MECHANISM prev_hash linkage: the duplicate's copied prev_hash does "
            f"not link to the real chain tail; got: {reasons}",
        )

    # ── Attack 9 — flip reason_code between a value and NULL ────────────────
    def test_attack_09_reason_code_flip_null_and_value(self) -> None:
        """reason_code is NOT in the row-hash payload, so the local chain is
        BLIND to it. It IS in the anchor fold canonical (with the omit-when-None
        guard), so ONLY the anchored head catches the flip — in both directions.
        """
        # Direction A: NULL -> value (start from the all-None seeded chain).
        published_a = self._publish()
        mid = self._rows()[2]
        self._assert_trigger_blocks(
            "UPDATE audit_events SET reason_code=:c WHERE seq=:s",
            {"c": "access_granted", "s": mid["seq"]},
        )
        self._disable_immutability()
        self.db.execute(
            "UPDATE audit_events SET reason_code=:c WHERE seq=:s",
            {"c": "access_granted", "s": mid["seq"]},
        )
        self.assertTrue(
            self._verify()["valid"],
            "the row-hash chain is expected to be BLIND to reason_code (it is not "
            "in the row-hash payload); if this now fails the finding is stale",
        )
        self.assertNotEqual(
            self._anchor_head()["final_hash"], published_a["final_hash"],
            "MECHANISM on-chain anchored head (fold canonical): setting a NULL "
            "reason_code to a value must change the anchored head (the "
            "omit-when-None field enters the fold once it carries a value)",
        )

        # Direction B: value -> NULL. Same DB, triggers already dropped.
        published_b = self._anchor_head()
        self.db.execute(
            "UPDATE audit_events SET reason_code=NULL WHERE seq=:s",
            {"s": mid["seq"]},
        )
        self.assertNotEqual(
            self._anchor_head()["final_hash"], published_b["final_hash"],
            "MECHANISM on-chain anchored head (fold canonical): clearing a "
            "reason_code back to NULL must change the anchored head",
        )

    # ── Attack 10 — anchor fold vs public-export fold divergence (gl-378) ───
    def test_attack_10_fold_parity_divergence(self) -> None:
        """The anchored head is only trustworthy if an auditor recomputing from
        the PUBLIC export arrives at the same head. A canonicalization drift
        between the two folds (the gl-378 class: the anchor path dropping a
        column the public export carries) is caught by the fold-parity
        pre-flight — recompute both, they must be byte-identical."""
        # A chain exercising the omit-when-None guard: mixed reason_codes.
        self._append_one(action="none-rc", reason_code=None)
        self._append_one(action="set-rc", reason_code="access_granted")

        anchor = self._anchor_head()
        public = self._public_export_head()
        # Pre-flight PASSES on the real code.
        self.assertEqual(
            anchor["final_hash"], public["final_hash"],
            "MECHANISM anchor<->public-export fold parity: the anchored head "
            "already differs from the auditor-recomputable public head",
        )
        self.assertEqual(anchor["entry_count"], public["entry_count"])

        # Now REPRODUCE the gl-378 regression: the anchor path silently drops
        # reason_code. The parity pre-flight must CATCH the divergence.
        real_loader = ac._load_workspace_entries

        def _regressed_loader(session: Any, workspace_id: str) -> list[dict]:
            entries = real_loader(session, workspace_id)
            for e in entries:
                e.pop("reason_code", None)  # gl-378: column dropped by the fold
            return entries

        with mock.patch.object(ac, "_load_workspace_entries", _regressed_loader):
            regressed = self._anchor_head()
        self.assertNotEqual(
            regressed["final_hash"], public["final_hash"],
            "MECHANISM anchor<->public-export fold parity: a fold that drops "
            "reason_code produced the SAME head as the public export — the "
            "parity pre-flight would not have caught the gl-378 divergence",
        )


class TestDetectionIsNonVacuous(_BaseChainAttack):
    """RED-before-GREEN: prove each GREEN detection genuinely DEPENDS on its
    defence by disabling the defence and showing the same attack slips through.
    If these ever start FAILING (i.e. the attack is still caught with the
    defence off), the corresponding detection assertion above is vacuous."""

    def test_hash_link_detection_depends_on_row_hash_recompute(self) -> None:
        """Disable the row-hash recomputation (make it echo the stored hash) and
        the attack-4 mutation is no longer detected — proving attack 4's GREEN
        assertion rides on the real recomputation, not on incidental failure."""
        self._disable_immutability()
        mid = self._rows()[2]
        self.db.execute(
            "UPDATE audit_events SET action=:a WHERE seq=:s",
            {"a": "TAMPERED", "s": mid["seq"]},
        )
        # Sanity: with the real defence, this IS detected.
        self.assertFalse(self._verify()["valid"])

        # Defence disabled: recompute returns whatever hash is stored.
        def _echo(event, prev_hash):  # type: ignore[no-untyped-def]
            return event.row_hash

        with mock.patch.object(self.audit, "_compute_row_hash", _echo):
            self.assertTrue(
                self._verify()["valid"],
                "row-hash detection is VACUOUS: the mutation was still caught "
                "with the row-hash recomputation disabled",
            )

    def test_fold_detection_depends_on_reason_code_in_canonical(self) -> None:
        """Disable reason_code participation in the fold canonical and the
        attack-9 flip no longer moves the head — proving attack 9's GREEN
        assertion rides on reason_code actually being folded in."""
        # A canonical that always drops reason_code (the disabled defence).
        real_canonical = ac._entry_canonical

        def _blind_canonical(entry):  # type: ignore[no-untyped-def]
            return real_canonical({k: v for k, v in entry.items() if k != "reason_code"})

        published_real = self._publish()
        # Snapshot the PRISTINE head under the blind canonical, before tampering.
        with mock.patch.object(ac, "_entry_canonical", _blind_canonical):
            pristine_blind = self._anchor_head()

        self._disable_immutability()
        mid = self._rows()[2]
        self.db.execute(
            "UPDATE audit_events SET reason_code=:c WHERE seq=:s",
            {"c": "access_granted", "s": mid["seq"]},
        )
        # Sanity: with the real fold, the reason_code flip moves the head.
        self.assertNotEqual(
            self._anchor_head()["final_hash"], published_real["final_hash"]
        )

        # Defence disabled: the tampered head under the blind canonical is
        # identical to the pristine head under the blind canonical — the flip is
        # invisible, so detection genuinely depends on reason_code being folded.
        with mock.patch.object(ac, "_entry_canonical", _blind_canonical):
            after_blind = self._anchor_head()
        self.assertEqual(
            after_blind["final_hash"], pristine_blind["final_hash"],
            "fold detection is VACUOUS: the reason_code flip still moved the head "
            "with reason_code excluded from the canonical",
        )


if __name__ == "__main__":
    unittest.main()
