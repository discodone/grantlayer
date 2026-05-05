"""GrantLayer MVP — GL-022 Grant Request workflow.

This module provides functions for managing grant requests as a separate
lifecycle entity from grants themselves. A grant request can be:
- requested (initial state)
- approved (creates an actual grant)
- denied (rejected without creating a grant)
- revoked (was approved but later withdrawn)
- expired (auto-transitions after TTL)
"""

import sqlite3
import datetime
from typing import List, Optional, Dict, Any, Tuple

from . import db
from . import grants
from . import audit_log
from .models import GrantRequest, Grant, AuditEvent


def create_grant_request(request: GrantRequest) -> GrantRequest:
    """Create a new grant request in the 'requested' state."""
    conn = db.get_conn()
    try:
        conn.execute(
            """
            INSERT INTO grant_requests (
                id, subject_id, role, action, resource, valid_from, valid_until,
                requested_by, reason, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.id,
                request.subject_id,
                request.role,
                request.action,
                request.resource,
                request.valid_from,
                request.valid_until,
                request.requested_by,
                request.reason,
                request.status,
                request.created_at,
                request.updated_at,
            ),
        )
        conn.commit()
        return request
    finally:
        conn.close()


def get_grant_request(request_id: str) -> Optional[GrantRequest]:
    """Get a single grant request by ID."""
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM grant_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if not row:
            return None

        return _row_to_grant_request(row)
    finally:
        conn.close()


def list_grant_requests(status_filter: Optional[str] = None) -> List[GrantRequest]:
    """List all grant requests, optionally filtered by status."""
    conn = db.get_conn()
    try:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM grant_requests WHERE status = ? ORDER BY created_at DESC",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM grant_requests ORDER BY created_at DESC"
            ).fetchall()

        return [_row_to_grant_request(row) for row in rows]
    finally:
        conn.close()


def approve_grant_request(
    request_id: str, operator_id: str
) -> Tuple[GrantRequest, Grant]:
    """Approve a grant request, creating the actual grant.
    
    Returns both the updated request and the newly created grant.
    """
    conn = db.get_conn()
    try:
        # Get the request
        request = get_grant_request(request_id)
        if not request:
            raise ValueError(f"Grant request {request_id} not found")

        # Ensure the request is in the 'requested' state
        if request.status != "requested":
            raise ValueError(
                f"Cannot approve grant request {request_id} with status {request.status}"
            )

        # Start transaction
        conn.execute("BEGIN TRANSACTION")

        # Create the actual grant from the request
        grant = Grant(
            subject_id=request.subject_id,
            role=request.role,
            action=request.action,
            resource=request.resource,
            valid_from=request.valid_from,
            valid_until=request.valid_until,
            created_by=operator_id,
            reason=f"Approved from request {request_id}: {request.reason}",
        )

        # Save the grant
        grants.create_grant(grant)

        # Update the request to approved state
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        conn.execute(
            """
            UPDATE grant_requests
            SET status = ?, approved_by = ?, approved_at = ?, grant_id = ?, updated_at = ?
            WHERE id = ?
            """,
            ("approved", operator_id, now, grant.id, now, request_id),
        )
        
        # Commit the transaction
        conn.commit()
        
        # Log an audit event for the approval
        audit_log.append_event(
            AuditEvent(
                subject_id=operator_id,
                role="operator",
                action="approve_grant_request",
                resource=f"grant_request/{request_id}",
                approved=True,
                reason=f"Grant request {request_id} approved",
            )
        )
        
        # Return the updated request and the newly created grant
        updated_request = get_grant_request(request_id)
        return updated_request, grant
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def deny_grant_request(
    request_id: str, operator_id: str, reason: str
) -> GrantRequest:
    """Deny a grant request without creating a grant."""
    conn = db.get_conn()
    try:
        # Get the request
        request = get_grant_request(request_id)
        if not request:
            raise ValueError(f"Grant request {request_id} not found")

        # Ensure the request is in the 'requested' state
        if request.status != "requested":
            raise ValueError(
                f"Cannot deny grant request {request_id} with status {request.status}"
            )

        # Update the request to denied state
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        conn.execute(
            """
            UPDATE grant_requests
            SET status = ?, denied_by = ?, denied_at = ?, denial_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            ("denied", operator_id, now, reason, now, request_id),
        )
        conn.commit()
        
        # Log an audit event for the denial
        audit_log.append_event(
            AuditEvent(
                subject_id=operator_id,
                role="operator",
                action="deny_grant_request",
                resource=f"grant_request/{request_id}",
                approved=True,  # approval of the action, not the grant
                reason=f"Grant request {request_id} denied: {reason}",
            )
        )
        
        # Return the updated request
        updated_request = get_grant_request(request_id)
        return updated_request
    finally:
        conn.close()


def revoke_grant_request(
    request_id: str, operator_id: str, reason: str
) -> GrantRequest:
    """Revoke a previously approved grant request."""
    conn = db.get_conn()
    try:
        # Get the request
        request = get_grant_request(request_id)
        if not request:
            raise ValueError(f"Grant request {request_id} not found")

        # Ensure the request is in the 'approved' state
        if request.status != "approved":
            raise ValueError(
                f"Cannot revoke grant request {request_id} with status {request.status}"
            )

        # Start transaction
        conn.execute("BEGIN TRANSACTION")

        # If there's an associated grant, revoke it too
        if request.grant_id:
            grants.revoke_grant(
                request.grant_id, operator_id, f"Revoked from request: {reason}"
            )

        # Update the request to revoked state
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        conn.execute(
            """
            UPDATE grant_requests
            SET status = ?, revoked_by = ?, revoked_at = ?, revoked_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            ("revoked", operator_id, now, reason, now, request_id),
        )
        
        # Commit the transaction
        conn.commit()
        
        # Log an audit event for the revocation
        audit_log.append_event(
            AuditEvent(
                subject_id=operator_id,
                role="operator",
                action="revoke_grant_request",
                resource=f"grant_request/{request_id}",
                approved=True,  # approval of the action, not the grant
                reason=f"Grant request {request_id} revoked: {reason}",
            )
        )
        
        # Return the updated request
        updated_request = get_grant_request(request_id)
        return updated_request
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def expire_old_requests() -> int:
    """Expire grant requests that have been in 'requested' state for too long.
    
    Returns the number of requests expired.
    """
    conn = db.get_conn()
    try:
        # Calculate the expiry cutoff time (24 hours ago)
        cutoff = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
        ).isoformat().replace("+00:00", "Z")
        
        # Find requests to expire
        to_expire = conn.execute(
            """
            SELECT id FROM grant_requests 
            WHERE status = 'requested' AND created_at < ?
            """,
            (cutoff,),
        ).fetchall()
        
        if not to_expire:
            return 0
            
        # Update requests to expired state
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        conn.executemany(
            """
            UPDATE grant_requests
            SET status = 'expired', updated_at = ?
            WHERE id = ?
            """,
            [(now, row["id"]) for row in to_expire],
        )
        conn.commit()
        
        # Return number of expired requests
        return len(to_expire)
    finally:
        conn.close()


def _row_to_grant_request(row: sqlite3.Row) -> GrantRequest:
    """Convert a database row to a GrantRequest object."""
    return GrantRequest(
        id=row["id"],
        subject_id=row["subject_id"],
        role=row["role"],
        action=row["action"],
        resource=row["resource"],
        valid_from=row["valid_from"],
        valid_until=row["valid_until"],
        requested_by=row["requested_by"],
        reason=row["reason"],
        status=row["status"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
        denied_by=row["denied_by"],
        denied_at=row["denied_at"],
        denial_reason=row["denial_reason"],
        revoked_by=row["revoked_by"],
        revoked_at=row["revoked_at"],
        revoked_reason=row["revoked_reason"],
        grant_id=row["grant_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_grant_request_id_by_grant_id(grant_id: str) -> Optional[str]:
    """Get the most recent grant_request_id associated with a grant_id."""
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM grant_requests WHERE grant_id = ? ORDER BY updated_at DESC LIMIT 1",
            (grant_id,),
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()