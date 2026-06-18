"""Webhook subscription management endpoints (FastAPI)."""

from __future__ import annotations

import datetime
import json
import secrets
import uuid
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_async_db
from ...core.webhook_dispatcher import WEBHOOK_EVENTS
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_ALLOWED_CREATE_ROLES = ["owner", "grant_admin"]
_ALLOWED_READ_ROLES = ["owner", "grant_admin", "auditor"]


def _now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class WebhookCreateRequest(BaseModel):
    url: str = Field(..., max_length=2048)
    events: List[str]
    secret: Optional[str] = Field(None, max_length=256)

    model_config = {"populate_by_name": True}

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("url must be non-empty")
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("url must start with http:// or https://")
        return v.strip()

    @field_validator("events")
    @classmethod
    def _validate_events(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("events must contain at least one event type")
        invalid = [e for e in v if e not in WEBHOOK_EVENTS]
        if invalid:
            raise ValueError(
                f"Unknown event types: {invalid}. Valid: {sorted(WEBHOOK_EVENTS)}"
            )
        return list(set(v))


class WebhookResponse(BaseModel):
    id: str
    tenant_id: str = Field(alias="tenantId")
    workspace_id: Optional[str] = Field(alias="workspaceId")
    url: str
    events: List[str]
    active: bool
    created_at: str = Field(alias="createdAt")
    created_by: str = Field(alias="createdBy")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "WebhookResponse":
        events = json.loads(row["events"]) if isinstance(row["events"], str) else row["events"]
        return cls(
            id=row["id"],
            tenantId=row["tenant_id"],
            workspaceId=row.get("workspace_id"),
            url=row["url"],
            events=events,
            active=bool(row["active"]),
            createdAt=row["created_at"],
            createdBy=row["created_by"],
        )


class WebhookListResponse(BaseModel):
    items: List[WebhookResponse]
    total: int


# ── Helper ────────────────────────────────────────────────────────────────────

async def _fetch_webhook(
    db: AsyncSession, webhook_id: str, tenant_id: str
) -> Optional[Dict[str, Any]]:
    result = await db.execute(
        text(
            "SELECT id, tenant_id, workspace_id, url, events, active, created_at, created_by "
            "FROM webhook_subscriptions WHERE id = :id AND tenant_id = :tenant_id"
        ).bindparams(id=webhook_id, tenant_id=tenant_id)
    )
    row = result.mappings().fetchone()
    return dict(row) if row is not None else None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=WebhookResponse, response_model_by_alias=True, status_code=201)
async def create_webhook_endpoint(
    body: WebhookCreateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Register a new webhook subscription."""
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=_ALLOWED_CREATE_ROLES,
        workspace_id=x_workspace_id,
    )

    webhook_id = str(uuid.uuid4())
    secret = body.secret if body.secret else secrets.token_hex(32)
    events_json = json.dumps(sorted(body.events))
    now = _now_utc_iso()

    operator_id = (
        auth_ctx.get("operator", {}).get("operatorId")
        or auth_ctx.get("sub")
        or "unknown"
    )

    await db.execute(
        text(
            "INSERT INTO webhook_subscriptions "
            "(id, tenant_id, workspace_id, url, events, secret, active, created_at, created_by) "
            "VALUES (:id, :tenant_id, :workspace_id, :url, :events, :secret, 1, :created_at, :created_by)"
        ).bindparams(
            id=webhook_id,
            tenant_id=ws_ctx["tenant_id"],
            workspace_id=ws_ctx["workspace_id"],
            url=body.url,
            events=events_json,
            secret=secret,
            created_at=now,
            created_by=operator_id,
        )
    )
    await db.commit()

    row = await _fetch_webhook(db, webhook_id, ws_ctx["tenant_id"])
    if row is None:
        raise HTTPException(status_code=500, detail={"error": "internal_error", "errorCode": "internal_error", "reason": "Failed to create webhook."})
    return WebhookResponse.from_row(row)


@router.get("", response_model=WebhookListResponse, response_model_by_alias=True)
async def list_webhooks_endpoint(
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """List webhook subscriptions for the authenticated tenant/workspace."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=_ALLOWED_READ_ROLES,
        workspace_id=x_workspace_id,
    )

    result = await db.execute(
        text(
            "SELECT id, tenant_id, workspace_id, url, events, active, created_at, created_by "
            "FROM webhook_subscriptions WHERE tenant_id = :tenant_id "
            "ORDER BY created_at DESC"
        ).bindparams(tenant_id=ws_ctx["tenant_id"])
    )
    rows = [dict(r) for r in result.mappings().fetchall()]
    items = [WebhookResponse.from_row(r) for r in rows]
    return WebhookListResponse(items=items, total=len(items))


@router.get("/{webhook_id}", response_model=WebhookResponse, response_model_by_alias=True)
async def get_webhook_endpoint(
    webhook_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Retrieve a webhook subscription by ID."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=_ALLOWED_READ_ROLES,
        workspace_id=x_workspace_id,
    )

    row = await _fetch_webhook(db, webhook_id, ws_ctx["tenant_id"])
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Webhook not found",
                "errorCode": "webhook_not_found",
                "reason": "The requested webhook subscription does not exist.",
            },
        )
    return WebhookResponse.from_row(row)


@router.delete("/{webhook_id}", status_code=204, response_class=Response)
async def delete_webhook_endpoint(
    webhook_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Deactivate (soft-delete) a webhook subscription."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=_ALLOWED_CREATE_ROLES,
        workspace_id=x_workspace_id,
    )

    row = await _fetch_webhook(db, webhook_id, ws_ctx["tenant_id"])
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Webhook not found",
                "errorCode": "webhook_not_found",
                "reason": "The requested webhook subscription does not exist.",
            },
        )

    await db.execute(
        text(
            "UPDATE webhook_subscriptions SET active = 0 WHERE id = :id AND tenant_id = :tenant_id"
        ).bindparams(id=webhook_id, tenant_id=ws_ctx["tenant_id"])
    )
    await db.commit()
    return Response(status_code=204)
