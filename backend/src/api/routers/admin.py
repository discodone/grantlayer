"""Admin control-plane operator management endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ...audit.audit_log import append_event
from ...auth.operator_service import OperatorService
from ...core.db import get_db
from ...core.logging_utils import get_logger, safe_log
from ...core.models import AuditEvent
from ..deps import get_operator_service, require_admin
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
def list_operators_endpoint(
    authorization: Annotated[Optional[str], Header()] = None,
    svc: OperatorService = Depends(get_operator_service),
) -> Any:
    require_admin(authorization)
    return svc.list_operators_for_admin()


@router.get("/operators/{operator_id}", response_model=dict[str, Any])
def get_operator_endpoint(
    operator_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    svc: OperatorService = Depends(get_operator_service),
) -> Any:
    require_admin(authorization)
    op_safe = svc.get_operator_safe(operator_id)
    if op_safe is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Operator not found", "errorCode": "operator_not_found", "reason": "The requested operator does not exist."},
        )
    return op_safe


@router.post("/operators", status_code=201, response_model=DynamicResponse)
def create_operator_endpoint(
    body: OperatorCreateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    svc: OperatorService = Depends(get_operator_service),
    db: Session = Depends(get_db),
) -> Any:
    require_admin(authorization)

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

    try:
        op, returned_token = svc.create_operator(
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
    append_event(
        AuditEvent(
            subject_id="admin",
            role="admin",
            action="operator_created",
            resource=f"operator/{op.operator_id}",
            approved=True,
            reason="Admin created operator.",
            tenant_id=op.tenant_id,
            scope="tenant_admin",
        ),
        conn=db.connection(),
    )
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
def revoke_operator_endpoint(
    operator_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    svc: OperatorService = Depends(get_operator_service),
    db: Session = Depends(get_db),
) -> Any:
    require_admin(authorization)
    revoked = svc.revoke_operator(operator_id)
    if not revoked:
        raise HTTPException(
            status_code=404,
            detail={"error": "Operator not found", "errorCode": "operator_not_found", "reason": "The requested operator does not exist."},
        )
    safe_log(_logger, "info", "operator_action", action="operator_revoked", operator_id=operator_id)
    op_safe = svc.get_operator_safe(operator_id) or {}
    append_event(
        AuditEvent(
            subject_id="admin",
            role="admin",
            action="operator_revoked",
            resource=f"operator/{operator_id}",
            approved=True,
            reason="Admin revoked operator.",
            tenant_id=op_safe.get("tenantId"),
            scope="tenant_admin",
        ),
        conn=db.connection(),
    )
    return {"ok": True, "operatorId": operator_id, "revoked": True}
