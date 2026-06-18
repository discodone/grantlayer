"""OIDC JWT bearer-token validation for GrantLayer.

Validates externally-issued JWTs from OIDC providers (Keycloak, Okta, Azure AD, etc.)
using the provider's JWKS endpoint.

Security guarantees:
- Signature validated via JWKS before any claim is trusted.
- Issuer and audience are exact-matched against configured values (allowlist).
- Expiration, not-before, and issued-at claims are validated with a bounded clock skew.
- Algorithm allowlist: only RS256 and ES256 accepted; none/HS256/other algorithms rejected.
- Unknown kid (key ID) → deny, not fallback.
- Provider outage (JWKS fetch failure) → fail-closed (deny access).
- JWKS cached with a TTL; expired cache triggers a blocking refresh.
- Token values and key material are never logged.

Configuration (environment variables):
  GRANTLAYER_ENABLE_OIDC          — "true" to enable OIDC JWT acceptance
  GRANTLAYER_OIDC_ISSUER          — exact issuer value (iss claim), e.g. https://auth.example.com/realms/myrealm
  GRANTLAYER_OIDC_AUDIENCE        — expected audience (aud claim), e.g. grantlayer-api
  GRANTLAYER_OIDC_JWKS_URL        — JWKS endpoint URL, e.g. https://auth.example.com/realms/myrealm/protocol/openid-connect/certs
  GRANTLAYER_OIDC_ALGORITHMS      — comma-separated allowed algorithms, default "RS256,ES256"
  GRANTLAYER_OIDC_TENANT_CLAIM    — OIDC claim that maps to GrantLayer tenant_id, default "tenant_id"
  GRANTLAYER_OIDC_ROLE_CLAIM      — OIDC claim that maps to GrantLayer role, default "role"
  GRANTLAYER_OIDC_CLOCK_SKEW_SECONDS — allowed clock skew in seconds, default 30
  GRANTLAYER_OIDC_JWKS_CACHE_TTL_SECONDS — JWKS cache TTL in seconds, default 300
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import jwt as _pyjwt

# ──────────────────────────────────────────────
# Exceptions (defined here to avoid circular imports with api/auth_jwt.py)
# ──────────────────────────────────────────────


class OIDCError(ValueError):
    """Base class for OIDC validation errors."""


class OIDCExpiredError(OIDCError):
    """Raised when the OIDC token exp claim is in the past."""


class OIDCInvalidError(OIDCError):
    """Raised when the OIDC token is invalid for any reason."""


# Re-export under the api/auth_jwt names so callers can use either.
# auth/oidc.py is below api/auth_jwt.py in the dependency tree;
# importing from there would create a cross-package cycle.
JWTExpiredError = OIDCExpiredError
JWTInvalidError = OIDCInvalidError


_ALLOWED_ALGORITHMS: frozenset[str] = frozenset({"RS256", "ES256"})
_DISALLOWED_ALGORITHMS: frozenset[str] = frozenset({"none", "HS256", "HS384", "HS512"})


# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class OIDCConfig:
    enabled: bool
    issuer: str
    audience: str
    jwks_url: str
    algorithms: list[str]
    tenant_claim: str
    role_claim: str
    clock_skew_seconds: int
    jwks_cache_ttl_seconds: int

    @classmethod
    def from_env(cls) -> "OIDCConfig":
        def _env_bool(name: str, default: bool = False) -> bool:
            v = os.environ.get(name, "").strip().lower()
            return v in {"1", "true", "yes", "on"} if v else default

        def _env_str(name: str, default: str = "") -> str:
            return os.environ.get(name, default).strip()

        def _env_int(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, str(default)))
            except (ValueError, TypeError):
                return default

        raw_algs = _env_str("GRANTLAYER_OIDC_ALGORITHMS", "RS256,ES256")
        algorithms = [a.strip() for a in raw_algs.split(",") if a.strip()]
        # Enforce the allowed algorithm set regardless of configuration.
        algorithms = [a for a in algorithms if a in _ALLOWED_ALGORITHMS]
        if not algorithms:
            algorithms = ["RS256", "ES256"]

        return cls(
            enabled=_env_bool("GRANTLAYER_ENABLE_OIDC"),
            issuer=_env_str("GRANTLAYER_OIDC_ISSUER"),
            audience=_env_str("GRANTLAYER_OIDC_AUDIENCE"),
            jwks_url=_env_str("GRANTLAYER_OIDC_JWKS_URL"),
            algorithms=algorithms,
            tenant_claim=_env_str("GRANTLAYER_OIDC_TENANT_CLAIM", "tenant_id"),
            role_claim=_env_str("GRANTLAYER_OIDC_ROLE_CLAIM", "role"),
            clock_skew_seconds=_env_int("GRANTLAYER_OIDC_CLOCK_SKEW_SECONDS", 30),
            jwks_cache_ttl_seconds=_env_int("GRANTLAYER_OIDC_JWKS_CACHE_TTL_SECONDS", 300),
        )

    def is_fully_configured(self) -> bool:
        """True when all required fields for OIDC validation are present."""
        return bool(self.enabled and self.issuer and self.audience and self.jwks_url)

    def startup_errors(self) -> list[str]:
        """Return configuration errors that block OIDC from starting safely."""
        if not self.enabled:
            return []
        errors: list[str] = []
        if not self.issuer:
            errors.append("ERROR: GRANTLAYER_OIDC_ISSUER is required when GRANTLAYER_ENABLE_OIDC=true.")
        if not self.audience:
            errors.append("ERROR: GRANTLAYER_OIDC_AUDIENCE is required when GRANTLAYER_ENABLE_OIDC=true.")
        if not self.jwks_url:
            errors.append("ERROR: GRANTLAYER_OIDC_JWKS_URL is required when GRANTLAYER_ENABLE_OIDC=true.")
        return errors


# ──────────────────────────────────────────────
# JWKS Cache
# ──────────────────────────────────────────────

@dataclass
class _JWKSCache:
    """Thread-safe JWKS cache with TTL refresh."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _keys: dict[str, Any] = field(default_factory=dict, repr=False)
    _fetched_at: float = field(default=0.0, repr=False)
    _ttl: float = field(default=300.0, repr=False)

    def get_key(self, kid: str | None, jwks_url: str, ttl_seconds: float) -> Any | None:
        """Return the public key for the given kid (or the sole key if kid is None).

        Fetches JWKS from jwks_url when the cache is empty or expired.
        Returns None if the kid is unknown — callers must deny access in that case.
        """
        self._ttl = ttl_seconds
        with self._lock:
            if time.monotonic() - self._fetched_at >= self._ttl or not self._keys:
                self._refresh(jwks_url)
            return self._pick(kid)

    def _refresh(self, jwks_url: str) -> None:
        """Fetch JWKS and update the cache. Raises OIDCInvalidError on any failure."""
        try:
            with urllib.request.urlopen(jwks_url, timeout=5) as resp:  # noqa: S310
                data = json.loads(resp.read().decode())
        except Exception as exc:
            raise OIDCInvalidError(
                f"OIDC provider unavailable: JWKS fetch failed. Access denied. ({type(exc).__name__})"
            ) from exc

        new_keys: dict[str, Any] = {}
        for jwk in data.get("keys", []):
            for alg_id in ("RS256", "ES256"):
                try:
                    from jwt.algorithms import get_default_algorithms
                    alg_obj = get_default_algorithms()[alg_id]
                    pub_key = alg_obj.from_jwk(jwk)
                    k = jwk.get("kid") or "_sole_"
                    new_keys[k] = pub_key
                    break
                except Exception:
                    continue

        if not new_keys:
            raise OIDCInvalidError("OIDC JWKS contains no usable public keys. Access denied.")

        self._keys = new_keys
        self._fetched_at = time.monotonic()

    def _pick(self, kid: str | None) -> Any | None:
        if not self._keys:
            return None
        if kid is None:
            # If there is exactly one key, use it; otherwise deny (ambiguous).
            if len(self._keys) == 1:
                return next(iter(self._keys.values()))
            return None
        return self._keys.get(kid)  # None → unknown kid

    def invalidate(self) -> None:
        with self._lock:
            self._keys = {}
            self._fetched_at = 0.0


# Module-level JWKS cache shared across requests.
_jwks_cache = _JWKSCache()


# ──────────────────────────────────────────────
# Token validation
# ──────────────────────────────────────────────

def _check_algorithm(token: str, allowed: list[str]) -> str:
    """Extract and validate the JWT alg header. Never trust alg=none."""
    try:
        header = _pyjwt.get_unverified_header(token)
    except Exception as exc:
        raise OIDCInvalidError("JWT header is malformed or unreadable.") from exc

    alg = header.get("alg", "")
    if not alg or alg.lower() == "none":
        raise OIDCInvalidError("JWT algorithm 'none' is not permitted.")
    if alg in _DISALLOWED_ALGORITHMS:
        raise OIDCInvalidError(
            f"JWT algorithm {alg!r} is not accepted by OIDC validator. "
            f"Allowed: {', '.join(sorted(allowed))}."
        )
    if alg not in allowed:
        raise OIDCInvalidError(
            f"JWT algorithm {alg!r} is not in the configured OIDC allowlist. "
            f"Allowed: {', '.join(sorted(allowed))}."
        )
    return alg


def _get_kid(token: str) -> str | None:
    try:
        header = _pyjwt.get_unverified_header(token)
    except Exception:
        return None
    return header.get("kid")


def validate_oidc_token(
    token: str,
    config: OIDCConfig,
    *,
    jwks_cache: "_JWKSCache | None" = None,
) -> dict[str, Any]:
    """Validate an OIDC JWT bearer token.

    Steps (in security-critical order):
    1. Algorithm allowlist check (rejects none/HS256/unknown algs).
    2. Public key lookup from JWKS (fail-closed on provider outage or unknown kid).
    3. Signature verification via PyJWT.
    4. Expiration, nbf, iat validation with bounded clock skew.
    5. Issuer exact-match.
    6. Audience exact-match.
    7. Tenant claim extraction (fail-closed if claim is missing or empty).

    Returns the verified payload dict on success.
    Raises OIDCExpiredError for expired tokens, OIDCInvalidError for all other failures.
    """
    if not config.is_fully_configured():
        raise OIDCInvalidError("OIDC is not fully configured.")

    alg = _check_algorithm(token, config.algorithms)
    kid = _get_kid(token)

    cache = jwks_cache or _jwks_cache
    pub_key = cache.get_key(kid, config.jwks_url, config.jwks_cache_ttl_seconds)
    if pub_key is None:
        raise OIDCInvalidError(
            f"OIDC JWT references an unknown or ambiguous key id (kid={kid!r}). Access denied."
        )

    now = int(time.time())
    leeway = config.clock_skew_seconds

    try:
        payload: dict[str, Any] = _pyjwt.decode(
            token,
            pub_key,
            algorithms=[alg],
            options={
                "verify_aud": False,  # We verify aud manually below for exact-match.
                "verify_iss": False,  # We verify iss manually below for exact-match.
            },
            leeway=leeway,
        )
    except _pyjwt.ExpiredSignatureError as exc:
        raise OIDCExpiredError("OIDC token has expired.") from exc
    except _pyjwt.InvalidTokenError as exc:
        raise OIDCInvalidError(f"OIDC token signature or claims are invalid: {exc}") from exc

    # Issuer exact-match (no wildcards, no prefix matching).
    token_iss = payload.get("iss", "")
    if token_iss != config.issuer:
        raise OIDCInvalidError(
            f"OIDC token issuer {token_iss!r} does not match configured issuer. Access denied."
        )

    # Audience exact-match.
    token_aud = payload.get("aud")
    if token_aud is None:
        raise OIDCInvalidError("OIDC token is missing the required 'aud' claim.")
    if isinstance(token_aud, list):
        if config.audience not in token_aud:
            raise OIDCInvalidError(
                "OIDC token audience does not include the required audience. Access denied."
            )
    elif token_aud != config.audience:
        raise OIDCInvalidError(
            f"OIDC token audience {token_aud!r} does not match configured audience. Access denied."
        )

    # Not-before (nbf) — reject tokens presented before they are valid.
    nbf = payload.get("nbf")
    if nbf is not None and now < (nbf - leeway):
        raise OIDCInvalidError("OIDC token is not yet valid (nbf in the future).")

    # Tenant claim — must be present and non-empty.
    tenant_id = payload.get(config.tenant_claim, "")
    if not tenant_id:
        raise OIDCInvalidError(
            f"OIDC token is missing the required tenant claim '{config.tenant_claim}'."
        )

    return payload


# ──────────────────────────────────────────────
# Claim mapping
# ──────────────────────────────────────────────

def map_oidc_claims_to_auth_payload(
    oidc_payload: dict[str, Any],
    config: OIDCConfig,
) -> dict[str, Any]:
    """Map verified OIDC claims to GrantLayer's internal auth payload format.

    The returned dict is compatible with the auth_payload consumed by
    resolve_workspace_context() and the rest of the auth stack.

    Claim mapping:
    - sub               → sub (principal identifier)
    - <tenant_claim>    → tenant_id
    - <role_claim>      → role
    - email             → email (optional)
    """
    tenant_id = oidc_payload.get(config.tenant_claim, "")
    role = oidc_payload.get(config.role_claim, "")
    return {
        "sub": oidc_payload.get("sub", ""),
        "tenant_id": tenant_id,
        "role": role,
        "email": oidc_payload.get("email", ""),
        "iss": oidc_payload.get("iss", ""),
        "oidc": True,
        "oidc_claims": {
            k: v for k, v in oidc_payload.items()
            if k not in {"sub", "iss", "aud", "exp", "iat", "nbf"}
        },
    }


# ──────────────────────────────────────────────
# Public helpers
# ──────────────────────────────────────────────

def oidc_is_enabled() -> bool:
    """True when OIDC is enabled and fully configured."""
    return OIDCConfig.from_env().is_fully_configured()


def validate_oidc_header(
    auth_header: str | None,
    *,
    config: "OIDCConfig | None" = None,
    jwks_cache: "_JWKSCache | None" = None,
) -> "tuple[bool | None, int | None, dict | None]":
    """Try to validate an OIDC Bearer JWT from an Authorization header.

    Return semantics mirror validate_jwt_header() so callers can use either:
    - (None, None, None)    — OIDC not configured; fall back to next auth method.
    - (True,  200, payload) — valid OIDC token; payload is the mapped auth dict.
    - (False, 4xx, error)   — OIDC configured but token is missing or invalid.
    """
    cfg = config or OIDCConfig.from_env()
    if not cfg.is_fully_configured():
        return None, None, None

    if not auth_header:
        return False, 401, {
            "error": "oidc_token_required",
            "errorCode": "oidc_token_required",
            "reason": "OIDC Bearer token is required.",
        }

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return False, 401, {
            "error": "oidc_token_invalid",
            "errorCode": "oidc_token_invalid",
            "reason": "Authorization header must use Bearer scheme with an OIDC JWT.",
        }

    try:
        oidc_payload = validate_oidc_token(token.strip(), cfg, jwks_cache=jwks_cache)
        auth_payload = map_oidc_claims_to_auth_payload(oidc_payload, cfg)
        return True, 200, auth_payload
    except OIDCExpiredError:
        return False, 401, {
            "error": "oidc_token_expired",
            "errorCode": "oidc_token_expired",
            "reason": "OIDC token has expired.",
        }
    except OIDCInvalidError as exc:
        return False, 401, {
            "error": "oidc_token_invalid",
            "errorCode": "oidc_token_invalid",
            "reason": str(exc),
        }


def get_jwks_cache() -> _JWKSCache:
    """Return the module-level JWKS cache (injectable for tests)."""
    return _jwks_cache
