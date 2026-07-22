"""The offline verifier (scripts/verify-anchor.py) must fold identically to the
backend export fold — including the forward-only omit-when-None rule.

verify-anchor.py is a DELIBERATE stdlib-only re-implementation that shares no
GrantLayer code. Two independent implementations only stay honest if something
holds them against each other; this test runs the REAL verifier module and the
REAL backend fold against the same entries and asserts byte-identical output.

Without the guard the verifier folds ``"reason_code": null`` while the backend
omits it, so any export regenerated after the reason_code rollout (which carries
reason_code=None on every legacy row) would recompute a different head and fail
offline verification — even though it still recomputes correctly backend-side.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from backend.src.api.routers.audit_compliance import (
    _entry_canonical,
    _iter_chain,
    recompute_head_from_records,
)

_VERIFY_PATH = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "verify-anchor.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_anchor_under_test", _VERIFY_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


_ENTRY_BASE = {
    "id": "e1", "timestamp": "2026-01-01T00:00:00Z", "subject_id": "s1",
    "role": "agent", "action": "read", "resource": "res/1", "approved": True,
    "reason": "ok", "matched_grant_id": "g1", "challenge_id": None,
    "challenge_present": False, "challenge_result": "legacy_mode",
    "grant_signature_result": "valid", "tenant_id": "t1", "workspace_id": "w1",
    "scope": "tenant", "seq": 1, "row_hash": "a" * 64, "prev_hash": None,
}


def _entry(**over):
    e = dict(_ENTRY_BASE)
    e.update(over)
    return e


class TestVerifierFoldParity(unittest.TestCase):
    def setUp(self):
        self.va = _load_verifier()

    def test_none_reason_code_canonical_matches_backend(self):
        """The forward-only field (reason_code) None => omitted by BOTH."""
        e = _entry(reason_code=None)
        self.assertEqual(self.va.entry_canonical(e), _entry_canonical(e))

    def test_set_reason_code_canonical_matches_backend(self):
        e = _entry(reason_code="access_granted")
        self.assertEqual(self.va.entry_canonical(e), _entry_canonical(e))

    def test_other_none_fields_are_KEPT_by_both(self):
        """Non-forward-only None fields (matched_grant_id, challenge_id, scope,
        tenant_id …) stay as null in BOTH — the guard must NOT omit all None,
        or the many legacy events with those None fields stop verifying."""
        e = _entry(reason_code=None, matched_grant_id=None, challenge_id=None,
                   scope=None, tenant_id=None)
        self.assertEqual(self.va.entry_canonical(e), _entry_canonical(e))

    def test_empty_string_reason_code_is_kept_not_omitted(self):
        """The guard fires on None only, not on falsy '' — pin the boundary."""
        e = _entry(reason_code="")
        self.assertEqual(self.va.entry_canonical(e), _entry_canonical(e))

    def test_full_head_parity_mixed_chain(self):
        """A regenerated export (reason_code keys present, mixed None/non-None):
        the verifier's recompute_head must equal the backend head with no
        VerifyError against the backend-stamped _chain_hash."""
        entries = [
            _entry(id="e1", seq=1, reason_code=None, prev_hash=None, row_hash="a" * 64),
            _entry(id="e2", seq=2, reason_code="access_granted", prev_hash="a" * 64, row_hash="b" * 64),
        ]
        # Stamp _chain_hash/_prev_hash with the BACKEND (guarded) fold, exactly
        # like _build_anchor_export does.
        records = []
        for rec, prev, entry_hash in _iter_chain(entries):
            records.append({**rec, "_chain_hash": entry_hash, "_prev_hash": prev})
        backend_head = recompute_head_from_records(entries)
        verifier_head = self.va.recompute_head(records)  # raises if a line mismatches
        self.assertEqual(verifier_head["final_hash"], backend_head["final_hash"])
        self.assertEqual(verifier_head["entry_count"], backend_head["entry_count"])


if __name__ == "__main__":
    unittest.main()
