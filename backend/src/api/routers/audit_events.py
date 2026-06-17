"""Audit events endpoints (FastAPI)."""

from __future__ import annotations

import base64
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, Query

from ...audit.audit_log import count_events, list_events
from ..deps import resolve_auth_and_workspace
from ..schemas import AuditEventListResponse, AuditEventResponse

router = APIRouter(tags=["audit"])


def _encode_cursor(seq: int) -> str:
    """Encode a seq value as an opaque URL-safe cursor string."""
    return base64.urlsafe_b64encode(str(seq).encode()).decode()


def _decode_cursor(cursor: str) -> Optional[int]:
    """Decode a cursor string back to a seq value; returns None on invalid input."""
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return None


@router.get("/audit-events", response_model=AuditEventListResponse)
async def list_audit_events(
    limit: int = Query(default=100, ge=1, le=1000),
    cursor: Optional[str] = Query(default=None),
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

    after_seq: Optional[int] = None
    if cursor is not None:
        after_seq = _decode_cursor(cursor)

    events = list_events(
        limit=limit,
        offset=offset,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        after_seq=after_seq,
    )

    # Build next_cursor from the last item's seq when the page is full.
    next_cursor: Optional[str] = None
    if len(events) == limit:
        last_seq = events[-1].seq
        if last_seq is not None:
            next_cursor = _encode_cursor(last_seq)

    return AuditEventListResponse(
        items=[AuditEventResponse(**e.to_dict()) for e in events],
        total=count_events(tenant_id=tenant_id, workspace_id=workspace_id),
        limit=limit,
        offset=offset,
        next_cursor=next_cursor,
    )
