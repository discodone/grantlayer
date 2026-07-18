"""GrantLayer MVP — Grant Request workflow.

A grant request can be:
- requested (initial state)
- approved (creates an actual grant)
- denied (rejected without creating a grant)
- revoked (was approved but later withdrawn)
- expired (auto-transitions after TTL)
"""

import datetime
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, List, Optional, Tuple

from sqlalchemy.orm import Session as _Session

from ..audit import audit_log
from ..core.db import get_engine
from ..core.models import SYSTEM_WORKSPACE, AuditEvent, Grant, GrantRequest
from ..core.repositories_sqlalchemy import SqlAlchemyGrantRequestRepository
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

MAX_DENIAL_REASON_LENGTH = MAX_REASON_LENGTH  # alias kept for tests

VALID_REQUEST_STATUSES: frozenset[str] = frozenset({
    "requested", "approved", "denied", "revoked", "expired",
})

ALLOWED_GRANT_ROLES: frozenset[str] = frozenset({
    "viewer",
    "reviewer",
    "approver",
    "auditor",
    "operator",
    "admin",
    "agent",
})

_DEMO_WORKSPACE_ID = "default"


@contextmanager
def _auto_session() -> Generator["Session", None, None]:
    from sqlalchemy.orm import Session as _Session

    from ..core.db import get_engine
    session = _Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_grant_request(
    request: GrantRequest,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> GrantRequest:
    validate_string_length(request.subject_id, "subject_id", MAX_SHORT_ID_LENGTH)
    validate_string_length(request.role, "role", MAX_ROLE_LENGTH)
    validate_string_length(request.action, "action", MAX_NAME_LENGTH)
    validate_string_length(request.resource, "resource", MAX_NAME_LENGTH)
    validate_string_length(request.reason, "reason", MAX_REASON_LENGTH)
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_workspace = workspace_id if workspace_id is not None else _DEMO_WORKSPACE_ID
    if session is not None:
        return SqlAlchemyGrantRequestRepository(session).create(request, tenant_id, effective_workspace)
    with _auto_session() as sess:
        return SqlAlchemyGrantRequestRepository(sess).create(request, tenant_id, effective_workspace)


def get_grant_request(
    request_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> Optional[GrantRequest]:
    if session is not None:
        return SqlAlchemyGrantRequestRepository(session).get(
            request_id, tenant_id=tenant_id, workspace_id=workspace_id
        )
    with _auto_session() as sess:
        return SqlAlchemyGrantRequestRepository(sess).get(
            request_id, tenant_id=tenant_id, workspace_id=workspace_id
        )


def list_grant_requests(
    status_filter: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    session: "Optional[Session]" = None,
) -> List[GrantRequest]:
    if session is not None:
        return SqlAlchemyGrantRequestRepository(session).list(
            status_filter=status_filter,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            limit=limit,
            offset=offset,
        )
    with _auto_session() as sess:
        return SqlAlchemyGrantRequestRepository(sess).list(
            status_filter=status_filter,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            limit=limit,
            offset=offset,
        )


def count_grant_requests(
    status_filter: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> int:
    if session is not None:
        return SqlAlchemyGrantRequestRepository(session).count(
            status_filter=status_filter, tenant_id=tenant_id, workspace_id=workspace_id
        )
    with _auto_session() as sess:
        return SqlAlchemyGrantRequestRepository(sess).count(
            status_filter=status_filter, tenant_id=tenant_id, workspace_id=workspace_id
        )


def _is_request_expired(request: GrantRequest) -> bool:
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
    """Approve a grant request, creating the actual grant."""
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_tenant = tenant_id
    effective_workspace = workspace_id if workspace_id is not None else _DEMO_WORKSPACE_ID

    with _Session(get_engine()) as session:
        with session.begin():
            req_repo = SqlAlchemyGrantRequestRepository(session)

            request = req_repo.get(request_id, tenant_id=effective_tenant, workspace_id=workspace_id)
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

            # Use create_grant so that module-level _sign_grant can be patched in tests.
            grants.create_grant(grant, session=session, tenant_id=effective_tenant, workspace_id=effective_workspace)

            now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            req_repo.mark_approved(request_id, operator_id, grant.id, now)

            audit_log.append_event(
                AuditEvent(
                    subject_id=operator_id,
                    role="operator",
                    action="approve_grant_request",
                    resource=f"grant_request/{request_id}",
                    approved=True,
                    reason=f"Grant request {request_id} approved",
                    tenant_id=effective_tenant,
                    workspace_id=effective_workspace,
                    scope="tenant",
                ),
                conn=session.connection(),
            )

        updated_request = req_repo.get(request_id)
        if updated_request is None:
            raise ValueError(f"Grant request {request_id} not found after approval")
        return updated_request, grant


def deny_grant_request(
    request_id: str,
    operator_id: str,
    reason: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> GrantRequest:
    """Deny a grant request without creating a grant."""
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_tenant = tenant_id
    effective_workspace = workspace_id if workspace_id is not None else _DEMO_WORKSPACE_ID

    validate_string_length(reason, "reason", MAX_REASON_LENGTH)

    with _Session(get_engine()) as session:
        with session.begin():
            req_repo = SqlAlchemyGrantRequestRepository(session)

            request = req_repo.get(request_id, tenant_id=effective_tenant, workspace_id=workspace_id)
            if not request:
                raise ValueError(f"Grant request {request_id} not found")
            if request.status != "requested":
                raise ValueError(
                    f"Cannot deny grant request {request_id} with status {request.status}"
                )

            now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            req_repo.mark_denied(request_id, operator_id, reason, now)

            audit_log.append_event(
                AuditEvent(
                    subject_id=operator_id,
                    role="operator",
                    action="deny_grant_request",
                    resource=f"grant_request/{request_id}",
                    approved=False,
                    reason=f"Grant request {request_id} denied: {reason}",
                    tenant_id=effective_tenant,
                    workspace_id=effective_workspace,
                    scope="tenant",
                ),
                conn=session.connection(),
            )

        updated_request = req_repo.get(request_id)
        if updated_request is None:
            raise ValueError(f"Grant request {request_id} not found after denial")
        return updated_request


def revoke_grant_request(
    request_id: str,
    operator_id: str,
    reason: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> GrantRequest:
    """Revoke a previously approved grant request."""
    validate_string_length(reason, "reason", MAX_REASON_LENGTH)

    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_tenant = tenant_id
    effective_workspace = workspace_id if workspace_id is not None else _DEMO_WORKSPACE_ID

    with _Session(get_engine()) as session:
        with session.begin():
            req_repo = SqlAlchemyGrantRequestRepository(session)

            request = req_repo.get(request_id, tenant_id=effective_tenant, workspace_id=workspace_id)
            if not request:
                raise ValueError(f"Grant request {request_id} not found")
            if request.status != "approved":
                raise ValueError(
                    f"Cannot revoke grant request {request_id} with status {request.status}"
                )

            if request.grant_id:
                grants.revoke_grant(
                    request.grant_id, operator_id,
                    f"Revoked from request: {reason}",
                    session=session,
                    tenant_id=effective_tenant, workspace_id=workspace_id,
                )

            now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            req_repo.mark_revoked(request_id, operator_id, reason, now)

            audit_log.append_event(
                AuditEvent(
                    subject_id=operator_id,
                    role="operator",
                    action="revoke_grant_request",
                    resource=f"grant_request/{request_id}",
                    approved=False,
                    reason=f"Grant request {request_id} revoked: {reason}",
                    tenant_id=effective_tenant,
                    workspace_id=effective_workspace,
                    scope="tenant",
                ),
                conn=session.connection(),
            )

        updated_request = req_repo.get(request_id)
        if updated_request is None:
            raise ValueError(f"Grant request {request_id} not found after revocation")
        return updated_request


def expire_old_requests() -> int:
    """Expire grant requests older than 24 hours in 'requested' state."""
    cutoff = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    ).isoformat().replace("+00:00", "Z")

    with _auto_session() as session:
        req_repo = SqlAlchemyGrantRequestRepository(session)
        to_expire = req_repo.list_pending_for_expiry(cutoff)
        if not to_expire:
            return 0

        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        for row_id, _tenant, _workspace in to_expire:
            req_repo.mark_expired(row_id, now)

        audit_conn = session.connection()
        for row_id, row_tenant, row_workspace in to_expire:
            audit_log.append_event(
                AuditEvent(
                    subject_id="system",
                    role="system",
                    action="expire_grant_request",
                    resource=f"grant_request/{row_id}",
                    approved=False,
                    reason=f"Grant request {row_id} expired after 24 hours",
                    tenant_id=row_tenant,
                    workspace_id=row_workspace if row_workspace is not None else SYSTEM_WORKSPACE,
                    scope="tenant" if row_tenant else "system",
                ),
                conn=audit_conn,
            )

        return len(to_expire)


def get_grant_request_id_by_grant_id(grant_id: str) -> Optional[str]:
    with _auto_session() as sess:
        return SqlAlchemyGrantRequestRepository(sess).get_id_by_grant_id(grant_id)
