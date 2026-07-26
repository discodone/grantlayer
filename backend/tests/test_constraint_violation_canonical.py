"""Pinned canonical form of the constraint-violation witness JSON.

The audit chain's constraint_violation column stores a canonical JSON string
{"type":...,"limit":...,"attempted":...}. Because that string enters the
anchored export fold, its bytes must be deterministic forever:

  * key order pinned: type, limit, attempted;
  * compact separators (no whitespace) — the row-hash canonical precedent;
  * integers encoded as unquoted JSON ints;
  * ensure_ascii.

Also pins the canonical form of the grant-side constraints object (sorted
keys, compact separators) and the closed set of known constraint types
(unknown type -> deny, mirroring the api-keys unknown-scope rank pattern).
"""

import unittest


class TestViolationCanonical(unittest.TestCase):
    def test_pinned_bytes(self):
        from backend.src.policy.constraints import canonical_violation

        self.assertEqual(
            canonical_violation("max_fee_lovelace", 200000, 200001),
            '{"type":"max_fee_lovelace","limit":200000,"attempted":200001}',
        )

    def test_reserialization_is_deterministic(self):
        import json

        from backend.src.policy.constraints import canonical_violation

        first = canonical_violation("max_fee_lovelace", 200000, 200001)
        parsed = json.loads(first)
        again = canonical_violation(
            parsed["type"], parsed["limit"], parsed["attempted"]
        )
        self.assertEqual(first, again,
                         "the same logical violation must re-serialize to "
                         "identical bytes — the fold hashes these bytes")

    def test_no_incidental_whitespace_or_float_encoding(self):
        from backend.src.policy.constraints import canonical_violation

        c = canonical_violation("max_fee_lovelace", 1, 2)
        self.assertNotIn(" ", c)
        self.assertNotIn("1.0", c)
        self.assertEqual(c, '{"type":"max_fee_lovelace","limit":1,"attempted":2}')


class TestConstraintsCanonical(unittest.TestCase):
    def test_grant_constraints_canonical_sorted_compact(self):
        from backend.src.policy.constraints import canonical_constraints

        self.assertEqual(
            canonical_constraints({"max_fee_lovelace": 200000}),
            '{"max_fee_lovelace":200000}',
        )

    def test_known_constraints_is_the_closed_set(self):
        from backend.src.policy.constraints import KNOWN_CONSTRAINTS

        self.assertEqual(
            set(KNOWN_CONSTRAINTS),
            {"max_fee_lovelace", "max_wallet_balance_lovelace"},
            "the closed constraint vocabulary; extend deliberately (update "
            "this pin in the same change that registers a type), never "
            "implicitly",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
