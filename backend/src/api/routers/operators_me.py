"""Operator self-info endpoint (FastAPI)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException

from ...core import config
from ..deps import resolve_auth_and_workspace

router = APIRouter(tags=["operators"])


@router.get("/operators/me", response_model=dict[str, Any])
def get_current_operator(
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    auth_ctx, _ = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    if not config.ENABLE_OPERATOR_MODEL:
        raise HTTPException(
            status_code=404,
            detail={"error": "Operator model is disabled", "errorCode": "operator_model_disabled", "reason": "The operator model is not enabled on this instance."},
        )
    return auth_ctx.get("operator", {})
