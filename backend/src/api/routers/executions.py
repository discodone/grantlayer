"""GL-229: Grant executions endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from ... import config
from ...grant_executions import (
    get_grant_execution,
    list_grant_executions,
    list_grant_executions_for_grant,
)
from ...grants import get_grant
from ..deps import resolve_auth_and_workspace

router = APIRouter(tags=["executions"])

_OPERATOR_REQUIRED = {"error": "Operator model is disabled", "errorCode": "operator_model_disabled", "reason": "The operator model is not enabled on this instance."}


def _require_operator_model() -> None:
    if not config.ENABLE_OPERATOR_MODEL:
        raise HTTPException(status_code=404, detail=_OPERATOR_REQUIRED)


@router.get("/grant-executions")
def list_executions_endpoint(
    grant_id: Optional[str] = Query(default=None, alias="grantId"),
    operator_id: Optional[str] = Query(default=None, alias="operatorId"),
    limit: Optional[int] = Query(default=200, ge=1, le=1000),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _require_operator_model()
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    executions = list_grant_executions(
        grant_id=grant_id,
        operator_id=operator_id,
        limit=limit,
        tenant_id=tenant_id,
    )
    return [e.to_dict() for e in executions]


@router.get("/grant-executions/{execution_id}")
def get_execution_endpoint(
    execution_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _require_operator_model()
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    execution = get_grant_execution(execution_id, tenant_id=tenant_id)
    if execution is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Grant execution not found", "errorCode": "grant_execution_not_found", "reason": "The requested grant execution does not exist."},
        )
    return execution.to_dict()


@router.get("/grants/{grant_id}/executions")
def list_executions_for_grant_endpoint(
    grant_id: str,
    limit: Optional[int] = Query(default=200, ge=1, le=1000),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    _require_operator_model()
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    grant = get_grant(grant_id, tenant_id=tenant_id)
    if grant is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Grant not found", "errorCode": "grant_not_found", "reason": "The requested grant does not exist."},
        )
    executions = list_grant_executions_for_grant(grant_id, limit=limit, tenant_id=tenant_id)
    return [e.to_dict() for e in executions]
