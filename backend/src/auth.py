"""Demo-only admin token guard for GrantLayer.

This is NOT production authentication.
It only protects local demo mutating endpoints when GRANTLAYER_ADMIN_TOKEN is set.
"""

from __future__ import annotations

import hmac
import os
from typing import Any


def admin_token_is_configured() -> bool:
    return bool(os.environ.get("GRANTLAYER_ADMIN_TOKEN"))


def check_admin_token(authorization_header: str | None) -> tuple[bool, int, dict[str, Any]]:
    """Validate Authorization: Bearer <token> for demo admin endpoints.

    If GRANTLAYER_ADMIN_TOKEN is not set, allow legacy local demo behavior.
    Never logs or returns the configured token.
    """
    expected = os.environ.get("GRANTLAYER_ADMIN_TOKEN")

    if not expected:
        return True, 200, {}

    if not authorization_header or not authorization_header.startswith("Bearer "):
        return False, 401, {"error": "admin_token_required"}

    provided = authorization_header.removeprefix("Bearer ").strip()

    if not hmac.compare_digest(provided, expected):
        return False, 403, {"error": "admin_token_invalid"}

    return True, 200, {}


def admin_token_warning() -> str | None:
    if admin_token_is_configured():
        return None
    return "WARNING: GRANTLAYER_ADMIN_TOKEN not set — admin endpoints are unprotected. Demo only."
