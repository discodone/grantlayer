"""GrantLayer MVP — Provenance Event Model & Persistence.

Append-only provenance event tracing.
No update / delete operations.
"""

from __future__ import annotations

import json
from typing import Optional

from ..core.db import execute, query_all, query_one
from ..core.models import ProvenanceEvent

# ──────────────────────────────────────────────────────────────
# Validation helpers
# ──────────────────────────────────────────────────────────────

_VALID_ACTOR_TYPES = {"user", "agent", "system", "external"}
_VALID_EVENT_TYPES = {
    "decision_rendered",
    "grant_issued",
    "grant_revoked",
    "grant_executed",
    "evidence_created",
    "evidence_verified",
    "audit_event_created",
    "policy_evaluated",
}


def _validate_actor_type(actor_type: str) -> None:
    if actor_type not in _VALID_ACTOR_TYPES:
        raise ValueError(
            f"Invalid actor_type '{actor_type}'. "
            f"Must be one of: {sorted(_VALID_ACTOR_TYPES)}"
        )


def _validate_event_type(event_type: str) -> None:
    if event_type not in _VALID_EVENT_TYPES:
        raise ValueError(
            f"Invalid event_type '{event_type}'. "
            f"Must be one of: {sorted(_VALID_EVENT_TYPES)}"
        )


# ──────────────────────────────────────────────────────────────
# Row mapping
# ──────────────────────────────────────────────────────────────

def _row_to_provenance_event(row: dict | None) -> Optional[ProvenanceEvent]:
    if row is None:
        return None
    return ProvenanceEvent(
        id=row["id"],
        event_type=row["event_type"],
        actor_type=row["actor_type"],
        actor_id=row["actor_id"],
        action=row["action"],
        occurred_at=row["occurred_at"],
        created_at=row["created_at"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        execution_id=row["execution_id"],
        grant_id=row["grant_id"],
        evidence_hash=row["evidence_hash"],
        verification_status=row["verification_status"],
        metadata_json=row["metadata_json"],
    )


# ──────────────────────────────────────────────────────────────
# Core API
# ──────────────────────────────────────────────────────────────

def record_provenance_event(
    event_type: str,
    actor_type: str,
    actor_id: str,
    action: str,
    occurred_at: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    grant_id: Optional[str] = None,
    evidence_hash: Optional[str] = None,
    verification_status: Optional[str] = None,
    metadata_json: Optional[str] = None,
) -> ProvenanceEvent:
    """Record a new provenance event.

    Validates actor_type and event_type.
    Returns the created ProvenanceEvent.
    """
    _validate_event_type(event_type)
    _validate_actor_type(actor_type)

    # Validate metadata_json is valid JSON if provided
    if metadata_json is not None:
        try:
            json.loads(metadata_json)
        except json.JSONDecodeError as exc:
            raise ValueError("metadata_json must be valid JSON") from exc

    event = ProvenanceEvent(
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        occurred_at=occurred_at,
        resource_type=resource_type,
        resource_id=resource_id,
        execution_id=execution_id,
        grant_id=grant_id,
        evidence_hash=evidence_hash,
        verification_status=verification_status,
        metadata_json=metadata_json,
    )

    execute(
        """
        INSERT INTO provenance_events (
            id, event_type, actor_type, actor_id, action, occurred_at, created_at,
            resource_type, resource_id, execution_id, grant_id,
            evidence_hash, verification_status, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.id,
            event.event_type,
            event.actor_type,
            event.actor_id,
            event.action,
            event.occurred_at,
            event.created_at,
            event.resource_type,
            event.resource_id,
            event.execution_id,
            event.grant_id,
            event.evidence_hash,
            event.verification_status,
            event.metadata_json,
        ),
    )
    return event


def get_provenance_event(event_id: str) -> Optional[ProvenanceEvent]:
    """Retrieve a single provenance event by its stable UUID."""
    row = query_one(
        "SELECT * FROM provenance_events WHERE id = ?",
        (event_id,),
    )
    return _row_to_provenance_event(row)


def list_provenance_events(
    execution_id: Optional[str] = None,
    grant_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    actor_type: Optional[str] = None,
    limit: int = 100,
) -> list[ProvenanceEvent]:
    """List provenance events with optional filters.

    Always ordered by occurred_at DESC, then id DESC for stability.
    Limit defaults to 100 and is capped at 1000.
    """
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000

    # Validate actor_type if provided
    if actor_type is not None:
        _validate_actor_type(actor_type)

    conditions: list[str] = []
    params: list = []

    if execution_id is not None:
        conditions.append("execution_id = ?")
        params.append(execution_id)
    if grant_id is not None:
        conditions.append("grant_id = ?")
        params.append(grant_id)
    if resource_type is not None:
        conditions.append("resource_type = ?")
        params.append(resource_type)
    if resource_id is not None:
        conditions.append("resource_id = ?")
        params.append(resource_id)
    if actor_type is not None:
        conditions.append("actor_type = ?")
        params.append(actor_type)

    where_clause = " AND ".join(conditions) if conditions else "1 = 1"
    sql = f"""
        SELECT * FROM provenance_events
        WHERE {where_clause}
        ORDER BY occurred_at DESC, id DESC
        LIMIT ?
    """
    params.append(limit)

    rows = query_all(sql, tuple(params))
    return [event for r in rows if (event := _row_to_provenance_event(r)) is not None]
