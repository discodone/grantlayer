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
from typing import TYPE_CHECKING, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy import insert as sa_insert
from sqlalchemy import update as sa_update

from ..audit import audit_log
from ..core import db
from ..core.db import get_engine
from ..core.models import AuditEvent, Grant, GrantRequest
from ..core.orm import GrantRequest as OrmGrantRequest
from ..core.validation import (
    MAX_NAME_LENGTH,
    MAX_REASON_LENGTH,
    MAX_ROLE_LENGTH,
    MAX_SHORT_ID_LENGTH,
    validate_string_length,
)
from . import grants

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

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

_DEMO_WORKSPACE_ID = "default"


def _orm_to_grant_request(row: OrmGrantRequest) -> GrantRequest:
    return GrantRequest(
        id=row.id,
        subject_id=row.subject_id,
        role=row.role,
        action=row.action,
        resource=row.resource,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        requested_by=row.requested_by,
        reason=row.reason,
        status=row.status,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        denied_by=row.denied_by,
        denied_at=row.denied_at,
        denial_reason=row.denial_reason,
        revoked_by=row.revoked_by,
        revoked_at=row.revoked_at,
        revoked_reason=row.revoked_reason,
        grant_id=row.grant_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create_grant_request(
    request: GrantRequest,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
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
    effective_workspace = workspace_id if workspace_id is not None else _DEMO_WORKSPACE_ID
    if session is not None:
        session.execute(
            sa_insert(OrmGrantRequest.__table__).values(
                id=request.id,
                subject_id=request.subject_id,
                role=request.role,
                action=request.action,
                resource=request.resource,
                valid_from=request.valid_from,
                valid_until=request.valid_until,
                requested_by=request.requested_by,
                reason=request.reason,
                status=request.status,
                created_at=request.created_at,
                updated_at=request.updated_at,
                tenant_id=effective_tenant,
                workspace_id=effective_workspace,
            )
        )
    else:
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
                effective_workspace,
            ),
        )
    return request


def get_grant_request(
    request_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> Optional[GrantRequest]:
    """Get a single grant request by ID."""
    if session is not None:
        stmt = select(OrmGrantRequest).where(OrmGrantRequest.id == request_id)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantRequest.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantRequest.workspace_id == workspace_id)
        orm_row = session.execute(stmt).scalars().first()
        return _orm_to_grant_request(orm_row) if orm_row else None
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
    limit: Optional[int] = None,
    offset: int = 0,
    session: "Optional[Session]" = None,
) -> List[GrantRequest]:
    """List grant requests, optionally filtered by status, tenant, and workspace."""
    if session is not None:
        stmt = select(OrmGrantRequest).order_by(OrmGrantRequest.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantRequest.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantRequest.workspace_id == workspace_id)
        if status_filter is not None:
            stmt = stmt.where(OrmGrantRequest.status == status_filter)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return [_orm_to_grant_request(r) for r in session.execute(stmt).scalars().all()]
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
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    rows = db.query_all(sql, tuple(params))
    return [_row_to_grant_request(row) for row in rows]


def count_grant_requests(
    status_filter: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> int:
    if session is not None:
        stmt = select(func.count()).select_from(OrmGrantRequest)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantRequest.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantRequest.workspace_id == workspace_id)
        if status_filter is not None:
            stmt = stmt.where(OrmGrantRequest.status == status_filter)
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
    if status_filter is not None:
        conditions.append("status = ?")
        params.append(status_filter)
    sql = "SELECT COUNT(*) AS count FROM grant_requests"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    row = db.query_one(sql, tuple(params))
    return int(row["count"]) if row else 0


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
    conn = get_engine().connect()
    try:
        request = get_grant_request(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if not request:
            raise ValueError(f"Grant request {request_id} not found")

        if request.status != "requested":
            raise ValueError(
                f"Cannot approve grant request {request_id} with status {request.status}"
            )

        if _is_request_expired(request):
            raise ValueError("Grant request has expired")

        if request.requested_by == operator_id:
            raise ValueError("Self-approval is not permitted")

        if tenant_id is None:
            raise ValueError("tenant_id is required")
        effective_tenant = tenant_id
        effective_workspace = workspace_id if workspace_id is not None else _DEMO_WORKSPACE_ID

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

        with conn.begin():
            grants.create_grant(grant, conn=conn, tenant_id=effective_tenant, workspace_id=effective_workspace)

            now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            conn.execute(
                sa_update(OrmGrantRequest.__table__)
                .where(OrmGrantRequest.id == request_id)
                .values(
                    status="approved",
                    approved_by=operator_id,
                    approved_at=now,
                    grant_id=grant.id,
                    updated_at=now,
                )
            )

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

        updated_request = get_grant_request(request_id)
        if updated_request is None:
            raise ValueError(f"Grant request {request_id} not found after approval")
        return updated_request, grant
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
    conn = get_engine().connect()
    try:
        request = get_grant_request(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if not request:
            raise ValueError(f"Grant request {request_id} not found")

        if request.status != "requested":
            raise ValueError(
                f"Cannot deny grant request {request_id} with status {request.status}"
            )

        validate_string_length(reason, "reason", MAX_REASON_LENGTH)

        if tenant_id is None:
            raise ValueError("tenant_id is required")
        effective_tenant = tenant_id

        with conn.begin():
            now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            conn.execute(
                sa_update(OrmGrantRequest.__table__)
                .where(OrmGrantRequest.id == request_id)
                .values(
                    status="denied",
                    denied_by=operator_id,
                    denied_at=now,
                    denial_reason=reason,
                    updated_at=now,
                )
            )

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

        updated_request = get_grant_request(request_id)
        if updated_request is None:
            raise ValueError(f"Grant request {request_id} not found after denial")
        return updated_request
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
    conn = get_engine().connect()
    try:
        request = get_grant_request(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if not request:
            raise ValueError(f"Grant request {request_id} not found")

        if request.status != "approved":
            raise ValueError(
                f"Cannot revoke grant request {request_id} with status {request.status}"
            )

        if tenant_id is None:
            raise ValueError("tenant_id is required")
        effective_tenant = tenant_id

        with conn.begin():
            if request.grant_id:
                grants.revoke_grant(
                    request.grant_id, operator_id,
                    f"Revoked from request: {reason}", conn=conn,
                    tenant_id=effective_tenant, workspace_id=workspace_id,
                )

            now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            conn.execute(
                sa_update(OrmGrantRequest.__table__)
                .where(OrmGrantRequest.id == request_id)
                .values(
                    status="revoked",
                    revoked_by=operator_id,
                    revoked_at=now,
                    revoked_reason=reason,
                    updated_at=now,
                )
            )

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

        updated_request = get_grant_request(request_id)
        if updated_request is None:
            raise ValueError(f"Grant request {request_id} not found after revocation")
        return updated_request
    finally:
        conn.close()


def expire_old_requests() -> int:
    """Expire grant requests that have been in 'requested' state for too long.

    Returns the number of requests expired.
    """
    conn = get_engine().connect()
    try:
        cutoff = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
        ).isoformat().replace("+00:00", "Z")

        to_expire = conn.execute(
            select(OrmGrantRequest.id, OrmGrantRequest.tenant_id)
            .where(
                OrmGrantRequest.status == "requested",
                OrmGrantRequest.created_at < cutoff,
            )
        ).fetchall()

        if not to_expire:
            return 0

        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        for row in to_expire:
            conn.execute(
                sa_update(OrmGrantRequest.__table__)
                .where(OrmGrantRequest.id == row.id)
                .values(status="expired", updated_at=now)
            )

        for row in to_expire:
            row_tenant = row.tenant_id or None
            audit_log.append_event(
                AuditEvent(
                    subject_id="system",
                    role="system",
                    action="expire_grant_request",
                    resource=f"grant_request/{row.id}",
                    approved=False,
                    reason=f"Grant request {row.id} expired after 24 hours",
                    tenant_id=row_tenant,
                    scope="tenant" if row_tenant else None,
                ),
                conn=conn,
            )

        conn.commit()
        return len(to_expire)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_grant_request(row: dict) -> GrantRequest:
    """Convert a database row dict to a GrantRequest object."""
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
