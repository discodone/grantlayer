"""SQLAlchemy repository implementations.

Each class takes a Session and performs all DB access through the ORM.
No raw SQL, no text(), no execute().
"""

from __future__ import annotations

import datetime
import secrets
import uuid
from typing import TYPE_CHECKING, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy import insert as sa_insert
from sqlalchemy import update as sa_update
from sqlalchemy.engine import CursorResult

from .models import Grant, GrantExecution, GrantRequest
from .orm import (
    Grant as OrmGrant,
)
from .orm import (
    GrantExecution as OrmGrantExecution,
)
from .orm import (
    GrantRequest as OrmGrantRequest,
)
from .orm import (
    Operator as OrmOperator,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session

    from ..auth.operators import Operator

_DEMO_WORKSPACE_ID = "default"


# ── Converter helpers ────────────────────────────────────────────────────────

def _orm_to_grant(row: OrmGrant) -> Grant:
    return Grant(
        id=str(row.id),
        subject_id=str(row.subject_id),
        role=str(row.role),
        action=str(row.action),
        resource=str(row.resource),
        valid_from=str(row.valid_from),
        valid_until=str(row.valid_until),
        created_by=str(row.created_by),
        reason=str(row.reason),
        revoked=bool(row.revoked),
        revoked_by=str(row.revoked_by) if row.revoked_by is not None else None,
        revoked_reason=str(row.revoked_reason) if row.revoked_reason is not None else None,
        revoked_at=str(row.revoked_at) if row.revoked_at is not None else None,
        created_at=str(row.created_at),
        signature=str(row.signature) if row.signature is not None else None,
        signing_key_id=str(row.signing_key_id) if row.signing_key_id is not None else None,
        payload_hash=str(row.payload_hash) if row.payload_hash is not None else None,
        max_uses=int(row.max_uses) if row.max_uses is not None else None,
        use_count=int(row.use_count) if row.use_count is not None else 0,
    )


def _orm_to_grant_request(row: OrmGrantRequest) -> GrantRequest:
    return GrantRequest(
        id=str(row.id),
        subject_id=str(row.subject_id),
        role=str(row.role),
        action=str(row.action),
        resource=str(row.resource),
        valid_from=str(row.valid_from),
        valid_until=str(row.valid_until),
        requested_by=str(row.requested_by),
        reason=str(row.reason),
        status=str(row.status),  # type: ignore[arg-type]
        approved_by=str(row.approved_by) if row.approved_by is not None else None,
        approved_at=str(row.approved_at) if row.approved_at is not None else None,
        denied_by=str(row.denied_by) if row.denied_by is not None else None,
        denied_at=str(row.denied_at) if row.denied_at is not None else None,
        denial_reason=str(row.denial_reason) if row.denial_reason is not None else None,
        revoked_by=str(row.revoked_by) if row.revoked_by is not None else None,
        revoked_at=str(row.revoked_at) if row.revoked_at is not None else None,
        revoked_reason=str(row.revoked_reason) if row.revoked_reason is not None else None,
        grant_id=str(row.grant_id) if row.grant_id is not None else None,
        created_at=str(row.created_at),
        updated_at=str(row.updated_at),
    )


def _orm_to_grant_execution(row: OrmGrantExecution) -> GrantExecution:
    return GrantExecution(
        id=str(row.id),
        grant_id=str(row.grant_id) if row.grant_id is not None else None,
        grant_request_id=str(row.grant_request_id) if row.grant_request_id is not None else None,
        operator_id=str(row.operator_id) if row.operator_id is not None else None,
        action=str(row.action),
        resource=str(row.resource),
        challenge_id=str(row.challenge_id) if row.challenge_id is not None else None,
        challenge_result=str(row.challenge_result) if row.challenge_result is not None else None,
        policy_result=str(row.policy_result) if row.policy_result is not None else "",
        result=str(row.result),  # type: ignore[arg-type]
        error_code=str(row.error_code) if row.error_code is not None else None,
        executed_at=str(row.executed_at),
        audit_event_id=str(row.audit_event_id) if row.audit_event_id is not None else None,
        metadata_json=str(row.metadata_json) if row.metadata_json is not None else None,
    )


def _orm_to_operator(row: OrmOperator) -> "Operator":
    from ..auth.operators import Operator
    return Operator(
        operator_id=str(row.id),
        name=str(row.name),
        role=str(row.role),
        active=bool(row.active),
        created_at=str(row.created_at) if row.created_at is not None else None,
        expires_at=str(row.expires_at) if row.expires_at is not None else None,
        rotated_at=str(row.rotated_at) if row.rotated_at is not None else None,
        tenant_id=str(row.tenant_id),
    )


def _now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


# ── Grant repository ─────────────────────────────────────────────────────────

class SqlAlchemyGrantRepository:
    def __init__(self, session: "Session") -> None:
        self._s = session

    def get(
        self,
        grant_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[Grant]:
        stmt = select(OrmGrant).where(OrmGrant.id == grant_id)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        row = self._s.execute(stmt).scalars().first()
        return _orm_to_grant(row) if row else None

    def list(
        self,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Grant]:
        stmt = select(OrmGrant).order_by(OrmGrant.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return [_orm_to_grant(r) for r in self._s.execute(stmt).scalars().all()]

    def create(
        self,
        grant: Grant,
        tenant_id: str,
        workspace_id: str,
    ) -> Grant:
        # Caller is responsible for signing before calling create().
        effective_workspace = workspace_id if workspace_id else _DEMO_WORKSPACE_ID
        self._s.execute(
            sa_insert(OrmGrant).values(
                id=grant.id,
                subject_id=grant.subject_id,
                role=grant.role,
                action=grant.action,
                resource=grant.resource,
                valid_from=grant.valid_from,
                valid_until=grant.valid_until,
                created_by=grant.created_by,
                reason=grant.reason,
                revoked=0,
                created_at=grant.created_at,
                max_uses=grant.max_uses,
                use_count=grant.use_count,
                signature=grant.signature,
                signing_key_id=grant.signing_key_id,
                payload_hash=grant.payload_hash,
                tenant_id=tenant_id,
                workspace_id=effective_workspace,
            )
        )
        return grant

    def revoke(
        self,
        grant_id: str,
        revoked_by: str,
        reason: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> bool:
        revoked_at = _now_utc_iso()
        stmt = (
            sa_update(OrmGrant)
            .where(OrmGrant.id == grant_id, OrmGrant.revoked == 0)
            .values(revoked=1, revoked_by=revoked_by, revoked_reason=reason, revoked_at=revoked_at)
        )
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        result: CursorResult = self._s.execute(stmt)  # type: ignore[assignment]
        return (result.rowcount or 0) > 0

    def renew(
        self,
        grant_id: str,
        new_valid_until: str,
        signature: str,
        payload_hash: str,
        signing_key_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> bool:
        # validUntil is inside the signed canonical payload, so a renewal must
        # land the new date and the fresh signature material in one guarded
        # UPDATE — a date-only edit would leave a row that fails verification.
        stmt = (
            sa_update(OrmGrant)
            .where(OrmGrant.id == grant_id, OrmGrant.revoked == 0)
            .values(
                valid_until=new_valid_until,
                signature=signature,
                payload_hash=payload_hash,
                signing_key_id=signing_key_id,
            )
        )
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        result: CursorResult = self._s.execute(stmt)  # type: ignore[assignment]
        return (result.rowcount or 0) > 0

    def count(
        self,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(OrmGrant)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        result = self._s.execute(stmt).scalar()
        return int(result) if result is not None else 0

    def try_consume_use(self, grant_id: str) -> bool:
        stmt = (
            sa_update(OrmGrant)
            .where(
                OrmGrant.id == grant_id,
                (OrmGrant.max_uses.is_(None)) | (OrmGrant.use_count < OrmGrant.max_uses),
            )
            .values(use_count=OrmGrant.use_count + 1)
        )
        result: CursorResult = self._s.execute(stmt)  # type: ignore[assignment]
        return (result.rowcount or 0) > 0


# ── Grant request repository ──────────────────────────────────────────────────

class SqlAlchemyGrantRequestRepository:
    def __init__(self, session: "Session") -> None:
        self._s = session

    def get(
        self,
        request_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[GrantRequest]:
        stmt = select(OrmGrantRequest).where(OrmGrantRequest.id == request_id)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantRequest.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantRequest.workspace_id == workspace_id)
        row = self._s.execute(stmt).scalars().first()
        return _orm_to_grant_request(row) if row else None

    def list(
        self,
        status_filter: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[GrantRequest]:
        stmt = select(OrmGrantRequest).order_by(OrmGrantRequest.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantRequest.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantRequest.workspace_id == workspace_id)
        if status_filter is not None:
            stmt = stmt.where(OrmGrantRequest.status == status_filter)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return [_orm_to_grant_request(r) for r in self._s.execute(stmt).scalars().all()]

    def create(
        self,
        request: GrantRequest,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantRequest:
        effective_workspace = workspace_id if workspace_id else _DEMO_WORKSPACE_ID
        self._s.execute(
            sa_insert(OrmGrantRequest).values(
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
                tenant_id=tenant_id,
                workspace_id=effective_workspace,
            )
        )
        return request

    def mark_approved(
        self,
        request_id: str,
        operator_id: str,
        grant_id: str,
        now: str,
    ) -> None:
        self._s.execute(
            sa_update(OrmGrantRequest)
            .where(OrmGrantRequest.id == request_id)
            .values(
                status="approved",
                approved_by=operator_id,
                approved_at=now,
                grant_id=grant_id,
                updated_at=now,
            )
        )

    def mark_denied(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        now: str,
    ) -> None:
        self._s.execute(
            sa_update(OrmGrantRequest)
            .where(OrmGrantRequest.id == request_id)
            .values(
                status="denied",
                denied_by=operator_id,
                denied_at=now,
                denial_reason=reason,
                updated_at=now,
            )
        )

    def mark_revoked(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        now: str,
    ) -> None:
        self._s.execute(
            sa_update(OrmGrantRequest)
            .where(OrmGrantRequest.id == request_id)
            .values(
                status="revoked",
                revoked_by=operator_id,
                revoked_at=now,
                revoked_reason=reason,
                updated_at=now,
            )
        )

    def list_pending_for_expiry(
        self,
        cutoff: str,
    ) -> List[Tuple[str, Optional[str], Optional[str]]]:
        rows = self._s.execute(
            select(
                OrmGrantRequest.id,
                OrmGrantRequest.tenant_id,
                OrmGrantRequest.workspace_id,
            ).where(
                OrmGrantRequest.status == "requested",
                OrmGrantRequest.created_at < cutoff,
            )
        ).fetchall()
        return [
            (
                str(r.id),
                str(r.tenant_id) if r.tenant_id is not None else None,
                str(r.workspace_id) if r.workspace_id is not None else None,
            )
            for r in rows
        ]

    def mark_expired(self, request_id: str, now: str) -> None:
        self._s.execute(
            sa_update(OrmGrantRequest)
            .where(OrmGrantRequest.id == request_id)
            .values(status="expired", updated_at=now)
        )

    def count(
        self,
        status_filter: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(OrmGrantRequest)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantRequest.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantRequest.workspace_id == workspace_id)
        if status_filter is not None:
            stmt = stmt.where(OrmGrantRequest.status == status_filter)
        result = self._s.execute(stmt).scalar()
        return int(result) if result is not None else 0

    def get_id_by_grant_id(self, grant_id: str) -> Optional[str]:
        stmt = (
            select(OrmGrantRequest.id)
            .where(OrmGrantRequest.grant_id == grant_id)
            .order_by(OrmGrantRequest.updated_at.desc())
            .limit(1)
        )
        row = self._s.execute(stmt).scalar()
        return str(row) if row is not None else None


# ── Grant execution repository ───────────────────────────────────────────────

class SqlAlchemyGrantExecutionRepository:
    def __init__(self, session: "Session") -> None:
        self._s = session

    def get(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[GrantExecution]:
        stmt = select(OrmGrantExecution).where(OrmGrantExecution.id == execution_id)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantExecution.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantExecution.workspace_id == workspace_id)
        row = self._s.execute(stmt).scalars().first()
        return _orm_to_grant_execution(row) if row else None

    def list(
        self,
        grant_id: Optional[str] = None,
        grant_request_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> List[GrantExecution]:
        stmt = select(OrmGrantExecution).order_by(OrmGrantExecution.executed_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantExecution.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantExecution.workspace_id == workspace_id)
        if grant_id is not None:
            stmt = stmt.where(OrmGrantExecution.grant_id == grant_id)
        if grant_request_id is not None:
            stmt = stmt.where(OrmGrantExecution.grant_request_id == grant_request_id)
        if operator_id is not None:
            stmt = stmt.where(OrmGrantExecution.operator_id == operator_id)
        stmt = stmt.limit(limit).offset(offset)
        return [_orm_to_grant_execution(r) for r in self._s.execute(stmt).scalars().all()]

    def create(
        self,
        execution: GrantExecution,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantExecution:
        effective_workspace = workspace_id if workspace_id else _DEMO_WORKSPACE_ID
        self._s.execute(
            sa_insert(OrmGrantExecution).values(
                id=execution.id,
                grant_id=execution.grant_id,
                grant_request_id=execution.grant_request_id,
                operator_id=execution.operator_id,
                action=execution.action,
                resource=execution.resource,
                challenge_id=execution.challenge_id,
                challenge_result=execution.challenge_result,
                policy_result=execution.policy_result,
                result=execution.result,
                error_code=execution.error_code,
                executed_at=execution.executed_at,
                audit_event_id=execution.audit_event_id,
                metadata_json=execution.metadata_json,
                tenant_id=tenant_id,
                workspace_id=effective_workspace,
            )
        )
        return execution

    def update_audit_event_id(
        self,
        execution_id: str,
        audit_event_id: str,
    ) -> None:
        self._s.execute(
            sa_update(OrmGrantExecution)
            .where(OrmGrantExecution.id == execution_id)
            .values(audit_event_id=audit_event_id)
        )

    def count(
        self,
        grant_id: Optional[str] = None,
        grant_request_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(OrmGrantExecution)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantExecution.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantExecution.workspace_id == workspace_id)
        if grant_id is not None:
            stmt = stmt.where(OrmGrantExecution.grant_id == grant_id)
        if grant_request_id is not None:
            stmt = stmt.where(OrmGrantExecution.grant_request_id == grant_request_id)
        if operator_id is not None:
            stmt = stmt.where(OrmGrantExecution.operator_id == operator_id)
        result = self._s.execute(stmt).scalar()
        return int(result) if result is not None else 0


# ── Operator repository ───────────────────────────────────────────────────────

class SqlAlchemyOperatorRepository:
    def __init__(self, session: "Session") -> None:
        self._s = session

    def get(self, operator_id: str) -> "Optional[Operator]":
        stmt = select(OrmOperator).where(
            OrmOperator.id == operator_id, OrmOperator.active == 1
        )
        row = self._s.execute(stmt).scalars().first()
        return _orm_to_operator(row) if row else None

    def get_any(self, operator_id: str) -> "Optional[Operator]":
        """Get operator regardless of active status (admin read)."""
        row = self._s.execute(
            select(OrmOperator).where(OrmOperator.id == operator_id)
        ).scalars().first()
        return _orm_to_operator(row) if row else None

    def list(self, tenant_id: "Optional[str]" = None) -> "List[Operator]":
        stmt = select(OrmOperator).order_by(OrmOperator.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmOperator.tenant_id == tenant_id)
        return [_orm_to_operator(r) for r in self._s.execute(stmt).scalars().all()]

    def count(self) -> int:
        result = self._s.execute(
            select(func.count()).select_from(OrmOperator)
        ).scalar()
        return int(result) if result is not None else 0

    def create(
        self,
        name: str,
        role: str,
        token: str,
        tenant_id: str,
        ttl_days: int = 90,
    ) -> "Tuple[Operator, str]":
        from ..auth.operators import (
            Operator,
            derive_token_lookup_hash,
            hash_token,
        )
        op_id = str(uuid.uuid4())
        token_hash = hash_token(token)
        lookup = derive_token_lookup_hash(token)
        now = _now_utc_iso()
        expires = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=ttl_days)
        ).isoformat().replace("+00:00", "Z")
        self._s.execute(
            sa_insert(OrmOperator).values(
                id=op_id,
                name=name,
                role=role,
                token_hash=token_hash,
                token_lookup_hash=lookup,
                active=1,
                created_at=now,
                expires_at=expires,
                tenant_id=tenant_id,
            )
        )
        op = Operator(
            operator_id=op_id,
            name=name,
            role=role,
            active=True,
            created_at=now,
            expires_at=expires,
            tenant_id=tenant_id,
        )
        return op, token

    def revoke(self, operator_id: str) -> bool:
        result: CursorResult = self._s.execute(  # type: ignore[assignment]
            sa_update(OrmOperator)
            .where(OrmOperator.id == operator_id)
            .values(active=0)
        )
        return (result.rowcount or 0) > 0

    def rotate_token(
        self,
        operator_id: str,
        ttl_days: int = 90,
    ) -> Optional[str]:
        op = self.get(operator_id)
        if op is None:
            return None
        from ..auth.operators import derive_token_lookup_hash, hash_token
        new_token = secrets.token_urlsafe(32)
        new_hash = hash_token(new_token)
        new_lookup = derive_token_lookup_hash(new_token)
        now = _now_utc_iso()
        expires = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=ttl_days)
        ).isoformat().replace("+00:00", "Z")
        self._s.execute(
            sa_update(OrmOperator)
            .where(OrmOperator.id == operator_id)
            .values(
                token_hash=new_hash,
                token_lookup_hash=new_lookup,
                rotated_at=now,
                expires_at=expires,
            )
        )
        return new_token

    def find_by_lookup_hash(
        self, lookup_hash: str
    ) -> "Optional[OrmOperator]":
        return self._s.execute(
            select(OrmOperator).where(
                OrmOperator.token_lookup_hash == lookup_hash,
                OrmOperator.active == 1,
            )
        ).scalars().first()

    def find_all_without_lookup_hash(self) -> "List[OrmOperator]":
        return list(
            self._s.execute(
                select(OrmOperator).where(
                    OrmOperator.active == 1,
                    OrmOperator.token_lookup_hash.is_(None),
                )
            ).scalars().all()
        )

    def bootstrap_if_needed(self) -> None:
        from ..auth.operators import (
            DEFAULT_TOKEN_TTL_DAYS,
            derive_token_lookup_hash,
            hash_token,
        )
        from ..core import config
        if not config.ENABLE_OPERATOR_MODEL:
            return
        if not config.GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN:
            return
        if self.count() > 0:
            return
        expires = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=DEFAULT_TOKEN_TTL_DAYS)
        ).isoformat().replace("+00:00", "Z")
        self._s.execute(
            sa_insert(OrmOperator).values(
                id=config.GRANTLAYER_BOOTSTRAP_OPERATOR_ID,
                name=config.GRANTLAYER_BOOTSTRAP_OPERATOR_NAME,
                role=config.GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE,
                token_hash=hash_token(config.GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN),
                token_lookup_hash=derive_token_lookup_hash(
                    config.GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN
                ),
                active=1,
                created_at=_now_utc_iso(),
                expires_at=expires,
                tenant_id="demo",
            )
        )


# ── Async repository implementations ────────────────────────────────────────
# These mirror the sync implementations above but use AsyncSession.
# All DB calls use `await session.execute(stmt)`.

class SqlAlchemyAsyncGrantRepository:
    def __init__(self, session: "AsyncSession") -> None:
        self._s = session

    async def get(
        self,
        grant_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[Grant]:
        stmt = select(OrmGrant).where(OrmGrant.id == grant_id)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        row = (await self._s.execute(stmt)).scalars().first()
        return _orm_to_grant(row) if row else None

    async def list(
        self,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Grant]:
        stmt = select(OrmGrant).order_by(OrmGrant.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return [_orm_to_grant(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def create(
        self,
        grant: Grant,
        tenant_id: str,
        workspace_id: str,
    ) -> Grant:
        effective_workspace = workspace_id if workspace_id else _DEMO_WORKSPACE_ID
        await self._s.execute(
            sa_insert(OrmGrant).values(
                id=grant.id,
                subject_id=grant.subject_id,
                role=grant.role,
                action=grant.action,
                resource=grant.resource,
                valid_from=grant.valid_from,
                valid_until=grant.valid_until,
                created_by=grant.created_by,
                reason=grant.reason,
                revoked=0,
                created_at=grant.created_at,
                max_uses=grant.max_uses,
                use_count=grant.use_count,
                signature=grant.signature,
                signing_key_id=grant.signing_key_id,
                payload_hash=grant.payload_hash,
                tenant_id=tenant_id,
                workspace_id=effective_workspace,
            )
        )
        return grant

    async def revoke(
        self,
        grant_id: str,
        revoked_by: str,
        reason: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> bool:
        revoked_at = _now_utc_iso()
        stmt = (
            sa_update(OrmGrant)
            .where(OrmGrant.id == grant_id, OrmGrant.revoked == 0)
            .values(revoked=1, revoked_by=revoked_by, revoked_reason=reason, revoked_at=revoked_at)
        )
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        result = await self._s.execute(stmt)
        return (result.rowcount or 0) > 0  # type: ignore[attr-defined]

    async def renew(
        self,
        grant_id: str,
        new_valid_until: str,
        signature: str,
        payload_hash: str,
        signing_key_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> bool:
        # validUntil is inside the signed canonical payload, so a renewal must
        # land the new date and the fresh signature material in one guarded
        # UPDATE — a date-only edit would leave a row that fails verification.
        stmt = (
            sa_update(OrmGrant)
            .where(OrmGrant.id == grant_id, OrmGrant.revoked == 0)
            .values(
                valid_until=new_valid_until,
                signature=signature,
                payload_hash=payload_hash,
                signing_key_id=signing_key_id,
            )
        )
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        result = await self._s.execute(stmt)
        return (result.rowcount or 0) > 0  # type: ignore[attr-defined]

    async def count(
        self,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(OrmGrant)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        result = (await self._s.execute(stmt)).scalar()
        return int(result) if result is not None else 0

    async def try_consume_use(self, grant_id: str) -> bool:
        stmt = (
            sa_update(OrmGrant)
            .where(
                OrmGrant.id == grant_id,
                (OrmGrant.max_uses.is_(None)) | (OrmGrant.use_count < OrmGrant.max_uses),
            )
            .values(use_count=OrmGrant.use_count + 1)
        )
        result = await self._s.execute(stmt)
        return (result.rowcount or 0) > 0  # type: ignore[attr-defined]


class SqlAlchemyAsyncGrantRequestRepository:
    def __init__(self, session: "AsyncSession") -> None:
        self._s = session

    async def get(
        self,
        request_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[GrantRequest]:
        stmt = select(OrmGrantRequest).where(OrmGrantRequest.id == request_id)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantRequest.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantRequest.workspace_id == workspace_id)
        row = (await self._s.execute(stmt)).scalars().first()
        return _orm_to_grant_request(row) if row else None

    async def list(
        self,
        status_filter: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[GrantRequest]:
        stmt = select(OrmGrantRequest).order_by(OrmGrantRequest.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantRequest.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantRequest.workspace_id == workspace_id)
        if status_filter is not None:
            stmt = stmt.where(OrmGrantRequest.status == status_filter)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return [_orm_to_grant_request(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def create(
        self,
        request: GrantRequest,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantRequest:
        effective_workspace = workspace_id if workspace_id else _DEMO_WORKSPACE_ID
        await self._s.execute(
            sa_insert(OrmGrantRequest).values(
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
                tenant_id=tenant_id,
                workspace_id=effective_workspace,
            )
        )
        return request

    async def mark_approved(
        self,
        request_id: str,
        operator_id: str,
        grant_id: str,
        now: str,
    ) -> None:
        await self._s.execute(
            sa_update(OrmGrantRequest)
            .where(OrmGrantRequest.id == request_id)
            .values(
                status="approved",
                approved_by=operator_id,
                approved_at=now,
                grant_id=grant_id,
                updated_at=now,
            )
        )

    async def mark_denied(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        now: str,
    ) -> None:
        await self._s.execute(
            sa_update(OrmGrantRequest)
            .where(OrmGrantRequest.id == request_id)
            .values(
                status="denied",
                denied_by=operator_id,
                denied_at=now,
                denial_reason=reason,
                updated_at=now,
            )
        )

    async def mark_revoked(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        now: str,
    ) -> None:
        await self._s.execute(
            sa_update(OrmGrantRequest)
            .where(OrmGrantRequest.id == request_id)
            .values(
                status="revoked",
                revoked_by=operator_id,
                revoked_at=now,
                revoked_reason=reason,
                updated_at=now,
            )
        )

    async def mark_expired(self, request_id: str, now: str) -> None:
        await self._s.execute(
            sa_update(OrmGrantRequest)
            .where(OrmGrantRequest.id == request_id)
            .values(status="expired", updated_at=now)
        )

    async def count(
        self,
        status_filter: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(OrmGrantRequest)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantRequest.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantRequest.workspace_id == workspace_id)
        if status_filter is not None:
            stmt = stmt.where(OrmGrantRequest.status == status_filter)
        result = (await self._s.execute(stmt)).scalar()
        return int(result) if result is not None else 0

    async def get_id_by_grant_id(self, grant_id: str) -> Optional[str]:
        stmt = (
            select(OrmGrantRequest.id)
            .where(OrmGrantRequest.grant_id == grant_id)
            .order_by(OrmGrantRequest.updated_at.desc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).scalar()
        return str(row) if row is not None else None


class SqlAlchemyAsyncGrantExecutionRepository:
    def __init__(self, session: "AsyncSession") -> None:
        self._s = session

    async def get(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[GrantExecution]:
        stmt = select(OrmGrantExecution).where(OrmGrantExecution.id == execution_id)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantExecution.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantExecution.workspace_id == workspace_id)
        row = (await self._s.execute(stmt)).scalars().first()
        return _orm_to_grant_execution(row) if row else None

    async def list(
        self,
        grant_id: Optional[str] = None,
        grant_request_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> List[GrantExecution]:
        stmt = select(OrmGrantExecution).order_by(OrmGrantExecution.executed_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantExecution.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantExecution.workspace_id == workspace_id)
        if grant_id is not None:
            stmt = stmt.where(OrmGrantExecution.grant_id == grant_id)
        if grant_request_id is not None:
            stmt = stmt.where(OrmGrantExecution.grant_request_id == grant_request_id)
        if operator_id is not None:
            stmt = stmt.where(OrmGrantExecution.operator_id == operator_id)
        stmt = stmt.limit(limit).offset(offset)
        return [_orm_to_grant_execution(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def create(
        self,
        execution: GrantExecution,
        tenant_id: str,
        workspace_id: str,
    ) -> GrantExecution:
        effective_workspace = workspace_id if workspace_id else _DEMO_WORKSPACE_ID
        await self._s.execute(
            sa_insert(OrmGrantExecution).values(
                id=execution.id,
                grant_id=execution.grant_id,
                grant_request_id=execution.grant_request_id,
                operator_id=execution.operator_id,
                action=execution.action,
                resource=execution.resource,
                challenge_id=execution.challenge_id,
                challenge_result=execution.challenge_result,
                policy_result=execution.policy_result,
                result=execution.result,
                error_code=execution.error_code,
                executed_at=execution.executed_at,
                audit_event_id=execution.audit_event_id,
                metadata_json=execution.metadata_json,
                tenant_id=tenant_id,
                workspace_id=effective_workspace,
            )
        )
        return execution

    async def update_audit_event_id(
        self,
        execution_id: str,
        audit_event_id: str,
    ) -> None:
        await self._s.execute(
            sa_update(OrmGrantExecution)
            .where(OrmGrantExecution.id == execution_id)
            .values(audit_event_id=audit_event_id)
        )

    async def count(
        self,
        grant_id: Optional[str] = None,
        grant_request_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(OrmGrantExecution)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantExecution.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantExecution.workspace_id == workspace_id)
        if grant_id is not None:
            stmt = stmt.where(OrmGrantExecution.grant_id == grant_id)
        if grant_request_id is not None:
            stmt = stmt.where(OrmGrantExecution.grant_request_id == grant_request_id)
        if operator_id is not None:
            stmt = stmt.where(OrmGrantExecution.operator_id == operator_id)
        result = (await self._s.execute(stmt)).scalar()
        return int(result) if result is not None else 0


class SqlAlchemyAsyncOperatorRepository:
    def __init__(self, session: "AsyncSession") -> None:
        self._s = session

    async def get(self, operator_id: str) -> "Optional[Operator]":
        stmt = select(OrmOperator).where(
            OrmOperator.id == operator_id, OrmOperator.active == 1
        )
        row = (await self._s.execute(stmt)).scalars().first()
        return _orm_to_operator(row) if row else None

    async def get_any(self, operator_id: str) -> "Optional[Operator]":
        row = (await self._s.execute(
            select(OrmOperator).where(OrmOperator.id == operator_id)
        )).scalars().first()
        return _orm_to_operator(row) if row else None

    async def list(self, tenant_id: "Optional[str]" = None) -> "List[Operator]":
        stmt = select(OrmOperator).order_by(OrmOperator.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(OrmOperator.tenant_id == tenant_id)
        return [_orm_to_operator(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def count(self) -> int:
        result = (await self._s.execute(
            select(func.count()).select_from(OrmOperator)
        )).scalar()
        return int(result) if result is not None else 0

    async def create(
        self,
        name: str,
        role: str,
        token: str,
        tenant_id: str,
        ttl_days: int = 90,
    ) -> "Tuple[Operator, str]":
        from ..auth.operators import (
            Operator,
            derive_token_lookup_hash,
            hash_token,
        )
        op_id = str(uuid.uuid4())
        token_hash = hash_token(token)
        lookup = derive_token_lookup_hash(token)
        now = _now_utc_iso()
        expires = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=ttl_days)
        ).isoformat().replace("+00:00", "Z")
        await self._s.execute(
            sa_insert(OrmOperator).values(
                id=op_id,
                name=name,
                role=role,
                token_hash=token_hash,
                token_lookup_hash=lookup,
                active=1,
                created_at=now,
                expires_at=expires,
                tenant_id=tenant_id,
            )
        )
        op = Operator(
            operator_id=op_id,
            name=name,
            role=role,
            active=True,
            created_at=now,
            expires_at=expires,
            tenant_id=tenant_id,
        )
        return op, token

    async def revoke(self, operator_id: str) -> bool:
        result = await self._s.execute(
            sa_update(OrmOperator)
            .where(OrmOperator.id == operator_id)
            .values(active=0)
        )
        return (result.rowcount or 0) > 0  # type: ignore[attr-defined]

    async def rotate_token(
        self,
        operator_id: str,
        ttl_days: int = 90,
    ) -> Optional[str]:
        op = await self.get(operator_id)
        if op is None:
            return None
        from ..auth.operators import derive_token_lookup_hash, hash_token
        new_token = secrets.token_urlsafe(32)
        new_hash = hash_token(new_token)
        new_lookup = derive_token_lookup_hash(new_token)
        now = _now_utc_iso()
        expires = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=ttl_days)
        ).isoformat().replace("+00:00", "Z")
        await self._s.execute(
            sa_update(OrmOperator)
            .where(OrmOperator.id == operator_id)
            .values(
                token_hash=new_hash,
                token_lookup_hash=new_lookup,
                rotated_at=now,
                expires_at=expires,
            )
        )
        return new_token
