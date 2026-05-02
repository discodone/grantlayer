"""GrantLayer MVP — Audit log."""

from typing import List
from .db import get_conn
from .models import AuditEvent


def append_event(event: AuditEvent) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO audit_events
               (id, timestamp, subject_id, role, action, resource,
                approved, reason, matched_grant_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id, event.timestamp, event.subject_id, event.role,
                event.action, event.resource, int(event.approved),
                event.reason, event.matched_grant_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_events(limit: int = 200) -> List[AuditEvent]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    return [
        AuditEvent(
            id=r["id"],
            timestamp=r["timestamp"],
            subject_id=r["subject_id"],
            role=r["role"],
            action=r["action"],
            resource=r["resource"],
            approved=bool(r["approved"]),
            reason=r["reason"],
            matched_grant_id=r["matched_grant_id"],
        )
        for r in rows
    ]
