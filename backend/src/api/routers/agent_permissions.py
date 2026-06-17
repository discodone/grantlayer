"""Agent permissions endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException

from ...policy.agent_permission_assignments import resolve_agent_permission_assignment
from ...policy.agent_permission_profiles import (
    get_agent_permission_profile,
    list_agent_permission_profiles,
)
from ...policy.agent_permissions import evaluate_agent_permission
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/agent-permissions", tags=["agent-permissions"])


@router.get("/profiles", response_model=list[dict[str, Any]])
async def list_profiles(
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    return list_agent_permission_profiles()


@router.get("/profiles/{profile_name}", response_model=dict[str, Any])
async def get_profile(
    profile_name: str,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    profile = get_agent_permission_profile(profile_name)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Profile not found",
                "errorCode": "profile_not_found",
                "reason": "The requested permission profile does not exist.",
                "profileName": profile_name,
            },
        )
    return profile


@router.post("/evaluate", response_model=dict[str, Any])
async def evaluate_permission(
    body: dict,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    missing = [f for f in ("agentId", "requestedScope", "assignedScopes") if f not in body or body.get(f) is None]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Missing fields: {missing}", "errorCode": "missing_required_fields", "reason": f"The following required fields are missing: {missing}."},
        )
    return evaluate_agent_permission(
        agent_id=body["agentId"],
        requested_scope=body["requestedScope"],
        assigned_scopes=body["assignedScopes"],
        resource_type=body.get("resourceType"),
        resource_id=body.get("resourceId"),
        context=body.get("context"),
    )


@router.post("/assignments/resolve", response_model=dict[str, Any])
async def resolve_assignment(
    body: dict,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    missing = [f for f in ("agentId", "requestedScope") if f not in body or body.get(f) is None]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Missing fields: {missing}", "errorCode": "missing_required_fields", "reason": f"The following required fields are missing: {missing}."},
        )
    return resolve_agent_permission_assignment(
        agent_id=body["agentId"],
        requested_scope=body["requestedScope"],
        assigned_scopes=body.get("assignedScopes"),
        assigned_profiles=body.get("assignedProfiles"),
        resource_type=body.get("resourceType"),
        resource_id=body.get("resourceId"),
        context=body.get("context"),
        include_details=body.get("includeDetails", True),
    )
