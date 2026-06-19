"""Admin control-plane operator management endpoints (FastAPI)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit.audit_log import append_event
from ...auth.operator_service import AsyncOperatorService
from ...core.db import get_async_db
from ...core.logging_utils import get_logger, safe_log
from ...core.models import AuditEvent
from ..deps import AdminScope, get_async_operator_service, require_admin_scope
from ..schemas import DynamicResponse

router = APIRouter(prefix="/admin", tags=["admin"])

_logger = get_logger("grantlayer.fastapi.admin")

_ADMIN_OPERATOR_CREATE_ROLES = frozenset({"owner", "grant_admin", "auditor"})


from pydantic import BaseModel, Field


class OperatorCreateRequest(BaseModel):
    name: str
    role: str
    tenant_id: str = Field(alias="tenantId")

    model_config = {"populate_by_name": True}


@router.get("/operators", response_model=list[dict[str, Any]])
async def list_operators_endpoint(
    scope: AdminScope = Depends(require_admin_scope),
    svc: AsyncOperatorService = Depends(get_async_operator_service),
) -> Any:
    # Data-layer scoping: a tenant-scoped admin's query is filtered to its own tenant;
    # a deployment admin (tenant_filter is None) sees every tenant.
    return await svc.list_operators_for_admin(caller_tenant_id=scope.tenant_filter)


@router.get("/operators/{operator_id}", response_model=dict[str, Any])
async def get_operator_endpoint(
    operator_id: str,
    scope: AdminScope = Depends(require_admin_scope),
    svc: AsyncOperatorService = Depends(get_async_operator_service),
) -> Any:
    op_safe = await svc.get_operator_safe(operator_id)
    if op_safe is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Operator not found", "errorCode": "operator_not_found", "reason": "The requested operator does not exist."},
        )
    scope.assert_target(op_safe.get("tenantId"))
    return op_safe


@router.post("/operators", status_code=201, response_model=DynamicResponse)
async def create_operator_endpoint(
    body: OperatorCreateRequest,
    scope: AdminScope = Depends(require_admin_scope),
    svc: AsyncOperatorService = Depends(get_async_operator_service),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    name = body.name
    role = body.role
    tenant_id = body.tenant_id

    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail={"error": "Invalid field: name", "errorCode": "invalid_field", "reason": "name must be a non-empty string."})
    if not isinstance(role, str) or not role.strip():
        raise HTTPException(status_code=400, detail={"error": "Invalid field: role", "errorCode": "invalid_field", "reason": "role must be a non-empty string."})
    role = role.strip()
    if role not in _ADMIN_OPERATOR_CREATE_ROLES:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid field: role", "errorCode": "invalid_operator_role", "reason": "role must be one of: owner, grant_admin, auditor."},
        )
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise HTTPException(status_code=400, detail={"error": "Invalid field: tenantId", "errorCode": "invalid_field", "reason": "tenantId must be a non-empty string."})

    # A tenant-scoped admin may only create operators within its own tenant;
    # the body-supplied tenant_id must not let it escalate into another tenant.
    scope.assert_target(tenant_id.strip())

    try:
        op, returned_token = await svc.create_operator(
            name=name.strip(),
            role=role,
            tenant_id=tenant_id.strip(),
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"error": "Operator creation failed", "errorCode": "operator_create_failed", "reason": "Failed to create operator."},
        )

    safe_log(_logger, "info", "operator_action", action="operator_created", operator_id=op.operator_id, tenant_id=op.tenant_id)
    event = AuditEvent(
        subject_id="admin",
        role="admin",
        action="operator_created",
        resource=f"operator/{op.operator_id}",
        approved=True,
        reason="Admin created operator.",
        tenant_id=op.tenant_id,
        scope="tenant_admin",
    )
    await db.run_sync(lambda sync_sess: append_event(event, conn=sync_sess.connection()))
    return {
        "operatorId": op.operator_id,
        "name": op.name,
        "role": op.role,
        "active": op.active,
        "tenantId": op.tenant_id,
        "createdAt": op.created_at,
        "expiresAt": op.expires_at,
        "token": returned_token,
    }


@router.post("/operators/{operator_id}/revoke", response_model=DynamicResponse)
async def revoke_operator_endpoint(
    operator_id: str,
    scope: AdminScope = Depends(require_admin_scope),
    svc: AsyncOperatorService = Depends(get_async_operator_service),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    # Resolve the target operator's tenant and enforce scope BEFORE the write, so a
    # tenant-scoped admin can never revoke another tenant's operator (cross-tenant DoS).
    op_safe = await svc.get_operator_safe(operator_id)
    if op_safe is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Operator not found", "errorCode": "operator_not_found", "reason": "The requested operator does not exist."},
        )
    scope.assert_target(op_safe.get("tenantId"))

    revoked = await svc.revoke_operator(operator_id)
    if not revoked:
        raise HTTPException(
            status_code=404,
            detail={"error": "Operator not found", "errorCode": "operator_not_found", "reason": "The requested operator does not exist."},
        )
    safe_log(_logger, "info", "operator_action", action="operator_revoked", operator_id=operator_id)
    event = AuditEvent(
        subject_id="admin",
        role="admin",
        action="operator_revoked",
        resource=f"operator/{operator_id}",
        approved=True,
        reason="Admin revoked operator.",
        tenant_id=op_safe.get("tenantId"),
        scope="tenant_admin",
    )
    await db.run_sync(lambda sync_sess: append_event(event, conn=sync_sess.connection()))
    return {"ok": True, "operatorId": operator_id, "revoked": True}
