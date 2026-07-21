"""GrantLayer MVP — Grant Execution ledger.

One row per protected action attempt.
"""

from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, List, Optional

from ..core.models import GrantExecution
from ..core.repositories_sqlalchemy import SqlAlchemyGrantExecutionRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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


def create_grant_execution(
    execution: GrantExecution,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> GrantExecution:
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    if not workspace_id:
        raise ValueError("workspace_id is required")
    if session is not None:
        return SqlAlchemyGrantExecutionRepository(session).create(execution, tenant_id, workspace_id)
    with _auto_session() as sess:
        return SqlAlchemyGrantExecutionRepository(sess).create(execution, tenant_id, workspace_id)


def get_grant_execution(
    execution_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> Optional[GrantExecution]:
    if session is not None:
        return SqlAlchemyGrantExecutionRepository(session).get(
            execution_id, tenant_id=tenant_id, workspace_id=workspace_id
        )
    with _auto_session() as sess:
        return SqlAlchemyGrantExecutionRepository(sess).get(
            execution_id, tenant_id=tenant_id, workspace_id=workspace_id
        )


def list_grant_executions(
    grant_id: Optional[str] = None,
    grant_request_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> List[GrantExecution]:
    if session is not None:
        return SqlAlchemyGrantExecutionRepository(session).list(
            grant_id=grant_id,
            grant_request_id=grant_request_id,
            operator_id=operator_id,
            limit=limit,
            offset=offset,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
    with _auto_session() as sess:
        return SqlAlchemyGrantExecutionRepository(sess).list(
            grant_id=grant_id,
            grant_request_id=grant_request_id,
            operator_id=operator_id,
            limit=limit,
            offset=offset,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )


def count_grant_executions(
    grant_id: Optional[str] = None,
    grant_request_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> int:
    if session is not None:
        return SqlAlchemyGrantExecutionRepository(session).count(
            grant_id=grant_id,
            grant_request_id=grant_request_id,
            operator_id=operator_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
    with _auto_session() as sess:
        return SqlAlchemyGrantExecutionRepository(sess).count(
            grant_id=grant_id,
            grant_request_id=grant_request_id,
            operator_id=operator_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )


def list_grant_executions_for_grant(
    grant_id: str,
    limit: int = 200,
    offset: int = 0,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> List[GrantExecution]:
    return list_grant_executions(
        grant_id=grant_id,
        limit=limit,
        offset=offset,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        session=session,
    )


def update_grant_execution_audit_event_id(
    execution_id: str,
    audit_event_id: str,
    session: "Optional[Session]" = None,
) -> None:
    if session is not None:
        SqlAlchemyGrantExecutionRepository(session).update_audit_event_id(execution_id, audit_event_id)
        return
    with _auto_session() as sess:
        SqlAlchemyGrantExecutionRepository(sess).update_audit_event_id(execution_id, audit_event_id)
