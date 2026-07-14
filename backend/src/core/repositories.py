"""Abstract repository interfaces (Protocol) for GrantLayer domain objects.

All database access in domain modules must go through these interfaces.
Implementations live in repositories_sqlalchemy.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Protocol, Tuple, runtime_checkable

if TYPE_CHECKING:
    from ..auth.operators import Operator
    from .models import Grant, GrantExecution, GrantRequest


@runtime_checkable
class IGrantRepository(Protocol):
    def get(
        self,
        grant_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> "Optional[Grant]": ...

    def list(
        self,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> "List[Grant]": ...

    def create(
        self,
        grant: "Grant",
        tenant_id: str,
        workspace_id: str,
    ) -> "Grant": ...

    def revoke(
        self,
        grant_id: str,
        revoked_by: str,
        reason: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> bool: ...

    def count(
        self,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int: ...

    def try_consume_use(self, grant_id: str) -> bool: ...


@runtime_checkable
class IGrantRequestRepository(Protocol):
    def get(
        self,
        request_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> "Optional[GrantRequest]": ...

    def list(
        self,
        status_filter: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> "List[GrantRequest]": ...

    def create(
        self,
        request: "GrantRequest",
        tenant_id: str,
        workspace_id: str,
    ) -> "GrantRequest": ...

    def mark_approved(
        self,
        request_id: str,
        operator_id: str,
        grant_id: str,
        now: str,
    ) -> None: ...

    def mark_denied(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        now: str,
    ) -> None: ...

    def mark_revoked(
        self,
        request_id: str,
        operator_id: str,
        reason: str,
        now: str,
    ) -> None: ...

    def list_pending_for_expiry(
        self,
        cutoff: str,
    ) -> "List[Tuple[str, Optional[str], Optional[str]]]": ...

    def mark_expired(self, request_id: str, now: str) -> None: ...

    def count(
        self,
        status_filter: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int: ...

    def get_id_by_grant_id(self, grant_id: str) -> Optional[str]: ...


@runtime_checkable
class IGrantExecutionRepository(Protocol):
    def get(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> "Optional[GrantExecution]": ...

    def list(
        self,
        grant_id: Optional[str] = None,
        grant_request_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> "List[GrantExecution]": ...

    def create(
        self,
        execution: "GrantExecution",
        tenant_id: str,
        workspace_id: str,
    ) -> "GrantExecution": ...

    def update_audit_event_id(
        self,
        execution_id: str,
        audit_event_id: str,
    ) -> None: ...

    def count(
        self,
        grant_id: Optional[str] = None,
        grant_request_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int: ...


@runtime_checkable
class IOperatorRepository(Protocol):
    def get(self, operator_id: str) -> "Optional[Operator]": ...

    def get_any(self, operator_id: str) -> "Optional[Operator]": ...

    def list(self, tenant_id: "Optional[str]" = None) -> "List[Operator]": ...

    def create(
        self,
        name: str,
        role: str,
        token: str,
        tenant_id: str,
        ttl_days: int = 90,
    ) -> "Tuple[Operator, str]": ...

    def revoke(self, operator_id: str) -> bool: ...

    def rotate_token(
        self,
        operator_id: str,
        ttl_days: int = 90,
    ) -> Optional[str]: ...

    def count(self) -> int: ...

    def bootstrap_if_needed(self) -> None: ...
