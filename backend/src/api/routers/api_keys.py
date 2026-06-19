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
from ..deps import assert_admin_tenant_scope

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

_KEY_PREFIX = "gl_live_"
_VALID_SCOPES = {"read_only", "read_write", "admin"}
# Roles permitted to mint an ``admin``-scoped API key. A non-admin caller must not be
# able to escalate by issuing itself an admin key.
_ADMIN_ROLES = {"admin", "grant_admin", "owner"}


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

    # SECURITY: scope is gated by the caller's role. A non-admin must not be able to
    # mint an admin-scoped key (privilege escalation to a key more powerful than itself).
    if "admin" in body.scopes and payload.get("role") not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Forbidden",
                "errorCode": "insufficient_role_for_scope",
                "reason": "Only an admin (owner, grant_admin, admin) may create an admin-scoped API key.",
            },
        )

    user_id = payload.get("sub", "unknown")
    # SECURITY: the workspace binding comes exclusively from the
    # signature-verified auth context. A body workspace_id, if present, must equal
    # the authenticated workspace — it can never override it (cross-tenant priv-esc).
    verified_workspace_id = payload.get("workspace_id") or "default"
    requested_workspace_id = body.workspace_id.strip() if body.workspace_id else ""
    if requested_workspace_id and requested_workspace_id != verified_workspace_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Forbidden",
                "errorCode": "workspace_mismatch",
                "reason": "workspace_id must match your authenticated workspace.",
            },
        )
    workspace_id = verified_workspace_id
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
        await db.run_sync(lambda s: append_event(audit_evt, conn=s.connection()))
    except Exception:
        pass

    return {
        "id": key_id,
        "key": raw_key,  # shown ONCE only
        "name": body.name,
        "scopes": body.scopes,
        "workspaceId": workspace_id,
        "expiresAt": body.expires_at,
        "createdAt": now,
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
        # Normalize to camelCase for external response
        out.append({
            "id": d.get("id"),
            "name": d.get("name"),
            "scopes": d["scopes"],
            "workspaceId": d.get("workspace_id"),
            "userId": d.get("user_id"),
            "expiresAt": d.get("expires_at"),
            "lastUsedAt": d.get("last_used_at"),
            "createdAt": d.get("created_at"),
            "revokedAt": d.get("revoked_at"),
        })
    return out


@router.delete("/{key_id}", status_code=200, response_model=dict[str, Any])
async def revoke_api_key(
    key_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    payload = _resolve_user(authorization)
    user_id = payload.get("sub", "unknown")

    # Resolve the key's owning tenant (via its workspace) so an admin acting on a key
    # it does not own is confined to its own tenant.
    result = await db.execute(
        text(
            "SELECT ak.id, ak.user_id, ak.name, "
            "COALESCE(w.tenant_id, ak.workspace_id) AS tenant_id "
            "FROM api_keys ak LEFT JOIN workspaces w ON w.id = ak.workspace_id "
            "WHERE ak.id=:id AND ak.revoked_at IS NULL"
        ),
        {"id": key_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "API key not found", "errorCode": "api_key_not_found"},
        )

    # The owner may always revoke their own key. Otherwise the caller must be an admin
    # AND scoped to the key's tenant — is_admin must NOT short-circuit the tenant check
    # (a prior cross-tenant revoke hole let an admin disable another tenant's key).
    if row["user_id"] != user_id:
        is_admin = payload.get("role") in _ADMIN_ROLES
        if not is_admin:
            raise HTTPException(
                status_code=403,
                detail={"error": "Forbidden", "errorCode": "forbidden"},
            )
        assert_admin_tenant_scope(payload, row["tenant_id"])

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
        await db.run_sync(lambda s: append_event(audit_evt, conn=s.connection()))
    except Exception:
        pass

    return {"id": key_id, "revokedAt": now, "status": "revoked"}


def resolve_api_key_sync(raw_key: str) -> Optional[dict[str, Any]]:
    """Synchronous API key resolution for use in the sync auth chain.

    Looks up the key via the SQLAlchemy sync engine (same pattern as audit_log).
    Returns a payload dict on success, None if the key is invalid/revoked/expired.
    """
    from sqlalchemy import text as _text

    from ...core.db import get_engine

    if not raw_key.startswith(_KEY_PREFIX):
        return None

    key_hash = _hash_key(raw_key)
    now = datetime.now(timezone.utc).isoformat()

    try:
        with get_engine().connect() as conn:
            result = conn.execute(
                _text(
                    "SELECT ak.id, ak.workspace_id, ak.user_id, ak.scopes, "
                    "ak.expires_at, ak.revoked_at, "
                    "COALESCE(w.tenant_id, ak.workspace_id) AS tenant_id "
                    "FROM api_keys ak "
                    "LEFT JOIN workspaces w ON w.id = ak.workspace_id "
                    "WHERE ak.key_hash = :kh"
                ),
                {"kh": key_hash},
            )
            row = result.mappings().first()
            if row is None:
                return None
            if row["revoked_at"] is not None:
                return None
            if row["expires_at"] is not None and row["expires_at"] < now:
                return None
            key_id = row["id"]
            workspace_id = row["workspace_id"]
            tenant_id = row["tenant_id"]
            user_id = row["user_id"]
            scopes = json.loads(row["scopes"] or "[]")

            conn.execute(
                _text("UPDATE api_keys SET last_used_at = :now WHERE id = :id"),
                {"now": now, "id": key_id},
            )
            conn.commit()

        return {
            "sub": user_id,
            "workspace_id": workspace_id,
            "tenant_id": tenant_id,
            "api_key_id": key_id,
            "scopes": scopes,
            "auth_method": "api_key",
            "role": "api_key",
        }
    except Exception:
        return None


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
