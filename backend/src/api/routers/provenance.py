"""Provenance endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from ... import config
from ...grant_executions import get_grant_execution
from ...provenance_summary import build_decision_provenance_summary
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/provenance", tags=["provenance"])


@router.get("/executions/{execution_id}/summary")
def provenance_summary(
    execution_id: str,
    include_timeline: bool = Query(default=True, alias="includeTimeline"),
    include_warnings: bool = Query(default=True, alias="includeWarnings"),
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

    # Mirror server.py: operator-model enforces tenant-scope; legacy mode allows orphan execution
    if get_grant_execution(execution_id, tenant_id=tenant_id) is None:
        if config.ENABLE_OPERATOR_MODEL or get_grant_execution(execution_id) is not None:
            raise HTTPException(
                status_code=404,
                detail={"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist or has no provenance records."},
            )

    summary = build_decision_provenance_summary(
        execution_id,
        include_timeline=include_timeline,
        include_warnings=include_warnings,
        include_raw_evidence=include_raw_evidence,
    )
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist or has no provenance records."},
        )
    return summary
