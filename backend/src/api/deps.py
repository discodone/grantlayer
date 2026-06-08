"""GL-229: Shared FastAPI dependency helpers."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from .. import config
from ..auth import check_auth, check_admin_token, resolve_workspace_context, check_workspace_resource_access


def resolve_auth_and_workspace(
    authorization: Optional[str],
    required_roles: list[str],
    workspace_id: Optional[str] = None,
) -> tuple[dict, dict]:
    """Authenticate and resolve workspace context.

    Returns (auth_ctx, ws_ctx).  Raises HTTPException on failure.
    Mirrors server.py _require_operator + _resolve_workspace logic exactly,
    including the pre-workspace-enforcement backward-compat fallback.
    """
    ok, http_status, payload = check_auth(authorization, required_roles=required_roles)
    if not ok:
        raise HTTPException(status_code=http_status, detail=payload)

    ws_id, ws_status, ws_ctx = resolve_workspace_context(payload, workspace_id)

    if ws_status != 200:
        error_code = ws_ctx.get("errorCode", "")
        if error_code in ("no_workspace_membership", "workspace_id_required"):
            tenant_id = payload.get("tenant_id") or "demo"
            if tenant_id != "demo":
                from ..db import query_all as _qa
                tenant_has_ws = _qa(
                    "SELECT id FROM workspaces WHERE tenant_id = ? AND status = 'active' LIMIT 1",
                    (tenant_id,),
                )
                if not tenant_has_ws:
                    ws_ctx = {
                        "workspace_id": "default",
                        "tenant_id": tenant_id,
                        "workspace_member_role": None,
                        "cross_workspace_access": False,
                        "resolution_mode": "no_tenant_workspaces_fallback",
                    }
                    return payload, ws_ctx
        raise HTTPException(status_code=ws_status, detail=ws_ctx)

    return payload, ws_ctx


def require_admin(authorization: Optional[str]) -> dict:
    """Check admin token. Returns payload dict or raises HTTPException."""
    ok, status, payload = check_admin_token(authorization)
    if not ok:
        raise HTTPException(status_code=status, detail=payload)
    return {"tenant_id": "demo"}


def enforce_workspace_mutation(ws_ctx: dict) -> None:
    """Raise 403 if the caller's workspace context does not allow mutation."""
    access_ok, access_status, access_err = check_workspace_resource_access(
        resource_workspace_id=None,
        caller_workspace_id=ws_ctx["workspace_id"],
        caller_tenant_id=ws_ctx["tenant_id"],
        resource_tenant_id=ws_ctx["tenant_id"],
        cross_workspace_access=ws_ctx.get("cross_workspace_access", False),
        require_mutation=True,
        workspace_member_role=ws_ctx.get("workspace_member_role"),
    )
    if not access_ok:
        raise HTTPException(status_code=access_status, detail=access_err)
