"""GrantService — business logic for grant lifecycle.

Routers call this service; the service owns signing, repo mutations, and audit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

from ..audit import audit_log as _audit_log
from ..core.crypto_signing import sign_grant as _sign_grant
from ..core.models import AuditEvent, Grant
from ..core.repositories import IGrantRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class GrantService:
    def __init__(self, repo: IGrantRepository, session: "Session") -> None:
        self._repo = repo
        self._session = session

    def get_grant(
        self,
        grant_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> Optional[Grant]:
        return self._repo.get(grant_id, tenant_id=tenant_id, workspace_id=workspace_id)

    def list_grants(
        self,
        tenant_id: str,
        workspace_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Grant], int]:
        grants = self._repo.list(
            tenant_id=tenant_id, workspace_id=workspace_id, limit=limit, offset=offset
        )
        total = self._repo.count(tenant_id=tenant_id, workspace_id=workspace_id)
        return grants, total

    def create_grant(
        self,
        grant: Grant,
        tenant_id: str,
        workspace_id: str,
        operator_id: Optional[str] = None,
    ) -> Grant:
        if operator_id:
            grant.created_by = operator_id
        sig_hex, hash_hex, key_id = _sign_grant(grant)
        grant.signature = sig_hex
        grant.payload_hash = hash_hex
        grant.signing_key_id = key_id
        self._repo.create(grant, tenant_id, workspace_id)
        _audit_log.append_event(
            AuditEvent(
                subject_id=grant.subject_id,
                role=grant.role,
                action=grant.action,
                resource=grant.resource,
                approved=True,
                reason=f"grant_created: {grant.reason}",
                matched_grant_id=grant.id,
                grant_signature_result="valid",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            ),
            conn=self._session.connection(),
        )
        return grant

    def revoke_grant(
        self,
        grant_id: str,
        tenant_id: str,
        workspace_id: str,
        revoked_by: str,
        reason: str,
    ) -> bool:
        return self._repo.revoke(
            grant_id, revoked_by, reason, tenant_id=tenant_id, workspace_id=workspace_id
        )
