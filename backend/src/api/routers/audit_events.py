"""GL-229: Audit events endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from ...audit_log import list_events
from ..deps import resolve_auth_and_workspace

router = APIRouter(tags=["audit"])


@router.get("/audit-events")
def list_audit_events(
    limit: Optional[int] = Query(default=200, ge=1, le=1000),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    events = list_events(limit=limit, tenant_id=tenant_id)
    return [e.to_dict() for e in events]
