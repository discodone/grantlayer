"""GrantLayer MVP — Grant storage."""

import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, select
from sqlalchemy import insert as sa_insert
from sqlalchemy import update as sa_update

from ..core.crypto_signing import sign_grant as _sign_grant
from ..core.db import (
    execute,
    query_all,
    query_one,
)
from ..core.models import Grant
from ..core.orm import Grant as OrmGrant

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_DEMO_WORKSPACE_ID = "default"


def _orm_to_grant(row: OrmGrant) -> Grant:
    return Grant(
        id=row.id,
        subject_id=row.subject_id,
        role=row.role,
        action=row.action,
        resource=row.resource,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        created_by=row.created_by,
        reason=row.reason,
        revoked=bool(row.revoked),
        revoked_by=row.revoked_by,
        revoked_reason=row.revoked_reason,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
        signature=row.signature,
        signing_key_id=row.signing_key_id,
        payload_hash=row.payload_hash,
        max_uses=row.max_uses,
        use_count=row.use_count or 0,
    )


def _row_to_grant(row: dict) -> Grant:
    return Grant(
        id=row["id"],
        subject_id=row["subject_id"],
        role=row["role"],
        action=row["action"],
        resource=row["resource"],
        valid_from=row["valid_from"],
        valid_until=row["valid_until"],
        created_by=row["created_by"],
        reason=row["reason"],
        revoked=bool(row["revoked"]),
        revoked_by=row["revoked_by"],
        revoked_reason=row["revoked_reason"],
        revoked_at=row["revoked_at"],
        created_at=row["created_at"],
        signature=row["signature"],
        signing_key_id=row["signing_key_id"],
        payload_hash=row["payload_hash"],
        max_uses=row["max_uses"],
        use_count=row["use_count"] or 0,
    )


def list_grants(
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    session: "Optional[Session]" = None,
) -> List[Grant]:
    if session is not None:
        stmt = select(OrmGrant).order_by(OrmGrant.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return [_orm_to_grant(r) for r in session.execute(stmt).scalars().all()]
    conditions: list[str] = []
    params: list = []
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    sql = "SELECT * FROM grants"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    return [_row_to_grant(r) for r in query_all(sql, tuple(params))]


def count_grants(
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> int:
    if session is not None:
        stmt = select(func.count()).select_from(OrmGrant)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        result = session.execute(stmt).scalar()
        return int(result) if result is not None else 0
    conditions: list[str] = []
    params: list = []
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    sql = "SELECT COUNT(*) AS count FROM grants"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    row = query_one(sql, tuple(params))
    return int(row["count"]) if row else 0


def get_grant(
    grant_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> Optional[Grant]:
    if session is not None:
        stmt = select(OrmGrant).where(OrmGrant.id == grant_id)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        orm_row = session.execute(stmt).scalars().first()
        return _orm_to_grant(orm_row) if orm_row else None
    conditions = ["id = ?"]
    params: list = [grant_id]
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    row = query_one("SELECT * FROM grants WHERE " + " AND ".join(conditions), tuple(params))
    return _row_to_grant(row) if row else None


def create_grant(
    grant: Grant,
    conn=None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Grant:
    # Generate signature before inserting to ensure atomic creation
    sig_hex, hash_hex, key_id = _sign_grant(grant)
    grant.signature = sig_hex
    grant.payload_hash = hash_hex
    grant.signing_key_id = key_id

    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_tenant = tenant_id
    effective_workspace = workspace_id if workspace_id is not None else _DEMO_WORKSPACE_ID

    if conn is not None:
        conn.execute(
            sa_insert(OrmGrant.__table__).values(
                id=grant.id,
                subject_id=grant.subject_id,
                role=grant.role,
                action=grant.action,
                resource=grant.resource,
                valid_from=grant.valid_from,
                valid_until=grant.valid_until,
                created_by=grant.created_by,
                reason=grant.reason,
                revoked=0,
                created_at=grant.created_at,
                max_uses=grant.max_uses,
                use_count=grant.use_count,
                signature=sig_hex,
                signing_key_id=key_id,
                payload_hash=hash_hex,
                tenant_id=effective_tenant,
                workspace_id=effective_workspace,
            )
        )
    else:
        execute(
            """INSERT INTO grants
               (id, subject_id, role, action, resource, valid_from, valid_until,
                created_by, reason, revoked, created_at, max_uses, use_count,
                signature, signing_key_id, payload_hash, tenant_id, workspace_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                grant.id, grant.subject_id, grant.role, grant.action,
                grant.resource, grant.valid_from, grant.valid_until,
                grant.created_by, grant.reason, grant.created_at,
                grant.max_uses, grant.use_count,
                sig_hex, key_id, hash_hex, effective_tenant, effective_workspace,
            ),
        )
    return grant


def tamper_grant(grant_id: str, tenant_id: Optional[str] = None) -> Optional[dict]:
    """Demo-only: change a grant field without re-signing to demonstrate tamper detection."""
    grant = get_grant(grant_id, tenant_id=tenant_id)
    if grant is None:
        return None
    old_value = grant.role
    new_value = "tampered-role"
    if tenant_id is not None:
        execute(
            "UPDATE grants SET role = ? WHERE id = ? AND tenant_id = ?",
            (new_value, grant_id, tenant_id),
        )
    else:
        execute("UPDATE grants SET role = ? WHERE id = ?", (new_value, grant_id))
    return {
        "ok": True,
        "grantId": grant_id,
        "tamperedField": "role",
        "oldValue": old_value,
        "newValue": new_value,
        "subjectId": grant.subject_id,
        "action": grant.action,
        "resource": grant.resource,
        "message": "Grant tampered without re-signing. Signature should now fail.",
    }


def revoke_grant(
    grant_id: str,
    revoked_by: str,
    reason: str,
    conn=None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> bool:
    revoked_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    if conn is not None:
        stmt = (
            sa_update(OrmGrant.__table__)
            .where(OrmGrant.id == grant_id, OrmGrant.revoked == 0)
            .values(revoked=1, revoked_by=revoked_by, revoked_reason=reason, revoked_at=revoked_at)
        )
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        result = conn.execute(stmt)
        return (result.rowcount or 0) > 0
    conditions = ["id = ?", "revoked = 0"]
    params: list = [revoked_by, reason, revoked_at, grant_id]
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    sql = (
        "UPDATE grants SET revoked = 1, revoked_by = ?, revoked_reason = ?, revoked_at = ?"
        " WHERE " + " AND ".join(conditions)
    )
    rowcount = execute(sql, tuple(params))
    return rowcount > 0


def try_consume_grant_use(grant_id: str) -> bool:
    """Atomically increment use_count if the grant is not exhausted.

    Returns True if the consumption succeeded, False if the grant
    was already exhausted (use_count >= max_uses).
    """
    rowcount = execute(
        """
        UPDATE grants
        SET use_count = use_count + 1
        WHERE id = ?
          AND (max_uses IS NULL OR use_count < max_uses)
        """,
        (grant_id,),
    )
    return rowcount > 0
