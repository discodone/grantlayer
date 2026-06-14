"""Audit events endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, Query

from ...audit.audit_log import count_events, list_events
from ..deps import resolve_auth_and_workspace
from ..schemas import AuditEventListResponse, AuditEventResponse

router = APIRouter(tags=["audit"])


@router.get("/audit-events", response_model=AuditEventListResponse)
def list_audit_events(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]
    events = list_events(limit=limit, offset=offset, tenant_id=tenant_id, workspace_id=workspace_id)
    return AuditEventListResponse(
        items=[AuditEventResponse(**e.to_dict()) for e in events],
        total=count_events(tenant_id=tenant_id, workspace_id=workspace_id),
        limit=limit,
        offset=offset,
    )
