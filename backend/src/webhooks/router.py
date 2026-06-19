"""Webhook management router — CRUD + delivery history + test endpoint."""

from __future__ import annotations

import datetime
import hashlib
import hmac as _hmac
import json
import secrets
import uuid
from typing import Annotated, Any, Dict, Optional

import httpx as _httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import require_mutation_authz, resolve_auth_and_workspace
from ..core.db import get_async_db
from .schemas import (
    WebhookCreateRequest,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookListResponse,
    WebhookResponse,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_ALLOWED_CREATE_ROLES = ["owner", "grant_admin"]
_ALLOWED_READ_ROLES = ["owner", "grant_admin", "auditor"]


def _now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


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


# ── CRUD endpoints ─────────────────────────────────────────────────────────────

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
    await require_mutation_authz(auth_ctx, ws_ctx)

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
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "errorCode": "internal_error", "reason": "Failed to create webhook."},
        )
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


@router.get("/{webhook_id}/deliveries", response_model=WebhookDeliveryListResponse, response_model_by_alias=True)
async def list_webhook_deliveries(
    webhook_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Retrieve recent delivery attempts for a webhook subscription."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=_ALLOWED_READ_ROLES,
        workspace_id=x_workspace_id,
    )

    row = await _fetch_webhook(db, webhook_id, ws_ctx["tenant_id"])
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Webhook not found", "errorCode": "webhook_not_found", "reason": "The requested webhook subscription does not exist."},
        )

    result = await db.execute(
        text(
            "SELECT id, webhook_id, tenant_id, event_type, payload, status, "
            "http_status, error, attempt, created_at, delivered_at "
            "FROM webhook_deliveries "
            "WHERE webhook_id = :webhook_id AND tenant_id = :tenant_id "
            "ORDER BY created_at DESC LIMIT 50"
        ).bindparams(webhook_id=webhook_id, tenant_id=ws_ctx["tenant_id"])
    )
    rows = [dict(r) for r in result.mappings().fetchall()]
    items = [WebhookDeliveryResponse.from_row(r) for r in rows]
    return WebhookDeliveryListResponse(items=items, total=len(items))


@router.post("/{webhook_id}/test", response_model=WebhookDeliveryResponse, response_model_by_alias=True, status_code=200)
async def test_webhook_endpoint(
    webhook_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Send a test ping event to the webhook endpoint and record the delivery attempt."""
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=_ALLOWED_CREATE_ROLES,
        workspace_id=x_workspace_id,
    )
    await require_mutation_authz(auth_ctx, ws_ctx)

    result = await db.execute(
        text(
            "SELECT id, tenant_id, workspace_id, url, events, secret, active, created_at, created_by "
            "FROM webhook_subscriptions WHERE id = :id AND tenant_id = :tenant_id"
        ).bindparams(id=webhook_id, tenant_id=ws_ctx["tenant_id"])
    )
    row = result.mappings().fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Webhook not found", "errorCode": "webhook_not_found", "reason": "The requested webhook subscription does not exist."},
        )
    ep = dict(row)

    payload = {
        "event": "webhook.test",
        "timestamp": _now_utc_iso(),
        "tenant_id": ws_ctx["tenant_id"],
        "workspace_id": ws_ctx.get("workspace_id"),
        "data": {"webhook_id": webhook_id, "message": "This is a test delivery."},
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    delivery_id = str(uuid.uuid4())
    secret = ep.get("secret", "")
    sig = "sha256=" + _hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-GrantLayer-Event": "webhook.test",
        "X-GrantLayer-Signature": sig,
        "X-GrantLayer-Delivery": delivery_id,
        "User-Agent": "GrantLayer-Webhooks/1.0",
    }

    status = "pending"
    http_status: Optional[int] = None
    error: Optional[str] = None
    delivered_at: Optional[str] = None

    try:
        async with _httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(ep["url"], content=body, headers=headers)
        http_status = resp.status_code
        delivered_at = _now_utc_iso()
        status = "success" if resp.status_code < 500 else "failed"
        if resp.status_code >= 500:
            error = f"server error {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        error = str(exc)

    now = _now_utc_iso()
    new_delivery_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO webhook_deliveries "
            "(id, webhook_id, tenant_id, event_type, payload, status, http_status, "
            "error, attempt, created_at, delivered_at) "
            "VALUES (:id, :webhook_id, :tenant_id, :event_type, :payload, :status, "
            ":http_status, :error, :attempt, :created_at, :delivered_at)"
        ).bindparams(
            id=new_delivery_id,
            webhook_id=webhook_id,
            tenant_id=ws_ctx["tenant_id"],
            event_type="webhook.test",
            payload=json.dumps(payload),
            status=status,
            http_status=http_status,
            error=error,
            attempt=1,
            created_at=now,
            delivered_at=delivered_at,
        )
    )
    await db.commit()

    delivery_result = await db.execute(
        text("SELECT id, webhook_id, tenant_id, event_type, payload, status, http_status, error, attempt, created_at, delivered_at FROM webhook_deliveries WHERE id = :id").bindparams(id=new_delivery_id)
    )
    delivery_row = delivery_result.mappings().fetchone()
    if delivery_row is None:
        raise HTTPException(status_code=500, detail={"error": "internal_error", "errorCode": "internal_error", "reason": "Failed to record delivery."})
    return WebhookDeliveryResponse.from_row(dict(delivery_row))


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
            detail={"error": "Webhook not found", "errorCode": "webhook_not_found", "reason": "The requested webhook subscription does not exist."},
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
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=_ALLOWED_CREATE_ROLES,
        workspace_id=x_workspace_id,
    )
    await require_mutation_authz(auth_ctx, ws_ctx)

    row = await _fetch_webhook(db, webhook_id, ws_ctx["tenant_id"])
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Webhook not found", "errorCode": "webhook_not_found", "reason": "The requested webhook subscription does not exist."},
        )

    await db.execute(
        text(
            "UPDATE webhook_subscriptions SET active = 0 WHERE id = :id AND tenant_id = :tenant_id"
        ).bindparams(id=webhook_id, tenant_id=ws_ctx["tenant_id"])
    )
    await db.commit()
    return Response(status_code=204)
