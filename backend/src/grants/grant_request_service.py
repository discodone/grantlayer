"""GrantRequestService — business logic for grant request lifecycle.

Handles create/approve/deny/revoke/list for grant requests.
Routers call this service; the service owns state transitions and audit.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, List, Optional, Tuple

from ..audit import audit_log as _audit_log
from ..core.models import AuditEvent, Grant, GrantRequest
from ..core.repositories import IGrantRepository, IGrantRequestRepository
from ..core.webhook_dispatcher import dispatch as _webhook_dispatch
from ..grants import grants as _grants_module

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session

    from ..core.repositories_sqlalchemy import (
        SqlAlchemyAsyncGrantRepository,
        SqlAlchemyAsyncGrantRequestRepository,
    )

_DEMO_WORKSPACE_ID = "default"


def _now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _is_request_expired(request: GrantRequest) -> bool:
    cutoff = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    ).isoformat().replace("+00:00", "Z")
    return request.created_at < cutoff


class GrantRequestService:
    def __init__(
        self,
        repo: IGrantRequestRepository,
        grant_repo: IGrantRepository,
        session: "Session",
    ) -> None:
        self._repo = repo
        self._grant_repo = grant_repo
        self._session = session

    def get_request(
        self,
        request_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> Optional[GrantRequest]:
        return self._repo.get(request_id, tenant_id=tenant_id, workspace_id=workspace_id)

    def list_requests(
        self,
        tenant_id: str,
        workspace_id: str,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[GrantRequest], int]:
        requests = self._repo.list(
            status_filter=status_filter,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            limit=limit,
            offset=offset,
        )
        total = self._repo.count(
            status_filter=status_filter, tenant_id=tenant_id, workspace_id=workspace_id
        )
        return requests, total

    def create_request(
        self,
        request: GrantRequest,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantRequest:
        return self._repo.create(request, tenant_id, workspace_id)

    def approve_request(
        self,
        request_id: str,
        operator_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> Tuple[GrantRequest, Grant]:
        req = self._repo.get(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if req is None:
            raise ValueError(f"Grant request {request_id} not found")
        if req.status != "requested":
            raise ValueError(
                f"Cannot approve grant request {request_id} with status {req.status}"
            )
        if _is_request_expired(req):
            raise ValueError("Grant request has expired")
        if req.requested_by == operator_id:
            raise ValueError("Self-approval is not permitted")

        grant = Grant(
            subject_id=req.subject_id,
            role=req.role,
            action=req.action,
            resource=req.resource,
            valid_from=req.valid_from,
            valid_until=req.valid_until,
            created_by=operator_id,
            reason=f"Approved from request {request_id}: {req.reason}",
        )
        _grants_module.create_grant(
            grant, session=self._session, tenant_id=tenant_id, workspace_id=workspace_id
        )

        now = _now_utc_iso()
        self._repo.mark_approved(request_id, operator_id, grant.id, now)

        _audit_log.append_event(
            AuditEvent(
                subject_id=operator_id,
                role="operator",
                action="approve_grant_request",
                resource=f"grant_request/{request_id}",
                approved=True,
                reason=f"Grant request {request_id} approved",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                scope="tenant",
            ),
            conn=self._session.connection(),
        )

        updated = self._repo.get(request_id)
        if updated is None:
            raise ValueError(f"Grant request {request_id} not found after approval")
        return updated, grant

    def deny_request(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantRequest:
        req = self._repo.get(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if req is None:
            raise ValueError(f"Grant request {request_id} not found")
        if req.status != "requested":
            raise ValueError(
                f"Cannot deny grant request {request_id} with status {req.status}"
            )

        now = _now_utc_iso()
        self._repo.mark_denied(request_id, operator_id, reason, now)

        _audit_log.append_event(
            AuditEvent(
                subject_id=operator_id,
                role="operator",
                action="deny_grant_request",
                resource=f"grant_request/{request_id}",
                approved=False,
                reason=f"Grant request {request_id} denied: {reason}",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                scope="tenant",
            ),
            conn=self._session.connection(),
        )

        updated = self._repo.get(request_id)
        if updated is None:
            raise ValueError(f"Grant request {request_id} not found after denial")
        return updated

    def revoke_request(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantRequest:
        req = self._repo.get(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if req is None:
            raise ValueError(f"Grant request {request_id} not found")
        if req.status != "approved":
            raise ValueError(
                f"Cannot revoke grant request {request_id} with status {req.status}"
            )

        if req.grant_id:
            _grants_module.revoke_grant(
                req.grant_id,
                operator_id,
                f"Revoked from request: {reason}",
                session=self._session,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            )

        now = _now_utc_iso()
        self._repo.mark_revoked(request_id, operator_id, reason, now)

        _audit_log.append_event(
            AuditEvent(
                subject_id=operator_id,
                role="operator",
                action="revoke_grant_request",
                resource=f"grant_request/{request_id}",
                approved=False,
                reason=f"Grant request {request_id} revoked: {reason}",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                scope="tenant",
            ),
            conn=self._session.connection(),
        )

        updated = self._repo.get(request_id)
        if updated is None:
            raise ValueError(f"Grant request {request_id} not found after revocation")
        return updated


class AsyncGrantRequestService:
    """Async version of GrantRequestService — uses AsyncSession and async repositories."""

    def __init__(
        self,
        repo: "SqlAlchemyAsyncGrantRequestRepository",
        grant_repo: "SqlAlchemyAsyncGrantRepository",
        session: "AsyncSession",
    ) -> None:
        self._repo = repo
        self._grant_repo = grant_repo
        self._session = session

    async def get_request(
        self,
        request_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> Optional[GrantRequest]:
        return await self._repo.get(request_id, tenant_id=tenant_id, workspace_id=workspace_id)

    async def list_requests(
        self,
        tenant_id: str,
        workspace_id: str,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> "Tuple[List[GrantRequest], int]":
        requests = await self._repo.list(
            status_filter=status_filter,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count(
            status_filter=status_filter, tenant_id=tenant_id, workspace_id=workspace_id
        )
        return requests, total

    async def create_request(
        self,
        request: GrantRequest,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantRequest:
        created = await self._repo.create(request, tenant_id, workspace_id)
        await _webhook_dispatch(
            "grant_request.created",
            {
                "id": created.id,
                "subject_id": created.subject_id,
                "role": created.role,
                "action": created.action,
                "resource": created.resource,
                "requested_by": created.requested_by,
                "reason": created.reason,
            },
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        return created

    async def approve_request(
        self,
        request_id: str,
        operator_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> "Tuple[GrantRequest, Grant]":
        req = await self._repo.get(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if req is None:
            raise ValueError(f"Grant request {request_id} not found")
        if req.status != "requested":
            raise ValueError(
                f"Cannot approve grant request {request_id} with status {req.status}"
            )
        if _is_request_expired(req):
            raise ValueError("Grant request has expired")
        if req.requested_by == operator_id:
            raise ValueError("Self-approval is not permitted")

        from ..core.crypto_signing import sign_grant as _sign_grant_fn
        grant = Grant(
            subject_id=req.subject_id,
            role=req.role,
            action=req.action,
            resource=req.resource,
            valid_from=req.valid_from,
            valid_until=req.valid_until,
            created_by=operator_id,
            reason=f"Approved from request {request_id}: {req.reason}",
        )
        sig_hex, hash_hex, key_id = _sign_grant_fn(grant)
        grant.signature = sig_hex
        grant.payload_hash = hash_hex
        grant.signing_key_id = key_id
        await self._grant_repo.create(grant, tenant_id=tenant_id, workspace_id=workspace_id)

        now = _now_utc_iso()
        await self._repo.mark_approved(request_id, operator_id, grant.id, now)

        approve_event = AuditEvent(
            subject_id=operator_id,
            role="operator",
            action="approve_grant_request",
            resource=f"grant_request/{request_id}",
            approved=True,
            reason=f"Grant request {request_id} approved",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            scope="tenant",
        )
        await self._session.run_sync(
            lambda sync_sess: _audit_log.append_event(approve_event, conn=sync_sess.connection())
        )

        updated = await self._repo.get(request_id)
        if updated is None:
            raise ValueError(f"Grant request {request_id} not found after approval")
        await _webhook_dispatch(
            "grant_request.approved",
            {"id": request_id, "grant_id": grant.id, "approved_by": operator_id},
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        return updated, grant

    async def deny_request(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantRequest:
        req = await self._repo.get(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if req is None:
            raise ValueError(f"Grant request {request_id} not found")
        if req.status != "requested":
            raise ValueError(
                f"Cannot deny grant request {request_id} with status {req.status}"
            )

        now = _now_utc_iso()
        await self._repo.mark_denied(request_id, operator_id, reason, now)

        deny_event = AuditEvent(
            subject_id=operator_id,
            role="operator",
            action="deny_grant_request",
            resource=f"grant_request/{request_id}",
            approved=False,
            reason=f"Grant request {request_id} denied: {reason}",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            scope="tenant",
        )
        await self._session.run_sync(
            lambda sync_sess: _audit_log.append_event(deny_event, conn=sync_sess.connection())
        )

        updated = await self._repo.get(request_id)
        if updated is None:
            raise ValueError(f"Grant request {request_id} not found after denial")
        await _webhook_dispatch(
            "grant_request.denied",
            {"id": request_id, "denied_by": operator_id, "reason": reason},
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        return updated

    async def revoke_request(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantRequest:
        req = await self._repo.get(request_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if req is None:
            raise ValueError(f"Grant request {request_id} not found")
        if req.status != "approved":
            raise ValueError(
                f"Cannot revoke grant request {request_id} with status {req.status}"
            )

        if req.grant_id:
            await self._grant_repo.revoke(
                req.grant_id,
                operator_id,
                f"Revoked from request: {reason}",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            )

        now = _now_utc_iso()
        await self._repo.mark_revoked(request_id, operator_id, reason, now)

        revoke_event = AuditEvent(
            subject_id=operator_id,
            role="operator",
            action="revoke_grant_request",
            resource=f"grant_request/{request_id}",
            approved=False,
            reason=f"Grant request {request_id} revoked: {reason}",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            scope="tenant",
        )
        await self._session.run_sync(
            lambda sync_sess: _audit_log.append_event(revoke_event, conn=sync_sess.connection())
        )

        updated = await self._repo.get(request_id)
        if updated is None:
            raise ValueError(f"Grant request {request_id} not found after revocation")
        return updated
