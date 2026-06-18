"""GrantLayer MVP — Centralized configuration.

Reads environment variables with safe defaults for local development.
Product mode is opt-in via explicit flags; unsafe demo defaults emit startup warnings.

Security rules:
- No secrets are logged.
- No secrets are written to disk.
- Presence of a token is reported; its value is NOT.
- Placeholder/demo/weak tokens are rejected in production-like modes.
"""

from __future__ import annotations

import os

from ..auth.identity_access import external_identity_startup_errors
from .runtime_config import PRODUCTION_LIKE_MODES, get_runtime_mode
from .secret_sources import SecretResolver

# ──────────────────────────────────────────────────────────────
# Placeholder/weak token detection constants
# ──────────────────────────────────────────────────────────────

_UNSAFE_PLACEHOLDER_TOKENS: frozenset = frozenset({
    "admin", "token", "secret", "demo", "changeme", "password", "test",
    "placeholder", "default", "example", "sample", "foobar", "foo", "bar",
    "unsafe", "insecure", "dev", "local", "replace-me", "replace_me",
    "your-secret-here", "your_secret_here", "my-secret", "my_secret",
    "supersecret", "super-secret", "super_secret", "secretkey", "secret-key",
    "secret_key", "admintoken", "admin-token", "admin_token", "testtoken",
    "test-token", "test_token", "demotoken", "demo-token", "demo_token",
    "bootstrap", "bootstrap-token", "bootstrap_token",
})

_PROD_MIN_ADMIN_TOKEN_LENGTH: int = 16

_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse an environment variable as a boolean (case-insensitive)."""
    value = os.environ.get(name, "").strip().lower()
    return value in ("1", "true", "yes", "on") if value else default


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (ValueError, TypeError):
        return default


def _env_log_level(name: str, default: str = "INFO") -> str:
    value = os.environ.get(name, "").strip().upper()
    return value if value in _LOG_LEVELS else default


def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.environ.get(name, "")
    if not value:
        return default if default is not None else []
    return [item.strip() for item in value.split(",") if item.strip()]


# ──────────────────────────────────────────────────────────────
# Runtime Mode
# ──────────────────────────────────────────────────────────────

RUNTIME_MODE: str = get_runtime_mode()

# ──────────────────────────────────────────────────────────────
# Secret Resolver — Vault > Docker Secrets file > env var
# ──────────────────────────────────────────────────────────────

_SECRET_RESOLVER: SecretResolver = SecretResolver.from_env()


def _secret(name: str, default: str = "") -> str:
    """Resolve *name* via the priority chain; return *default* when absent."""
    value = _SECRET_RESOLVER.resolve(name)
    return value if value is not None else default


# ──────────────────────────────────────────────────────────────
# Product / Demo Mode Flags
# ──────────────────────────────────────────────────────────────

# If True, all protected endpoints require the admin token.
# If False, they fall back to optional/legacy behavior.
# Default is secure (True) in production-like modes; opt-in (False) for local/test.
REQUIRE_ADMIN_TOKEN: bool = _env_bool(
    "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
    default=RUNTIME_MODE not in ("local", "test"),
)

# If True, POST /demo-action MUST include a valid challengeId.
# If False, legacy mode without challenge remains allowed.
REQUIRE_CHALLENGE: bool = _env_bool("GRANTLAYER_REQUIRE_CHALLENGE", default=False)

# If True, the demo-only tamper endpoint is available.
# Default is False — product mode disables demo endpoints.
ENABLE_DEMO_ENDPOINTS: bool = _env_bool("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", default=False)

# Explicit acknowledgement required when demo endpoints are enabled on a
# non-local host binding.  Must be exactly "true" (case-insensitive).
GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS: bool = _env_bool(
    "GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", default=False
)

# ──────────────────────────────────────────────────────────────
# Runtime Settings
# ──────────────────────────────────────────────────────────────

GRANTLAYER_HOST: str = _env_str("GRANTLAYER_HOST", "127.0.0.1")
GRANTLAYER_PORT: int = _env_int("GRANTLAYER_PORT", 8765)
GRANTLAYER_DB: str = _env_str("GRANTLAYER_DB", "")
GRANTLAYER_DATABASE_URL: str = _env_str("GRANTLAYER_DATABASE_URL", "")

# ──────────────────────────────────────────────────────────────
# Logging & Health
# ──────────────────────────────────────────────────────────────

GRANTLAYER_LOG_LEVEL: str = _env_log_level("GRANTLAYER_LOG_LEVEL", default="INFO")
GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS: int = _env_int("GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS", 2000)

# ──────────────────────────────────────────────────────────────
# Admin Token (Demo / Sprint-2C only)
# ──────────────────────────────────────────────────────────────

GRANTLAYER_ADMIN_TOKEN: str = _secret("GRANTLAYER_ADMIN_TOKEN")

# ──────────────────────────────────────────────────────────────
# Operator Model
# ──────────────────────────────────────────────────────────────

ENABLE_OPERATOR_MODEL: bool = _env_bool("GRANTLAYER_ENABLE_OPERATOR_MODEL", default=True)

GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN: str = _secret("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
GRANTLAYER_BOOTSTRAP_OPERATOR_ID: str = _env_str("GRANTLAYER_BOOTSTRAP_OPERATOR_ID", "bootstrap-admin")
GRANTLAYER_BOOTSTRAP_OPERATOR_NAME: str = _env_str("GRANTLAYER_BOOTSTRAP_OPERATOR_NAME", "Bootstrap Admin")
GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE: str = _env_str("GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE", "owner")

# ──────────────────────────────────────────────────────────────
# CORS Origin Allowlist
# ──────────────────────────────────────────────────────────────

# Comma-separated list of allowed origins for CORS.
# Empty list disables CORS entirely (no Access-Control-Allow-Origin header).
# Exact origin matching only; no wildcards, no subdomains, no reflection.
CORS_ALLOWED_ORIGINS: list[str] = _env_list(
    "GRANTLAYER_CORS_ALLOWED_ORIGINS",
    default=["http://127.0.0.1:8765", "http://localhost:8765"],
)

# ──────────────────────────────────────────────────────────────
# Private Key Configuration
# ──────────────────────────────────────────────────────────────

# Externalized private key material (PEM string). Takes precedence over file.
GRANTLAYER_SIGNING_PRIVATE_KEY: str = _secret("GRANTLAYER_SIGNING_PRIVATE_KEY")

# Explicit private key file path. Falls back to default data/ path if unset.
GRANTLAYER_SIGNING_PRIVATE_KEY_FILE: str = _env_str("GRANTLAYER_SIGNING_PRIVATE_KEY_FILE", "")

# Passphrase for encrypted private key files.
GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE: str = _env_str("GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE", "")

# Allow plaintext private key file loading. Default is True in local/test for
# backward compatibility; False in production-like modes.
GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE: bool = _env_bool(
    "GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE",
    default=RUNTIME_MODE in ("local", "test"),
)

# ──────────────────────────────────────────────────────────────
# JWT Claims
# ──────────────────────────────────────────────────────────────

# Issuer claim added to every self-signed JWT.  When set, validate_jwt_header()
# rejects tokens whose iss claim differs.  Old tokens without iss are still
# accepted (backward compat) unless JWT_STRICT_CLAIMS is enabled.
# Set to "" to disable iss injection and validation.
JWT_ISSUER: str = _env_str("GRANTLAYER_JWT_ISSUER", "grantlayer")

# Audience claim added to every self-signed JWT.  Same optional-validation rules
# as JWT_ISSUER apply.  Set to "" to disable.
JWT_AUDIENCE: str = _env_str("GRANTLAYER_JWT_AUDIENCE", "grantlayer-api")

# When true: tokens MISSING iss/aud claims are rejected (401) when the server
# has JWT_ISSUER / JWT_AUDIENCE configured.  Default false preserves backward
# compat with tokens issued before iss/aud injection was introduced.
# Enable in new deployments to close the cross-environment token replay window.
JWT_STRICT_CLAIMS: bool = _env_bool("GRANTLAYER_JWT_STRICT_CLAIMS", default=False)

# ──────────────────────────────────────────────────────────────
# OIDC / External Identity Provider
# ──────────────────────────────────────────────────────────────

GRANTLAYER_ENABLE_OIDC: bool = _env_bool("GRANTLAYER_ENABLE_OIDC", default=False)
GRANTLAYER_OIDC_ISSUER: str = _env_str("GRANTLAYER_OIDC_ISSUER", "")
GRANTLAYER_OIDC_AUDIENCE: str = _env_str("GRANTLAYER_OIDC_AUDIENCE", "")
GRANTLAYER_OIDC_JWKS_URL: str = _env_str("GRANTLAYER_OIDC_JWKS_URL", "")
GRANTLAYER_OIDC_ALGORITHMS: str = _env_str("GRANTLAYER_OIDC_ALGORITHMS", "RS256,ES256")
GRANTLAYER_OIDC_TENANT_CLAIM: str = _env_str("GRANTLAYER_OIDC_TENANT_CLAIM", "tenant_id")
GRANTLAYER_OIDC_ROLE_CLAIM: str = _env_str("GRANTLAYER_OIDC_ROLE_CLAIM", "role")
GRANTLAYER_OIDC_CLOCK_SKEW_SECONDS: int = _env_int("GRANTLAYER_OIDC_CLOCK_SKEW_SECONDS", 30)
GRANTLAYER_OIDC_JWKS_CACHE_TTL_SECONDS: int = _env_int("GRANTLAYER_OIDC_JWKS_CACHE_TTL_SECONDS", 300)

# ──────────────────────────────────────────────────────────────
# Rate Limiting
# ──────────────────────────────────────────────────────────────

GRANTLAYER_RATE_LIMIT_AUTH: int = max(1, _env_int("GRANTLAYER_RATE_LIMIT_AUTH", 10))
GRANTLAYER_RATE_LIMIT_API: int = max(1, _env_int("GRANTLAYER_RATE_LIMIT_API", 120))

# Redis URL for the shared rate-limiter backend (optional).
# When unset the in-process sliding-window fallback is used.
_redis_url_raw: str = _env_str("GRANTLAYER_REDIS_URL", "")
GRANTLAYER_REDIS_URL: str | None = _redis_url_raw if _redis_url_raw else None

# ──────────────────────────────────────────────────────────────
# Demo Endpoint Host Safety
# ──────────────────────────────────────────────────────────────

# Canonical set of host values that are considered local/loopback.
# Empty string is treated as local (default / unset context).
_LOCAL_DEMO_HOSTS: frozenset = frozenset({"localhost", "127.0.0.1", "::1", ""})

# ──────────────────────────────────────────────────────────────
# Startup Warnings (explicit, not noisy)
# ──────────────────────────────────────────────────────────────


def _token_is_unsafe_placeholder(token: str) -> bool:
    """Return True if token matches a known unsafe placeholder or is too short.

    Used only in production-like mode startup checks.
    The raw token value is never logged or exposed — only the verdict.
    """
    if not token:
        return True
    if len(token) < _PROD_MIN_ADMIN_TOKEN_LENGTH:
        return True
    return token.strip().lower() in _UNSAFE_PLACEHOLDER_TOKENS


def startup_warnings() -> list[str]:
    """Return a list of human-readable warning strings for unsafe defaults.

    Call once at server startup.  The caller decides whether to print or log.
    """
    msgs: list[str] = []

    if ENABLE_DEMO_ENDPOINTS:
        msgs.append(
            "WARNING: GRANTLAYER_ENABLE_DEMO_ENDPOINTS=true — "
            "demo-only tamper endpoint is exposed. Do not use in production."
        )

    if not REQUIRE_ADMIN_TOKEN:
        msgs.append(
            "WARNING: GRANTLAYER_REQUIRE_ADMIN_TOKEN is not true — "
            "protected endpoints may fall back to optional token mode."
        )

    if not REQUIRE_CHALLENGE:
        msgs.append(
            "WARNING: GRANTLAYER_REQUIRE_CHALLENGE is not true — "
            "POST /demo-action accepts requests without challengeId."
        )

    # Do NOT log or return the token value — only its presence.
    if not GRANTLAYER_ADMIN_TOKEN:
        msgs.append(
            "WARNING: GRANTLAYER_ADMIN_TOKEN is not set — "
            "admin endpoints are unprotected."
        )
    else:
        # Token is configured; note that REQUIRE_ADMIN_TOKEN determines
        # whether it is actually enforced.
        if not REQUIRE_ADMIN_TOKEN:
            msgs.append(
                "WARNING: GRANTLAYER_ADMIN_TOKEN is present but "
                "GRANTLAYER_REQUIRE_ADMIN_TOKEN is not true — "
                "token is available but not mandatory."
            )

    # Warn if CORS defaults include localhost origins in production-like mode.
    _localhost_cors = {"http://127.0.0.1:8765", "http://localhost:8765"}
    if RUNTIME_MODE in PRODUCTION_LIKE_MODES and CORS_ALLOWED_ORIGINS:
        if set(CORS_ALLOWED_ORIGINS) & _localhost_cors:
            msgs.append(
                "WARNING: GRANTLAYER_CORS_ALLOWED_ORIGINS includes localhost origins "
                "in a production-like runtime mode. Set to your actual public origin(s) "
                "or leave empty to disable CORS."
            )

    # Warn when JWT_ISSUER carries the non-unique default value in non-test mode.
    # Two deployments with the same default issuer and a shared signing key will
    # cross-accept each other's tokens.
    _JWT_ISSUER_DEFAULT = "grantlayer"
    if RUNTIME_MODE != "test" and JWT_ISSUER == _JWT_ISSUER_DEFAULT:
        msgs.append(
            "WARNING: GRANTLAYER_JWT_ISSUER is set to the default value 'grantlayer'. "
            "Set a unique issuer per deployment to prevent cross-instance token acceptance "
            "when multiple GrantLayer instances share a signing key."
        )

    # Warn when strict claims enforcement is disabled but an issuer is configured.
    # Without strict mode, tokens that omit iss/aud bypass issuer/audience validation.
    if JWT_ISSUER and not JWT_STRICT_CLAIMS and RUNTIME_MODE not in ("local", "test"):
        msgs.append(
            "WARNING: GRANTLAYER_JWT_STRICT_CLAIMS is not enabled. "
            "Tokens without iss/aud claims are accepted even though JWT_ISSUER is configured. "
            "Set GRANTLAYER_JWT_STRICT_CLAIMS=true to require iss/aud on all tokens."
        )

    return msgs


def startup_ok() -> bool:
    """Return True if the current config looks safe for a product build.

    In non-local / production-like modes this gate is enforced; the caller
    must refuse to start the server if False.
    """
    return bool(not startup_errors())


def startup_errors() -> list[str]:
    """Return a list of human-readable fatal config errors.

    Messages are deterministic and safe (no secrets).
    Raw secret values are never included in error messages.
    """
    errs: list[str] = []

    if not REQUIRE_ADMIN_TOKEN:
        errs.append(
            "ERROR: GRANTLAYER_REQUIRE_ADMIN_TOKEN is not enabled. "
            "Admin token enforcement is mandatory in non-local / production-like modes."
        )

    if not GRANTLAYER_ADMIN_TOKEN:
        errs.append(
            "ERROR: GRANTLAYER_ADMIN_TOKEN is not set. "
            "A configured admin token is mandatory when admin token enforcement is on."
        )
    elif RUNTIME_MODE in PRODUCTION_LIKE_MODES and _token_is_unsafe_placeholder(GRANTLAYER_ADMIN_TOKEN):
        # Reject placeholder, demo, or short admin tokens in production-like modes only.
        errs.append(
            "ERROR: GRANTLAYER_ADMIN_TOKEN is a known placeholder, demo value, or "
            f"shorter than the required {_PROD_MIN_ADMIN_TOKEN_LENGTH} characters. "
            "Set a strong, unique admin token for production-like modes."
        )

    if not REQUIRE_CHALLENGE:
        errs.append(
            "ERROR: GRANTLAYER_REQUIRE_CHALLENGE is not enabled. "
            "Challenge enforcement is mandatory in non-local / production-like modes."
        )

    if ENABLE_DEMO_ENDPOINTS:
        errs.append(
            "ERROR: GRANTLAYER_ENABLE_DEMO_ENDPOINTS is enabled. "
            "Demo endpoints must be disabled in non-local / production-like modes."
        )

    # Reject placeholder bootstrap operator tokens in production-like modes.
    if RUNTIME_MODE in PRODUCTION_LIKE_MODES and GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN:
        if _token_is_unsafe_placeholder(GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN):
            errs.append(
                "ERROR: GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN is a known placeholder, "
                f"demo value, or shorter than {_PROD_MIN_ADMIN_TOKEN_LENGTH} characters. "
                "Set a strong, unique bootstrap operator token or leave it unset in "
                "production-like modes to disable automatic bootstrapping."
            )

    # Redis is a hard requirement in production-like modes.
    if RUNTIME_MODE in PRODUCTION_LIKE_MODES and not GRANTLAYER_REDIS_URL:
        errs.append(
            "ERROR: GRANTLAYER_REDIS_URL is not set. "
            "Redis is required in production-like modes for distributed rate limiting. "
            "Set GRANTLAYER_REDIS_URL to a valid Redis connection URL."
        )

    errs.extend(external_identity_startup_errors(os.environ, RUNTIME_MODE))

    # OIDC-specific startup errors (missing required OIDC config when OIDC is enabled).
    from ..auth.oidc import OIDCConfig
    errs.extend(OIDCConfig.from_env().startup_errors())

    return errs


def demo_endpoint_public_exposure_errors(host: str | None = None) -> list[str]:
    """Return startup errors if demo endpoints are configured for non-local exposure.

    This check is mode-independent: it applies regardless of RUNTIME_MODE
    because host binding determines network exposure, not runtime mode.

    Args:
        host: The actual bind host the server will use.  Falls back to
              GRANTLAYER_HOST when None.

    Returns:
        A list of safe, deterministic error strings.  Empty list means safe.
    """
    if not ENABLE_DEMO_ENDPOINTS:
        return []

    effective_host = (host if host is not None else GRANTLAYER_HOST).strip().lower()
    if effective_host in _LOCAL_DEMO_HOSTS:
        return []

    if GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS:
        return []

    return [
        "ERROR: demo_endpoints_public_exposure_blocked. "
        "Demo endpoints are enabled with a non-local host binding. "
        "Set GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS=true to explicitly acknowledge."
    ]
