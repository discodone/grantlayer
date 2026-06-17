"""JWT authentication for the GrantLayer FastAPI layer.

Algorithm: RS256 (default) — recommended for production.
  Set GRANTLAYER_JWT_PRIVATE_KEY (base64-encoded PEM) for token signing.
  Set GRANTLAYER_JWT_PUBLIC_KEY  (base64-encoded PEM) for token verification.
  Generate keys:
    openssl genrsa -out private.pem 2048
    openssl rsa -in private.pem -pubout -out public.pem
    export GRANTLAYER_JWT_PRIVATE_KEY=$(base64 -w0 private.pem)
    export GRANTLAYER_JWT_PUBLIC_KEY=$(base64 -w0 public.pem)

Legacy HS256: set GRANTLAYER_JWT_ALGORITHM=HS256 and GRANTLAYER_JWT_SECRET.

Backward compat: when no key material is configured, validate_jwt_header()
returns (None, None, None) so callers fall back to legacy static-token auth.
"""
from __future__ import annotations

import base64
import os
import time
from typing import cast

import jwt as _pyjwt

# ──────────────────────────────────────────────
# Custom exceptions
# ──────────────────────────────────────────────

class JWTError(ValueError):
    """Base class for JWT errors."""


class JWTExpiredError(JWTError):
    """Raised when the JWT exp claim is in the past."""


class JWTInvalidError(JWTError):
    """Raised when the JWT is malformed or the signature is wrong."""


# ──────────────────────────────────────────────
# Internal helpers (kept for test-side token crafting)
# ──────────────────────────────────────────────

_DEFAULT_TTL_HOURS: int = 1


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = (4 - len(s) % 4) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def _sign_rs256(signing_input: str, private_key_pem: bytes) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    private_key = cast(RSAPrivateKey, private_key)
    sig_bytes = private_key.sign(
        signing_input.encode("utf-8"),
        asym_padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return _b64url_encode(sig_bytes)


# ──────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────

def _get_algorithm() -> str:
    explicit = os.environ.get("GRANTLAYER_JWT_ALGORITHM", "").upper()
    if explicit:
        return explicit
    # Backward compat: if only GRANTLAYER_JWT_SECRET is present with no RS256 keys,
    # default to HS256 so existing deployments with only a secret continue to work.
    if os.environ.get("GRANTLAYER_JWT_SECRET", "").strip():
        if not (os.environ.get("GRANTLAYER_JWT_PUBLIC_KEY", "").strip()
                or os.environ.get("GRANTLAYER_JWT_PRIVATE_KEY", "").strip()):
            return "HS256"
    return "RS256"


def _get_jwt_secret() -> str | None:
    return os.environ.get("GRANTLAYER_JWT_SECRET", "").strip() or None


def _get_private_key_pem() -> bytes | None:
    b64 = os.environ.get("GRANTLAYER_JWT_PRIVATE_KEY", "").strip()
    if not b64:
        return None
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def _get_public_key_pem() -> bytes | None:
    b64 = os.environ.get("GRANTLAYER_JWT_PUBLIC_KEY", "").strip()
    if not b64:
        return None
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def is_jwt_enabled() -> bool:
    """True when JWT auth is configured (can verify tokens)."""
    algo = _get_algorithm()
    if algo == "HS256":
        return bool(_get_jwt_secret())
    # RS256: enabled when public key (for verification) or private key (can derive public) is set
    return bool(_get_public_key_pem() or _get_private_key_pem())


# ──────────────────────────────────────────────
# HS256 encode / decode (backward compat)
# ──────────────────────────────────────────────

def encode_token(
    payload: dict,
    secret: str,
    ttl_hours: int = _DEFAULT_TTL_HOURS,
) -> str:
    """Return a signed HS256 JWT string."""
    if not secret:
        raise ValueError("JWT secret must not be empty.")
    now = int(time.time())
    full_payload = {**payload, "iat": now, "exp": now + ttl_hours * 3600}
    return _pyjwt.encode(full_payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict:
    """Decode and verify an HS256 JWT."""
    if not secret:
        raise JWTInvalidError("JWT secret must not be empty.")
    try:
        # Algorithm confusion guard: reject tokens claiming a different alg
        header = _pyjwt.get_unverified_header(token)
        if header.get("alg") != "HS256":
            raise JWTInvalidError(
                f"Unsupported JWT algorithm: {header.get('alg')!r}. Expected HS256."
            )
        # verify_aud=False: aud is validated manually in validate_jwt_header()
        # to preserve backward compat with tokens that predate iss/aud injection.
        return _pyjwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except JWTInvalidError:
        raise
    except _pyjwt.ExpiredSignatureError as exc:
        raise JWTExpiredError("JWT token has expired.") from exc
    except _pyjwt.InvalidTokenError as exc:
        raise JWTInvalidError(str(exc)) from exc


# ──────────────────────────────────────────────
# RS256 encode / decode
# ──────────────────────────────────────────────

def encode_token_rs256(
    payload: dict,
    private_key_pem: bytes,
    ttl_hours: int = _DEFAULT_TTL_HOURS,
) -> str:
    """Return a signed RS256 JWT string."""
    if not private_key_pem:
        raise ValueError("RS256 private key PEM must not be empty.")
    now = int(time.time())
    full_payload = {**payload, "iat": now, "exp": now + ttl_hours * 3600}
    return _pyjwt.encode(full_payload, private_key_pem, algorithm="RS256")


def decode_token_rs256(token: str, public_key_pem: bytes) -> dict:
    """Decode and verify an RS256 JWT."""
    if not public_key_pem:
        raise JWTInvalidError("RS256 public key PEM must not be empty.")
    try:
        # Algorithm confusion guard: reject tokens claiming a different alg
        header = _pyjwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise JWTInvalidError(
                f"Unsupported JWT algorithm: {header.get('alg')!r}. Expected RS256."
            )
        # verify_aud=False: aud is validated manually in validate_jwt_header()
        # to preserve backward compat with tokens that predate iss/aud injection.
        return _pyjwt.decode(token, public_key_pem, algorithms=["RS256"], options={"verify_aud": False})
    except JWTInvalidError:
        raise
    except _pyjwt.ExpiredSignatureError as exc:
        raise JWTExpiredError("JWT token has expired.") from exc
    except _pyjwt.InvalidTokenError as exc:
        raise JWTInvalidError(str(exc)) from exc


# ──────────────────────────────────────────────
# iss/aud claim helpers
# ──────────────────────────────────────────────

def _check_iss_aud(payload: dict) -> None:
    """Validate iss and aud claims against server configuration.

    Non-strict mode (GRANTLAYER_JWT_STRICT_CLAIMS=false, default):
      Only validates claims that are PRESENT in the token — backward compat
      for tokens issued before iss/aud injection was introduced.

    Strict mode (GRANTLAYER_JWT_STRICT_CLAIMS=true):
      Rejects tokens MISSING iss or aud when the server has those claims
      configured (JWT_ISSUER / JWT_AUDIENCE non-empty).  Use this to prevent
      cross-environment token replay via claim omission.
    """
    from ..core import config as _config  # deferred to avoid circular import
    expected_iss = _config.JWT_ISSUER
    expected_aud = _config.JWT_AUDIENCE
    strict = _config.JWT_STRICT_CLAIMS

    if expected_iss:
        if "iss" not in payload:
            if strict:
                raise JWTInvalidError("Token is missing required iss claim.")
        elif payload["iss"] != expected_iss:
            raise JWTInvalidError("Invalid issuer.")

    if expected_aud:
        if "aud" not in payload:
            if strict:
                raise JWTInvalidError("Token is missing required aud claim.")
        else:
            aud = payload["aud"]
            if isinstance(aud, list):
                if expected_aud not in aud:
                    raise JWTInvalidError("Invalid audience.")
            elif aud != expected_aud:
                raise JWTInvalidError("Invalid audience.")


# ──────────────────────────────────────────────
# Env-driven signing (used by /auth/token router)
# ──────────────────────────────────────────────

def sign_token(payload: dict, ttl_hours: int = _DEFAULT_TTL_HOURS) -> str:
    """Issue a JWT using the algorithm and key material from environment variables."""
    from ..core import config as _config  # deferred to avoid circular import
    claims = dict(payload)
    if _config.JWT_ISSUER:
        claims.setdefault("iss", _config.JWT_ISSUER)
    if _config.JWT_AUDIENCE:
        claims.setdefault("aud", _config.JWT_AUDIENCE)

    algo = _get_algorithm()
    if algo == "HS256":
        secret = _get_jwt_secret()
        if not secret:
            raise ValueError(
                "GRANTLAYER_JWT_SECRET is not set. "
                "Export it before generating a token:\n"
                "  export GRANTLAYER_JWT_SECRET=$(python3 -c \"import secrets; print(secrets.token_hex(32))\")"
            )
        return encode_token(claims, secret, ttl_hours)
    else:  # RS256
        pem = _get_private_key_pem()
        if not pem:
            raise ValueError(
                "GRANTLAYER_JWT_PRIVATE_KEY is not set. "
                "Generate a key pair and export it:\n"
                "  openssl genrsa -out private.pem 2048\n"
                "  export GRANTLAYER_JWT_PRIVATE_KEY=$(base64 -w0 private.pem)"
            )
        return encode_token_rs256(claims, pem, ttl_hours)


# ──────────────────────────────────────────────
# Dev/demo token generation
# ──────────────────────────────────────────────

def create_dev_token(
    secret: str | None = None,
    ttl_hours: int = _DEFAULT_TTL_HOURS,
    tenant_id: str = "demo",
    sub: str = "dev-operator",
    role: str = "owner",
) -> str:
    """Generate a dev/demo HS256 JWT. Not for production use.

    Reads GRANTLAYER_JWT_SECRET from the environment when secret is None.
    """
    effective_secret = secret or _get_jwt_secret()
    if not effective_secret:
        raise ValueError(
            "GRANTLAYER_JWT_SECRET is not set. "
            "Export it before generating a token:\n"
            "  export GRANTLAYER_JWT_SECRET=$(python3 -c \"import secrets; print(secrets.token_hex(32))\")"
        )
    from ..core import config as _config  # deferred to avoid circular import
    claims: dict = {"sub": sub, "tenant_id": tenant_id, "role": role}
    if _config.JWT_ISSUER:
        claims["iss"] = _config.JWT_ISSUER
    if _config.JWT_AUDIENCE:
        claims["aud"] = _config.JWT_AUDIENCE
    return encode_token(claims, effective_secret, ttl_hours)


# ──────────────────────────────────────────────
# FastAPI / deps integration
# ──────────────────────────────────────────────

def validate_jwt_header(
    auth_header: str | None,
) -> tuple[bool | None, int | None, dict | None]:
    """Try to validate a Bearer JWT from an Authorization header.

    Returns a 3-tuple (ok, http_status, payload_or_error):
    - (None, None, None)   — JWT auth not configured; fall back to legacy auth.
    - (True,  200, payload) — valid JWT; payload contains the decoded claims.
    - (False, 4xx, error)  — JWT configured but token is missing or invalid.

    The algorithm is determined by GRANTLAYER_JWT_ALGORITHM (default RS256).
    The JWT header's alg claim is validated against the configured algorithm
    to prevent algorithm-confusion attacks.
    """
    # Read all key material once to avoid TOCTOU race between is_jwt_enabled()
    # and the per-key reads inside the validation logic.
    algo = _get_algorithm()
    secret = _get_jwt_secret()
    pub_pem = _get_public_key_pem()
    priv_pem = _get_private_key_pem()

    # Determine whether JWT auth is actually configured using local copies.
    if algo == "HS256":
        if not secret:
            return None, None, None
    else:
        if not (pub_pem or priv_pem):
            return None, None, None

    if not auth_header:
        return False, 401, {
            "error": "jwt_required",
            "errorCode": "jwt_required",
            "reason": "JWT Bearer token is required.",
        }

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return False, 401, {
            "error": "jwt_invalid",
            "errorCode": "jwt_invalid",
            "reason": "Authorization header must use Bearer scheme with a JWT.",
        }

    try:
        if algo == "HS256":
            payload = decode_token(token.strip(), secret)  # type: ignore[arg-type]
        else:  # RS256
            if not pub_pem:
                # Only private key is available — derive public key for verification.
                # priv_pem is guaranteed non-None here (checked above).
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
                assert priv_pem is not None  # guaranteed by the check above
                priv_key = serialization.load_pem_private_key(priv_pem, password=None)
                pub_pem = priv_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
            payload = decode_token_rs256(token.strip(), pub_pem)

        _check_iss_aud(payload)

        if "tenant_id" not in payload:
            return False, 400, {
                "error": "jwt_missing_tenant",
                "errorCode": "jwt_missing_tenant",
                "reason": "JWT is missing required tenant_id claim.",
            }
        return True, 200, payload
    except JWTExpiredError:
        return False, 401, {
            "error": "jwt_expired",
            "errorCode": "jwt_expired",
            "reason": "JWT token has expired.",
        }
    except JWTInvalidError:
        return False, 401, {
            "error": "jwt_invalid",
            "errorCode": "jwt_invalid",
            "reason": "Invalid JWT token.",
        }
