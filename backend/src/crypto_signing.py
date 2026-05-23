"""GrantLayer MVP — Ed25519 grant signing and verification (Sprint 2B).

Demo only. Do not use in production.
Private key is stored unencrypted at data/demo_ed25519_private_key.pem.
"""

import hashlib
import os
import stat
from typing import Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)

from .models import Grant, GrantSignatureResult

_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../data")
_PRIVATE_KEY_PATH = os.path.join(_DATA_DIR, "demo_ed25519_private_key.pem")
_PUBLIC_KEY_PATH = os.path.join(_DATA_DIR, "demo_ed25519_public_key.pem")

DEMO_KEY_ID = "demo-ed25519-v1"


def _check_private_key_permissions(path: str) -> None:
    """Fail closed if the private key file has unsafe permissions.

    Rejects group-readable, group-writable, world-readable, and world-writable.
    Safe modes are owner-only (e.g. 0o600).
    """
    file_stat = os.stat(path)
    mode = stat.S_IMODE(file_stat.st_mode)
    if mode & 0o077:
        raise PermissionError(
            "Private key file has unsafe permissions. "
            "Expected owner-only access (mode 0o600 or stricter)."
        )


def ensure_demo_keypair() -> None:
    """Generate Ed25519 keypair if not present at data/ paths. Idempotent."""
    os.makedirs(os.path.abspath(_DATA_DIR), exist_ok=True)
    if os.path.exists(_PRIVATE_KEY_PATH) and os.path.exists(_PUBLIC_KEY_PATH):
        # Harden pre-existing private key files created before permission enforcement
        file_stat = os.stat(_PRIVATE_KEY_PATH)
        mode = stat.S_IMODE(file_stat.st_mode)
        if mode != 0o600:
            os.chmod(_PRIVATE_KEY_PATH, 0o600)
        return
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    with open(_PRIVATE_KEY_PATH, "wb") as f:
        f.write(private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    os.chmod(_PRIVATE_KEY_PATH, 0o600)
    with open(_PUBLIC_KEY_PATH, "wb") as f:
        f.write(public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))


def load_private_key() -> Ed25519PrivateKey:
    _check_private_key_permissions(_PRIVATE_KEY_PATH)
    with open(_PRIVATE_KEY_PATH, "rb") as f:
        return load_pem_private_key(f.read(), password=None)


def load_public_key() -> Ed25519PublicKey:
    with open(_PUBLIC_KEY_PATH, "rb") as f:
        return load_pem_public_key(f.read())


def canonical_grant_payload(grant: Grant) -> bytes:
    """Deterministic UTF-8 bytes over the 9 immutable grant fields (alphabetically sorted).

    Excludes: revocation fields, signature, signing_key_id, payload_hash.
    This allows revocation without invalidating the original signature.
    """
    lines = [
        f"action={grant.action}",
        f"createdBy={grant.created_by}",
        f"id={grant.id}",
        f"reason={grant.reason}",
        f"resource={grant.resource}",
        f"role={grant.role}",
        f"subjectId={grant.subject_id}",
        f"validFrom={grant.valid_from}",
        f"validUntil={grant.valid_until}",
    ]
    return "\n".join(lines).encode("utf-8")


def payload_hash(grant: Grant) -> str:
    """Hex-encoded SHA-256 of the canonical payload."""
    return hashlib.sha256(canonical_grant_payload(grant)).hexdigest()


def sign_grant(grant: Grant) -> Tuple[str, str, str]:
    """Sign the grant with the demo private key.

    Returns (signature_hex, payload_hash_hex, signing_key_id).
    Calls ensure_demo_keypair() to guarantee key existence.
    """
    ensure_demo_keypair()
    private_key = load_private_key()
    raw_payload = canonical_grant_payload(grant)
    signature_bytes = private_key.sign(raw_payload)
    hash_hex = hashlib.sha256(raw_payload).hexdigest()
    return signature_bytes.hex(), hash_hex, DEMO_KEY_ID


def verify_grant_signature(grant: Grant) -> GrantSignatureResult:
    """Verify the Ed25519 signature on a grant. Fail-closed.

    Returns: 'valid', 'missing', 'invalid', or 'hash_mismatch'.
    """
    if not grant.signature or not grant.signing_key_id or not grant.payload_hash:
        return "missing"

    # Check payload hash first (cheap, detects field tampering)
    expected_hash = hashlib.sha256(canonical_grant_payload(grant)).hexdigest()
    if grant.payload_hash != expected_hash:
        return "hash_mismatch"

    # Verify Ed25519 signature
    try:
        public_key = load_public_key()
        raw_payload = canonical_grant_payload(grant)
        sig_bytes = bytes.fromhex(grant.signature)
        public_key.verify(sig_bytes, raw_payload)
        return "valid"
    except (InvalidSignature, ValueError):
        return "invalid"
