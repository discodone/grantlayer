"""GL-350b WRITER step 1 — RED tests: anchor_records model + head→payload helper.

These reference not-yet-existing code, so they fail at import FIRST (imports are
inside each method → per-test failures, not one collection error):
  - backend.src.core.orm.AnchorRecord           (the new PII-free persistence table)
  - backend.src.anchoring.writer.head_to_payload (anchor_head result → AnchorPayload)

Locked persistence contract (mirrors WebhookDelivery, all Text/Integer columns):
  EXACTLY 9 columns — id, workspace_id, final_hash, entry_count, anchored_at,
  tx_id, network, anchor_label, status. No FK to grants/applications, no PII.
"""

from __future__ import annotations

import datetime as _dt
import unittest

# The exact, closed column set — adding ANY column must break the PII test.
_EXPECTED_COLUMNS = {
    "id",
    "workspace_id",
    "final_hash",
    "entry_count",
    "anchored_at",
    "tx_id",
    "network",
    "anchor_label",
    "status",
}

_VALID_H = "a" * 64  # one SHA-256 digest: 64 lowercase hex chars, no 0x prefix


class TestAnchorRecordsModel(unittest.TestCase):

    # 1 ──────────────────────────────────────────────────────────────────
    def test_anchor_records_columns_are_pii_free(self):
        from backend.src.core.orm import AnchorRecord

        assert AnchorRecord.__tablename__ == "anchor_records"

        cols = {c.name for c in AnchorRecord.__table__.columns}
        assert cols == _EXPECTED_COLUMNS, (
            f"anchor_records must carry EXACTLY {_EXPECTED_COLUMNS} (PII-free); got {cols}"
        )

        # No foreign keys at all — the row must not reference grants/applications.
        fks = {
            (c.name, fk.target_fullname)
            for c in AnchorRecord.__table__.columns
            for fk in c.foreign_keys
        }
        assert not fks, f"anchor_records must have NO foreign keys; got {fks}"

        # Defence-in-depth: no column name hints at a grant/application linkage.
        forbidden = {"grant", "application", "subject", "reason", "resource", "payload"}
        leaks = {c for c in cols if any(tok in c for tok in forbidden)}
        assert not leaks, f"anchor_records column name leaks PII-bearing concept: {leaks}"

    # 2 ──────────────────────────────────────────────────────────────────
    def test_head_to_payload_conversion(self):
        from backend.src.anchoring.models import AnchorPayload
        from backend.src.anchoring.writer import head_to_payload

        now = _dt.datetime(2026, 6, 26, 2, 0, 0, tzinfo=_dt.timezone.utc)
        head = {"final_hash": _VALID_H, "entry_count": 7}

        payload = head_to_payload(head, now)

        assert isinstance(payload, AnchorPayload)
        assert payload.h == _VALID_H          # final_hash → h, verbatim
        assert payload.s == 7                 # entry_count → s
        assert isinstance(payload.t, str) and payload.t.strip()  # timestamp → non-empty t

    # 2b ─────────────────────────────────────────────────────────────────
    def test_head_to_payload_rejects_bad_final_hash(self):
        # The helper must reuse AnchorPayload's validation, never bypass it:
        # a 0x-prefixed / non-64-hex final_hash can never reach the chain.
        from backend.src.anchoring.writer import head_to_payload

        now = _dt.datetime(2026, 6, 26, 2, 0, 0, tzinfo=_dt.timezone.utc)
        with self.assertRaises(ValueError):
            head_to_payload({"final_hash": "0x" + "a" * 62, "entry_count": 1}, now)


if __name__ == "__main__":
    unittest.main()
