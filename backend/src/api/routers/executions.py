"""Grant executions endpoints (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ...core import config
from ...core.repositories_sqlalchemy import (
    SqlAlchemyAsyncGrantExecutionRepository,
    SqlAlchemyAsyncGrantRepository,
)
from ..deps import get_async_grant_execution_repo, get_async_grant_repo, resolve_auth_and_workspace
from ..schemas import GrantExecutionListResponse, GrantExecutionResponse

router = APIRouter(tags=["executions"])

_OPERATOR_REQUIRED = {"error": "Operator model is disabled", "errorCode": "operator_model_disabled", "reason": "The operator model is not enabled on this instance."}


def _require_operator_model() -> None:
    if not config.ENABLE_OPERATOR_MODEL:
        raise HTTPException(status_code=404, detail=_OPERATOR_REQUIRED)


@router.get("/grant-executions", response_model=GrantExecutionListResponse, response_model_by_alias=True)
async def list_executions_endpoint(
    grant_id: Optional[str] = Query(default=None, alias="grantId"),
    operator_id: Optional[str] = Query(default=None, alias="operatorId"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    exec_repo: SqlAlchemyAsyncGrantExecutionRepository = Depends(get_async_grant_execution_repo),
) -> Any:
    _require_operator_model()
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]
    executions = await exec_repo.list(
        grant_id=grant_id,
        operator_id=operator_id,
        limit=limit,
        offset=offset,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    return GrantExecutionListResponse(
        items=[GrantExecutionResponse(**e.to_dict()) for e in executions],
        total=await exec_repo.count(
            grant_id=grant_id,
            operator_id=operator_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        ),
        limit=limit,
        offset=offset,
    )


@router.get("/grant-executions/{execution_id}", response_model=GrantExecutionResponse, response_model_by_alias=True)
async def get_execution_endpoint(
    execution_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    exec_repo: SqlAlchemyAsyncGrantExecutionRepository = Depends(get_async_grant_execution_repo),
) -> Any:
    _require_operator_model()
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]
    execution = await exec_repo.get(execution_id, tenant_id=tenant_id, workspace_id=workspace_id)
    if execution is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Grant execution not found", "errorCode": "grant_execution_not_found", "reason": "The requested grant execution does not exist."},
        )
    return execution.to_dict()


@router.get("/grants/{grant_id}/executions", response_model=GrantExecutionListResponse, response_model_by_alias=True)
async def list_executions_for_grant_endpoint(
    grant_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
    grant_repo: SqlAlchemyAsyncGrantRepository = Depends(get_async_grant_repo),
    exec_repo: SqlAlchemyAsyncGrantExecutionRepository = Depends(get_async_grant_execution_repo),
) -> Any:
    _require_operator_model()
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]
    grant = await grant_repo.get(grant_id, tenant_id=tenant_id, workspace_id=workspace_id)
    if grant is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Grant not found", "errorCode": "grant_not_found", "reason": "The requested grant does not exist."},
        )
    executions = await exec_repo.list(
        grant_id=grant_id,
        limit=limit,
        offset=offset,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    return GrantExecutionListResponse(
        items=[GrantExecutionResponse(**e.to_dict()) for e in executions],
        total=await exec_repo.count(grant_id=grant_id, tenant_id=tenant_id, workspace_id=workspace_id),
        limit=limit,
        offset=offset,
    )
