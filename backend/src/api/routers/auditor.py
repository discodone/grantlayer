"""Auditor report and export endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from ...audit.auditor_export import build_institutional_auditor_export
from ...audit.auditor_report import build_auditor_report_for_execution
from ...grants.grant_executions import get_grant_execution
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/auditor", tags=["auditor"])


@router.get("/reports/executions/{execution_id}", response_model=dict[str, Any])
def get_auditor_report(
    execution_id: str,
    include_raw_evidence: bool = Query(default=False, alias="includeRawEvidence"),
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
    report = build_auditor_report_for_execution(execution_id, include_raw_evidence=include_raw_evidence)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist or has no linked provenance records."},
        )
    return report


@router.post("/exports/build", response_model=dict[str, Any])
def build_auditor_export(
    body: dict,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin", "auditor"])
    return build_institutional_auditor_export(
        export_id=body.get("exportId"),
        export_type=body.get("exportType"),
        subject_id=body.get("subjectId"),
        decision_id=body.get("decisionId"),
        generated_by=body.get("generatedBy"),
        auditor_id=body.get("auditorId"),
        decision_provenance=body.get("decisionProvenance"),
        auditor_report=body.get("auditorReport"),
        evidence_completeness=body.get("evidenceCompleteness"),
        compliance_gap_report=body.get("complianceGapReport"),
        permission_result=body.get("permissionResult"),
        approval_requirement=body.get("approvalRequirement"),
        approval_lifecycle=body.get("approvalLifecycle"),
        policy_results=body.get("policyResults"),
        metadata=body.get("metadata"),
        context=body.get("context"),
        created_at=body.get("createdAt"),
        include_details=body.get("includeDetails", True),
    )
