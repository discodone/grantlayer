"""Policy requirements evaluation endpoint (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header

from ...policy.policy_requirements import evaluate_policy_requirements
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/policy-requirements", tags=["policy-requirements"])


@router.post("/evaluate")
def evaluate_policy(
    body: dict,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin", "auditor"])
    return evaluate_policy_requirements(
        policy_pack=body.get("policyPack"),
        subject=body.get("subject"),
        evidence_completeness=body.get("evidenceCompleteness"),
        compliance_gap_report=body.get("complianceGapReport"),
        permission_result=body.get("permissionResult"),
        approval_requirement=body.get("approvalRequirement"),
        approval_lifecycle=body.get("approvalLifecycle"),
        decision_provenance=body.get("decisionProvenance"),
        auditor_export=body.get("auditorExport"),
        context=body.get("context"),
        created_at=body.get("createdAt"),
        include_details=body.get("includeDetails", True),
    )
