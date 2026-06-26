"""Anchor metadata model (GL-350).

The on-chain payload structurally carries ONLY {h, s, t}:
  h = export-chain final_hash (64-char lowercase hex SHA-256 digest)
  s = entry_count (non-negative int)
  t = ISO-8601 timestamp string

No free-text, no foreign key to grants/applications, no PII. The field set is an
enforced invariant (see backend/tests/test_anchor_payload_schema.py): adding any
attribute is a deliberate breaking change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Custom integer metadata label for GrantLayer anchors (NOT CIP-20/674).
ANCHOR_LABEL = 923350

# Exactly 64 lowercase hex chars — one SHA-256 digest, which is exactly 64 UTF-8
# bytes and so fits Cardano's 64-byte metadata-string cap without chunking.
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class AnchorPayload:
    """The structured value placed on-chain under ANCHOR_LABEL.

    Carries EXACTLY three fields. Construction rejects invalid input (it never
    silently coerces) so a malformed or oversized head can never reach the chain.
    """

    h: str
    s: int
    t: str

    def __post_init__(self) -> None:
        # h: reject anything that is not exactly 64 lowercase hex chars. A leading
        # '0x' would be 66 bytes on-chain (> 64-byte cap) — reject, do not strip.
        if not isinstance(self.h, str) or self.h.startswith("0x") or not _HEX64.match(self.h):
            raise ValueError(
                "AnchorPayload.h must be exactly 64 lowercase hex chars (no '0x' prefix)"
            )
        # s: non-negative int (bool is rejected — it is not a valid entry count).
        if not isinstance(self.s, int) or isinstance(self.s, bool) or self.s < 0:
            raise ValueError("AnchorPayload.s must be a non-negative int")
        # t: non-empty ISO timestamp string.
        if not isinstance(self.t, str) or not self.t.strip():
            raise ValueError("AnchorPayload.t must be a non-empty ISO timestamp string")

    def to_dict(self) -> dict[str, object]:
        """The exact on-chain metadata map under ANCHOR_LABEL — nothing else."""
        return {"h": self.h, "s": self.s, "t": self.t}
