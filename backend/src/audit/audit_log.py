"""GrantLayer MVP — Audit log."""

import hashlib
import json
from threading import RLock
from typing import List, Optional, cast

from sqlalchemy import text

from ..core.db import (
    DB_BACKEND,
    execute,
    get_engine,
    query_all,
    query_one,
)
from ..core.models import AuditEvent

# ──────────────────────────────────────────────────────────────
# Process-local write lock — SQLite fallback for in-process safety
# ──────────────────────────────────────────────────────────────

_AUDIT_HASH_CHAIN_WRITE_LOCK = RLock()

# Transaction-scoped advisory lock key used on PostgreSQL to serialize
# hash-chain appends across multiple workers/processes in a cluster.
_PG_AUDIT_CHAIN_LOCK_KEY = 6252


# ──────────────────────────────────────────────────────────────
# Hash-chain helpers
# ──────────────────────────────────────────────────────────────

_Genesis_PREV_HASH = "0" * 64  # fixed genesis for first event when no prior hash exists


def _get_latest_row_hash(conn=None) -> Optional[str]:
    """Return the row_hash of the most recent audit event that has one."""
    sql = (
        "SELECT row_hash FROM audit_events "
        "WHERE row_hash IS NOT NULL "
        "ORDER BY timestamp DESC, seq DESC LIMIT 1"
    )
    if conn is not None:
        row = conn.execute(text(sql)).fetchone()
    else:
        row = query_one(sql)
    if row is None:
        return None
    if hasattr(row, "_mapping"):
        return row._mapping.get("row_hash")
    return row["row_hash"] if isinstance(row, dict) else row[0]


def _hash_payload(event: AuditEvent, prev_hash: Optional[str]) -> str:
    """Build a deterministic canonical JSON payload for hashing.

    Includes all stable audit fields plus prev_hash.
    Excludes row_hash itself.

    dual-mode: tenant_id is included in the canonical payload only
    when it is explicitly set (non-None). Pre-migration events (tenant_id=None)
    use the original payload format so their stored row_hash values remain valid.
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
    if event.tenant_id is not None:
        payload["tenant_id"] = event.tenant_id
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _compute_row_hash(event: AuditEvent, prev_hash: Optional[str]) -> str:
    """Compute SHA-256 row hash over deterministic canonical payload."""
    canonical = _hash_payload(event, prev_hash)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _row_to_audit_event(row: dict) -> AuditEvent:
    """Build an AuditEvent from a DB row dict."""
    raw_seq = row.get("seq")
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
        tenant_id=row.get("tenant_id"),
        # Legacy/pre-migration rows may still carry a NULL workspace_id; the
        # DB column stays nullable until the NOT NULL migration (separate ticket),
        # so preserve the stored value as-is rather than fabricating a workspace.
        workspace_id=cast(str, row.get("workspace_id")),
        scope=row.get("scope"),
        seq=int(raw_seq) if raw_seq is not None else None,
    )


# ──────────────────────────────────────────────────────────────
# Internal helpers to reduce duplication
# ──────────────────────────────────────────────────────────────

def _fetch_all_audit_events_ordered() -> list[dict]:
    """Fetch all audit events in deterministic insertion order."""
    return query_all("SELECT * FROM audit_events ORDER BY timestamp ASC, seq ASC")


def _filter_chain_rows(rows: list[dict]) -> list[dict]:
    """Filter to chain rows only; historical/pre-chain NULL rows are skipped."""
    return [r for r in rows if r.get("row_hash") is not None]


def _verify_single_event(
    event: AuditEvent,
    expected_prev_hash: Optional[str],
    index: int,
) -> list[dict]:
    """Verify a single audit event against its expected prev_hash.

    Returns a list of failure dicts (empty if valid).
    """
    failures: list[dict] = []

    # Verify prev_hash continuity
    if event.prev_hash != expected_prev_hash:
        failures.append({
            "event_id": event.id,
            "index": index,
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
            "index": index,
            "reason": (
                f"row_hash mismatch: stored={event.row_hash!r} "
                f"expected={recomputed!r}"
            ),
        })

    return failures


def _build_report_summary(
    valid: bool,
    checked_events: int,
    skipped_events: int,
    failure_count: int,
) -> tuple[str, str]:
    """Build human-readable summary and status for the verification report."""
    if valid:
        if checked_events == 0:
            if skipped_events > 0:
                summary = (
                    f"No chain events to verify; {skipped_events} "
                    "historical/pre-chain row(s) skipped."
                )
                status = "historical_only"
            else:
                summary = "No chain events to verify; audit log is empty."
                status = "empty"
        else:
            if skipped_events > 0:
                summary = (
                    f"Audit chain verified: {checked_events} event(s) checked, "
                    f"{skipped_events} historical/pre-chain row(s) skipped, "
                    "no failures."
                )
            else:
                summary = (
                    f"Audit chain verified: {checked_events} event(s) checked, "
                    "no failures."
                )
            status = "valid"
    else:
        summary = (
            f"Audit chain verification failed: {failure_count} failure(s) in "
            f"{checked_events} event(s) checked."
        )
        status = "invalid"
    return summary, status


def _build_report_recommendations(
    valid: bool,
    checked_events: int,
    failures: list[dict],
) -> list[str]:
    """Build deterministic recommendations based on verification result."""
    recommendations: list[str] = []
    if valid:
        if checked_events == 0:
            recommendations.append(
                "No action required; no chain events present."
            )
        else:
            recommendations.append(
                "No action required; chain integrity is intact."
            )
    else:
        has_row_hash_mismatch = any(
            "row_hash mismatch" in f["reason"] for f in failures
        )
        has_prev_hash_mismatch = any(
            "prev_hash mismatch" in f["reason"] for f in failures
        )

        if has_row_hash_mismatch:
            recommendations.append(
                "Investigate row_hash mismatches: audit event data may have "
                "been tampered with."
            )
        if has_prev_hash_mismatch:
            recommendations.append(
                "Investigate prev_hash mismatches: chain continuity may be "
                "broken or events reordered."
            )
        if not has_row_hash_mismatch and not has_prev_hash_mismatch:
            recommendations.append(
                "Investigate verification failures: review audit_events for "
                "anomalies."
            )
    return recommendations


# ──────────────────────────────────────────────────────────────
# Chain verification
# ──────────────────────────────────────────────────────────────

def verify_audit_hash_chain() -> dict:
    """Read-only verification of audit_events hash-chain integrity.

    Reads audit events in deterministic insertion order (timestamp ASC, id ASC),
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
    rows = _fetch_all_audit_events_ordered()
    chain_rows = _filter_chain_rows(rows)
    failures: list[dict] = []

    for i, row in enumerate(chain_rows):
        event = _row_to_audit_event(row)
        expected_prev_hash = chain_rows[i - 1]["row_hash"] if i > 0 else None
        failures.extend(_verify_single_event(event, expected_prev_hash, i))

    return {
        "valid": len(failures) == 0,
        "checked": len(chain_rows),
        "failures": failures,
    }


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

# PostgreSQL: omit seq so the column DEFAULT (nextval from sequence) fires.
_INSERT_SQL_PG = """INSERT INTO audit_events
               (id, timestamp, subject_id, role, action, resource,
                approved, reason, matched_grant_id,
                challenge_id, challenge_present, challenge_result,
                grant_signature_result, row_hash, prev_hash,
                tenant_id, workspace_id, scope)
               VALUES (:id, :timestamp, :subject_id, :role, :action, :resource,
                       :approved, :reason, :matched_grant_id,
                       :challenge_id, :challenge_present, :challenge_result,
                       :grant_signature_result, :row_hash, :prev_hash,
                       :tenant_id, :workspace_id, :scope)"""

# SQLite: include seq explicitly (computed in Python under the write lock).
_INSERT_SQL_SQLITE = """INSERT INTO audit_events
               (id, timestamp, subject_id, role, action, resource,
                approved, reason, matched_grant_id,
                challenge_id, challenge_present, challenge_result,
                grant_signature_result, row_hash, prev_hash,
                tenant_id, workspace_id, scope, seq)
               VALUES (:id, :timestamp, :subject_id, :role, :action, :resource,
                       :approved, :reason, :matched_grant_id,
                       :challenge_id, :challenge_present, :challenge_result,
                       :grant_signature_result, :row_hash, :prev_hash,
                       :tenant_id, :workspace_id, :scope, :seq)"""

# Legacy alias kept for any external callers that import it directly.
_INSERT_SQL = _INSERT_SQL_PG


def _build_insert_params(event: AuditEvent, row_hash: str, prev_hash: Optional[str]) -> dict:
    return {
        "id": event.id,
        "timestamp": event.timestamp,
        "subject_id": event.subject_id,
        "role": event.role,
        "action": event.action,
        "resource": event.resource,
        "approved": int(event.approved),
        "reason": event.reason,
        "matched_grant_id": event.matched_grant_id,
        "challenge_id": event.challenge_id,
        "challenge_present": int(event.challenge_present),
        "challenge_result": event.challenge_result,
        "grant_signature_result": event.grant_signature_result,
        "row_hash": row_hash,
        "prev_hash": prev_hash,
        "tenant_id": event.tenant_id,
        "workspace_id": event.workspace_id,
        "scope": event.scope,
    }


def _get_next_seq_sqlite(conn=None) -> int:
    """Return the next seq value for a SQLite INSERT (called under the write lock)."""
    if conn is not None:
        row = conn.execute(text("SELECT MAX(seq) AS max_seq FROM audit_events")).fetchone()
        if hasattr(row, "_mapping"):
            max_seq = row._mapping.get("max_seq")
        elif isinstance(row, dict):
            max_seq = row.get("max_seq")
        else:
            max_seq = row[0] if row else None
    else:
        row = query_one("SELECT MAX(seq) AS max_seq FROM audit_events")
        max_seq = row["max_seq"] if row else None
    return (max_seq or 0) + 1


def append_event(event: AuditEvent, conn=None) -> None:
    """Append an audit event with hash-chain linkage.

    Multi-worker safety:
    - PostgreSQL: acquires a transaction-scoped advisory lock (pg_advisory_xact_lock)
      so that only one worker at a time can read the chain tail and insert, even
      across multiple processes or containers.  The lock is always acquired on the
      PostgreSQL path regardless of whether the caller provides a connection.
    - SQLite: uses an in-process RLock (SQLite serializes writes at the file level,
      and single-process deployments don't need cross-process coordination).
    """
    if DB_BACKEND == "postgres":
        if conn is None:
            _append_event_postgres(event)
        else:
            _append_event_postgres_with_conn(event, conn)
    else:
        _append_event_sqlite(event, conn)


def _append_event_postgres(event: AuditEvent) -> None:
    """PostgreSQL path: advisory lock serializes across all workers."""
    conn = get_engine().connect()
    try:
        # Acquire a cluster-wide transaction-scoped exclusive advisory lock.
        # Released automatically when the transaction commits or rolls back.
        conn.execute(text(f"SELECT pg_advisory_xact_lock({_PG_AUDIT_CHAIN_LOCK_KEY})"))
        prev_hash = _get_latest_row_hash(conn)
        row_hash = _compute_row_hash(event, prev_hash)
        conn.execute(text(_INSERT_SQL_PG), _build_insert_params(event, row_hash, prev_hash))
        conn.commit()
        event.row_hash = row_hash
        event.prev_hash = prev_hash
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _append_event_postgres_with_conn(event: AuditEvent, conn) -> None:
    """PostgreSQL path when the caller already holds an open connection.

    Acquires the same advisory lock within the caller's transaction so that
    the audit chain read-then-insert is serialized across all workers.
    The caller retains ownership of the transaction and must commit/rollback.
    """
    conn.execute(text(f"SELECT pg_advisory_xact_lock({_PG_AUDIT_CHAIN_LOCK_KEY})"))
    prev_hash = _get_latest_row_hash(conn)
    row_hash = _compute_row_hash(event, prev_hash)
    conn.execute(text(_INSERT_SQL_PG), _build_insert_params(event, row_hash, prev_hash))
    event.row_hash = row_hash
    event.prev_hash = prev_hash


def _append_event_sqlite(event: AuditEvent, conn=None) -> None:
    """SQLite path: process-local RLock for in-process serialization."""
    with _AUDIT_HASH_CHAIN_WRITE_LOCK:
        prev_hash = _get_latest_row_hash(conn)
        row_hash = _compute_row_hash(event, prev_hash)
        next_seq = _get_next_seq_sqlite(conn)
        params = {**_build_insert_params(event, row_hash, prev_hash), "seq": next_seq}
        if conn is not None:
            conn.execute(text(_INSERT_SQL_SQLITE), params)
        else:
            execute(_INSERT_SQL_SQLITE, params)
        event.row_hash = row_hash
        event.prev_hash = prev_hash
        event.seq = next_seq


def get_event(event_id: str) -> Optional[AuditEvent]:
    row = query_one("SELECT * FROM audit_events WHERE id = ?", (event_id,))
    if row is None:
        return None
    return _row_to_audit_event(row)


def list_events(
    limit: int = 200,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    offset: int = 0,
    after_seq: Optional[int] = None,
) -> List[AuditEvent]:
    """Return audit events in descending (newest-first) order.

    Cursor-based pagination: pass after_seq to retrieve events with seq < after_seq.
    When after_seq is provided offset is ignored.
    Offset-based pagination: pass offset without after_seq (kept for backward compat).
    """
    conditions: list[str] = []
    params: list = []
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    if after_seq is not None:
        conditions.append("seq < ?")
        params.append(after_seq)
    sql = "SELECT * FROM audit_events"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY timestamp DESC, seq DESC LIMIT ? OFFSET ?"
    actual_offset = 0 if after_seq is not None else offset
    params.extend([limit, actual_offset])
    rows = query_all(sql, tuple(params))
    return [_row_to_audit_event(r) for r in rows]


def count_events(
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> int:
    conditions: list[str] = []
    params: list = []
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    sql = "SELECT COUNT(*) AS count FROM audit_events"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    row = query_one(sql, tuple(params))
    return int(row["count"]) if row else 0


def list_events_by_grant(grant_id: str, limit: int = 50) -> List[AuditEvent]:
    """Return audit events linked to a specific grant (via matched_grant_id)."""
    rows = query_all(
        "SELECT * FROM audit_events WHERE matched_grant_id = ? ORDER BY timestamp DESC LIMIT ?",
        (grant_id, limit),
    )
    return [_row_to_audit_event(r) for r in rows]


# ──────────────────────────────────────────────────────────────
# Chain verification report builder
# ──────────────────────────────────────────────────────────────

def build_audit_chain_verification_report() -> dict:
    """Build a stable auditor-readable structured report from verification.

    Uses verify_audit_hash_chain() internally and produces a deterministic,
    read-only structured report object suitable for auditor review.

    Returns a structured dict:
        {
            "report_type": str,
            "valid": bool,
            "checked_events": int,
            "failure_count": int,
            "failures": list[dict],
            "summary": str,
            "status": str,
            "recommendations": list[str],
        }

    This helper is read-only and does not insert or mutate audit_events.
    """
    # Count total and skipped rows to represent historical/pre-chain behavior
    rows = _fetch_all_audit_events_ordered()
    total_events = len(rows)
    chain_rows = _filter_chain_rows(rows)
    skipped_events = total_events - len(chain_rows)

    result = verify_audit_hash_chain()
    failures = result["failures"]
    failure_count = len(failures)
    checked_events = result["checked"]
    valid = result["valid"]

    summary, status = _build_report_summary(
        valid, checked_events, skipped_events, failure_count
    )
    recommendations = _build_report_recommendations(valid, checked_events, failures)

    return {
        "report_type": "audit_chain_verification",
        "valid": valid,
        "checked_events": checked_events,
        "failure_count": failure_count,
        "failures": list(failures),
        "summary": summary,
        "status": status,
        "recommendations": recommendations,
    }
