"""GL-350a — RED tests pinning anchor-export determinism.

These tests define the contract for the (not-yet-implemented) anchor export
used by GL-350 on-chain anchoring. They are expected to FAIL until the
implementation lands — that is the intended RED state.

Design under test (proposed, not yet built):
  * ``_build_anchor_export(session, workspace_id) -> str``
        Returns the canonical NDJSON anchor export for a SINGLE workspace:
        the FULL hash chain, no date filter, NO limit/window, ordered by the
        stable ``seq`` tiebreak. Reuses the existing
        ``_entry_canonical`` / ``_chain_hash`` primitives in
        ``audit_compliance`` so the anchored value pins the REAL computation.
  * ``anchor_head(session, workspace_id) -> {"final_hash": str, "entry_count": int}``
        Head extractor: the fold over the entire workspace chain.

Both are expected to live in
``backend.src.api.routers.audit_compliance`` (co-located with the
canonicalization helpers they reuse). The tests import them lazily inside each
test via ``_load_anchor_funcs`` so the RED failure is a clear per-test
ImportError rather than a whole-module collection error.

Pinning the REAL hash (no reimplementation):
  The offline head recompute below (`_recompute_head`) uses the REAL
  ``_entry_canonical`` and ``_chain_hash`` imported from the production module
  — the test never reimplements SHA-256 or the canonical JSON form. Only the
  genesis seed ("0"*64) and the left-fold loop are mirrored in-test, because
  that fold currently lives INLINE inside ``export_audit_log._generate`` and
  ``verify_ndjson_export``.

  FLAG for GREEN (do NOT do it yet): to pin the fold itself (not just the
  primitives), GL-350a should factor a single shared helper, e.g.
  ``recompute_head_from_records(records) -> {"final_hash", "entry_count"}``,
  in ``audit_compliance`` and have the builder, ``verify_ndjson_export``, and
  the offline CLI all call it. The tests would then import and assert against
  that helper instead of the local ``_recompute_head`` mirror.
"""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest

# These primitives ALREADY exist — import at module load so the test pins the
# real canonicalization + chain hash (not a reimplementation).
from backend.src.api.routers.audit_compliance import _chain_hash, _entry_canonical

# Genesis seed for the export chain (matches export_audit_log / verify_ndjson_export).
_GENESIS = "0" * 64


class _BaseAnchorDeterminism(unittest.TestCase):
    """Fresh temp SQLite DB per test; seed audit events directly via append_event."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()
        self.db_mod = db_mod

        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

    def tearDown(self):
        try:
            os.unlink(self.tmp_db.name)
        except OSError:
            pass
        if self._orig_db is None:
            os.environ.pop("GRANTLAYER_DB", None)
        else:
            os.environ["GRANTLAYER_DB"] = self._orig_db

    # ── helpers ────────────────────────────────────────────────────────

    def _load_anchor_funcs(self):
        """Import the not-yet-existing anchor functions. Raises ImportError → RED."""
        from backend.src.api.routers.audit_compliance import (
            _build_anchor_export,
            anchor_head,
        )
        return _build_anchor_export, anchor_head

    def _seed(self, workspace_id, n, tenant_id="tenant-1", action_prefix="act"):
        """Append n audit events for one workspace; seq is assigned by append_event."""
        events = []
        for i in range(n):
            ev = self.models_mod.AuditEvent(
                subject_id=f"subj-{i}",
                role="agent",
                action=f"{action_prefix}-{i}",
                resource=f"res-{i}",
                approved=(i % 2 == 0),
                reason=f"reason-{i}",
                timestamp=f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}Z",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                scope="tenant",
            )
            self.audit_mod.append_event(ev)
            events.append(ev)
        return events

    @staticmethod
    def _parse(ndjson):
        """Split NDJSON into (data_records, manifest)."""
        records = [json.loads(line) for line in ndjson.splitlines() if line.strip()]
        manifest = None
        if records and records[-1].get("_type") == "manifest":
            manifest = records[-1]
            records = records[:-1]
        return records, manifest

    @staticmethod
    def _recompute_head(data_records):
        """Re-fold the head from data records using the REAL primitives.

        Mirrors verify_ndjson_export's recompute: strip _-prefixed chain fields,
        re-canonicalize with the real _entry_canonical, re-chain with the real
        _chain_hash from genesis. Returns (final_hash, entry_count).
        """
        prev = _GENESIS
        for rec in data_records:
            clean = {k: v for k, v in rec.items() if not k.startswith("_")}
            prev = _chain_hash(prev, _entry_canonical(clean))
        return prev, len(data_records)


class TestAnchorExportDeterminism(_BaseAnchorDeterminism):

    def test_double_export_byte_identical(self):
        """Two builds of the same workspace chain → byte-identical NDJSON + equal head."""
        build, _head = self._load_anchor_funcs()
        self._seed("ws-id", 8)

        s1 = self.db_mod.get_session()
        try:
            out1 = build(s1, "ws-id")
        finally:
            s1.close()
        s2 = self.db_mod.get_session()
        try:
            out2 = build(s2, "ws-id")
        finally:
            s2.close()

        self.assertEqual(out1, out2, "anchor export not byte-identical across two builds")
        _, m1 = self._parse(out1)
        _, m2 = self._parse(out2)
        self.assertEqual(m1["_final_hash"], m2["_final_hash"])

    def test_final_hash_is_total_chain_not_windowed(self):
        """Head must fold over the ENTIRE workspace chain, never a recent window.

        Determinism risk: the public GET /v1/audit/export defaults to
        limit=10000, hashing only a recent slice if the dataset is larger.
        Seeding 10 000+ rows per test is prohibitively slow, so we seed a
        smaller set (N) and assert the anchor head covers it EXACTLY. A windowed
        implementation (LIMIT < dataset) would make entry_count < N and change
        _final_hash. The anchor builder must apply NO limit. (A slow opt-in test
        crossing the real 10 000 default belongs with the GREEN implementation.)
        """
        build, head = self._load_anchor_funcs()
        N = 120
        self._seed("ws-full", N)

        out = build(self.db_mod.get_session(), "ws-full")
        data, manifest = self._parse(out)
        self.assertEqual(len(data), N, "export did not cover all rows (windowed?)")
        self.assertEqual(manifest["_entry_count"], N)

        h = head(self.db_mod.get_session(), "ws-full")
        self.assertEqual(h["entry_count"], N, "head entry_count != full chain length")

        recomputed, count = self._recompute_head(data)
        self.assertEqual(count, N)
        self.assertEqual(h["final_hash"], recomputed, "head is not a fold over the full chain")
        self.assertEqual(manifest["_final_hash"], recomputed)

    def test_tail_truncation_detected(self):
        """Removing the LAST data line must change BOTH the head and the count.

        This is the gap the audit flagged: verify_ndjson_export does not, keyless,
        compare the recomputed head/count against the manifest. Anchoring _final_hash
        closes it — head + entry_count comparison catches tail removal.
        """
        build, _head = self._load_anchor_funcs()
        self._seed("ws-trunc", 6)

        out = build(self.db_mod.get_session(), "ws-trunc")
        data, manifest = self._parse(out)
        self.assertGreaterEqual(len(data), 2)
        original_final = manifest["_final_hash"]
        original_count = manifest["_entry_count"]

        truncated = data[:-1]  # drop the last data line (immediately before manifest)
        recomputed, count = self._recompute_head(truncated)

        self.assertNotEqual(
            recomputed, original_final,
            "tail truncation NOT detected: head unchanged after dropping last line",
        )
        self.assertNotEqual(
            count, original_count,
            "tail truncation NOT detected: entry_count still matches line count",
        )

    def test_reorder_detected(self):
        """Swapping two adjacent data lines must change the recomputed head."""
        build, _head = self._load_anchor_funcs()
        self._seed("ws-reorder", 6)

        out = build(self.db_mod.get_session(), "ws-reorder")
        data, manifest = self._parse(out)
        self.assertGreaterEqual(len(data), 3)
        original_final = manifest["_final_hash"]

        swapped = list(data)
        swapped[1], swapped[2] = swapped[2], swapped[1]
        recomputed, _count = self._recompute_head(swapped)

        self.assertNotEqual(
            recomputed, original_final,
            "reordering two lines did not change the head (linkage not order-bound)",
        )

    def test_workspace_isolation(self):
        """Distinct workspaces → distinct heads; an export contains only its own rows."""
        build, head = self._load_anchor_funcs()
        self._seed("ws-A", 5, action_prefix="A")
        self._seed("ws-B", 7, action_prefix="B")

        out_a = build(self.db_mod.get_session(), "ws-A")
        data_a, _manifest_a = self._parse(out_a)
        self.assertEqual(len(data_a), 5, "ws-A export row count wrong (leakage?)")
        for rec in data_a:
            self.assertEqual(rec.get("workspace_id"), "ws-A", "foreign workspace row in export")

        head_a = head(self.db_mod.get_session(), "ws-A")
        head_b = head(self.db_mod.get_session(), "ws-B")
        self.assertEqual(head_a["entry_count"], 5)
        self.assertEqual(head_b["entry_count"], 7)
        self.assertNotEqual(
            head_a["final_hash"], head_b["final_hash"],
            "distinct workspaces produced identical anchor heads",
        )


if __name__ == "__main__":
    unittest.main()
