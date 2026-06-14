"""Demo endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ...core import config
from ...core.validation import (
    MAX_NAME_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_SHORT_ID_LENGTH,
    validate_optional_string_length,
    validate_string_length,
)
from ...demo.demo_action import handle_demo_action
from ...grants.grants import tamper_grant
from ..deps import resolve_auth_and_workspace
from ..schemas import DynamicResponse

router = APIRouter(tags=["demo"])

# Registered only when GRANTLAYER_ENABLE_DEMO_ENDPOINTS=true (see app.py).
# Kept separate so demo-action (always available) is not gated.
tamper_router = APIRouter(tags=["demo"])


class DemoActionRequest(BaseModel):
    subject_id: str = Field(alias="subjectId", max_length=MAX_SHORT_ID_LENGTH)
    role: str = Field(max_length=MAX_ROLE_LENGTH)
    action: str = Field(max_length=MAX_NAME_LENGTH)
    resource: str = Field(max_length=MAX_NAME_LENGTH)
    challenge_id: Optional[str] = Field(default=None, alias="challengeId", max_length=MAX_SHORT_ID_LENGTH)

    model_config = {"populate_by_name": True}


@tamper_router.post("/demo/tamper-grant/{grant_id}", response_model=DynamicResponse)
def tamper_grant_endpoint(
    grant_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "demo_operator"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    result = tamper_grant(grant_id, tenant_id=tenant_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Grant not found", "errorCode": "grant_not_found", "reason": "The requested grant does not exist."},
        )
    return result


@router.post("/demo-action", response_model=dict[str, Any])
def demo_action_endpoint(
    body: DemoActionRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    auth_ctx, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin"],
        workspace_id=x_workspace_id,
    )
    caller_operator_id: Optional[str] = None
    if config.ENABLE_OPERATOR_MODEL:
        caller_operator_id = auth_ctx.get("operator", {}).get("operatorId")
    tenant_id = ws_ctx["tenant_id"]

    for field_name, value, max_len in (
        ("subjectId", body.subject_id, MAX_SHORT_ID_LENGTH),
        ("role", body.role, MAX_ROLE_LENGTH),
        ("action", body.action, MAX_NAME_LENGTH),
        ("resource", body.resource, MAX_NAME_LENGTH),
    ):
        try:
            validate_string_length(value, field_name, max_len)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": f"Invalid field: {field_name}", "errorCode": "invalid_field", "reason": str(exc)},
            ) from exc

    try:
        validate_optional_string_length(body.challenge_id, "challengeId", MAX_SHORT_ID_LENGTH)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid field", "errorCode": "invalid_field", "reason": str(exc)},
        ) from exc

    result = handle_demo_action(
        subject_id=body.subject_id,
        role=body.role,
        action=body.action,
        resource=body.resource,
        challenge_id=body.challenge_id,
        operator_id=caller_operator_id,
        tenant_id=tenant_id,
    )
    status_code = 200 if result["approved"] else 403
    from fastapi.responses import JSONResponse
    return JSONResponse(content=result, status_code=status_code)
