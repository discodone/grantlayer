"""Product-hardened admin token guard for GrantLayer.

This is NOT production authentication.
It protects local/demo mutating endpoints.
When GRANTLAYER_REQUIRE_ADMIN_TOKEN is true, protected endpoints fail closed
if the token is missing, blank, or incorrect.
"""

from __future__ import annotations

import hmac
import os
from typing import Any
from . import config


def admin_token_is_configured() -> bool:
    return bool(os.environ.get("GRANTLAYER_ADMIN_TOKEN", "").strip())


def _get_env_bool(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in ("1", "true", "yes", "on")


def check_admin_token(auth_header: str | None) -> tuple[bool, int, dict]:
    """Validate the Authorization header against GRANTLAYER_ADMIN_TOKEN.

    Returns (ok, http_status, payload).  On success payload is {}.
    Token value is never leaked in payload.
    """
    token_env = os.environ.get("GRANTLAYER_ADMIN_TOKEN", "").strip()
    require_token = _get_env_bool("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

    # Case: no token configured
    if not token_env:
        if require_token:
            # Fail closed
            return False, 403, {"error": "admin_token_required"}
        # Legacy/demo mode: optional token
        return True, 200, {}

    # Case: token configured but missing header
    if not auth_header:
        return False, 401, {"error": "admin_token_required"}

    # Case: token present — validate scheme + value
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        return False, 403, {"error": "admin_token_invalid"}

    token = token.strip()
    if not token:
        return False, 403, {"error": "admin_token_invalid"}

    if hmac.compare_digest(token, token_env):
        return True, 200, {}

    return False, 403, {"error": "admin_token_invalid"}


def admin_token_warning() -> str | None:
    if admin_token_is_configured():
        return None
    return "WARNING: GRANTLAYER_ADMIN_TOKEN not set — admin endpoints are unprotected. Demo only."
