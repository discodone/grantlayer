"""Decision provenance v2 endpoint (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header

from ...policy.decision_provenance import build_decision_provenance_v2
from ..deps import require_mutation_authz, resolve_auth_and_workspace

router = APIRouter(prefix="/decision-provenance", tags=["decision-provenance"])


@router.post("/v2/build", response_model=dict[str, Any])
async def build_provenance_v2(
    body: dict,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    auth_ctx, ws_ctx = resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin", "auditor"])
    await require_mutation_authz(auth_ctx, ws_ctx)
    return build_decision_provenance_v2(
        decision_id=body.get("decisionId"),
        decision_type=body.get("decisionType"),
        subject_id=body.get("subjectId"),
        actor_id=body.get("actorId"),
        action=body.get("action"),
        decision=body.get("decision"),
        reason=body.get("reason"),
        evidence_completeness=body.get("evidenceCompleteness"),
        compliance_gap_report=body.get("complianceGapReport"),
        permission_result=body.get("permissionResult"),
        approval_requirement=body.get("approvalRequirement"),
        approval_lifecycle=body.get("approvalLifecycle"),
        provenance_summary=body.get("provenanceSummary"),
        auditor_report=body.get("auditorReport"),
        policy_results=body.get("policyResults"),
        inputs=body.get("inputs"),
        context=body.get("context"),
        created_at=body.get("createdAt"),
        include_details=body.get("includeDetails", True),
    )
