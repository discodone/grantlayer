"""Golden fold vectors — the durable cross-implementation guard.

The backend export fold and the standalone stdlib verifier
(scripts/verify-anchor.py) are two INDEPENDENT implementations of one canonical
form. Independence is the point (the verifier depends on none of GrantLayer's
code), but two implementations drift unless something holds them against each
other. This file is that something: one data-only JSON fixture
(fixtures/fold_golden_vectors.json) of raw entries -> expected canonical form and
expected chain hash, run through TWO entry points — backend and verifier. A drift
in EITHER direction fails.

Covered: all-None optional fields, a populated reason_code, an empty-string
reason_code (the guard fires on None only, not on falsy ""), and a mixed
None/non-None multi-event chain.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest

_HERE = pathlib.Path(__file__).resolve()
_FIXTURE = _HERE.parent / "fixtures" / "fold_golden_vectors.json"
_VERIFY_PATH = _HERE.parents[2] / "scripts" / "verify-anchor.py"


def _load_fixture() -> dict:
    with open(_FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_anchor_golden", _VERIFY_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class TestGoldenVectorsBackend(unittest.TestCase):
    """Entry point 1: the backend fold must reproduce every golden value."""

    def setUp(self):
        self.fx = _load_fixture()

    def test_single_entry_canonicals(self):
        from backend.src.api.routers.audit_compliance import _entry_canonical
        for v in self.fx["single_entry_vectors"]:
            self.assertEqual(
                _entry_canonical(v["entry"]), v["expected_canonical"],
                f"backend canonical drifted for vector {v['name']!r}",
            )

    def test_chain_heads(self):
        from backend.src.api.routers.audit_compliance import recompute_head_from_records
        for v in self.fx["chain_vectors"]:
            head = recompute_head_from_records(v["chain"])
            self.assertEqual(head["final_hash"], v["expected_final_hash"],
                             f"backend chain head drifted for {v['name']!r}")
            self.assertEqual(head["entry_count"], v["expected_entry_count"])


class TestGoldenVectorsVerifier(unittest.TestCase):
    """Entry point 2: the standalone verifier must reproduce every golden value."""

    def setUp(self):
        self.fx = _load_fixture()
        self.va = _load_verifier()

    def test_single_entry_canonicals(self):
        for v in self.fx["single_entry_vectors"]:
            self.assertEqual(
                self.va.entry_canonical(v["entry"]), v["expected_canonical"],
                f"verifier canonical drifted for vector {v['name']!r}",
            )

    def test_chain_heads(self):
        genesis = self.fx["genesis"]
        for v in self.fx["chain_vectors"]:
            prev = genesis
            for entry in v["chain"]:
                prev = self.va.chain_hash(prev, self.va.entry_canonical(entry))
            self.assertEqual(prev, v["expected_final_hash"],
                             f"verifier chain head drifted for {v['name']!r}")


if __name__ == "__main__":
    unittest.main()
