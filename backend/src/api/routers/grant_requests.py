"""Grant requests endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ...core import config
from ...core.models import GrantRequest
from ...core.validation import (
    MAX_NAME_LENGTH,
    MAX_REASON_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_SHORT_ID_LENGTH,
    validate_string_length,
)
from ...grants.grant_request_service import AsyncGrantRequestService
from ...grants.grant_requests import ALLOWED_GRANT_ROLES, VALID_REQUEST_STATUSES
from ..deps import (
    enforce_workspace_mutation,
    get_async_grant_request_service,
    require_mutation_authz,
    resolve_auth_and_workspace,
)
from ..schemas import DynamicResponse, GrantRequestListResponse, GrantRequestResponse
from ..schemas import _validate_grant_dates as _validate_dates

router = APIRouter(prefix="/grant-requests", tags=["grant-requests"])

_OPERATOR_REQUIRED = {"error": "Operator model is disabled", "errorCode": "operator_model_disabled", "reason": "The operator model is not enabled on this instance."}


def _require_operator_model() -> None:
    if not config.ENABLE_OPERATOR_MODEL:
        raise HTTPException(status_code=404, detail=_OPERATOR_REQUIRED)


class GrantRequestCreateRequest(BaseModel):
    subject_id: str = Field(alias="subjectId", max_length=MAX_SHORT_ID_LENGTH)
    role: str = Field(max_length=MAX_ROLE_LENGTH)
    action: str = Field(max_length=MAX_NAME_LENGTH)
    resource: str = Field(max_length=MAX_NAME_LENGTH)
    valid_from: str = Field(alias="validFrom")
    valid_until: str = Field(alias="validUntil")
    reason: str = Field(max_length=MAX_REASON_LENGTH)

    model_config = {"populate_by_name": True}


class DenyRequest(BaseModel):
    reason: str = Field(max_length=MAX_REASON_LENGTH)


@router.get("", response_model=GrantRequestListResponse, response_model_by_alias=True)
async def list_grant_requests_endpoint(
    status: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    svc: AsyncGrantRequestService = Depends(get_async_grant_request_service),
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    if status is not None and status not in VALID_REQUEST_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid query parameter: status",
                "errorCode": "invalid_query_parameter",
                "reason": f"status must be one of: {sorted(VALID_REQUEST_STATUSES)}",
            },
        )
    requests, total = await svc.list_requests(
        tenant_id=ws_ctx["tenant_id"],
        workspace_id=ws_ctx["workspace_id"],
        status_filter=status,
        limit=limit,
        offset=offset,
    )
    return GrantRequestListResponse(
        items=[GrantRequestResponse.from_grant_request(r) for r in requests],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{request_id}", response_model=GrantRequestResponse, response_model_by_alias=True)
async def get_grant_request_endpoint(
    request_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    svc: AsyncGrantRequestService = Depends(get_async_grant_request_service),
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    req = await svc.get_request(
        request_id,
        tenant_id=ws_ctx["tenant_id"],
        workspace_id=ws_ctx["workspace_id"],
    )
    if req is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Grant request not found",
                "errorCode": "grant_request_not_found",
                "reason": "The requested grant request does not exist.",
            },
        )
    return GrantRequestResponse.from_grant_request(req)


@router.post("", status_code=201, response_model=GrantRequestResponse, response_model_by_alias=True)
async def create_grant_request_endpoint(
    body: GrantRequestCreateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    svc: AsyncGrantRequestService = Depends(get_async_grant_request_service),
) -> Any:
    _require_operator_model()
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin"],
        workspace_id=x_workspace_id,
    )
    await require_mutation_authz(auth_ctx, ws_ctx)
    operator_id = auth_ctx.get("operator", {}).get("operatorId") or auth_ctx.get("sub")
    if not operator_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "Cannot determine caller identity", "errorCode": "missing_caller_identity", "reason": "operator_id could not be resolved from the authentication token."},
        )

    for alias, value in (
        ("subjectId", body.subject_id),
        ("role", body.role),
        ("action", body.action),
        ("resource", body.resource),
        ("reason", body.reason),
    ):
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(
                status_code=400,
                detail={"error": f"Invalid field: {alias}", "errorCode": "invalid_field", "reason": f"{alias} must be a non-empty string."},
            )

    for field_name, value, max_len in (
        ("subjectId", body.subject_id, MAX_SHORT_ID_LENGTH),
        ("role", body.role, MAX_ROLE_LENGTH),
        ("action", body.action, MAX_NAME_LENGTH),
        ("resource", body.resource, MAX_NAME_LENGTH),
        ("reason", body.reason, MAX_REASON_LENGTH),
    ):
        try:
            validate_string_length(value, field_name, max_len)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": f"Invalid field: {field_name}", "errorCode": "invalid_field", "reason": str(exc)},
            ) from exc

    if body.role not in ALLOWED_GRANT_ROLES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid field: role",
                "errorCode": "invalid_field",
                "reason": f"role must be one of: {sorted(ALLOWED_GRANT_ROLES)}",
            },
        )

    _validate_dates(body.valid_from, body.valid_until)

    req = GrantRequest(
        subject_id=body.subject_id,
        role=body.role,
        action=body.action,
        resource=body.resource,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        requested_by=operator_id,
        reason=body.reason,
    )
    created = await svc.create_request(req, ws_ctx["tenant_id"], ws_ctx["workspace_id"])
    return GrantRequestResponse.from_grant_request(created)


@router.post("/{request_id}/approve", response_model=DynamicResponse)
async def approve_grant_request_endpoint(
    request_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    svc: AsyncGrantRequestService = Depends(get_async_grant_request_service),
) -> Any:
    _require_operator_model()
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin"],
        workspace_id=x_workspace_id,
    )
    await require_mutation_authz(auth_ctx, ws_ctx)
    operator_id = auth_ctx.get("operator", {}).get("operatorId") or auth_ctx.get("sub")
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]
    if not operator_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "Cannot determine caller identity", "errorCode": "missing_caller_identity", "reason": "operator_id could not be resolved from the authentication token."},
        )

    req = await svc.get_request(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
    if req is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Grant request not found", "errorCode": "grant_request_not_found", "reason": "The requested grant request does not exist."},
        )

    if req.requested_by == operator_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Cannot approve your own request",
                "errorCode": "self_approval_forbidden",
                "reason": "An operator cannot approve their own grant request.",
                "requestedBy": req.requested_by,
                "approverId": operator_id,
            },
        )

    enforce_workspace_mutation(ws_ctx, auth_ctx)

    try:
        updated_req, new_grant = await svc.approve_request(
            request_id, operator_id, tenant_id=tenant_id, workspace_id=workspace_id
        )
        return {
            "ok": True,
            "request": GrantRequestResponse.from_grant_request(updated_req).model_dump(by_alias=True),
            "grant": new_grant.to_dict(),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": str(exc), "errorCode": "invalid_request", "reason": str(exc)},
        ) from exc


@router.post("/{request_id}/deny", response_model=DynamicResponse)
async def deny_grant_request_endpoint(
    request_id: str,
    body: DenyRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    svc: AsyncGrantRequestService = Depends(get_async_grant_request_service),
) -> Any:
    _require_operator_model()
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin"],
        workspace_id=x_workspace_id,
    )
    await require_mutation_authz(auth_ctx, ws_ctx)
    operator_id = auth_ctx.get("operator", {}).get("operatorId") or auth_ctx.get("sub")
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]
    if not operator_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "Cannot determine caller identity", "errorCode": "missing_caller_identity", "reason": "operator_id could not be resolved from the authentication token."},
        )

    req = await svc.get_request(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
    if req is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Grant request not found", "errorCode": "grant_request_not_found", "reason": "The requested grant request does not exist."},
        )

    if not body.reason or not str(body.reason).strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "Denial reason is required", "errorCode": "missing_denial_reason", "reason": "A reason is required when denying a grant request."},
        )

    try:
        validate_string_length(body.reason, "reason", MAX_REASON_LENGTH)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid field", "errorCode": "invalid_field", "reason": str(exc)},
        ) from exc

    enforce_workspace_mutation(ws_ctx, auth_ctx)

    try:
        updated_req = await svc.deny_request(
            request_id, operator_id, body.reason, tenant_id=tenant_id, workspace_id=workspace_id
        )
        return {"ok": True, "request": GrantRequestResponse.from_grant_request(updated_req).model_dump(by_alias=True)}
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": str(exc), "errorCode": "invalid_request", "reason": str(exc)},
        ) from exc
