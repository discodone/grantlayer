#!/usr/bin/env python3
"""Assemble the LOCAL agent evidence bundle (NOT published anywhere).

Writes a self-contained directory that lets an external reviewer verify,
with ONLY Python stdlib + public Koios, (a) that the bundled audit export is
byte-anchored on Cardano mainnet, (b) which SIGNED grant authorized the
agent (grant signature checked against the bundled PUBLIC key), and (c) a
deterministic per-subject trace derived from that export.

Bundle contents:
    export.ndjson            anchored-prefix audit export (s entries)
    anchor.json              {txId, network, label, h, s, t}
    grant.json               the signed grant record (immutable fields +
                             signature + payloadHash + signingKeyId)
    signing-public-key.pem   the signing PUBLIC key (never the private key)
    verify-anchor.py         stdlib chain/anchor verifier (copied)
    verify-grant.py          stdlib grant-signature verifier (copied)
    extract_agent_trace.py   stdlib trace derivation (copied)
    trace.json               the derived trace (re-derivable by the reviewer)
    README.md                the keyless verification procedure

Input modes:
  OFFLINE (explicit files — used by tests):
    --export --grant-json --pubkey --anchor-json --subject --out
  LIVE (operator-side; imports backend, reads live API/DB via env — run
  through run_with_env.py):
    --live --grant-id <id> --anchor-record-id <id> --subject --out
    [--api http://127.0.0.1:8765] [--key-file ~/grantlayer-ops/...json]

The live mode truncates the fetched export to the anchored entry count so
the bundle's export is EXACTLY the prefix the anchor commits to.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_VERIFIERS = ("verify-anchor.py", "verify-grant.py", "extract_agent_trace.py")

_README = """\
# Agent Evidence Bundle — verify it yourself (Python stdlib + public Koios)

This bundle proves what the agent `{subject}` was ALLOWED to do and what it
DID, without trusting the operator's server. Everything below runs with a
plain Python 3 installation — the three bundled verifiers import no
GrantLayer code and no third-party libraries ("stdlib" only); the single
network dependency is the public, keyless Koios API for reading the Cardano
chain.

## 1. Verify the export is anchored on Cardano mainnet

    python3 verify-anchor.py --ndjson export.ndjson \\
        --tx-id {tx_id} --network {network}

Expected: `VERIFIED` and exit code 0. This recomputes the hash-chain fold
over every line of `export.ndjson` from a fixed genesis and compares the
resulting head AND entry count to the metadata that transaction carries
on-chain under label {label} (payload `{{h, s, t}}` = `{h_short}…`,
s={s}). Any edited, reordered, inserted, or removed line changes the head.
You can independently confirm the on-chain payload via Koios or any
Cardano explorer for that transaction.

## 2. Verify WHICH signed grant authorized the agent

    python3 verify-grant.py --grant grant.json \\
        --pubkey signing-public-key.pem --expect-key-id {key_id}

Expected: `VERIFIED` and exit code 0. This rebuilds the grant's canonical
payload from `grant.json`, checks its SHA-256 against `payloadHash`, checks
the public key's fingerprint equals `signingKeyId`, and verifies the
Ed25519 signature in pure Python (RFC 8032). A change to ANY immutable
field — subject, action, resource, validity, constraints — breaks it.

## 3. Re-derive the trace and compare

    python3 extract_agent_trace.py export.ndjson {subject} rederived.json
    diff trace.json rederived.json

Expected: empty diff. The trace is a pure projection of the verified
export: every witnessed event for `{subject}` with only
{{seq, timestamp, action, approved, reasonCode, matchedGrantId}}. Check
that each approved entry's `matchedGrantId` equals the `id` in
`grant.json` — that links every action to the signed authorization you
verified in step 2.

## What this proves — and what it does not

PROVES:
* The export is byte-identical to what existed when the anchor transaction
  was accepted into a Cardano block — nothing in it was rewritten since.
* The grant in `grant.json` (subject/action/resource/validity/constraints)
  was signed by the holder of the key with fingerprint `{key_id}`.
* Every trace entry is derived 1:1 from that anchored export.

DOES NOT PROVE:
* That the entries were complete or truthful WHEN WRITTEN — anchoring
  freezes a record, it does not vouch for its original honesty.
* Wall-clock accuracy of timestamps (server-assigned).
* Anything about tool ARGUMENTS — by design only the tool NAME is
  witnessed; arguments never enter the chain.
* Anything after entry s={s} — later events await the next anchor.
"""


def _copy_verifiers(out_dir: str) -> None:
    for name in _VERIFIERS:
        shutil.copy2(os.path.join(_SCRIPTS_DIR, name),
                     os.path.join(out_dir, name))
        os.chmod(os.path.join(out_dir, name), 0o755)


def _write_readme(out_dir: str, anchor: dict, grant: dict, subject: str) -> None:
    with open(os.path.join(out_dir, "README.md"), "w") as fh:
        fh.write(_README.format(
            subject=subject,
            tx_id=anchor["txId"],
            network=anchor["network"],
            label=anchor["label"],
            h_short=str(anchor["h"])[:16],
            s=anchor["s"],
            key_id=grant["signingKeyId"],
        ))


def _derive_trace(out_dir: str, subject: str) -> None:
    r = subprocess.run(
        [sys.executable, os.path.join(out_dir, "extract_agent_trace.py"),
         os.path.join(out_dir, "export.ndjson"), subject,
         os.path.join(out_dir, "trace.json")],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"trace derivation failed: {r.stderr}")


def _assemble(out_dir: str, export_path: str, grant: dict, pubkey_path: str,
              anchor: dict, subject: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    shutil.copy2(export_path, os.path.join(out_dir, "export.ndjson"))
    with open(os.path.join(out_dir, "grant.json"), "w") as fh:
        json.dump(grant, fh, sort_keys=True, indent=2)
        fh.write("\n")
    shutil.copy2(pubkey_path, os.path.join(out_dir, "signing-public-key.pem"))
    with open(os.path.join(out_dir, "anchor.json"), "w") as fh:
        json.dump(anchor, fh, sort_keys=True, indent=2)
        fh.write("\n")
    _copy_verifiers(out_dir)
    _derive_trace(out_dir, subject)
    _write_readme(out_dir, anchor, grant, subject)


def _live_inputs(args) -> tuple:
    """Operator-side gathering: fresh export (truncated to the anchored s),
    grant row, keyring public key, anchor record. Imports backend; run via
    run_with_env.py so env carries DB/API access. Reads only."""
    sys.path.insert(0, os.path.dirname(_SCRIPTS_DIR))
    import urllib.request

    import sqlalchemy as sa

    from backend.src.core import config as _cfg  # noqa: F401 (env-derived)
    from backend.src.core.db import get_session_maker

    with get_session_maker()() as s:
        a = s.execute(sa.text(
            "SELECT tx_id, network, anchor_label, final_hash, entry_count, "
            "anchored_at FROM anchor_records WHERE id = :i"),
            {"i": args.anchor_record_id}).mappings().first()
        if a is None:
            raise SystemExit(f"anchor record {args.anchor_record_id} not found")
        g = s.execute(sa.text(
            "SELECT id, subject_id, role, action, resource, valid_from, "
            "valid_until, created_by, reason, constraints, signature, "
            "payload_hash, signing_key_id FROM grants WHERE id = :i"),
            {"i": args.grant_id}).mappings().first()
        if g is None:
            raise SystemExit(f"grant {args.grant_id} not found")

    anchor = {"txId": a["tx_id"], "network": a["network"],
              "label": str(a["anchor_label"]), "h": a["final_hash"],
              "s": int(a["entry_count"]),
              "t": str(a["anchored_at"]).replace("+00:00", "Z")}
    grant = {"id": g["id"], "subjectId": g["subject_id"], "role": g["role"],
             "action": g["action"], "resource": g["resource"],
             "validFrom": g["valid_from"], "validUntil": g["valid_until"],
             "createdBy": g["created_by"], "reason": g["reason"],
             "constraints": g["constraints"], "signature": g["signature"],
             "payloadHash": g["payload_hash"],
             "signingKeyId": g["signing_key_id"]}

    with open(os.path.expanduser(args.key_file)) as fh:
        key_data = json.load(fh)
    raw_key = next(v for v in key_data.values()
                   if isinstance(v, str) and v.startswith("gl_live_"))
    req = urllib.request.Request(
        f"{args.api}/v1/audit/export?order=anchor",
        headers={"Authorization": f"Bearer {raw_key}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        lines = [ln for ln in resp.read().decode().splitlines() if ln.strip()]

    prefix = lines[: anchor["s"]]
    if len(prefix) < anchor["s"]:
        raise SystemExit(
            f"export has only {len(prefix)} data lines, anchor attests "
            f"{anchor['s']} — refusing to build an incomplete bundle")
    fd, export_path = tempfile.mkstemp(suffix=".ndjson",
                                       prefix="bundle-export-")
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(prefix) + "\n")

    keyring_dir = os.path.expanduser(args.keyring)
    pubkey_path = os.path.join(keyring_dir, f"{grant['signingKeyId']}.pem")
    if not os.path.exists(pubkey_path):
        raise SystemExit(f"public key PEM not found: {pubkey_path}")
    return export_path, grant, pubkey_path, anchor


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="build_agent_evidence_bundle.py")
    parser.add_argument("--out", required=True)
    parser.add_argument("--subject", required=True)
    # offline inputs
    parser.add_argument("--export")
    parser.add_argument("--grant-json")
    parser.add_argument("--pubkey")
    parser.add_argument("--anchor-json")
    # live inputs
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--grant-id")
    parser.add_argument("--anchor-record-id")
    parser.add_argument("--api", default="http://127.0.0.1:8765")
    parser.add_argument("--key-file",
                        default="~/grantlayer-ops/backup-agent.key.json")
    parser.add_argument("--keyring", default="~/grantlayer-ops/keyring")
    args = parser.parse_args(argv)

    if args.live:
        if not (args.grant_id and args.anchor_record_id):
            parser.error("--live requires --grant-id and --anchor-record-id")
        export_path, grant, pubkey_path, anchor = _live_inputs(args)
        cleanup_tmp = export_path
    else:
        needed = (args.export, args.grant_json, args.pubkey, args.anchor_json)
        if not all(needed):
            parser.error("offline mode requires --export --grant-json "
                         "--pubkey --anchor-json")
        with open(args.grant_json) as fh:
            grant = json.load(fh)
        with open(args.anchor_json) as fh:
            anchor = json.load(fh)
        export_path, pubkey_path = args.export, args.pubkey
        cleanup_tmp = None

    _assemble(args.out, export_path, grant, pubkey_path, anchor, args.subject)
    if cleanup_tmp:
        os.unlink(cleanup_tmp)

    print(f"bundle assembled: {args.out}")
    for name in sorted(os.listdir(args.out)):
        size = os.path.getsize(os.path.join(args.out, name))
        print(f"  {name}  ({size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
