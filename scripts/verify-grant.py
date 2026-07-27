#!/usr/bin/env python3
"""Keyless, offline GrantLayer grant-signature verifier — STDLIB ONLY.

Proves, without any GrantLayer or third-party code, that a grant record
(the JSON produced for the agent evidence bundle) carries a valid Ed25519
signature over its immutable fields, made by the holder of the private key
matching the bundled PUBLIC key. Verifies:

  1. payload hash  — SHA-256 over the canonical payload matches payloadHash;
  2. key identity  — the public key's fingerprint id
                     ("ed25519-" + first 16 hex of SHA-256(raw 32 bytes))
                     equals the grant's signingKeyId (and --expect-key-id
                     when given);
  3. signature     — pure-Python RFC 8032 Ed25519 verification of the hex
                     signature over the canonical payload bytes.

CANONICAL PAYLOAD — MUST STAY IN LOCKSTEP with the backend signer
(backend/src/core/crypto_signing.py::canonical_grant_payload): nine
``key=value`` lines in this exact order, plus ``constraints=<canonical JSON>``
appended ONLY when constraints is non-null, joined with "\n", UTF-8:

    action=..., createdBy=..., id=..., reason=..., resource=..., role=...,
    subjectId=..., validFrom=..., validUntil=...[, constraints=...]

This block is intentionally duplicated (the verify-anchor.py convention):
the verifier depends on NONE of GrantLayer's code.

PROVES: these exact grant fields were signed by that key.
DOES NOT PROVE: that the grant was ever active, is unrevoked, or was used —
pair with the anchored audit export (verify-anchor.py) for the usage side.

Exit codes: 0 verified, 1 verification failed, 2 usage/input error.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from typing import Optional

# --------------------------------------------------------------------------- #
# Canonical payload (lockstep with crypto_signing.canonical_grant_payload)     #
# --------------------------------------------------------------------------- #

_CANONICAL_FIELDS = [
    ("action", "action"),
    ("createdBy", "createdBy"),
    ("id", "id"),
    ("reason", "reason"),
    ("resource", "resource"),
    ("role", "role"),
    ("subjectId", "subjectId"),
    ("validFrom", "validFrom"),
    ("validUntil", "validUntil"),
]


def canonical_payload(grant: dict) -> bytes:
    lines = [f"{line}={grant[key]}" for line, key in _CANONICAL_FIELDS]
    if grant.get("constraints") is not None:
        lines.append(f"constraints={grant['constraints']}")
    return "\n".join(lines).encode("utf-8")


# --------------------------------------------------------------------------- #
# Ed25519 verification — RFC 8032 reference math, verification path only.      #
# Pure stdlib (hashlib + integers). Not constant-time: irrelevant for          #
# verifying a public signature with a public key.                              #
# --------------------------------------------------------------------------- #

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _recover_x(y: int, sign: int) -> Optional[int]:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_G_Y = 4 * pow(5, _P - 2, _P) % _P
_G_X = _recover_x(_G_Y, 0)
_G = (_G_X, _G_Y, 1, _G_X * _G_Y % _P)
_NEUTRAL = (0, 1, 1, 0)


def _point_add(p1, p2):
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = 2 * t1 * t2 * _D % _P
    d = 2 * z1 * z2 % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _point_mul(s: int, point):
    q = _NEUTRAL
    while s:
        if s & 1:
            q = _point_add(q, point)
        point = _point_add(point, point)
        s >>= 1
    return q


def _point_equal(p1, p2) -> bool:
    return ((p1[0] * p2[2] - p2[0] * p1[2]) % _P == 0
            and (p1[1] * p2[2] - p2[1] * p1[2]) % _P == 0)


def _point_decompress(raw: bytes):
    if len(raw) != 32:
        return None
    y = int.from_bytes(raw, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def ed25519_verify(public: bytes, message: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    a = _point_decompress(public)
    if a is None:
        return False
    r_bytes = signature[:32]
    r = _point_decompress(r_bytes)
    if r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    h = int.from_bytes(
        hashlib.sha512(r_bytes + public + message).digest(), "little"
    ) % _L
    return _point_equal(_point_mul(s, _G), _point_add(r, _point_mul(h, a)))


# --------------------------------------------------------------------------- #
# PEM SubjectPublicKeyInfo parsing (Ed25519 SPKI is a fixed 44-byte DER)        #
# --------------------------------------------------------------------------- #

_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")


def load_pubkey_raw(pem_path: str) -> bytes:
    with open(pem_path) as fh:
        body = "".join(
            line.strip() for line in fh
            if line.strip() and not line.startswith("-----")
        )
    der = base64.b64decode(body)
    if len(der) != 44 or not der.startswith(_SPKI_PREFIX):
        raise ValueError(
            "not an Ed25519 SubjectPublicKeyInfo PEM (expected the fixed "
            "44-byte DER with prefix 302a300506032b6570032100)"
        )
    return der[12:]


def key_id_of(raw_pub: bytes) -> str:
    """Fingerprint id, lockstep with crypto_signing.derive_key_id."""
    return f"ed25519-{hashlib.sha256(raw_pub).hexdigest()[:16]}"


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify-grant.py",
        description=(
            "Keyless offline proof that a GrantLayer grant record carries a "
            "valid Ed25519 signature over its immutable fields. Stdlib-only."
        ),
    )
    parser.add_argument("--grant", required=True,
                        help="Path to the grant JSON record")
    parser.add_argument("--pubkey", required=True,
                        help="Path to the signing PUBLIC key PEM")
    parser.add_argument("--expect-key-id", default=None,
                        help="Optionally pin the exact signing key id")
    args = parser.parse_args(argv)

    try:
        with open(args.grant) as fh:
            grant = json.load(fh)
        raw_pub = load_pubkey_raw(args.pubkey)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for field in ("signature", "payloadHash", "signingKeyId"):
        if not grant.get(field):
            print(f"FAILED: grant record has no {field}", file=sys.stderr)
            return 1

    payload = canonical_payload(grant)

    expected_hash = hashlib.sha256(payload).hexdigest()
    if grant["payloadHash"] != expected_hash:
        print(
            "FAILED: payload hash mismatch — the grant's immutable fields "
            f"were altered after signing (recomputed {expected_hash[:16]}…, "
            f"record says {str(grant['payloadHash'])[:16]}…)",
            file=sys.stderr,
        )
        return 1

    kid = key_id_of(raw_pub)
    if kid != grant["signingKeyId"]:
        print(
            f"FAILED: public key fingerprint {kid} does not match the "
            f"grant's signingKeyId {grant['signingKeyId']}",
            file=sys.stderr,
        )
        return 1
    if args.expect_key_id and kid != args.expect_key_id:
        print(
            f"FAILED: public key fingerprint {kid} does not match "
            f"--expect-key-id {args.expect_key_id}",
            file=sys.stderr,
        )
        return 1

    try:
        sig = bytes.fromhex(grant["signature"])
    except ValueError:
        print("FAILED: signature is not valid hex", file=sys.stderr)
        return 1

    if not ed25519_verify(raw_pub, payload, sig):
        print("FAILED: Ed25519 signature does not verify over the canonical "
              "payload", file=sys.stderr)
        return 1

    print("=" * 68)
    print("  VERIFIED — grant signature is valid")
    print("=" * 68)
    print(f"  grant id       : {grant.get('id')}")
    print(f"  subject        : {grant.get('subjectId')}")
    print(f"  action/resource: {grant.get('action')} / {grant.get('resource')}")
    print(f"  constraints    : {grant.get('constraints')}")
    print(f"  signing key id : {kid}")
    print(f"  payload sha256 : {expected_hash}")
    print("-" * 68)
    print("  PROVES : these exact fields were signed by that key.")
    print("  DOES NOT PROVE: the grant is unrevoked or was used — pair with")
    print("                  the anchored audit export (verify-anchor.py).")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
