"""Agent Evidence Bundle verifiers (gl-413).

Three standalone, stdlib-only artifacts that let an EXTERNAL party verify an
agent's witnessed activity without trusting the server and without any
GrantLayer or third-party code:

  R1 scripts/verify-grant.py    — Ed25519 grant-signature verifier (pure
                                  RFC 8032 verification + PEM SPKI parse),
                                  mirrors crypto_signing.canonical_grant_payload
                                  / sign_grant byte-for-byte.
  R2 scripts/extract_agent_trace.py — deterministic per-subject trace derived
                                  from the anchored export (NO tool arguments
                                  — they are never witnessed).
  R3 scripts/build_agent_evidence_bundle.py — assembles the LOCAL bundle
                                  (export prefix + grant.json + public key +
                                  verifiers + trace + README). Offline input
                                  mode used here; the Koios anchor step is
                                  exercised live, not in unit tests (network).

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_VERIFY_GRANT = os.path.join(_REPO, "scripts", "verify-grant.py")
_EXTRACT = os.path.join(_REPO, "scripts", "extract_agent_trace.py")
_BUILD = os.path.join(_REPO, "scripts", "build_agent_evidence_bundle.py")


def _run(script, *args):
    return subprocess.run(
        [sys.executable, script, *args], capture_output=True, text=True
    )


class _SignedGrantBase(unittest.TestCase):
    """Throwaway SQLite + demo keypair; creates one signed grant and dumps
    the grant JSON + public-key PEM the way the bundle assembler does."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()
        crypto_mod._ensure_keyring_baseline()
        self.crypto_mod = crypto_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)

        from backend.src.core.models import Grant
        g = Grant(
            subject_id="claude-code-agent", role="agent", action="*",
            resource="claude-code/tool",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="ops", reason="bundle test grant",
        )
        grants_mod.create_grant(g, tenant_id="demo")
        self.grant = g

        self.workdir = tempfile.mkdtemp()
        self.grant_json = os.path.join(self.workdir, "grant.json")
        with open(self.grant_json, "w") as f:
            json.dump({
                "id": g.id, "subjectId": g.subject_id, "role": g.role,
                "action": g.action, "resource": g.resource,
                "validFrom": g.valid_from, "validUntil": g.valid_until,
                "createdBy": g.created_by, "reason": g.reason,
                "constraints": g.constraints,
                "signature": g.signature, "payloadHash": g.payload_hash,
                "signingKeyId": g.signing_key_id,
            }, f, indent=1)

        key_id = g.signing_key_id
        self.pubkey_pem = self.crypto_mod._keyring_path(key_id)
        self.assertTrue(os.path.exists(self.pubkey_pem),
                        "keyring must hold the signing public key PEM")

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

    def _tampered(self, **overrides):
        with open(self.grant_json) as f:
            data = json.load(f)
        data.update(overrides)
        path = os.path.join(self.workdir, f"tampered-{uuid.uuid4().hex[:6]}.json")
        with open(path, "w") as f:
            json.dump(data, f)
        return path


class TestGrantSignatureVerifier(_SignedGrantBase):
    """R1 — stdlib verifier passes on the real grant, fails on tampering."""

    def test_real_grant_verifies(self):
        r = _run(_VERIFY_GRANT, "--grant", self.grant_json,
                 "--pubkey", self.pubkey_pem)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERIFIED", r.stdout)

    def test_tampered_action_fails(self):
        r = _run(_VERIFY_GRANT, "--grant", self._tampered(action="Bash"),
                 "--pubkey", self.pubkey_pem)
        self.assertNotEqual(r.returncode, 0,
                            "a tampered action must fail signature verification")

    def test_tampered_resource_fails(self):
        r = _run(_VERIFY_GRANT,
                 "--grant", self._tampered(resource="everything/*"),
                 "--pubkey", self.pubkey_pem)
        self.assertNotEqual(r.returncode, 0)

    def test_tampered_constraints_fails(self):
        r = _run(_VERIFY_GRANT,
                 "--grant", self._tampered(
                     constraints='{"max_fee_lovelace":999999999}'),
                 "--pubkey", self.pubkey_pem)
        self.assertNotEqual(r.returncode, 0,
                            "injected constraints must fail verification")

    def test_wrong_pubkey_fails(self):
        # The demo baseline keyring entry is a DIFFERENT key than the one that
        # signed (unless ids collide); a mismatching key id must be refused.
        r = _run(_VERIFY_GRANT, "--grant", self.grant_json,
                 "--pubkey", self.pubkey_pem,
                 "--expect-key-id", "ed25519-0000000000000000")
        self.assertNotEqual(r.returncode, 0)


_FIXTURE_EVENTS = [
    {"id": "e1", "seq": 30, "timestamp": "2026-07-24T19:10:00Z",
     "subject_id": "claude-code-agent", "role": "agent", "action": "Bash",
     "resource": "claude-code/tool", "approved": True,
     "reason_code": "access_granted", "matched_grant_id": "g-1",
     "row_hash": "aa", "prev_hash": None},
    {"id": "e2", "seq": 31, "timestamp": "2026-07-24T19:11:00Z",
     "subject_id": "someone-else", "role": "agent", "action": "pg_dump",
     "resource": "db/x", "approved": False,
     "reason_code": "no_matching_grant", "matched_grant_id": None,
     "row_hash": "bb", "prev_hash": "aa"},
    {"id": "e3", "seq": 32, "timestamp": "2026-07-24T19:12:00Z",
     "subject_id": "claude-code-agent", "role": "agent", "action": "Read",
     "resource": "claude-code/tool", "approved": True,
     "reason_code": "access_granted", "matched_grant_id": "g-1",
     "row_hash": "cc", "prev_hash": "bb"},
]


class TestTraceExtraction(unittest.TestCase):
    """R2 — the trace is deterministic and derived only from the export."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.export = os.path.join(self.workdir, "export.ndjson")
        with open(self.export, "w") as f:
            for e in _FIXTURE_EVENTS:
                f.write(json.dumps(e) + "\n")

    def _extract(self, out):
        r = _run(_EXTRACT, self.export, "claude-code-agent", out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(out, "rb") as f:
            return f.read()

    def test_extraction_is_byte_deterministic(self):
        a = self._extract(os.path.join(self.workdir, "t1.json"))
        b = self._extract(os.path.join(self.workdir, "t2.json"))
        self.assertEqual(a, b, "same export must yield byte-identical traces")

    def test_trace_content(self):
        raw = self._extract(os.path.join(self.workdir, "t.json"))
        trace = json.loads(raw)
        self.assertEqual(trace["subject"], "claude-code-agent")
        self.assertEqual(len(trace["entries"]), 2)
        self.assertEqual([e["action"] for e in trace["entries"]],
                         ["Bash", "Read"])
        self.assertEqual([e["seq"] for e in trace["entries"]], [30, 32])
        # No tool arguments exist anywhere in the pipeline — pin the fields.
        for e in trace["entries"]:
            self.assertEqual(
                sorted(e), ["action", "approved", "matchedGrantId",
                            "reasonCode", "seq", "timestamp"])


class TestBundleAssembly(_SignedGrantBase):
    """R3 — offline assembly produces a complete, self-verifying bundle."""

    _EXPECTED_FILES = {
        "export.ndjson", "grant.json", "signing-public-key.pem",
        "anchor.json", "trace.json", "verify-anchor.py", "verify-grant.py",
        "extract_agent_trace.py", "README.md",
    }

    def test_offline_assembly_completeness_and_self_verification(self):
        export = os.path.join(self.workdir, "export.ndjson")
        with open(export, "w") as f:
            for e in _FIXTURE_EVENTS:
                f.write(json.dumps(e) + "\n")
        anchor_json = os.path.join(self.workdir, "anchor.json")
        with open(anchor_json, "w") as f:
            json.dump({"txId": "ff" * 32, "network": "mainnet",
                       "label": "923350", "h": "00" * 32, "s": 3,
                       "t": "2026-07-27T04:49:00Z"}, f)

        out_dir = os.path.join(self.workdir, "bundle")
        r = _run(_BUILD, "--out", out_dir,
                 "--export", export,
                 "--grant-json", self.grant_json,
                 "--pubkey", self.pubkey_pem,
                 "--anchor-json", anchor_json,
                 "--subject", "claude-code-agent")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        self.assertEqual(set(os.listdir(out_dir)), self._EXPECTED_FILES)

        # The bundle must verify ITSELF with its own bundled verifier.
        rv = _run(os.path.join(out_dir, "verify-grant.py"),
                  "--grant", os.path.join(out_dir, "grant.json"),
                  "--pubkey", os.path.join(out_dir, "signing-public-key.pem"))
        self.assertEqual(rv.returncode, 0, rv.stdout + rv.stderr)

        # trace.json must equal a fresh derivation from the bundled export.
        rederived = os.path.join(self.workdir, "rederived.json")
        _run(os.path.join(out_dir, "extract_agent_trace.py"),
             os.path.join(out_dir, "export.ndjson"),
             "claude-code-agent", rederived)
        with open(os.path.join(out_dir, "trace.json"), "rb") as f1, \
                open(rederived, "rb") as f2:
            self.assertEqual(f1.read(), f2.read())

        # README must teach the keyless procedure.
        with open(os.path.join(out_dir, "README.md")) as f:
            readme = f.read()
        for needle in ("verify-anchor.py", "verify-grant.py",
                       "extract_agent_trace.py", "Koios", "stdlib"):
            self.assertIn(needle, readme)


if __name__ == "__main__":
    unittest.main()
