"""GrantLayer MVP — Audit log."""

import hashlib
import json
from typing import List, Optional
from .db import execute, query_one, query_all
from .models import AuditEvent


# ──────────────────────────────────────────────────────────────
# Hash-chain helpers (GL-103)
# ──────────────────────────────────────────────────────────────

_Genesis_PREV_HASH = "0" * 64  # fixed genesis for first event when no prior hash exists


def _get_latest_row_hash(conn=None) -> Optional[str]:
    """Return the row_hash of the most recent audit event that has one."""
    sql = (
        "SELECT row_hash FROM audit_events "
        "WHERE row_hash IS NOT NULL "
        "ORDER BY timestamp DESC, rowid DESC LIMIT 1"
    )
    if conn is not None:
        row = conn.execute(sql).fetchone()
    else:
        row = query_one(sql)
    if row is None:
        return None
    return row["row_hash"] if isinstance(row, dict) else row[0]


def _hash_payload(event: AuditEvent, prev_hash: Optional[str]) -> str:
    """Build a deterministic canonical JSON payload for hashing.

    Includes all stable audit fields plus prev_hash.
    Excludes row_hash itself.
    """
    payload = {
        "id": event.id,
        "timestamp": event.timestamp,
        "subject_id": event.subject_id,
        "role": event.role,
        "action": event.action,
        "resource": event.resource,
        "approved": bool(event.approved),
        "reason": event.reason,
        "matched_grant_id": event.matched_grant_id,
        "challenge_id": event.challenge_id,
        "challenge_present": bool(event.challenge_present),
        "challenge_result": event.challenge_result,
        "grant_signature_result": event.grant_signature_result,
        "prev_hash": prev_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _compute_row_hash(event: AuditEvent, prev_hash: Optional[str]) -> str:
    """Compute SHA-256 row hash over deterministic canonical payload."""
    canonical = _hash_payload(event, prev_hash)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _row_to_audit_event(row: dict) -> AuditEvent:
    """Build an AuditEvent from a DB row dict."""
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
        row_hash=row.get("row_hash"),
        prev_hash=row.get("prev_hash"),
    )


# ──────────────────────────────────────────────────────────────
# Chain verification (GL-104)
# ──────────────────────────────────────────────────────────────

def verify_audit_hash_chain() -> dict:
    """Read-only verification of audit_events hash-chain integrity.

    Reads audit events in deterministic insertion order (timestamp ASC, rowid ASC),
    skips historical/pre-chain rows where row_hash IS NULL, and verifies:
      1. Each stored row_hash matches the hash recomputed from the event fields
         and the expected prev_hash (previous event's row_hash, or None for genesis).
      2. Each stored prev_hash equals the expected prev_hash.

    Returns a structured dict:
        {
            "valid": bool,
            "checked": int,           # number of chain rows evaluated
            "failures": [
                {
                    "event_id": str,
                    "index": int,
                    "reason": str,
                },
                ...
            ],
        }

    This helper is read-only and does not insert or mutate audit_events.
    """
    rows = query_all(
        "SELECT * FROM audit_events ORDER BY timestamp ASC, rowid ASC"
    )

    # Filter to chain rows only; historical/pre-chain NULL rows are skipped.
    chain_rows = [r for r in rows if r.get("row_hash") is not None]
    failures: list[dict] = []

    for i, row in enumerate(chain_rows):
        event = _row_to_audit_event(row)
        expected_prev_hash = chain_rows[i - 1]["row_hash"] if i > 0 else None

        # Verify prev_hash continuity
        if event.prev_hash != expected_prev_hash:
            failures.append({
                "event_id": event.id,
                "index": i,
                "reason": (
                    f"prev_hash mismatch: stored={event.prev_hash!r} "
                    f"expected={expected_prev_hash!r}"
                ),
            })

        # Verify row_hash integrity
        recomputed = _compute_row_hash(event, expected_prev_hash)
        if event.row_hash != recomputed:
            failures.append({
                "event_id": event.id,
                "index": i,
                "reason": (
                    f"row_hash mismatch: stored={event.row_hash!r} "
                    f"expected={recomputed!r}"
                ),
            })

    return {
        "valid": len(failures) == 0,
        "checked": len(chain_rows),
        "failures": failures,
    }


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

_Genesis_PREV_HASH = "0" * 64  # fixed genesis for first event when no prior hash exists


def _get_latest_row_hash(conn=None) -> Optional[str]:
    """Return the row_hash of the most recent audit event that has one."""
    sql = (
        "SELECT row_hash FROM audit_events "
        "WHERE row_hash IS NOT NULL "
        "ORDER BY timestamp DESC, rowid DESC LIMIT 1"
    )
    if conn is not None:
        row = conn.execute(sql).fetchone()
    else:
        row = query_one(sql)
    if row is None:
        return None
    return row["row_hash"] if isinstance(row, dict) else row[0]


def _hash_payload(event: AuditEvent, prev_hash: Optional[str]) -> str:
    """Build a deterministic canonical JSON payload for hashing.

    Includes all stable audit fields plus prev_hash.
    Excludes row_hash itself.
    """
    payload = {
        "id": event.id,
        "timestamp": event.timestamp,
        "subject_id": event.subject_id,
        "role": event.role,
        "action": event.action,
        "resource": event.resource,
        "approved": bool(event.approved),
        "reason": event.reason,
        "matched_grant_id": event.matched_grant_id,
        "challenge_id": event.challenge_id,
        "challenge_present": bool(event.challenge_present),
        "challenge_result": event.challenge_result,
        "grant_signature_result": event.grant_signature_result,
        "prev_hash": prev_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _compute_row_hash(event: AuditEvent, prev_hash: Optional[str]) -> str:
    """Compute SHA-256 row hash over deterministic canonical payload."""
    canonical = _hash_payload(event, prev_hash)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _row_to_audit_event(row: dict) -> AuditEvent:
    """Build an AuditEvent from a DB row dict."""
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
        row_hash=row.get("row_hash"),
        prev_hash=row.get("prev_hash"),
    )


# ──────────────────────────────────────────────────────────────
# Chain verification (GL-104)
# ──────────────────────────────────────────────────────────────

def verify_audit_hash_chain() -> dict:
    """Read-only verification of audit_events hash-chain integrity.

    Reads audit events in deterministic insertion order (timestamp ASC, rowid ASC),
    skips historical/pre-chain rows where row_hash IS NULL, and verifies:
      1. Each stored row_hash matches the hash recomputed from the event fields
         and the expected prev_hash (previous event's row_hash, or None for genesis).
      2. Each stored prev_hash equals the expected prev_hash.

    Returns a structured dict:
        {
            "valid": bool,
            "checked": int,           # number of chain rows evaluated
            "failures": [
                {
                    "event_id": str,
                    "index": int,
                    "reason": str,
                },
                ...
            ],
        }

    This helper is read-only and does not insert or mutate audit_events.
    """
    rows = query_all(
        "SELECT * FROM audit_events ORDER BY timestamp ASC, rowid ASC"
    )

    # Filter to chain rows only; historical/pre-chain NULL rows are skipped.
    chain_rows = [r for r in rows if r.get("row_hash") is not None]
    failures: list[dict] = []

    for i, row in enumerate(chain_rows):
        event = _row_to_audit_event(row)
        expected_prev_hash = chain_rows[i - 1]["row_hash"] if i > 0 else None

        # Verify prev_hash continuity
        if event.prev_hash != expected_prev_hash:
            failures.append({
                "event_id": event.id,
                "index": i,
                "reason": (
                    f"prev_hash mismatch: stored={event.prev_hash!r} "
                    f"expected={expected_prev_hash!r}"
                ),
            })

        # Verify row_hash integrity
        recomputed = _compute_row_hash(event, expected_prev_hash)
        if event.row_hash != recomputed:
            failures.append({
                "event_id": event.id,
                "index": i,
                "reason": (
                    f"row_hash mismatch: stored={event.row_hash!r} "
                    f"expected={recomputed!r}"
                ),
            })

    return {
        "valid": len(failures) == 0,
        "checked": len(chain_rows),
        "failures": failures,
    }


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

_GenESIS_PREV_HASH = "0" * 64  # fixed genesis for first event when no prior hash exists


def _get_latest_row_hash(conn=None) -> Optional[str]:
    """Return the row_hash of the most recent audit event that has one."""
    sql = (
        "SELECT row_hash FROM audit_events "
        "WHERE row_hash IS NOT NULL "
        "ORDER BY timestamp DESC, rowid DESC LIMIT 1"
    )
    if conn is not None:
        row = conn.execute(sql).fetchone()
    else:
        row = query_one(sql)
    if row is None:
        return None
    return row["row_hash"] if isinstance(row, dict) else row[0]


def _hash_payload(event: AuditEvent, prev_hash: Optional[str]) -> str:
    """Build a deterministic canonical JSON payload for hashing.

    Includes all stable audit fields plus prev_hash.
    Excludes row_hash itself.
    """
    payload = {
        "id": event.id,
        "timestamp": event.timestamp,
        "subject_id": event.subject_id,
        "role": event.role,
        "action": event.action,
        "resource": event.resource,
        "approved": bool(event.approved),
        "reason": event.reason,
        "matched_grant_id": event.matched_grant_id,
        "challenge_id": event.challenge_id,
        "challenge_present": bool(event.challenge_present),
        "challenge_result": event.challenge_result,
        "grant_signature_result": event.grant_signature_result,
        "prev_hash": prev_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _compute_row_hash(event: AuditEvent, prev_hash: Optional[str]) -> str:
    """Compute SHA-256 row hash over deterministic canonical payload."""
    canonical = _hash_payload(event, prev_hash)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def append_event(event: AuditEvent, conn=None) -> None:
    # GL-103: compute hash-chain linkage
    latest = _get_latest_row_hash(conn)
    prev_hash = latest if latest is not None else None
    row_hash = _compute_row_hash(event, prev_hash)

    sql = """INSERT INTO audit_events
           (id, timestamp, subject_id, role, action, resource,
            approved, reason, matched_grant_id,
            challenge_id, challenge_present, challenge_result,
            grant_signature_result, row_hash, prev_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    params = (
        event.id, event.timestamp, event.subject_id, event.role,
        event.action, event.resource, int(event.approved),
        event.reason, event.matched_grant_id,
        event.challenge_id, int(event.challenge_present), event.challenge_result,
        event.grant_signature_result,
        row_hash, prev_hash,
    )
    if conn is not None:
        conn.execute(sql, params)
    else:
        execute(sql, params)
    # Mutate the event in-place so callers see the hashes
    event.row_hash = row_hash
    event.prev_hash = prev_hash


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
        row_hash=row.get("row_hash"),
        prev_hash=row.get("prev_hash"),
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
            row_hash=r.get("row_hash"),
            prev_hash=r.get("prev_hash"),
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
            row_hash=r.get("row_hash"),
            prev_hash=r.get("prev_hash"),
        )
        for r in rows
    ]
