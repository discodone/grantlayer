"""Grants CRUD endpoints (FastAPI)."""

from __future__ import annotations

import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from ...audit import audit_log as _audit_log
from ...core import config
from ...core.crypto_signing import sign_grant as _sign_grant
from ...core.crypto_signing import verify_grant_signature
from ...core.db import get_db
from ...core.models import AuditEvent, Grant
from ...core.repositories import IGrantRepository
from ...core.validation import (
    MAX_NAME_LENGTH,
    MAX_REASON_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_SHORT_ID_LENGTH,
    validate_string_length,
)
from ...grants.grant_requests import ALLOWED_GRANT_ROLES
from ..deps import get_grant_repo, resolve_auth_and_workspace
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
def list_grants_endpoint(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    grant_repo: IGrantRepository = Depends(get_grant_repo),
):
    """List all grants visible to the authenticated operator."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]
    grants = grant_repo.list(tenant_id=tenant_id, workspace_id=workspace_id, limit=limit, offset=offset)
    return GrantListResponse(
        items=[_grant_to_response(g) for g in grants],
        total=grant_repo.count(tenant_id=tenant_id, workspace_id=workspace_id),
        limit=limit,
        offset=offset,
    )


@router.get("/{grant_id}", response_model=GrantResponse, response_model_by_alias=True)
def get_grant_endpoint(
    grant_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    grant_repo: IGrantRepository = Depends(get_grant_repo),
):
    """Retrieve a single grant by ID."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]
    grant = grant_repo.get(grant_id, tenant_id=tenant_id, workspace_id=workspace_id)
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
    db: Session = Depends(get_db),
    grant_repo: IGrantRepository = Depends(get_grant_repo),
):
    """Create a new grant."""
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]

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
    sig_hex, hash_hex, key_id = _sign_grant(grant)
    grant.signature = sig_hex
    grant.payload_hash = hash_hex
    grant.signing_key_id = key_id
    grant_repo.create(grant, tenant_id, workspace_id)
    _audit_log.append_event(
        AuditEvent(
            subject_id=grant.subject_id,
            role=grant.role,
            action=grant.action,
            resource=grant.resource,
            approved=True,
            reason=f"grant_created: {grant.reason}",
            matched_grant_id=grant.id,
            grant_signature_result="valid",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        ),
        conn=db.connection(),
    )
    return _grant_to_response(grant)
