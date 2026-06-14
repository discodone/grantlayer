"""Challenges endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ...auth.challenges import count_challenges, create_challenge, list_challenges
from ...core.validation import MAX_NAME_LENGTH, MAX_SHORT_ID_LENGTH, validate_string_length
from ..deps import resolve_auth_and_workspace
from ..schemas import ChallengeCreateResponse, ChallengeListResponse, ChallengeResponse

router = APIRouter(prefix="/challenges", tags=["challenges"])


class ChallengeCreateRequest(BaseModel):
    subject_id: str = Field(alias="subjectId", max_length=MAX_SHORT_ID_LENGTH)
    action: str = Field(max_length=MAX_NAME_LENGTH)
    resource: str = Field(max_length=MAX_NAME_LENGTH)

    model_config = {"populate_by_name": True}


@router.get("", response_model=ChallengeListResponse, response_model_by_alias=True)
def list_challenges_endpoint(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]
    return ChallengeListResponse(
        items=[ChallengeResponse(**c.to_dict()) for c in list_challenges(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            limit=limit,
            offset=offset,
        )],
        total=count_challenges(tenant_id=tenant_id, workspace_id=workspace_id),
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=201, response_model=ChallengeCreateResponse, response_model_by_alias=True)
def create_challenge_endpoint(
    body: ChallengeCreateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]

    for field_name, value, max_len in (
        ("subjectId", body.subject_id, MAX_SHORT_ID_LENGTH),
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

    challenge = create_challenge(
        body.subject_id,
        body.action,
        body.resource,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    return {
        "challengeId": challenge.id,
        "subjectId": challenge.subject_id,
        "action": challenge.action,
        "resource": challenge.resource,
        "expiresAt": challenge.expires_at,
    }
