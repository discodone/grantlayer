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
from . import operators as ops


def admin_token_is_configured() -> bool:
    return bool(os.environ.get("GRANTLAYER_ADMIN_TOKEN", "").strip())


def _get_env_bool(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in ("1", "true", "yes", "on")


# ──────────────────────────────────────────────
# New unified auth guard
# ──────────────────────────────────────────────

def check_auth(
    auth_header: str | None,
    required_roles: list[str] | None = None,
) -> tuple[bool, int, dict]:
    """Unified authentication/authorization guard.

    If ENABLE_OPERATOR_MODEL is true -> use operator auth.
    If ENABLE_OPERATOR_MODEL is false -> fall back to legacy admin-token.

    Returns (ok, http_status, payload).
    """
    if config.ENABLE_OPERATOR_MODEL:
        op, reason = ops.authenticate_operator_with_reason(auth_header)
        if op is None:
            if reason == "operator_token_expired":
                return False, 401, {
                    "error": "operator_token_expired",
                    "errorCode": "operator_token_expired",
                    "reason": "Operator token has expired.",
                }
            return False, 401, {"error": "operator_auth_required", "errorCode": "operator_auth_required", "reason": "Operator authentication is required."}
        if required_roles is not None and not ops.check_role(op, required_roles):
            return False, 403, {"error": "operator_role_forbidden", "errorCode": "operator_role_forbidden", "reason": "Operator role is not authorized for this action."}
        return True, 200, {"operator": op.to_dict(), "tenant_id": op.tenant_id}

    # Legacy admin-token mode: bind to 'demo' tenant (backward compat with legacy resources)
    ok, status, payload = check_admin_token(auth_header)
    if ok:
        payload = dict(payload)
        payload["tenant_id"] = "demo"
    return ok, status, payload


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
            return False, 403, {"error": "admin_token_required", "errorCode": "admin_token_required", "reason": "Admin token is required for this endpoint."}
        # Legacy/demo mode: optional token
        return True, 200, {}

    # Case: token configured but missing header
    if not auth_header:
        return False, 401, {"error": "admin_token_required", "errorCode": "admin_token_required", "reason": "Admin token is required for this endpoint."}

    # Case: token present — validate scheme + value
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        return False, 403, {"error": "admin_token_invalid", "errorCode": "admin_token_invalid", "reason": "The provided admin token is invalid."}

    token = token.strip()
    if not token:
        return False, 403, {"error": "admin_token_invalid", "errorCode": "admin_token_invalid", "reason": "The provided admin token is invalid."}

    if hmac.compare_digest(token, token_env):
        return True, 200, {}

    return False, 403, {"error": "admin_token_invalid", "errorCode": "admin_token_invalid", "reason": "The provided admin token is invalid."}


def admin_token_warning() -> str | None:
    if admin_token_is_configured():
        return None
    return "WARNING: GRANTLAYER_ADMIN_TOKEN not set — admin endpoints are unprotected. Demo only."
