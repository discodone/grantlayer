"""GrantLayer MVP — Grant storage."""

import datetime
from typing import List, Optional
from .db import get_conn
from .models import Grant


def _row_to_grant(row) -> Grant:
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
    )


def list_grants() -> List[Grant]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM grants ORDER BY created_at DESC").fetchall()
        return [_row_to_grant(r) for r in rows]
    finally:
        conn.close()


def get_grant(grant_id: str) -> Optional[Grant]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM grants WHERE id = ?", (grant_id,)).fetchone()
        return _row_to_grant(row) if row else None
    finally:
        conn.close()


def create_grant(grant: Grant) -> Grant:
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO grants
               (id, subject_id, role, action, resource, valid_from, valid_until,
                created_by, reason, revoked, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (
                grant.id, grant.subject_id, grant.role, grant.action,
                grant.resource, grant.valid_from, grant.valid_until,
                grant.created_by, grant.reason, grant.created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return grant


def revoke_grant(grant_id: str, revoked_by: str, reason: str) -> bool:
    revoked_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    conn = get_conn()
    try:
        cur = conn.execute(
            """UPDATE grants
               SET revoked = 1, revoked_by = ?, revoked_reason = ?, revoked_at = ?
               WHERE id = ? AND revoked = 0""",
            (revoked_by, reason, revoked_at, grant_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
