"""Evidence bundle endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional
from urllib.parse import quote as _urlquote

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response

from ...evidence.evidence_bundle import build_evidence_bundle, export_bundle_json
from ...evidence.evidence_completeness import build_evidence_completeness_for_execution
from ...evidence.evidence_verification import verify_execution
from ...grants.grant_executions import get_grant_execution
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/evidence/executions", tags=["evidence"])

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}


def _check_execution_tenant(execution_id: str, tenant_id: str) -> None:
    if get_grant_execution(execution_id, tenant_id=tenant_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist."},
        )


@router.get("/{execution_id}")
def get_evidence_bundle(
    execution_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    _check_execution_tenant(execution_id, tenant_id)
    bundle = build_evidence_bundle(execution_id)
    if bundle is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist."},
        )
    return bundle


@router.get("/{execution_id}/export")
def export_evidence_bundle(
    execution_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Response:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    _check_execution_tenant(execution_id, tenant_id)
    bundle = build_evidence_bundle(execution_id)
    if bundle is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist."},
        )
    body = export_bundle_json(bundle).encode("utf-8")
    evidence_hash = bundle.get("evidenceHash", "")
    short_hash = evidence_hash[:8] if evidence_hash else ""
    filename = _urlquote(f"evidence-{execution_id}-{short_hash}.json", safe="-_.")
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Evidence-Hash": evidence_hash,
        **_SECURITY_HEADERS,
    }
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers=headers,
    )


@router.get("/{execution_id}/verify")
def verify_evidence_bundle(
    execution_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    _check_execution_tenant(execution_id, tenant_id)
    return verify_execution(execution_id)


@router.get("/{execution_id}/completeness")
def evidence_completeness(
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
    _check_execution_tenant(execution_id, tenant_id)
    report = build_evidence_completeness_for_execution(execution_id, include_details=include_details)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist or has no linked provenance records."},
        )
    return report
