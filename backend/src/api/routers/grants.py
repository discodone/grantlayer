"""GL-228: Grants CRUD endpoints (FastAPI)."""

from __future__ import annotations

import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from ... import config
from ...auth import (
    check_auth,
    resolve_workspace_context,
    check_workspace_resource_access,
)
from ...crypto_signing import verify_grant_signature
from ...grants import create_grant, get_grant, list_grants
from ...models import Grant
from ...validation import (
    MAX_NAME_LENGTH,
    MAX_REASON_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_SHORT_ID_LENGTH,
    validate_string_length,
)
from ..schemas import ErrorResponse, GrantCreateRequest, GrantResponse

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


def _resolve_auth_and_workspace(
    authorization: Optional[str],
    required_roles: list[str],
    workspace_id: Optional[str] = None,
):
    """Authenticate the request and resolve workspace context.

    Returns (auth_ctx, ws_ctx).  Raises HTTPException on any failure.
    """
    ok, http_status, payload = check_auth(authorization, required_roles=required_roles)
    if not ok:
        raise HTTPException(status_code=http_status, detail=payload)

    ws_id, ws_status, ws_ctx = resolve_workspace_context(payload, workspace_id)

    if ws_status != 200:
        error_code = ws_ctx.get("errorCode", "")
        # Pre-workspace-enforcement backward compat (mirrors server.py _resolve_workspace)
        if error_code in ("no_workspace_membership", "workspace_id_required"):
            tenant_id = payload.get("tenant_id") or "demo"
            if tenant_id != "demo":
                from ...db import query_all as _qa
                tenant_has_ws = _qa(
                    "SELECT id FROM workspaces WHERE tenant_id = ? AND status = 'active' LIMIT 1",
                    (tenant_id,),
                )
                if not tenant_has_ws:
                    ws_ctx = {
                        "workspace_id": "default",
                        "tenant_id": tenant_id,
                        "workspace_member_role": None,
                        "cross_workspace_access": False,
                        "resolution_mode": "no_tenant_workspaces_fallback",
                    }
                    return payload, ws_ctx
        raise HTTPException(status_code=ws_status, detail=ws_ctx)

    return payload, ws_ctx


def _grant_to_response(grant: Grant) -> GrantResponse:
    sig_result = verify_grant_signature(grant)
    return GrantResponse.from_grant(grant, signature_valid=(sig_result == "valid"))


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("", response_model=List[GrantResponse], response_model_by_alias=True)
def list_grants_endpoint(
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
):
    """List all grants visible to the authenticated operator."""
    _, ws_ctx = _resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    grants = list_grants(tenant_id=tenant_id)
    return [_grant_to_response(g) for g in grants]


@router.get("/{grant_id}", response_model=GrantResponse, response_model_by_alias=True)
def get_grant_endpoint(
    grant_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
):
    """Retrieve a single grant by ID."""
    _, ws_ctx = _resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    grant = get_grant(grant_id, tenant_id=tenant_id)
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
def create_grant_endpoint(
    body: GrantCreateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
):
    """Create a new grant."""
    auth_ctx, ws_ctx = _resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]

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
    create_grant(grant, tenant_id=tenant_id)
    return _grant_to_response(grant)
