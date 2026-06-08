"""GL-229: Challenges endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ...challenges import create_challenge, list_challenges
from ...validation import MAX_NAME_LENGTH, MAX_SHORT_ID_LENGTH, validate_string_length
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/challenges", tags=["challenges"])


class ChallengeCreateRequest(BaseModel):
    subject_id: str = Field(alias="subjectId", max_length=MAX_SHORT_ID_LENGTH)
    action: str = Field(max_length=MAX_NAME_LENGTH)
    resource: str = Field(max_length=MAX_NAME_LENGTH)

    model_config = {"populate_by_name": True}


@router.get("")
def list_challenges_endpoint(
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    return [c.to_dict() for c in list_challenges(tenant_id=tenant_id)]


@router.post("", status_code=201)
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

    challenge = create_challenge(body.subject_id, body.action, body.resource, tenant_id=tenant_id)
    return {
        "challengeId": challenge.id,
        "subjectId": challenge.subject_id,
        "action": challenge.action,
        "resource": challenge.resource,
        "expiresAt": challenge.expires_at,
    }
