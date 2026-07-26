"""constraint_violation is additive-and-forward-only in the anchored chain.

Mirrors the reason_code forward-only invariant (test_audit_reason_code_chain):
the anchored head folds _entry_canonical over each event's full dict, so a
naive column addition would put `"constraint_violation": null` into EVERY
historical event's canonical and change every anchored head — invalidating
the recomputation of all four live mainnet anchors.

Pinned here: a constraint_violation that is None (every pre-change event, and
every non-violation event) must be INVISIBLE to the fold; a set value must be
covered by the fold going forward. The verifier side of the same invariant is
held by the golden vectors (fold_golden_vectors.json) through BOTH
implementations.
"""

from __future__ import annotations

import unittest

from backend.src.api.routers.audit_compliance import recompute_head_from_records

_VIOLATION = '{"type":"max_fee_lovelace","limit":200000,"attempted":200001}'


def _chain(cv_key: bool, cv_value=None):
    rows = [
        {
            "id": "e1", "timestamp": "2026-01-01T00:00:00Z", "subject_id": "s1",
            "role": "agent", "action": "read", "resource": "res/1",
            "approved": True, "reason": "access granted", "matched_grant_id": "g1",
            "challenge_id": None, "challenge_present": False,
            "challenge_result": "legacy_mode", "grant_signature_result": "valid",
            "tenant_id": "t1", "workspace_id": "w1", "scope": "tenant", "seq": 1,
            "row_hash": "a" * 64, "prev_hash": None, "reason_code": None,
        },
        {
            "id": "e2", "timestamp": "2026-01-01T00:00:01Z", "subject_id": "s1",
            "role": "agent", "action": "write", "resource": "res/2",
            "approved": False, "reason": "grant expired", "matched_grant_id": None,
            "challenge_id": None, "challenge_present": False,
            "challenge_result": "legacy_mode", "grant_signature_result": "not_checked",
            "tenant_id": "t1", "workspace_id": "w1", "scope": "tenant", "seq": 2,
            "row_hash": "b" * 64, "prev_hash": "a" * 64, "reason_code": "grant_expired",
        },
    ]
    if cv_key:
        for r in rows:
            r["constraint_violation"] = cv_value
    return rows


class TestConstraintViolationForwardOnly(unittest.TestCase):
    def test_none_constraint_violation_is_invisible_to_the_fold(self):
        """Present-but-None must NOT change the anchored head — this is what
        keeps every past on-chain anchor recomputable."""
        head_without = recompute_head_from_records(_chain(cv_key=False))
        head_with_none = recompute_head_from_records(
            _chain(cv_key=True, cv_value=None)
        )
        self.assertEqual(
            head_without["final_hash"], head_with_none["final_hash"]
        )

    def test_set_constraint_violation_changes_the_head(self):
        """A SET violation must be covered by the fold — a witness that the
        fold ignored would be an unanchored claim."""
        head_none = recompute_head_from_records(
            _chain(cv_key=True, cv_value=None)
        )
        head_set = recompute_head_from_records(
            _chain(cv_key=True, cv_value=_VIOLATION)
        )
        self.assertNotEqual(head_none["final_hash"], head_set["final_hash"])

    def test_empty_string_is_kept(self):
        """The omit rule fires on None only — same contract as reason_code."""
        head_none = recompute_head_from_records(
            _chain(cv_key=True, cv_value=None)
        )
        head_empty = recompute_head_from_records(
            _chain(cv_key=True, cv_value="")
        )
        self.assertNotEqual(head_none["final_hash"], head_empty["final_hash"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
