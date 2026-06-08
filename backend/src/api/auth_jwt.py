"""GL-230: JWT authentication for the GrantLayer FastAPI layer.

Algorithm: HS256 (default) — suitable for single-server dev/demo.
Production option: use RS256 with GRANTLAYER_JWT_ALGORITHM=RS256 and supply
  GRANTLAYER_JWT_PUBLIC_KEY / GRANTLAYER_JWT_PRIVATE_KEY (PEM strings).
  RS256 is not implemented here; switch to PyJWT when upgrading to RS256.

Backward compat: when GRANTLAYER_JWT_SECRET is not set, validate_jwt_header()
returns (None, None, None) so the caller falls back to the existing
static-token / operator-model auth path transparently.

Implemented with stdlib only (hmac + hashlib + base64 + json).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time


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
# Internal helpers
# ──────────────────────────────────────────────

_DEFAULT_TTL_HOURS: int = 1
_ALGORITHM: str = "HS256"
_SUPPORTED_ALGORITHMS: frozenset = frozenset({"HS256"})


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = (4 - len(s) % 4) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def _sign(signing_input: str, secret: str) -> str:
    raw = hmac.digest(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    )
    return _b64url_encode(raw)


# ──────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────

def _get_jwt_secret() -> str | None:
    return os.environ.get("GRANTLAYER_JWT_SECRET", "").strip() or None


def is_jwt_enabled() -> bool:
    """True when GRANTLAYER_JWT_SECRET is set in the environment."""
    return bool(_get_jwt_secret())


# ──────────────────────────────────────────────
# Encode / decode
# ──────────────────────────────────────────────

def encode_token(
    payload: dict,
    secret: str,
    ttl_hours: int = _DEFAULT_TTL_HOURS,
) -> str:
    """Return a signed HS256 JWT string.

    Adds iat and exp claims automatically.  Caller-supplied iat/exp are
    overwritten so TTL is always authoritative.
    """
    if not secret:
        raise ValueError("JWT secret must not be empty.")

    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now = int(time.time())
    full_payload = {**payload, "iat": now, "exp": now + ttl_hours * 3600}
    body = _b64url_encode(json.dumps(full_payload, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}"
    sig = _sign(signing_input, secret)
    return f"{signing_input}.{sig}"


def decode_token(token: str, secret: str) -> dict:
    """Decode and verify a HS256 JWT.

    Raises:
        JWTExpiredError: if exp claim is in the past.
        JWTInvalidError: if the token is malformed or the signature is wrong.
    """
    if not secret:
        raise JWTInvalidError("JWT secret must not be empty.")

    parts = token.split(".")
    if len(parts) != 3:
        raise JWTInvalidError("JWT must have exactly three dot-separated parts.")

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"

    expected_sig = _sign(signing_input, secret)
    if not hmac.compare_digest(sig_b64, expected_sig):
        raise JWTInvalidError("JWT signature verification failed.")

    try:
        header_data = json.loads(_b64url_decode(header_b64))
    except Exception as exc:
        raise JWTInvalidError("JWT header is not valid JSON.") from exc

    alg = header_data.get("alg", "")
    if alg not in _SUPPORTED_ALGORITHMS:
        raise JWTInvalidError(f"Unsupported JWT algorithm: {alg!r}. Only HS256 is supported.")

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise JWTInvalidError("JWT payload is not valid JSON.") from exc

    exp = payload.get("exp")
    if exp is not None and int(time.time()) > int(exp):
        raise JWTExpiredError("JWT token has expired.")

    return payload


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
    """Generate a dev/demo JWT. Not for production use.

    Reads GRANTLAYER_JWT_SECRET from the environment when secret is None.
    """
    effective_secret = secret or _get_jwt_secret()
    if not effective_secret:
        raise ValueError(
            "GRANTLAYER_JWT_SECRET is not set. "
            "Export it before generating a token:\n"
            "  export GRANTLAYER_JWT_SECRET=$(python3 -c \"import secrets; print(secrets.token_hex(32))\")"
        )
    return encode_token(
        {"sub": sub, "tenant_id": tenant_id, "role": role},
        effective_secret,
        ttl_hours,
    )


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
    """
    if not is_jwt_enabled():
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

    secret = _get_jwt_secret()
    try:
        payload = decode_token(token.strip(), secret)
        if "tenant_id" not in payload:
            payload["tenant_id"] = "demo"
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
