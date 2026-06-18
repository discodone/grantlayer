"""Grants CRUD endpoints (FastAPI)."""

from __future__ import annotations

import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from ...core import config
from ...core.crypto_signing import verify_grant_signature
from ...core.models import Grant
from ...core.validation import (
    MAX_NAME_LENGTH,
    MAX_REASON_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_SHORT_ID_LENGTH,
    validate_string_length,
)
from ...grants.grant_requests import ALLOWED_GRANT_ROLES
from ...grants.grant_service import AsyncGrantService
from ...policy.opa_client import evaluate_policy
from ..deps import enforce_api_key_write_scope, get_async_grant_service, resolve_auth_and_workspace
from ..schemas import GrantCreateRequest, GrantListResponse, GrantResponse

router = APIRouter(prefix="/grants", tags=["grants"])


# ── Shared helpers ────────────────────────────────────────────────────────


def _validate_iso_timestamp(value: str, field_name: str) -> None:
    """Raise HTTPException 400 if *value* is not a parseable ISO-8601 timestamp."""
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Invalid {field_name}",
                "errorCode": "invalid_timestamp",
                "reason": f"{field_name} must be a valid ISO-8601 timestamp.",
            },
        )
    try:
        v = value.replace("Z", "+00:00") if value.endswith("Z") else value
        datetime.datetime.fromisoformat(v)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Invalid {field_name}",
                "errorCode": "invalid_timestamp",
                "reason": f"{field_name} must be a valid ISO-8601 timestamp.",
            },
        )


def _validate_grant_dates(valid_from: str, valid_until: str) -> None:
    _validate_iso_timestamp(valid_from, "validFrom")
    _validate_iso_timestamp(valid_until, "validUntil")
    vf = datetime.datetime.fromisoformat(valid_from.replace("Z", "+00:00") if valid_from.endswith("Z") else valid_from)
    vu = datetime.datetime.fromisoformat(valid_until.replace("Z", "+00:00") if valid_until.endswith("Z") else valid_until)
    if vf >= vu:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid date range",
                "errorCode": "invalid_date_range",
                "reason": "validFrom must be strictly before validUntil.",
            },
        )


def _grant_to_response(grant: Grant) -> GrantResponse:
    sig_result = verify_grant_signature(grant)
    return GrantResponse.from_grant(grant, signature_valid=(sig_result == "valid"))


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("", response_model=GrantListResponse, response_model_by_alias=True)
async def list_grants_endpoint(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    svc: AsyncGrantService = Depends(get_async_grant_service),
):
    """List all grants visible to the authenticated operator."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    grants, total = await svc.list_grants(
        tenant_id=ws_ctx["tenant_id"],
        workspace_id=ws_ctx["workspace_id"],
        limit=limit,
        offset=offset,
    )
    items = [_grant_to_response(g) for g in grants]
    next_offset = offset + limit
    next_cursor = str(next_offset) if next_offset < total else None
    return GrantListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        nextCursor=next_cursor,
    )


@router.get("/{grant_id}", response_model=GrantResponse, response_model_by_alias=True)
async def get_grant_endpoint(
    grant_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    svc: AsyncGrantService = Depends(get_async_grant_service),
):
    """Retrieve a single grant by ID."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    grant = await svc.get_grant(
        grant_id,
        tenant_id=ws_ctx["tenant_id"],
        workspace_id=ws_ctx["workspace_id"],
    )
    if grant is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Grant not found",
                "errorCode": "grant_not_found",
                "reason": "The requested grant does not exist.",
            },
        )
    return _grant_to_response(grant)


@router.post(
    "",
    response_model=GrantResponse,
    response_model_by_alias=True,
    status_code=201,
)
async def create_grant_endpoint(
    body: GrantCreateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    svc: AsyncGrantService = Depends(get_async_grant_service),
):
    """Create a new grant."""
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin"],
        workspace_id=x_workspace_id,
    )
    enforce_api_key_write_scope(auth_ctx)
    allowed = await evaluate_policy(
        "grant.create",
        {"role": auth_ctx.get("role"), "workspace_id": ws_ctx.get("workspace_id"),
         "tenant_id": ws_ctx.get("tenant_id"), "scopes": auth_ctx.get("scopes", [])},
        {"workspace_id": ws_ctx.get("workspace_id"), "tenant_id": ws_ctx.get("tenant_id")},
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={"error": "Forbidden", "errorCode": "policy_denied",
                    "reason": "Policy denied action 'grant.create'."},
        )

    # Validate that string fields are non-empty
    for alias, value in (
        ("subjectId", body.subject_id),
        ("role", body.role),
        ("action", body.action),
        ("resource", body.resource),
        ("createdBy", body.created_by),
        ("reason", body.reason),
    ):
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Invalid field: {alias}",
                    "errorCode": "invalid_field",
                    "reason": f"{alias} must be a non-empty string.",
                },
            )

    # Field length validation (belt-and-suspenders after Pydantic max_length)
    for field_name, value, max_len in (
        ("subjectId", body.subject_id, MAX_SHORT_ID_LENGTH),
        ("role", body.role, MAX_ROLE_LENGTH),
        ("action", body.action, MAX_NAME_LENGTH),
        ("resource", body.resource, MAX_NAME_LENGTH),
        ("createdBy", body.created_by, MAX_SHORT_ID_LENGTH),
        ("reason", body.reason, MAX_REASON_LENGTH),
    ):
        try:
            validate_string_length(value, field_name, max_len)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Invalid field: {field_name}",
                    "errorCode": "invalid_field",
                    "reason": str(exc),
                },
            ) from exc

    if body.role not in ALLOWED_GRANT_ROLES:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Invalid field: role",
                "errorCode": "invalid_role",
                "reason": f"role must be one of: {sorted(ALLOWED_GRANT_ROLES)}",
            },
        )

    _validate_grant_dates(body.valid_from, body.valid_until)

    operator_id = auth_ctx.get("operator", {}).get("operatorId") if config.ENABLE_OPERATOR_MODEL else None

    grant = Grant(
        subject_id=body.subject_id,
        role=body.role,
        action=body.action,
        resource=body.resource,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        created_by=operator_id if operator_id else body.created_by,
        reason=body.reason,
        max_uses=body.max_uses,
    )
    grant = await svc.create_grant(
        grant,
        tenant_id=ws_ctx["tenant_id"],
        workspace_id=ws_ctx["workspace_id"],
        operator_id=operator_id,
    )
    return _grant_to_response(grant)


@router.post("/{grant_id}/revoke", response_model=GrantResponse, response_model_by_alias=True)
async def revoke_grant_endpoint(
    grant_id: str,
    reason: Annotated[Optional[str], Body(embed=True)] = None,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    svc: AsyncGrantService = Depends(get_async_grant_service),
):
    """Revoke an existing grant."""
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin"],
        workspace_id=x_workspace_id,
    )
    enforce_api_key_write_scope(auth_ctx)
    operator_id = auth_ctx.get("sub") or auth_ctx.get("operator", {}).get("operatorId", "unknown")
    revoked = await svc.revoke_grant(
        grant_id,
        tenant_id=ws_ctx["tenant_id"],
        workspace_id=ws_ctx["workspace_id"],
        revoked_by=operator_id,
        reason=reason or "revoked via API",
    )
    if not revoked:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Grant not found",
                "errorCode": "grant_not_found",
                "reason": "The requested grant does not exist or is already revoked.",
            },
        )
    grant = await svc.get_grant(
        grant_id,
        tenant_id=ws_ctx["tenant_id"],
        workspace_id=ws_ctx["workspace_id"],
    )
    if grant is None:
        raise HTTPException(status_code=404, detail={"error": "Grant not found", "errorCode": "grant_not_found"})
    return _grant_to_response(grant)
