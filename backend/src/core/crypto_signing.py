"""GrantLayer MVP — Ed25519 grant signing and verification (Sprint 2B).

Demo only. Do not use in production.
Private key is stored unencrypted at data/demo_ed25519_private_key.pem.
"""

import hashlib
import os
import stat
from typing import Tuple, cast

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

from . import config
from .models import Grant, GrantSignatureResult

_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../data")
_PRIVATE_KEY_PATH = os.path.join(_DATA_DIR, "demo_ed25519_private_key.pem")
_PUBLIC_KEY_PATH = os.path.join(_DATA_DIR, "demo_ed25519_public_key.pem")
_DEFAULT_KEYRING_DIR = os.path.join(_DATA_DIR, "keyring")

# Legacy alias: rows signed before fingerprint ids were stamped carry this id.
# It resolves via a keyring entry (demo pubkey locally; the production pubkey
# on the live host after the transition step). New signatures never stamp it.
DEMO_KEY_ID = "demo-ed25519-v1"
_LEGACY_ALIAS = DEMO_KEY_ID


class SigningKeyNotRegisteredError(RuntimeError):
    """Raised when signing is attempted with a key absent from the keyring.

    Fail-closed: never mint a grant whose key cannot later verify.
    """


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


def _is_encrypted_pem(key_data: bytes) -> bool:
    """Return True if the PEM data appears to be encrypted."""
    return b"ENCRYPTED PRIVATE KEY" in key_data


def _get_passphrase() -> bytes | None:
    """Return passphrase bytes if configured, otherwise None."""
    passphrase = config.GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE
    if passphrase:
        return passphrase.encode("utf-8")
    return None


def _check_plaintext_production(key_data: bytes) -> None:
    """Fail closed in production-like modes when loading plaintext files."""
    if _is_encrypted_pem(key_data):
        return
    if not config.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE:
        raise PermissionError(
            "Plaintext private key file loading is not allowed in this runtime mode. "
            "Use an encrypted key file, externalized key config, or set the explicit override."
        )


def _load_private_key_from_bytes(key_data: bytes, passphrase: bytes | None) -> Ed25519PrivateKey:
    """Load an Ed25519 private key from PEM bytes with safe error handling.

    Does not leak key material or passphrase values in exceptions.
    """
    try:
        return cast(Ed25519PrivateKey, load_pem_private_key(key_data, password=passphrase))
    except TypeError as exc:
        exc_str = str(exc).lower()
        if "not given but private key is encrypted" in exc_str:
            raise ValueError(
                "Encrypted private key requires a passphrase."
            ) from None
        if "password was given but private key is not encrypted" in exc_str:
            raise ValueError(
                "Passphrase provided for an unencrypted private key."
            ) from None
        raise
    except ValueError as exc:
        exc_str = str(exc).lower()
        if any(term in exc_str for term in ("password", "passphrase", "incorrect", "decrypt")):
            raise ValueError(
                "Invalid passphrase or encrypted private key format."
            ) from None
        raise


def _resolve_private_key_path() -> str:
    """Resolve the private key file path from config or default."""
    if config.GRANTLAYER_SIGNING_PRIVATE_KEY_FILE:
        return config.GRANTLAYER_SIGNING_PRIVATE_KEY_FILE
    return _PRIVATE_KEY_PATH


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
    """Load the signing private key from env, file, or default path.

    Priority:
      1. GRANTLAYER_SIGNING_PRIVATE_KEY (externalized config/env)
      2. GRANTLAYER_SIGNING_PRIVATE_KEY_FILE (explicit file path)
      3. Default _PRIVATE_KEY_PATH (backward compatibility)

    In production-like modes, plaintext file loading is rejected unless
    GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE is explicitly enabled.
    """
    # Priority 1: externalized key material
    if config.GRANTLAYER_SIGNING_PRIVATE_KEY:
        key_data = config.GRANTLAYER_SIGNING_PRIVATE_KEY.encode("utf-8")
        passphrase = _get_passphrase()
        return _load_private_key_from_bytes(key_data, passphrase)

    # Priority 2 & 3: file-based loading
    path = _resolve_private_key_path()
    _check_private_key_permissions(path)
    with open(path, "rb") as f:
        key_data = f.read()
    _check_plaintext_production(key_data)
    passphrase = _get_passphrase()
    return _load_private_key_from_bytes(key_data, passphrase)


def load_public_key() -> Ed25519PublicKey:
    with open(_PUBLIC_KEY_PATH, "rb") as f:
        return cast(Ed25519PublicKey, load_pem_public_key(f.read()))


# ── Keyring: key_id -> public key resolution ──────────────────────────────────

def _keyring_dir() -> str:
    """Configured keyring directory, or the default under the data dir."""
    return config.GRANTLAYER_SIGNING_KEYRING_DIR or _DEFAULT_KEYRING_DIR


def _keyring_path(key_id: str) -> str:
    return os.path.join(_keyring_dir(), f"{key_id}.pem")


def derive_key_id(public_key: Ed25519PublicKey) -> str:
    """Deterministic id for a public key: ed25519-<first 16 hex of SHA-256(raw)>.

    Self-describing and collision-safe across ceremonies; no config to drift.
    """
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return f"ed25519-{hashlib.sha256(raw).hexdigest()[:16]}"


def register_public_key(
    key_id: str, public_key: Ed25519PublicKey, *, overwrite: bool = False
) -> None:
    """Write a public key into the keyring under *key_id*.

    Refuse-to-clobber by default so a transition-provisioned alias (e.g. the
    production public key under the legacy id) is never silently replaced.
    """
    os.makedirs(_keyring_dir(), exist_ok=True)
    path = _keyring_path(key_id)
    if os.path.exists(path) and not overwrite:
        return
    with open(path, "wb") as f:
        f.write(public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))


def load_public_key_by_id(key_id: str) -> Ed25519PublicKey | None:
    """Resolve a key_id to its public key, or None if unknown/unreadable."""
    path = _keyring_path(key_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return cast(Ed25519PublicKey, load_pem_public_key(f.read()))
    except (ValueError, OSError):
        return None


def _ensure_keyring_baseline() -> None:
    """Guarantee the demo key is resolvable — under its fingerprint and the
    legacy alias — without clobbering a transition-provisioned alias.
    """
    ensure_demo_keypair()
    demo_pub = load_public_key()
    register_public_key(derive_key_id(demo_pub), demo_pub)
    register_public_key(_LEGACY_ALIAS, demo_pub)  # refuse-to-clobber


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
    """Sign the grant and stamp the fingerprint id of the signing key.

    Returns (signature_hex, payload_hash_hex, signing_key_id).
    Fail-closed: refuses to sign a key whose id is not registered in the
    keyring, so a grant is never minted that cannot later verify.
    """
    _ensure_keyring_baseline()
    private_key = load_private_key()
    key_id = derive_key_id(private_key.public_key())
    if load_public_key_by_id(key_id) is None:
        raise SigningKeyNotRegisteredError(
            f"signing key {key_id} is not registered in the keyring; "
            "register its public key before signing"
        )
    raw_payload = canonical_grant_payload(grant)
    signature_bytes = private_key.sign(raw_payload)
    hash_hex = hashlib.sha256(raw_payload).hexdigest()
    return signature_bytes.hex(), hash_hex, key_id


def verify_grant_signature(grant: Grant) -> GrantSignatureResult:
    """Verify the Ed25519 signature on a grant. Fail-closed.

    Returns: 'valid', 'missing', 'hash_mismatch', 'unknown_key', or 'invalid'.
    The key is resolved from the keyring by the grant's signing_key_id, so a
    grant signed with a rotated-but-retained key still verifies; an id with no
    keyring entry is 'unknown_key' (never silently accepted).
    """
    if not grant.signature or not grant.signing_key_id or not grant.payload_hash:
        return "missing"

    # Check payload hash first (cheap, detects field tampering)
    expected_hash = hashlib.sha256(canonical_grant_payload(grant)).hexdigest()
    if grant.payload_hash != expected_hash:
        return "hash_mismatch"

    _ensure_keyring_baseline()
    public_key = load_public_key_by_id(grant.signing_key_id)
    if public_key is None:
        return "unknown_key"

    # Verify Ed25519 signature
    try:
        raw_payload = canonical_grant_payload(grant)
        sig_bytes = bytes.fromhex(grant.signature)
        public_key.verify(sig_bytes, raw_payload)
        return "valid"
    except (InvalidSignature, ValueError):
        return "invalid"
