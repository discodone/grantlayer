"""Compliance gaps and readiness endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from ...grants.grant_executions import get_grant_execution
from ...policy.compliance_gap_report import build_compliance_gap_report_for_execution
from ...policy.compliance_readiness import build_compliance_readiness_summary
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/gaps/executions/{execution_id}", response_model=dict[str, Any])
def compliance_gaps(
    execution_id: str,
    include_details: bool = Query(default=True, alias="includeDetails"),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    if get_grant_execution(execution_id, tenant_id=tenant_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist or has no linked provenance records."},
        )
    report = build_compliance_gap_report_for_execution(execution_id, include_details=include_details)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist or has no linked provenance records."},
        )
    return report


@router.post("/readiness/build", response_model=dict[str, Any])
def build_readiness(
    body: dict,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin", "auditor"])
    policy_req_eval = body.get("policyRequirementEvaluation")
    summary = build_compliance_readiness_summary(
        subject_id=body.get("subjectId"),
        workflow_id=body.get("workflowId"),
        evidence_completeness=body.get("evidenceCompleteness"),
        compliance_gap_report=body.get("complianceGapReport"),
        permission_result=body.get("permissionResult"),
        approval_requirement=body.get("approvalRequirement"),
        approval_lifecycle=body.get("approvalLifecycle"),
        provenance_summary=body.get("decisionProvenance"),
        auditor_report=body.get("auditorExport"),
        policy_results=[policy_req_eval] if policy_req_eval is not None else None,
        context=body.get("context"),
        created_at=body.get("createdAt"),
        include_details=body.get("includeDetails", True),
    )
    # Map builder output field names to API contract (mirrors server.py exactly)
    if summary.get("readinessStatus") == "not_assessed":
        summary["readinessStatus"] = "insufficient_data"
    if "approval" in summary:
        approval = summary.pop("approval")
        if approval is not None:
            summary["approvalRequirement"] = approval.get("requirement")
            summary["approvalLifecycle"] = approval.get("lifecycle")
    if "provenance" in summary:
        summary["decisionProvenance"] = summary.pop("provenance")
    if "auditorReport" in summary:
        summary["auditorExport"] = summary.pop("auditorReport")
    if "policy" in summary:
        policy_list = summary.pop("policy")
        if policy_list and len(policy_list) > 0:
            summary["policyRequirementEvaluation"] = policy_list[0]
        else:
            summary["policyRequirementEvaluation"] = None
    return summary
