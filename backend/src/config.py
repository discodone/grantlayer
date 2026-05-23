"""GrantLayer MVP — Centralized configuration.

Reads environment variables with safe defaults for local development.
Product mode is opt-in via explicit flags; unsafe demo defaults emit startup warnings.

Security rules:
- No secrets are logged.
- No secrets are written to disk.
- Presence of a token is reported; its value is NOT.
"""

from __future__ import annotations

import os
import warnings

from .runtime_config import get_runtime_mode

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

GRANTLAYER_ADMIN_TOKEN: str = _env_str("GRANTLAYER_ADMIN_TOKEN", "")

# ──────────────────────────────────────────────────────────────
# Operator Model (GL-021)
# ──────────────────────────────────────────────────────────────

ENABLE_OPERATOR_MODEL: bool = _env_bool("GRANTLAYER_ENABLE_OPERATOR_MODEL", default=False)

GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN: str = _env_str("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", "")
GRANTLAYER_BOOTSTRAP_OPERATOR_ID: str = _env_str("GRANTLAYER_BOOTSTRAP_OPERATOR_ID", "bootstrap-admin")
GRANTLAYER_BOOTSTRAP_OPERATOR_NAME: str = _env_str("GRANTLAYER_BOOTSTRAP_OPERATOR_NAME", "Bootstrap Admin")
GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE: str = _env_str("GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE", "owner")

# ──────────────────────────────────────────────────────────────
# CORS Origin Allowlist (GL-095)
# ──────────────────────────────────────────────────────────────

# Comma-separated list of allowed origins for CORS.
# Empty list disables CORS entirely (no Access-Control-Allow-Origin header).
# Exact origin matching only; no wildcards, no subdomains, no reflection.
CORS_ALLOWED_ORIGINS: list[str] = _env_list(
    "GRANTLAYER_CORS_ALLOWED_ORIGINS",
    default=["http://127.0.0.1:8765", "http://localhost:8765"],
)

# ──────────────────────────────────────────────────────────────
# Startup Warnings (explicit, not noisy)
# ──────────────────────────────────────────────────────────────


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

    return errs
