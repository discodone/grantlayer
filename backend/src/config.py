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


# ──────────────────────────────────────────────────────────────
# Product / Demo Mode Flags
# ──────────────────────────────────────────────────────────────

# If True, all protected endpoints require the admin token.
# If False, they fall back to optional/legacy behavior.
REQUIRE_ADMIN_TOKEN: bool = _env_bool("GRANTLAYER_REQUIRE_ADMIN_TOKEN", default=False)

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

# ──────────────────────────────────────────────────────────────
# Admin Token (Demo / Sprint-2C only)
# ──────────────────────────────────────────────────────────────

GRANTLAYER_ADMIN_TOKEN: str = _env_str("GRANTLAYER_ADMIN_TOKEN", "")

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

    This is advisory — the server still starts even if False.
    """
    return (
        REQUIRE_ADMIN_TOKEN
        and bool(GRANTLAYER_ADMIN_TOKEN)
        and REQUIRE_CHALLENGE
        and not ENABLE_DEMO_ENDPOINTS
    )
