"""Long-lived API key management endpoints."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit.audit_log import append_event
from ...core.db import get_async_db
from ...core.models import AuditEvent
from ..auth_jwt import validate_jwt_header

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

_KEY_PREFIX = "gl_live_"
_VALID_SCOPES = {"read_only", "read_write", "admin"}


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _generate_raw_key() -> str:
    return _KEY_PREFIX + secrets.token_hex(32)


def _resolve_user(authorization: Optional[str]) -> dict[str, Any]:
    """Resolve user from JWT or raise 401."""
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "Unauthorized", "errorCode": "unauthorized"})
    ok, status, result = validate_jwt_header(authorization)
    if ok is None or not ok:
        raise HTTPException(status_code=status or 401, detail={"error": "Unauthorized", "errorCode": "unauthorized"})
    return result  # type: ignore[return-value]


class ApiKeyCreateRequest(BaseModel):
    name: str
    scopes: list[str] = ["read_write"]
    expires_at: Optional[str] = None
    workspace_id: Optional[str] = None


@router.post("", status_code=201, response_model=dict[str, Any])
async def create_api_key(
    body: ApiKeyCreateRequest,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    payload = _resolve_user(authorization)

    invalid_scopes = set(body.scopes) - _VALID_SCOPES
    if invalid_scopes:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Invalid scopes",
                "errorCode": "invalid_scopes",
                "reason": f"Unknown scopes: {', '.join(sorted(invalid_scopes))}. Valid: {', '.join(sorted(_VALID_SCOPES))}",
            },
        )

    user_id = payload.get("sub", "unknown")
    workspace_id = body.workspace_id or payload.get("workspace_id", "default")
    raw_key = _generate_raw_key()
    key_hash = _hash_key(raw_key)
    key_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        text(
            "INSERT INTO api_keys (id, workspace_id, user_id, key_hash, name, scopes, "
            "expires_at, created_at) VALUES (:id, :ws, :uid, :kh, :name, :scopes, :exp, :now)"
        ),
        {
            "id": key_id,
            "ws": workspace_id,
            "uid": user_id,
            "kh": key_hash,
            "name": body.name,
            "scopes": json.dumps(body.scopes),
            "exp": body.expires_at,
            "now": now,
        },
    )
    await db.commit()

    audit_evt = AuditEvent(
        id=str(uuid.uuid4()),
        timestamp=now,
        subject_id=user_id,
        role=payload.get("role", "user"),
        action="api_key_created",
        resource=f"api_key/{key_id}",
        approved=True,
        reason=f"API key '{body.name}' created",
    )
    try:
        append_event(audit_evt)
    except Exception:
        pass

    return {
        "id": key_id,
        "key": raw_key,  # shown ONCE only
        "name": body.name,
        "scopes": body.scopes,
        "workspace_id": workspace_id,
        "expires_at": body.expires_at,
        "created_at": now,
    }


@router.get("", response_model=list[dict[str, Any]])
async def list_api_keys(
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    payload = _resolve_user(authorization)
    user_id = payload.get("sub", "unknown")

    result = await db.execute(
        text(
            "SELECT id, workspace_id, user_id, name, scopes, expires_at, "
            "last_used_at, created_at, revoked_at FROM api_keys "
            "WHERE user_id=:uid ORDER BY created_at DESC"
        ),
        {"uid": user_id},
    )
    rows = result.mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["scopes"] = json.loads(d.get("scopes") or "[]")
        out.append(d)
    return out


@router.delete("/{key_id}", status_code=200, response_model=dict[str, Any])
async def revoke_api_key(
    key_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    payload = _resolve_user(authorization)
    user_id = payload.get("sub", "unknown")

    # Check key exists and belongs to user (or admin)
    result = await db.execute(
        text("SELECT id, user_id, name FROM api_keys WHERE id=:id AND revoked_at IS NULL"),
        {"id": key_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "API key not found", "errorCode": "api_key_not_found"},
        )

    is_admin = payload.get("role") in ("admin", "grant_admin", "owner")
    if row["user_id"] != user_id and not is_admin:
        raise HTTPException(
            status_code=403,
            detail={"error": "Forbidden", "errorCode": "forbidden"},
        )

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        text("UPDATE api_keys SET revoked_at=:now WHERE id=:id"),
        {"now": now, "id": key_id},
    )
    await db.commit()

    audit_evt = AuditEvent(
        id=str(uuid.uuid4()),
        timestamp=now,
        subject_id=user_id,
        role=payload.get("role", "user"),
        action="api_key_revoked",
        resource=f"api_key/{key_id}",
        approved=True,
        reason=f"API key '{row['name']}' revoked",
    )
    try:
        append_event(audit_evt)
    except Exception:
        pass

    return {"id": key_id, "revoked_at": now, "status": "revoked"}


async def resolve_api_key_auth(
    raw_key: str,
    db: AsyncSession,
) -> Optional[dict[str, Any]]:
    """Resolve a gl_live_ API key to a user context dict, or None if invalid."""
    if not raw_key.startswith(_KEY_PREFIX):
        return None

    key_hash = _hash_key(raw_key)
    result = await db.execute(
        text(
            "SELECT id, workspace_id, user_id, scopes, expires_at, revoked_at "
            "FROM api_keys WHERE key_hash=:kh"
        ),
        {"kh": key_hash},
    )
    row = result.mappings().first()
    if row is None:
        return None
    if row["revoked_at"] is not None:
        return None
    if row["expires_at"] is not None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if row["expires_at"] < now_iso:
            return None

    # Update last_used_at
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        text("UPDATE api_keys SET last_used_at=:now WHERE id=:id"),
        {"now": now, "id": row["id"]},
    )
    await db.commit()

    scopes = json.loads(row["scopes"] or "[]")
    return {
        "sub": row["user_id"],
        "workspace_id": row["workspace_id"],
        "api_key_id": row["id"],
        "scopes": scopes,
        "auth_method": "api_key",
    }
