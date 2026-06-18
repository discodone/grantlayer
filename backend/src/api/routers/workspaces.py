"""Workspace management endpoints — plan tier, CRUD."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_async_db
from ..deps import require_admin

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

_VALID_TIERS = {"free", "pro", "enterprise"}


class PlanUpdateRequest(BaseModel):
    plan_tier: str
    rate_limit_override: Optional[int] = None


@router.get("", response_model=list[dict[str, Any]])
async def list_workspaces(
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    require_admin(authorization)
    result = await db.execute(
        text(
            "SELECT id, tenant_id, name, slug, owner_id, status, description, "
            "plan_tier, rate_limit_override, created_at, updated_at "
            "FROM workspaces ORDER BY created_at DESC"
        )
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.get("/{workspace_id}", response_model=dict[str, Any])
async def get_workspace(
    workspace_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    require_admin(authorization)
    result = await db.execute(
        text(
            "SELECT id, tenant_id, name, slug, owner_id, status, description, "
            "plan_tier, rate_limit_override, created_at, updated_at "
            "FROM workspaces WHERE id = :id"
        ),
        {"id": workspace_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Workspace not found",
                "errorCode": "workspace_not_found",
                "reason": "The requested workspace does not exist.",
            },
        )
    return dict(row)


@router.patch("/{workspace_id}/plan", response_model=dict[str, Any])
async def update_workspace_plan(
    workspace_id: str,
    body: PlanUpdateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    require_admin(authorization)

    if body.plan_tier not in _VALID_TIERS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Invalid plan_tier",
                "errorCode": "invalid_plan_tier",
                "reason": f"plan_tier must be one of: {', '.join(sorted(_VALID_TIERS))}",
            },
        )

    if body.rate_limit_override is not None and body.rate_limit_override < 0:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Invalid rate_limit_override",
                "errorCode": "invalid_rate_limit_override",
                "reason": "rate_limit_override must be a non-negative integer.",
            },
        )

    now = datetime.now(timezone.utc).isoformat()
    update_result = await db.execute(
        text(
            "UPDATE workspaces SET plan_tier=:tier, rate_limit_override=:override, "
            "updated_at=:now WHERE id=:id"
        ),
        {
            "tier": body.plan_tier,
            "override": body.rate_limit_override,
            "now": now,
            "id": workspace_id,
        },
    )
    await db.commit()

    if getattr(update_result, "rowcount", 1) == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Workspace not found",
                "errorCode": "workspace_not_found",
                "reason": "The requested workspace does not exist.",
            },
        )

    fetch = await db.execute(
        text(
            "SELECT id, tenant_id, name, slug, owner_id, status, "
            "plan_tier, rate_limit_override, created_at, updated_at "
            "FROM workspaces WHERE id=:id"
        ),
        {"id": workspace_id},
    )
    row = fetch.mappings().first()
    return dict(row) if row else {}
