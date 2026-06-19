"""Bulk operations API — POST /grants/bulk-update, /grant-requests/bulk-approve, /bulk-reject."""

from __future__ import annotations

from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit.audit_log import append_event
from ...core.db import get_async_db
from ...core.models import AuditEvent
from ...grants.grant_request_service import AsyncGrantRequestService
from ...grants.grant_service import AsyncGrantService
from ..deps import (
    get_async_grant_request_service,
    get_async_grant_service,
    require_mutation_authz,
    resolve_auth_and_workspace,
)
from ..schemas import DynamicResponse

_MAX_BULK = 100

grants_bulk_router = APIRouter(prefix="/grants", tags=["grants-bulk"])
grant_requests_bulk_router = APIRouter(prefix="/grant-requests", tags=["grant-requests-bulk"])


class BulkUpdateRequest(BaseModel):
    grantIds: List[str] = Field(..., min_length=1, max_length=_MAX_BULK)
    revoke: Optional[bool] = None
    reason: Optional[str] = None

    model_config = {"populate_by_name": True}


class BulkApproveRequest(BaseModel):
    requestIds: List[str] = Field(..., min_length=1, max_length=_MAX_BULK)
    reason: Optional[str] = ""

    model_config = {"populate_by_name": True}


class BulkRejectRequest(BaseModel):
    requestIds: List[str] = Field(..., min_length=1, max_length=_MAX_BULK)
    reason: Optional[str] = ""

    model_config = {"populate_by_name": True}


@grants_bulk_router.post("/bulk-update", response_model=DynamicResponse)
async def bulk_update_grants(
    body: BulkUpdateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    svc: AsyncGrantService = Depends(get_async_grant_service),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    auth_ctx, ws_ctx = resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    await require_mutation_authz(auth_ctx, ws_ctx)
    grant_ids = body.grantIds
    if len(grant_ids) > _MAX_BULK:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Too many grants",
                "errorCode": "bulk_limit_exceeded",
                "reason": f"Maximum {_MAX_BULK} grants per bulk operation.",
            },
        )

    tenant_id: str = ws_ctx.get("tenant_id") or "demo"
    workspace_id: str = ws_ctx.get("workspace_id") or ""
    operator_id: str = auth_ctx.get("sub", "bulk")
    results: list[dict] = []
    errors: list[dict] = []

    async with db.begin_nested():
        for gid in grant_ids:
            try:
                if body.revoke:
                    await svc.revoke_grant(
                        grant_id=gid,
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        revoked_by=operator_id,
                        reason=body.reason or "bulk revoke",
                    )
                    results.append({"grantId": gid, "status": "revoked"})
                else:
                    g = await svc.get_grant(gid, tenant_id=tenant_id, workspace_id=workspace_id)
                    if g is None:
                        errors.append({"grantId": gid, "error": "not_found"})
                        continue
                    results.append({"grantId": gid, "status": "ok"})
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "Bulk update failed",
                        "errorCode": "bulk_update_failed",
                        "reason": str(exc),
                        "grantId": gid,
                    },
                )

    event = AuditEvent(
        subject_id=operator_id,
        role=auth_ctx.get("role", "grant_admin"),
        action="bulk_update",
        resource=f"grants/{','.join(grant_ids[:3])}...",
        approved=True,
        reason=body.reason or "bulk update",
        tenant_id=tenant_id,
        scope="bulk",
    )
    await db.run_sync(lambda s: append_event(event, conn=s.connection()))

    return {"ok": True, "results": results, "errors": errors, "count": len(results)}


@grant_requests_bulk_router.post("/bulk-approve", response_model=DynamicResponse)
async def bulk_approve_grant_requests(
    body: BulkApproveRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    svc: AsyncGrantRequestService = Depends(get_async_grant_request_service),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    auth_ctx, ws_ctx = resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    await require_mutation_authz(auth_ctx, ws_ctx)
    request_ids = body.requestIds
    if len(request_ids) > _MAX_BULK:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Too many requests",
                "errorCode": "bulk_limit_exceeded",
                "reason": f"Maximum {_MAX_BULK} requests per bulk operation.",
            },
        )

    tenant_id: str = ws_ctx.get("tenant_id") or "demo"
    workspace_id: str = ws_ctx.get("workspace_id") or ""
    operator_id: str = auth_ctx.get("sub", "bulk")
    results: list[dict] = []

    async with db.begin_nested():
        for rid in request_ids:
            try:
                await svc.approve_request(
                    request_id=rid,
                    operator_id=operator_id,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                )
                results.append({"requestId": rid, "status": "approved"})
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "Bulk approve failed",
                        "errorCode": "bulk_approve_failed",
                        "reason": str(exc),
                        "requestId": rid,
                    },
                )

    event = AuditEvent(
        subject_id=operator_id,
        role=auth_ctx.get("role", "grant_admin"),
        action="bulk_approve",
        resource=f"grant-requests/{','.join(request_ids[:3])}...",
        approved=True,
        reason=body.reason or "bulk approve",
        tenant_id=tenant_id,
        scope="bulk",
    )
    await db.run_sync(lambda s: append_event(event, conn=s.connection()))
    return {"ok": True, "results": results, "errors": [], "count": len(results)}


@grant_requests_bulk_router.post("/bulk-reject", response_model=DynamicResponse)
async def bulk_reject_grant_requests(
    body: BulkRejectRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    svc: AsyncGrantRequestService = Depends(get_async_grant_request_service),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    auth_ctx, ws_ctx = resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    await require_mutation_authz(auth_ctx, ws_ctx)
    request_ids = body.requestIds
    if len(request_ids) > _MAX_BULK:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Too many requests",
                "errorCode": "bulk_limit_exceeded",
                "reason": f"Maximum {_MAX_BULK} requests per bulk operation.",
            },
        )

    tenant_id: str = ws_ctx.get("tenant_id") or "demo"
    workspace_id: str = ws_ctx.get("workspace_id") or ""
    operator_id: str = auth_ctx.get("sub", "bulk")
    results: list[dict] = []

    async with db.begin_nested():
        for rid in request_ids:
            try:
                await svc.deny_request(
                    request_id=rid,
                    operator_id=operator_id,
                    reason=body.reason or "bulk reject",
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                )
                results.append({"requestId": rid, "status": "rejected"})
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "Bulk reject failed",
                        "errorCode": "bulk_reject_failed",
                        "reason": str(exc),
                        "requestId": rid,
                    },
                )

    event = AuditEvent(
        subject_id=operator_id,
        role=auth_ctx.get("role", "grant_admin"),
        action="bulk_reject",
        resource=f"grant-requests/{','.join(request_ids[:3])}...",
        approved=False,
        reason=body.reason or "bulk reject",
        tenant_id=tenant_id,
        scope="bulk",
    )
    await db.run_sync(lambda s: append_event(event, conn=s.connection()))
    return {"ok": True, "results": results, "errors": [], "count": len(results)}
