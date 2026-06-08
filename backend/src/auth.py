"""Product-hardened admin token guard and workspace context resolver for GrantLayer.

This is NOT production authentication.
It protects local/demo mutating endpoints.
When GRANTLAYER_REQUIRE_ADMIN_TOKEN is true, protected endpoints fail closed
if the token is missing, blank, or incorrect.

GL-225/226: Workspace Context Resolver + Authorization Enforcement
- resolve_workspace_context() derives workspace from server-side identity/membership.
- No client-supplied workspace_id is trusted without membership verification.
- Fail-closed: no valid workspace context → request rejected.
- check_workspace_resource_access() enforces cross-workspace denial.
- Admin/operator-level bypass is explicit and documented (not silent).
"""

from __future__ import annotations

import hmac
import os
from typing import Any
from . import config
from . import operators as ops
from .db import query_one, query_all


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


# ──────────────────────────────────────────────────────────────
# GL-225: Workspace Context Resolver
# ──────────────────────────────────────────────────────────────

# Roles that are allowed to access resources across all workspaces within their tenant.
# Admin/operator cross-workspace access is explicit and auditable — not silent.
_CROSS_WORKSPACE_ROLES: frozenset = frozenset({"owner", "grant_admin_global"})

# The canonical demo/synthetic workspace id used for legacy / non-operator mode.
_DEMO_WORKSPACE_ID = "default"
_DEMO_TENANT_ID = "demo"

# Workspace member roles in ascending privilege order.
_WORKSPACE_MEMBER_ROLES: frozenset = frozenset({
    "workspace_owner",
    "workspace_admin",
    "workspace_member",
    "workspace_readonly",
})

# Roles that can perform mutations within a workspace.
_WORKSPACE_MUTATION_ROLES: frozenset = frozenset({
    "workspace_owner",
    "workspace_admin",
    "workspace_member",
})


def _get_workspace_row(workspace_id: str, tenant_id: str) -> dict | None:
    """Return the workspace row if it belongs to the specified tenant, else None.

    GL-225: Workspace must be verified against the caller's tenant_id — a
    workspace_id supplied by the client is never trusted without this check.
    """
    return query_one(
        "SELECT id, tenant_id, status FROM workspaces WHERE id = ? AND tenant_id = ?",
        (workspace_id, tenant_id),
    )


def _get_membership_row(operator_id: str, workspace_id: str) -> dict | None:
    """Return active membership row for operator in workspace, or None."""
    return query_one(
        "SELECT id, workspace_id, operator_id, role, status "
        "FROM workspace_members "
        "WHERE operator_id = ? AND workspace_id = ? AND status = 'active'",
        (operator_id, workspace_id),
    )


def _list_operator_workspaces(operator_id: str, tenant_id: str) -> list[dict]:
    """Return all active workspace membership rows for an operator within a tenant."""
    return query_all(
        """
        SELECT wm.workspace_id, wm.role, wm.status
        FROM workspace_members wm
        JOIN workspaces w ON w.id = wm.workspace_id
        WHERE wm.operator_id = ? AND w.tenant_id = ? AND wm.status = 'active' AND w.status = 'active'
        """,
        (operator_id, tenant_id),
    )


def resolve_workspace_context(
    auth_payload: dict,
    client_workspace_id: str | None = None,
) -> tuple[str | None, int, dict]:
    """Derive the effective workspace_id securely from server-side identity.

    GL-225: The workspace is derived from the operator's identity and membership.
    A client-supplied workspace_id is only accepted after membership verification.
    Fail-closed: if no valid workspace can be resolved, (None, 403, error) is returned.

    Modes:
    - Legacy/demo (no operator model): returns (_DEMO_WORKSPACE_ID, 200, {...})
    - Operator model, cross-workspace role (owner/grant_admin_global):
        If client_workspace_id provided and tenant matches → accepted.
        Otherwise returns demo workspace for demo tenant.
    - Operator model, regular member:
        If client_workspace_id provided → must have active membership.
        If no client_workspace_id → use single-membership workspace or fail.

    Returns:
        (workspace_id, http_status, context_dict) on success: http_status == 200.
        (None, http_status, error_dict) on failure: http_status in {403, 400}.

    The context_dict contains:
        workspace_id, tenant_id, workspace_member_role (if known),
        cross_workspace_access (bool), resolution_mode.
    """
    tenant_id: str = auth_payload.get("tenant_id") or _DEMO_TENANT_ID
    operator: dict = auth_payload.get("operator") or {}
    operator_id: str | None = operator.get("operatorId")
    operator_role: str | None = operator.get("role")

    # ── Legacy / demo mode (no operator model) ─────────────────
    if not operator_id:
        # Legacy admin-token path: bind to demo workspace, no membership check.
        ws_id = _DEMO_WORKSPACE_ID
        ctx: dict = {
            "workspace_id": ws_id,
            "tenant_id": _DEMO_TENANT_ID,
            "workspace_member_role": None,
            "cross_workspace_access": False,
            "resolution_mode": "legacy_demo",
        }
        return ws_id, 200, ctx

    # ── Operator model ──────────────────────────────────────────

    # Check for cross-workspace privileged roles (explicitly documented access).
    is_cross_workspace = operator_role in _CROSS_WORKSPACE_ROLES

    if client_workspace_id is not None:
        client_workspace_id = client_workspace_id.strip()
        if not client_workspace_id:
            return None, 400, {
                "error": "invalid_workspace_id",
                "errorCode": "invalid_workspace_id",
                "reason": "workspace_id must be a non-empty string.",
            }

        # Verify the workspace belongs to the operator's tenant.
        ws_row = _get_workspace_row(client_workspace_id, tenant_id)
        if ws_row is None:
            return None, 403, {
                "error": "workspace_not_found",
                "errorCode": "workspace_not_found",
                "reason": "The requested workspace does not exist or does not belong to your tenant.",
            }
        if ws_row.get("status") != "active":
            return None, 403, {
                "error": "workspace_inactive",
                "errorCode": "workspace_inactive",
                "reason": "The requested workspace is not active.",
            }

        if is_cross_workspace:
            # Cross-workspace roles may access any tenant workspace.
            # This is explicit and auditable — not silent.
            ctx = {
                "workspace_id": client_workspace_id,
                "tenant_id": tenant_id,
                "workspace_member_role": None,
                "cross_workspace_access": True,
                "resolution_mode": "cross_workspace_role",
            }
            return client_workspace_id, 200, ctx

        # Regular operator: must have active membership in the requested workspace.
        mem = _get_membership_row(operator_id, client_workspace_id)
        if mem is None:
            return None, 403, {
                "error": "workspace_access_denied",
                "errorCode": "workspace_access_denied",
                "reason": "You do not have membership in the requested workspace.",
            }
        ctx = {
            "workspace_id": client_workspace_id,
            "tenant_id": tenant_id,
            "workspace_member_role": mem.get("role"),
            "cross_workspace_access": False,
            "resolution_mode": "membership_verified",
        }
        return client_workspace_id, 200, ctx

    # No client_workspace_id supplied: auto-resolve from membership.
    if is_cross_workspace:
        # Cross-workspace roles without a specific workspace_id → use demo workspace
        # for demo tenant, else fail (they must specify which workspace they intend).
        if tenant_id == _DEMO_TENANT_ID:
            ctx = {
                "workspace_id": _DEMO_WORKSPACE_ID,
                "tenant_id": tenant_id,
                "workspace_member_role": None,
                "cross_workspace_access": True,
                "resolution_mode": "cross_workspace_role_demo_fallback",
            }
            return _DEMO_WORKSPACE_ID, 200, ctx
        return None, 400, {
            "error": "workspace_id_required",
            "errorCode": "workspace_id_required",
            "reason": (
                "Cross-workspace roles must specify a workspace_id. "
                "Include the target workspace in the request."
            ),
        }

    # Regular operator: look up all memberships and pick single or fail.
    memberships = _list_operator_workspaces(operator_id, tenant_id)
    active = [m for m in memberships if m.get("status") == "active"]

    if not active:
        return None, 403, {
            "error": "no_workspace_membership",
            "errorCode": "no_workspace_membership",
            "reason": "Operator has no active workspace memberships. Cannot resolve workspace context.",
        }

    if len(active) == 1:
        ws_id = active[0]["workspace_id"]
        ctx = {
            "workspace_id": ws_id,
            "tenant_id": tenant_id,
            "workspace_member_role": active[0].get("role"),
            "cross_workspace_access": False,
            "resolution_mode": "single_membership",
        }
        return ws_id, 200, ctx

    # Multiple memberships: ambiguous without explicit workspace_id.
    return None, 400, {
        "error": "workspace_id_required",
        "errorCode": "workspace_id_required",
        "reason": (
            "Operator has multiple workspace memberships. "
            "Include workspace_id in the request to specify the target workspace."
        ),
    }


# ──────────────────────────────────────────────────────────────
# GL-226: Cross-Workspace Authorization Enforcement
# ──────────────────────────────────────────────────────────────


def check_workspace_resource_access(
    resource_workspace_id: str | None,
    caller_workspace_id: str,
    caller_tenant_id: str,
    resource_tenant_id: str | None,
    cross_workspace_access: bool = False,
    require_mutation: bool = False,
    workspace_member_role: str | None = None,
) -> tuple[bool, int, dict]:
    """Enforce cross-workspace and cross-tenant access boundaries.

    GL-226: This is the enforcement point for all resource-level workspace checks.

    Rules:
    - Cross-tenant access is always denied (403).
    - Cross-workspace lookup: denied (403) unless cross_workspace_access is True.
    - Cross-workspace mutation: denied (403) unless cross_workspace_access is True.
    - Admin cross-workspace access (cross_workspace_access=True) is explicit and logged.
    - Role checks: readonly role cannot mutate.

    Args:
        resource_workspace_id: workspace_id on the resource being accessed.
        caller_workspace_id: workspace_id from the resolved workspace context.
        caller_tenant_id: tenant_id from the auth payload.
        resource_tenant_id: tenant_id on the resource (if available).
        cross_workspace_access: True if operator has a cross-workspace role.
        require_mutation: True for write operations (POST/PUT/PATCH/DELETE).
        workspace_member_role: The caller's workspace member role, if known.

    Returns:
        (True, 200, {}) on success.
        (False, 403, error_dict) on denial.
    """
    # Tenant boundary is always enforced — cross-tenant is always 403.
    if resource_tenant_id is not None and resource_tenant_id != caller_tenant_id:
        return False, 403, {
            "error": "cross_tenant_access_denied",
            "errorCode": "cross_tenant_access_denied",
            "reason": "Cross-tenant resource access is not permitted.",
        }

    # Normalize: None resource_workspace_id is treated as same-workspace for backward compat
    # (pre-GL-224 rows may lack workspace_id).
    if resource_workspace_id is None:
        # Treat unscoped resources as belonging to the caller's workspace.
        return True, 200, {}

    # Same-workspace: always allowed (subject to role checks below).
    if resource_workspace_id == caller_workspace_id:
        if require_mutation and workspace_member_role == "workspace_readonly":
            return False, 403, {
                "error": "workspace_role_insufficient",
                "errorCode": "workspace_role_insufficient",
                "reason": "Your workspace role does not permit write operations.",
            }
        return True, 200, {}

    # Cross-workspace access.
    if not cross_workspace_access:
        if require_mutation:
            return False, 403, {
                "error": "cross_workspace_mutation_denied",
                "errorCode": "cross_workspace_mutation_denied",
                "reason": "Write access to resources in another workspace is not permitted.",
            }
        return False, 403, {
            "error": "cross_workspace_lookup_denied",
            "errorCode": "cross_workspace_lookup_denied",
            "reason": "Read access to resources in another workspace is not permitted.",
        }

    # Cross-workspace access is permitted by role; enforce mutation role check.
    if require_mutation and workspace_member_role == "workspace_readonly":
        return False, 403, {
            "error": "workspace_role_insufficient",
            "errorCode": "workspace_role_insufficient",
            "reason": "Your workspace role does not permit write operations.",
        }

    # Cross-workspace role access granted (explicitly documented, not silent).
    return True, 200, {}
