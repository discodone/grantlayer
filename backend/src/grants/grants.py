"""GrantLayer MVP — Grant storage."""

import datetime
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, List, Optional

from sqlalchemy import insert as sa_insert
from sqlalchemy import update as sa_update

from ..core.crypto_signing import sign_grant as _sign_grant
from ..core.db import execute
from ..core.models import Grant
from ..core.orm import Grant as OrmGrant
from ..core.repositories_sqlalchemy import SqlAlchemyGrantRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_DEMO_WORKSPACE_ID = "default"


@contextmanager
def _auto_session() -> Generator["Session", None, None]:
    """Create a short-lived, auto-committing session for standalone calls."""
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


def _row_to_grant(row: dict) -> Grant:
    return Grant(
        id=row["id"],
        subject_id=row["subject_id"],
        role=row["role"],
        action=row["action"],
        resource=row["resource"],
        valid_from=row["valid_from"],
        valid_until=row["valid_until"],
        created_by=row["created_by"],
        reason=row["reason"],
        revoked=bool(row["revoked"]),
        revoked_by=row["revoked_by"],
        revoked_reason=row["revoked_reason"],
        revoked_at=row["revoked_at"],
        created_at=row["created_at"],
        signature=row["signature"],
        signing_key_id=row["signing_key_id"],
        payload_hash=row["payload_hash"],
        max_uses=row["max_uses"],
        use_count=row["use_count"] or 0,
    )


def list_grants(
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    session: "Optional[Session]" = None,
) -> List[Grant]:
    if session is not None:
        return SqlAlchemyGrantRepository(session).list(
            tenant_id=tenant_id, workspace_id=workspace_id, limit=limit, offset=offset
        )
    with _auto_session() as sess:
        return SqlAlchemyGrantRepository(sess).list(
            tenant_id=tenant_id, workspace_id=workspace_id, limit=limit, offset=offset
        )


def count_grants(
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> int:
    if session is not None:
        return SqlAlchemyGrantRepository(session).count(
            tenant_id=tenant_id, workspace_id=workspace_id
        )
    with _auto_session() as sess:
        return SqlAlchemyGrantRepository(sess).count(
            tenant_id=tenant_id, workspace_id=workspace_id
        )


def get_grant(
    grant_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> Optional[Grant]:
    if session is not None:
        return SqlAlchemyGrantRepository(session).get(
            grant_id, tenant_id=tenant_id, workspace_id=workspace_id
        )
    with _auto_session() as sess:
        return SqlAlchemyGrantRepository(sess).get(
            grant_id, tenant_id=tenant_id, workspace_id=workspace_id
        )


def _sign_and_insert(
    grant: Grant,
    tenant_id: str,
    workspace_id: str,
    session: "Optional[Session]" = None,
) -> Grant:
    """Sign the grant then insert via repo. Internal helper."""
    sig_hex, hash_hex, key_id = _sign_grant(grant)
    grant.signature = sig_hex
    grant.payload_hash = hash_hex
    grant.signing_key_id = key_id
    SqlAlchemyGrantRepository(session).create(grant, tenant_id, workspace_id)  # type: ignore[arg-type]
    return grant


def create_grant(
    grant: Grant,
    conn=None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> Grant:
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_workspace = workspace_id if workspace_id is not None else _DEMO_WORKSPACE_ID

    if conn is not None:
        # Transactional path: caller manages the connection (_ConnectionWrapper or SA Connection).
        sig_hex, hash_hex, key_id = _sign_grant(grant)
        grant.signature = sig_hex
        grant.payload_hash = hash_hex
        grant.signing_key_id = key_id
        conn.execute(
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
                signature=sig_hex,
                signing_key_id=key_id,
                payload_hash=hash_hex,
                tenant_id=tenant_id,
                workspace_id=effective_workspace,
            )
        )
        return grant

    if session is not None:
        return _sign_and_insert(grant, tenant_id, effective_workspace, session)

    with _auto_session() as sess:
        return _sign_and_insert(grant, tenant_id, effective_workspace, sess)


def tamper_grant(grant_id: str, tenant_id: Optional[str] = None) -> Optional[dict]:
    """Demo-only: change a grant field without re-signing to demonstrate tamper detection."""
    grant = get_grant(grant_id, tenant_id=tenant_id)
    if grant is None:
        return None
    old_value = grant.role
    new_value = "tampered-role"
    if tenant_id is not None:
        execute(
            "UPDATE grants SET role = ? WHERE id = ? AND tenant_id = ?",
            (new_value, grant_id, tenant_id),
        )
    else:
        execute("UPDATE grants SET role = ? WHERE id = ?", (new_value, grant_id))
    return {
        "ok": True,
        "grantId": grant_id,
        "tamperedField": "role",
        "oldValue": old_value,
        "newValue": new_value,
        "subjectId": grant.subject_id,
        "action": grant.action,
        "resource": grant.resource,
        "message": "Grant tampered without re-signing. Signature should now fail.",
    }


def revoke_grant(
    grant_id: str,
    revoked_by: str,
    reason: str,
    conn=None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> bool:
    revoked_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    if conn is not None:
        # Transactional path: caller manages the connection (_ConnectionWrapper or SA Connection).
        stmt = (
            sa_update(OrmGrant)
            .where(OrmGrant.id == grant_id, OrmGrant.revoked == 0)
            .values(revoked=1, revoked_by=revoked_by, revoked_reason=reason, revoked_at=revoked_at)
        )
        if tenant_id is not None:
            stmt = stmt.where(OrmGrant.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrant.workspace_id == workspace_id)
        result = conn.execute(stmt)
        return (result.rowcount or 0) > 0

    if session is not None:
        return SqlAlchemyGrantRepository(session).revoke(
            grant_id, revoked_by, reason, tenant_id=tenant_id, workspace_id=workspace_id
        )

    with _auto_session() as sess:
        return SqlAlchemyGrantRepository(sess).revoke(
            grant_id, revoked_by, reason, tenant_id=tenant_id, workspace_id=workspace_id
        )


def try_consume_grant_use(grant_id: str) -> bool:
    """Atomically increment use_count if the grant is not exhausted."""
    with _auto_session() as sess:
        return SqlAlchemyGrantRepository(sess).try_consume_use(grant_id)
