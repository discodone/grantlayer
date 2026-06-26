"""GL-350b — RED tests for AnchorPayload schema (backend/src/anchoring/models.py).

PII-prevention invariant: the on-chain payload structurally carries ONLY
{h, s, t} — h = export-chain final_hash (64-char hex), s = entry_count,
t = ISO timestamp. No free-text, no FK to grants/applications, no PII.

Expected RED: backend.src.anchoring.models does not exist yet → ImportError in
each test (imports inside the methods → per-test failures, not one collection
error).
"""

from __future__ import annotations

import dataclasses
import unittest


_VALID_H = "a" * 64  # 64-char lowercase hex, no 0x prefix (== one SHA-256 digest)
_TS = "2026-06-26T00:00:00Z"


class TestAnchorPayloadSchema(unittest.TestCase):

    # 5 ──────────────────────────────────────────────────────────────────
    def test_payload_has_only_h_s_t(self):
        # The PII-prevention invariant: adding ANY field must break this test.
        from backend.src.anchoring.models import ANCHOR_LABEL, AnchorPayload
        field_names = {f.name for f in dataclasses.fields(AnchorPayload)}
        assert field_names == {"h", "s", "t"}, (
            f"AnchorPayload must carry EXACTLY h/s/t (PII-prevention); got {field_names}"
        )
        # The custom integer metadata label is pinned alongside the model.
        assert ANCHOR_LABEL == 923350

    # 6 ──────────────────────────────────────────────────────────────────
    def test_h_is_64_hex_no_0x_prefix(self):
        from backend.src.anchoring.models import AnchorPayload
        p = AnchorPayload(h=_VALID_H, s=3, t=_TS)
        assert len(p.h) == 64
        assert not p.h.startswith("0x")
        int(p.h, 16)  # must parse as hex
        # A 0x-prefixed value is 66 UTF-8 bytes on-chain, over Cardano's 64-byte
        # metadata cap → construction must reject it (pinned behavior: ValueError).
        with self.assertRaises(ValueError):
            AnchorPayload(h="0x" + _VALID_H, s=3, t=_TS)
        # A non-hex / wrong-length value must also be rejected.
        with self.assertRaises(ValueError):
            AnchorPayload(h="not-hex", s=3, t=_TS)

    # 7 ──────────────────────────────────────────────────────────────────
    def test_serialized_metadata_contains_no_grant_or_pii_fields(self):
        from backend.src.anchoring.models import AnchorPayload
        p = AnchorPayload(h=_VALID_H, s=7, t=_TS)
        meta = p.to_dict()  # the dict that becomes the on-chain metadata value
        assert set(meta.keys()) == {"h", "s", "t"}
        blob = repr(meta).lower()
        for forbidden in (
            "grant", "applicant", "workspace", "subject", "reason", "resource", "role", "name",
        ):
            assert forbidden not in blob, f"PII/grant leak in serialized payload: {forbidden!r}"
        assert meta["h"] == _VALID_H
        assert meta["s"] == 7
        assert meta["t"] == _TS


if __name__ == "__main__":
    unittest.main()
