"""GrantLayer MVP — Audit log."""

from typing import List, Optional
from .db import execute, query_one, query_all
from .models import AuditEvent


def append_event(event: AuditEvent) -> None:
    execute(
        """INSERT INTO audit_events
           (id, timestamp, subject_id, role, action, resource,
            approved, reason, matched_grant_id,
            challenge_id, challenge_present, challenge_result,
            grant_signature_result)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event.id, event.timestamp, event.subject_id, event.role,
            event.action, event.resource, int(event.approved),
            event.reason, event.matched_grant_id,
            event.challenge_id, int(event.challenge_present), event.challenge_result,
            event.grant_signature_result,
        ),
    )


def get_event(event_id: str) -> Optional[AuditEvent]:
    row = query_one("SELECT * FROM audit_events WHERE id = ?", (event_id,))
    if row is None:
        return None
    return AuditEvent(
        id=row["id"],
        timestamp=row["timestamp"],
        subject_id=row["subject_id"],
        role=row["role"],
        action=row["action"],
        resource=row["resource"],
        approved=bool(row["approved"]),
        reason=row["reason"],
        matched_grant_id=row["matched_grant_id"],
        challenge_id=row["challenge_id"],
        challenge_present=int(row["challenge_present"] or 0) != 0,
        challenge_result=row["challenge_result"] or "legacy_mode",
        grant_signature_result=row["grant_signature_result"] or "not_checked",
    )


def list_events(limit: int = 200) -> List[AuditEvent]:
    rows = query_all(
        "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )
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
            challenge_id=r["challenge_id"],
            challenge_present=int(r["challenge_present"] or 0) != 0,
            challenge_result=r["challenge_result"] or "legacy_mode",
            grant_signature_result=r["grant_signature_result"] or "not_checked",
        )
        for r in rows
    ]


def list_events_by_grant(grant_id: str, limit: int = 50) -> List[AuditEvent]:
    """Return audit events linked to a specific grant (via matched_grant_id)."""
    rows = query_all(
        "SELECT * FROM audit_events WHERE matched_grant_id = ? ORDER BY timestamp DESC LIMIT ?",
        (grant_id, limit),
    )
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
            challenge_id=r["challenge_id"],
            challenge_present=int(r["challenge_present"] or 0) != 0,
            challenge_result=r["challenge_result"] or "legacy_mode",
            grant_signature_result=r["grant_signature_result"] or "not_checked",
        )
        for r in rows
    ]
