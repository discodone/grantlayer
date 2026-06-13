"""Approvals lifecycle and evaluation endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException

from ...policy.approval_lifecycle import (
    build_approval_request_lifecycle,
    transition_approval_request,
)
from ...policy.approval_rules import evaluate_approval_requirements
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/lifecycle/build")
def build_lifecycle(
    body: dict,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    return build_approval_request_lifecycle(
        approval_requirement=body.get("approvalRequirement"),
        request_id=body.get("requestId"),
        action=body.get("action"),
        actor_id=body.get("actorId"),
        subject_id=body.get("subjectId"),
        requested_by=body.get("requestedBy"),
        approvers=body.get("approvers"),
        status=body.get("status"),
        created_at=body.get("createdAt"),
        expires_at=body.get("expiresAt"),
        context=body.get("context"),
        include_details=body.get("includeDetails", True),
    )


@router.post("/lifecycle/transition")
def transition_lifecycle(
    body: dict,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    missing = [f for f in ("approvalRequest", "transition") if f not in body or body.get(f) is None]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Missing fields: {missing}", "errorCode": "missing_required_fields", "reason": f"The following required fields are missing: {missing}."},
        )
    return transition_approval_request(
        approval_request=body["approvalRequest"],
        transition=body["transition"],
        actor_id=body.get("actorId"),
        reason=body.get("reason"),
        at=body.get("at"),
        context=body.get("context"),
        include_details=body.get("includeDetails", True),
    )


@router.post("/evaluate")
def evaluate_approvals(
    body: dict,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin"])
    missing = [f for f in ("action",) if f not in body or body.get(f) is None]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Missing fields: {missing}", "errorCode": "missing_required_fields", "reason": f"The following required fields are missing: {missing}."},
        )
    return evaluate_approval_requirements(
        action=body["action"],
        actor_id=body.get("actorId"),
        amount=body.get("amount"),
        currency=body.get("currency"),
        risk_level=body.get("riskLevel"),
        compliance_report=body.get("complianceReport"),
        evidence_completeness=body.get("evidenceCompleteness"),
        permission_result=body.get("permissionResult"),
        policy_flags=body.get("policyFlags"),
        context=body.get("context"),
        include_details=body.get("includeDetails", True),
    )
