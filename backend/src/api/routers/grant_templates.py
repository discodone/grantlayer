"""Multi-workspace grant templates endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_async_db
from ..auth_jwt import validate_jwt_header
from ..deps import resolve_witness_identity

router = APIRouter(prefix="/grant-templates", tags=["grant-templates"])


def _resolve_user(authorization: Optional[str]) -> dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "Unauthorized", "errorCode": "unauthorized"})
    ok, status, result = validate_jwt_header(authorization)
    if ok is None or not ok:
        raise HTTPException(status_code=status or 401, detail={"error": "Unauthorized", "errorCode": "unauthorized"})
    return result  # type: ignore[return-value]


def _verified_workspace_id(payload: dict[str, Any], requested: Optional[str]) -> str:
    """Return the caller's signature-verified workspace.

    SECURITY: the workspace authority is the verified JWT/API-key claim,
    never a request-supplied value. A client-supplied workspace_id (body or query),
    if present, must equal the authenticated workspace or the request is rejected
    with 403 — preventing cross-tenant writes/reads.
    """
    verified = payload.get("workspace_id") or "default"
    candidate = (requested or "").strip()
    if candidate and candidate != verified:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Forbidden",
                "errorCode": "workspace_mismatch",
                "reason": "workspace_id must match your authenticated workspace.",
            },
        )
    return verified


class GrantTemplateCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    template_schema: dict[str, Any] = {}
    default_values: dict[str, Any] = {}
    workspace_id: Optional[str] = None

    model_config = {"populate_by_name": True}


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["schema_json"] = json.loads(d.get("schema_json") or "{}")
    d["default_values"] = json.loads(d.get("default_values") or "{}")
    return d


@router.get("/public", response_model=list[dict[str, Any]])
async def list_public_templates(
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """System-wide templates (workspace_id IS NULL, admin-curated)."""
    result = await db.execute(
        text(
            "SELECT id, workspace_id, name, description, schema_json, default_values, "
            "version, parent_id, is_active, locked, created_at, created_by "
            "FROM grant_templates WHERE workspace_id IS NULL AND is_active=1 "
            "ORDER BY created_at DESC"
        )
    )
    return [_row_to_dict(r) for r in result.mappings().all()]


@router.get("", response_model=list[dict[str, Any]])
async def list_templates(
    workspace_id: Optional[str] = None,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    payload = _resolve_user(authorization)
    ws_id = _verified_workspace_id(payload, workspace_id)

    result = await db.execute(
        text(
            "SELECT id, workspace_id, name, description, schema_json, default_values, "
            "version, parent_id, is_active, locked, created_at, created_by "
            "FROM grant_templates WHERE (workspace_id=:ws OR workspace_id IS NULL) "
            "AND is_active=1 ORDER BY created_at DESC"
        ),
        {"ws": ws_id},
    )
    return [_row_to_dict(r) for r in result.mappings().all()]


@router.post("", status_code=201, response_model=dict[str, Any])
async def create_template(
    body: GrantTemplateCreateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    payload = _resolve_user(authorization)
    user_id = resolve_witness_identity(payload)
    ws_id = _verified_workspace_id(payload, body.workspace_id)
    tmpl_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        text(
            "INSERT INTO grant_templates (id, workspace_id, name, description, "
            "schema_json, default_values, version, is_active, locked, created_at, created_by) "
            "VALUES (:id, :ws, :name, :desc, :schema, :defaults, 1, 1, 0, :now, :by)"
        ),
        {
            "id": tmpl_id,
            "ws": ws_id,
            "name": body.name,
            "desc": body.description,
            "schema": json.dumps(body.template_schema),
            "defaults": json.dumps(body.default_values),
            "now": now,
            "by": user_id,
        },
    )
    await db.commit()

    return {
        "id": tmpl_id,
        "workspace_id": ws_id,
        "name": body.name,
        "description": body.description,
        "schema_json": body.template_schema,
        "default_values": body.default_values,
        "version": 1,
        "parent_id": None,
        "is_active": True,
        "locked": False,
        "created_at": now,
        "created_by": user_id,
    }


@router.get("/{template_id}", response_model=dict[str, Any])
async def get_template(
    template_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    payload = _resolve_user(authorization)
    ws_id = _verified_workspace_id(payload, None)

    # SECURITY: scope the lookup to the caller's workspace (public
    # templates have workspace_id IS NULL and remain readable). Closes cross-tenant IDOR.
    result = await db.execute(
        text(
            "SELECT id, workspace_id, name, description, schema_json, default_values, "
            "version, parent_id, is_active, locked, created_at, created_by "
            "FROM grant_templates WHERE id=:id AND (workspace_id=:ws OR workspace_id IS NULL)"
        ),
        {"id": template_id, "ws": ws_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Template not found", "errorCode": "template_not_found"},
        )
    return _row_to_dict(row)


@router.post("/{template_id}/deactivate", response_model=dict[str, Any])
async def deactivate_template(
    template_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    payload = _resolve_user(authorization)
    ws_id = _verified_workspace_id(payload, None)

    # SECURITY: only the owning workspace can deactivate its template.
    result = await db.execute(
        text("SELECT id, locked FROM grant_templates WHERE id=:id AND workspace_id=:ws"),
        {"id": template_id, "ws": ws_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Template not found", "errorCode": "template_not_found"},
        )

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        text("UPDATE grant_templates SET is_active=0 WHERE id=:id AND workspace_id=:ws"),
        {"id": template_id, "ws": ws_id},
    )
    await db.commit()
    return {"id": template_id, "is_active": False, "deactivated_at": now}


@router.post("/{template_id}/new-version", status_code=201, response_model=dict[str, Any])
async def create_new_version(
    template_id: str,
    body: GrantTemplateCreateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Create a new version of a locked template (parent_id references original)."""
    payload = _resolve_user(authorization)
    user_id = resolve_witness_identity(payload)
    ws_id = _verified_workspace_id(payload, body.workspace_id)

    # SECURITY: a new version can only be derived from a parent in the
    # caller's own workspace, and is always bound to that verified workspace.
    result = await db.execute(
        text(
            "SELECT id, workspace_id, version, locked FROM grant_templates "
            "WHERE id=:id AND workspace_id=:ws"
        ),
        {"id": template_id, "ws": ws_id},
    )
    parent = result.mappings().first()
    if parent is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Template not found", "errorCode": "template_not_found"},
        )

    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    new_version = (parent["version"] or 1) + 1

    await db.execute(
        text(
            "INSERT INTO grant_templates (id, workspace_id, name, description, "
            "schema_json, default_values, version, parent_id, is_active, locked, created_at, created_by) "
            "VALUES (:id, :ws, :name, :desc, :schema, :defaults, :ver, :pid, 1, 0, :now, :by)"
        ),
        {
            "id": new_id,
            "ws": ws_id,
            "name": body.name,
            "desc": body.description,
            "schema": json.dumps(body.template_schema),
            "defaults": json.dumps(body.default_values),
            "ver": new_version,
            "pid": template_id,
            "now": now,
            "by": user_id,
        },
    )
    await db.commit()

    return {
        "id": new_id,
        "workspace_id": ws_id,
        "name": body.name,
        "description": body.description,
        "schema_json": body.template_schema,
        "default_values": body.default_values,
        "version": new_version,
        "parent_id": template_id,
        "is_active": True,
        "locked": False,
        "created_at": now,
        "created_by": user_id,
    }
