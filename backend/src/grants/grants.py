"""GrantLayer MVP — Grant storage."""

import datetime
from typing import List, Optional
from ..core.db import get_conn, execute, query_one, query_all
from ..core.models import Grant
from ..core.crypto_signing import sign_grant as _sign_grant


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


def list_grants(tenant_id: Optional[str] = None) -> List[Grant]:
    if tenant_id is not None:
        rows = query_all(
            "SELECT * FROM grants WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,),
        )
    else:
        rows = query_all("SELECT * FROM grants ORDER BY created_at DESC")
    return [_row_to_grant(r) for r in rows]


def get_grant(grant_id: str, tenant_id: Optional[str] = None) -> Optional[Grant]:
    if tenant_id is not None:
        row = query_one(
            "SELECT * FROM grants WHERE id = ? AND tenant_id = ?",
            (grant_id, tenant_id),
        )
    else:
        row = query_one("SELECT * FROM grants WHERE id = ?", (grant_id,))
    return _row_to_grant(row) if row else None


def create_grant(grant: Grant, conn=None, tenant_id: Optional[str] = None) -> Grant:
    # Generate signature before inserting to ensure atomic creation
    sig_hex, hash_hex, key_id = _sign_grant(grant)
    grant.signature = sig_hex
    grant.payload_hash = hash_hex
    grant.signing_key_id = key_id

    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_tenant = tenant_id

    sql = """INSERT INTO grants
           (id, subject_id, role, action, resource, valid_from, valid_until,
            created_by, reason, revoked, created_at, max_uses, use_count,
            signature, signing_key_id, payload_hash, tenant_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)"""
    params = (
        grant.id, grant.subject_id, grant.role, grant.action,
        grant.resource, grant.valid_from, grant.valid_until,
        grant.created_by, grant.reason, grant.created_at,
        grant.max_uses, grant.use_count,
        sig_hex, key_id, hash_hex, effective_tenant,
    )

    if conn is not None:
        conn.execute(sql, params)
    else:
        execute(sql, params)
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
) -> bool:
    revoked_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    if tenant_id is not None:
        sql = """UPDATE grants
               SET revoked = 1, revoked_by = ?, revoked_reason = ?, revoked_at = ?
               WHERE id = ? AND tenant_id = ? AND revoked = 0"""
        params = (revoked_by, reason, revoked_at, grant_id, tenant_id)
    else:
        sql = """UPDATE grants
               SET revoked = 1, revoked_by = ?, revoked_reason = ?, revoked_at = ?
               WHERE id = ? AND revoked = 0"""
        params = (revoked_by, reason, revoked_at, grant_id)
    if conn is not None:
        cur = conn.execute(sql, params)
        return (cur.rowcount or 0) > 0
    rowcount = execute(sql, params)
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
