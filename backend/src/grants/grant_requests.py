"""GrantLayer MVP — Grant Request workflow.

This module provides functions for managing grant requests as a separate
lifecycle entity from grants themselves. A grant request can be:
- requested (initial state)
- approved (creates an actual grant)
- denied (rejected without creating a grant)
- revoked (was approved but later withdrawn)
- expired (auto-transitions after TTL)
"""

import datetime
from typing import List, Optional, Tuple

from ..audit import audit_log
from ..core import db
from ..core.models import AuditEvent, Grant, GrantRequest
from ..core.validation import (
    MAX_NAME_LENGTH,
    MAX_REASON_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_SHORT_ID_LENGTH,
    validate_string_length,
)
from . import grants

MAX_DENIAL_REASON_LENGTH = MAX_REASON_LENGTH  # single source of truth; alias kept for tests

VALID_REQUEST_STATUSES: frozenset[str] = frozenset({
    "requested", "approved", "denied", "revoked", "expired",
})

# Explicit allowlist of permitted grant roles for the public API (developer preview).
# Enforced at the HTTP layer (server.py) to validate user input without breaking internal
# test fixtures that use non-standard role strings for isolation purposes.
ALLOWED_GRANT_ROLES: frozenset[str] = frozenset({
    "viewer",
    "reviewer",
    "approver",
    "auditor",
    "operator",
    "admin",
})


def create_grant_request(
    request: GrantRequest,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> GrantRequest:
    """Create a new grant request in the 'requested' state."""
    validate_string_length(request.subject_id, "subject_id", MAX_SHORT_ID_LENGTH)
    validate_string_length(request.role, "role", MAX_ROLE_LENGTH)
    validate_string_length(request.action, "action", MAX_NAME_LENGTH)
    validate_string_length(request.resource, "resource", MAX_NAME_LENGTH)
    validate_string_length(request.reason, "reason", MAX_REASON_LENGTH)
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_tenant = tenant_id
    db.execute(
        """
        INSERT INTO grant_requests (
            id, subject_id, role, action, resource, valid_from, valid_until,
            requested_by, reason, status, created_at, updated_at, tenant_id,
            workspace_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            effective_tenant,
            workspace_id,
        ),
    )
    return request


def get_grant_request(
    request_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Optional[GrantRequest]:
    """Get a single grant request by ID."""
    conditions = ["id = ?"]
    params: list = [request_id]
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    row = db.query_one(
        "SELECT * FROM grant_requests WHERE " + " AND ".join(conditions),
        tuple(params),
    )
    if not row:
        return None
    return _row_to_grant_request(row)


def list_grant_requests(
    status_filter: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> List[GrantRequest]:
    """List grant requests, optionally filtered by status, tenant, and workspace."""
    conditions: list[str] = []
    params: list = []
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    if status_filter is not None:
        conditions.append("status = ?")
        params.append(status_filter)
    sql = "SELECT * FROM grant_requests"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC"
    rows = db.query_all(sql, tuple(params))
    return [_row_to_grant_request(row) for row in rows]


def _is_request_expired(request: GrantRequest) -> bool:
    """Check if a grant request has exceeded the 24-hour expiry window."""
    cutoff = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    ).isoformat().replace("+00:00", "Z")
    return request.created_at < cutoff


def approve_grant_request(
    request_id: str,
    operator_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Tuple[GrantRequest, Grant]:
    """Approve a grant request, creating the actual grant.

    Returns both the updated request and the newly created grant.
    """
    conn = db.get_conn()
    try:
        # Get the request (scoped to tenant/workspace if provided)
        request = get_grant_request(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if not request:
            raise ValueError(f"Grant request {request_id} not found")

        # Ensure the request is in the 'requested' state
        if request.status != "requested":
            raise ValueError(
                f"Cannot approve grant request {request_id} with status {request.status}"
            )

        # Reject approval of expired requests deterministically
        if _is_request_expired(request):
            raise ValueError("Grant request has expired")

        # Self-approval guard
        if request.requested_by == operator_id:
            raise ValueError("Self-approval is not permitted")

        # Start transaction
        conn.execute("BEGIN TRANSACTION")

        if tenant_id is None:
            raise ValueError("tenant_id is required")
        effective_tenant = tenant_id

        # Create the actual grant from the request (inherit workspace_id from request)
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

        # Save the grant using the shared transaction connection
        grants.create_grant(grant, conn=conn, tenant_id=effective_tenant, workspace_id=workspace_id)

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

        # Log an audit event for the approval inside the same transaction
        audit_log.append_event(
            AuditEvent(
                subject_id=operator_id,
                role="operator",
                action="approve_grant_request",
                resource=f"grant_request/{request_id}",
                approved=True,
                reason=f"Grant request {request_id} approved",
                tenant_id=effective_tenant,
                scope="tenant",
            ),
            conn=conn,
        )

        # Commit the transaction
        conn.commit()

        # Return the updated request and the newly created grant
        updated_request = get_grant_request(request_id)
        return updated_request, grant
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def deny_grant_request(
    request_id: str,
    operator_id: str,
    reason: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> GrantRequest:
    """Deny a grant request without creating a grant."""
    conn = db.get_conn()
    try:
        # Get the request (scoped to tenant/workspace if provided)
        request = get_grant_request(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if not request:
            raise ValueError(f"Grant request {request_id} not found")

        # Ensure the request is in the 'requested' state
        if request.status != "requested":
            raise ValueError(
                f"Cannot deny grant request {request_id} with status {request.status}"
            )

        # Denial reason length guard
        validate_string_length(reason, "reason", MAX_REASON_LENGTH)

        if tenant_id is None:
            raise ValueError("tenant_id is required")
        effective_tenant = tenant_id

        # Start transaction
        conn.execute("BEGIN TRANSACTION")

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

        # Log an audit event for the denial inside the same transaction
        audit_log.append_event(
            AuditEvent(
                subject_id=operator_id,
                role="operator",
                action="deny_grant_request",
                resource=f"grant_request/{request_id}",
                approved=False,
                reason=f"Grant request {request_id} denied: {reason}",
                tenant_id=effective_tenant,
                scope="tenant",
            ),
            conn=conn,
        )

        conn.commit()

        # Return the updated request
        updated_request = get_grant_request(request_id)
        return updated_request
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def revoke_grant_request(
    request_id: str,
    operator_id: str,
    reason: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> GrantRequest:
    """Revoke a previously approved grant request."""
    validate_string_length(reason, "reason", MAX_REASON_LENGTH)
    conn = db.get_conn()
    try:
        # Get the request (scoped to tenant/workspace if provided)
        request = get_grant_request(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if not request:
            raise ValueError(f"Grant request {request_id} not found")

        # Ensure the request is in the 'approved' state
        if request.status != "approved":
            raise ValueError(
                f"Cannot revoke grant request {request_id} with status {request.status}"
            )

        if tenant_id is None:
            raise ValueError("tenant_id is required")
        effective_tenant = tenant_id

        # Start transaction
        conn.execute("BEGIN TRANSACTION")

        # If there's an associated grant, revoke it too
        if request.grant_id:
            grants.revoke_grant(
                request.grant_id, operator_id,
                f"Revoked from request: {reason}", conn=conn,
                tenant_id=effective_tenant, workspace_id=workspace_id,
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

        # Log an audit event for the revocation inside the same transaction
        audit_log.append_event(
            AuditEvent(
                subject_id=operator_id,
                role="operator",
                action="revoke_grant_request",
                resource=f"grant_request/{request_id}",
                approved=False,
                reason=f"Grant request {request_id} revoked: {reason}",
                tenant_id=effective_tenant,
                scope="tenant",
            ),
            conn=conn,
        )

        # Commit the transaction
        conn.commit()

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

        # Find requests to expire (include tenant_id for audit propagation)
        to_expire = conn.execute(
            """
            SELECT id, tenant_id FROM grant_requests
            WHERE status = 'requested' AND created_at < ?
            """,
            (cutoff,),
        ).fetchall()

        if not to_expire:
            return 0

        # Start transaction
        conn.execute("BEGIN TRANSACTION")

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

        # Create expiry audit events for each expired request,
        # propagating tenant_id so audit events are tenant-scoped.
        for row in to_expire:
            row_tenant = row["tenant_id"] if hasattr(row, "__getitem__") else None
            audit_log.append_event(
                AuditEvent(
                    subject_id="system",
                    role="system",
                    action="expire_grant_request",
                    resource=f"grant_request/{row['id']}",
                    approved=False,
                    reason=f"Grant request {row['id']} expired after 24 hours",
                    tenant_id=row_tenant,
                    scope="tenant" if row_tenant else None,
                ),
                conn=conn,
            )

        conn.commit()

        # Return number of expired requests
        return len(to_expire)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_grant_request(row: dict) -> GrantRequest:
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
    row = db.query_one(
        "SELECT id FROM grant_requests WHERE grant_id = ? ORDER BY updated_at DESC LIMIT 1",
        (grant_id,),
    )
    return row["id"] if row else None
