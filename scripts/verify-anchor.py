#!/usr/bin/env python3
"""Keyless, offline verifier for a GrantLayer on-chain audit anchor.

WHAT THIS PROVES
    Given only (a) a GrantLayer NDJSON audit export and (b) public Cardano chain
    access, this script proves that THE EXPORT HAS NOT BEEN REWRITTEN SINCE THE
    ANCHOR TIMESTAMP. It recomputes the export's hash-chain head from the file
    alone and checks it — byte for byte — against the digest that was published
    on-chain at anchor time. Because the on-chain digest is immutable and no one
    (not even GrantLayer) can alter a confirmed transaction, a match means the
    file you hold is exactly the file that existed when the anchor was written.

WHAT THIS DOES NOT PROVE
    It does NOT prove the audit entries were correct, complete, or honest when
    they were first written. Anchoring freezes a record; it cannot vouch for the
    truthfulness of what was recorded. A tamperer who controlled the log BEFORE
    the anchor could have anchored a doctored file. This verifier only rules out
    tampering that happened AFTER the anchor.

TRUST MODEL
    Zero trust in GrantLayer. This script imports NO GrantLayer code and NO
    Cardano library — only the Python standard library. It reads the chain over
    plain HTTPS from KOIOS (keyless public tier). The hash-chain fold below is a
    DELIBERATE reimplementation of the export-side fold; the two must agree, and
    duplicating it here is what makes verification independent of our codebase.

USAGE
    python3 verify-anchor.py --ndjson export.ndjson \\
        --tx-id <cardano_tx_id> [--network preprod|mainnet] [--hmac-key KEY]

    python3 verify-anchor.py --discover [--network preprod|mainnet]
        List candidate anchor transactions (metadata label 923350) on the chain.

    KOIOS_BASE_URL env var overrides the API base (e.g. for an offline stub).

EXIT CODES
    0  VERIFIED — the export's head matches the on-chain anchor.
    1  FAILED   — with a precise reason (tx not found / head mismatch / count
                  mismatch / a named line whose chain hash is inconsistent).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Optional

# --------------------------------------------------------------------------- #
# PROTOCOL CONSTANTS — MUST MATCH THE EXPORT SIDE                              #
# (backend/src/api/routers/audit_compliance.py). This block is intentionally  #
# duplicated: the verifier depends on NONE of GrantLayer's code. If the export #
# fold ever changes, these constants must change in lockstep or every anchor   #
# becomes unverifiable. Keep them dead simple and independently auditable.     #
# --------------------------------------------------------------------------- #
GENESIS = "0" * 64  # hash-chain seed
ANCHOR_LABEL = "923350"  # Cardano metadata label (string key in Koios JSON)
KOIOS_BASES = {
    "preprod": "https://preprod.koios.rest/api/v1",
    "mainnet": "https://api.koios.rest/api/v1",
}


def entry_canonical(entry: dict[str, Any]) -> str:
    """Canonical bytes for one entry: drop chain-metadata (``_``-prefixed) keys,
    sort keys, compact separators, ASCII-escaped. Identical to the export side."""
    clean = {k: v for k, v in entry.items() if not k.startswith("_")}
    return json.dumps(
        {k: clean.get(k) for k in sorted(clean.keys())},
        sort_keys=True,
        ensure_ascii=True,
    )


def chain_hash(prev_hash: str, canonical: str) -> str:
    """SHA-256 over (prev_hash + canonical), NO separator. Left-fold primitive."""
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


# --------------------------------------------------------------------------- #
# NDJSON parsing                                                              #
# --------------------------------------------------------------------------- #
class VerifyError(Exception):
    """A verification failure carrying a human-precise reason."""


def load_ndjson(path: str) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    """Return (data_records, manifest_or_None). Manifest is the ``_type==manifest``
    footer line. Raises VerifyError on unreadable / malformed lines."""
    data: list[dict[str, Any]] = []
    manifest: Optional[dict[str, Any]] = None
    try:
        with open(path, encoding="utf-8") as fh:
            raw_lines = fh.readlines()
    except OSError as exc:
        raise VerifyError(f"cannot read NDJSON file: {exc}") from exc

    lineno = 0
    for raw in raw_lines:
        if not raw.strip():
            continue
        lineno += 1
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VerifyError(f"line {lineno}: invalid JSON ({exc})") from exc
        if isinstance(obj, dict) and obj.get("_type") == "manifest":
            manifest = obj
            continue
        if manifest is not None:
            # A data line AFTER the manifest footer means the file was appended to.
            raise VerifyError(f"line {lineno}: data line found after manifest footer")
        data.append(obj)
    return data, manifest


def recompute_head(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Left-fold the chain from GENESIS, cross-checking each line's own stored
    ``_chain_hash`` / ``_prev_hash`` so a broken line can be named precisely.

    Returns {"final_hash", "entry_count"}. Raises VerifyError naming the first
    inconsistent line (edited content / reordered / broken linkage)."""
    prev = GENESIS
    for idx, record in enumerate(data, start=1):
        # Linkage: this line's stored prev must equal the running head so far.
        stored_prev = record.get("_prev_hash")
        if stored_prev is not None and stored_prev != prev:
            raise VerifyError(
                f"line {idx}: _prev_hash linkage broken "
                f"(expected {prev[:16]}…, file says {str(stored_prev)[:16]}…) "
                f"— reordered, inserted, or a deletion upstream"
            )
        entry_hash = chain_hash(prev, entry_canonical(record))
        # Content: this line's stored chain hash must equal the recomputed one.
        stored_chain = record.get("_chain_hash")
        if stored_chain is not None and stored_chain != entry_hash:
            raise VerifyError(
                f"line {idx}: _chain_hash mismatch "
                f"(recomputed {entry_hash[:16]}…, file says {str(stored_chain)[:16]}…) "
                f"— this entry's content was altered after export"
            )
        prev = entry_hash
    return {"final_hash": prev, "entry_count": len(data)}


# --------------------------------------------------------------------------- #
# Koios chain access (keyless, stdlib-only)                                    #
# --------------------------------------------------------------------------- #
def _base_url(network: str) -> str:
    import os

    override = os.environ.get("KOIOS_BASE_URL")
    if override:
        return override.rstrip("/")
    return KOIOS_BASES[network]


def _http_json(url: str, body: Optional[bytes] = None) -> Any:
    headers = {"accept": "application/json"}
    if body is not None:
        headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        raise VerifyError(f"chain access failed ({url}): {exc}") from exc


def fetch_onchain_payload(network: str, tx_id: str) -> Optional[dict[str, Any]]:
    """Return the {h,s,t} anchor payload for tx_id, or None if not found."""
    url = f"{_base_url(network)}/tx_metadata"
    body = json.dumps({"_tx_hashes": [tx_id]}).encode()
    rows = _http_json(url, body)
    if not isinstance(rows, list) or not rows:
        return None
    meta = rows[0].get("metadata") or {}
    payload = meta.get(ANCHOR_LABEL)
    if not isinstance(payload, dict):
        return None
    return payload


def discover(network: str) -> list[dict[str, Any]]:
    """List transactions carrying the GrantLayer anchor label (discovery mode)."""
    url = f"{_base_url(network)}/tx_by_metalabel?_label={ANCHOR_LABEL}"
    rows = _http_json(url)
    return rows if isinstance(rows, list) else []


# --------------------------------------------------------------------------- #
# Verification                                                                #
# --------------------------------------------------------------------------- #
def verify(ndjson_path: str, tx_id: str, network: str, hmac_key: Optional[str]) -> None:
    """Run the full keyless verification. Raises VerifyError on any failure."""
    data, manifest = load_ndjson(ndjson_path)
    if not data:
        raise VerifyError("export contains no data lines")

    head = recompute_head(data)  # raises on a named broken line
    recomputed_head = head["final_hash"]
    data_count = head["entry_count"]

    payload = fetch_onchain_payload(network, tx_id)
    if payload is None:
        raise VerifyError(
            f"tx not found on chain (or carries no label {ANCHOR_LABEL}): {tx_id}"
        )

    onchain_h = payload.get("h")
    onchain_s = payload.get("s")
    onchain_t = payload.get("t")

    # Count: actual data lines == on-chain s (closes tail-truncation) and, if a
    # manifest footer is present, its declared count must also agree.
    if manifest is not None:
        manifest_count = manifest.get("_entry_count")
        if manifest_count != data_count:
            raise VerifyError(
                f"count mismatch: {data_count} data lines but manifest declares "
                f"{manifest_count} — lines added or removed after export"
            )
    if onchain_s != data_count:
        raise VerifyError(
            f"count mismatch: {data_count} data lines but chain attests "
            f"s={onchain_s} — the export was truncated or padded after anchoring"
        )

    # Head: the authoritative anti-rewrite check.
    if onchain_h != recomputed_head:
        raise VerifyError(
            f"head mismatch: recomputed {recomputed_head} but chain attests "
            f"h={onchain_h} — the export does not match what was anchored"
        )

    # Optional insider HMAC manifest check (needs GrantLayer's audit HMAC key).
    hmac_status = "not checked (no --hmac-key)"
    if hmac_key is not None:
        if manifest is None:
            raise VerifyError("--hmac-key given but export has no manifest footer")
        entry_hashes = [chain_hash_of_line(rec, data, i) for i, rec in enumerate(data)]
        expected = hmac.new(
            hmac_key.encode(), "\n".join(entry_hashes).encode(), hashlib.sha256
        ).hexdigest()
        stored = manifest.get("_hmac_signature")
        if not hmac.compare_digest(expected, str(stored)):
            raise VerifyError(
                "HMAC manifest signature mismatch — wrong key or manifest tampered"
            )
        hmac_status = "OK (manifest signature valid)"

    _report_ok(
        ndjson_path, tx_id, network, recomputed_head, data_count, onchain_t, hmac_status
    )


def chain_hash_of_line(record: dict[str, Any], data: list[dict[str, Any]], idx: int) -> str:
    """Recompute the entry hash for data[idx] independently (for the HMAC list)."""
    prev = GENESIS
    for rec in data[:idx]:
        prev = chain_hash(prev, entry_canonical(rec))
    return chain_hash(prev, entry_canonical(record))


def _report_ok(
    ndjson_path: str,
    tx_id: str,
    network: str,
    head: str,
    count: int,
    onchain_t: Any,
    hmac_status: str,
) -> None:
    print("=" * 68)
    print("  VERIFIED — export matches the on-chain anchor")
    print("=" * 68)
    print(f"  export file    : {ndjson_path}")
    print(f"  network        : cardano {network}")
    print(f"  tx id          : {tx_id}")
    print(f"  metadata label : {ANCHOR_LABEL}")
    print(f"  recomputed head: {head}")
    print(f"  entry count    : {count} (matches on-chain s)")
    print(f"  anchored at    : {onchain_t}")
    print(f"  HMAC manifest  : {hmac_status}")
    print("-" * 68)
    print("  PROVES : this export has not been rewritten since the anchor time.")
    print("  DOES NOT PROVE: that the entries were correct or complete when")
    print("                  written — anchoring freezes a record, it does not")
    print("                  vouch for its original truthfulness.")
    print("=" * 68)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify-anchor.py",
        description=(
            "Keyless offline proof that a GrantLayer audit export has not been "
            "rewritten since its on-chain anchor timestamp. Stdlib-only; imports "
            "no GrantLayer or Cardano code. PROVES post-anchor immutability; does "
            "NOT prove the entries were correct or complete when written."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ndjson", help="Path to the NDJSON audit export file")
    parser.add_argument("--tx-id", help="Cardano transaction id carrying the anchor")
    parser.add_argument(
        "--network",
        choices=sorted(KOIOS_BASES),
        default="preprod",
        help="Cardano network (default: preprod)",
    )
    parser.add_argument(
        "--hmac-key",
        default=None,
        help="OPTIONAL insider key to also verify the HMAC manifest signature",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="List candidate anchor transactions on the chain and exit",
    )
    args = parser.parse_args(argv)

    if args.discover:
        try:
            rows = discover(args.network)
        except VerifyError as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1
        print(f"Anchor transactions on cardano {args.network} (label {ANCHOR_LABEL}):")
        for row in rows:
            print(f"  tx {row.get('tx_hash')}  block {row.get('block_height')}")
        print(f"({len(rows)} found)")
        return 0

    if not args.ndjson or not args.tx_id:
        parser.error("--ndjson and --tx-id are required (unless --discover)")

    try:
        verify(args.ndjson, args.tx_id, args.network, args.hmac_key)
    except VerifyError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
