"""GrantLayer MVP — Grant Execution ledger.

One row per protected action attempt.
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func, select
from sqlalchemy import insert as sa_insert
from sqlalchemy import update as sa_update

from ..core.db import execute, query_all, query_one
from ..core.models import GrantExecution
from ..core.orm import GrantExecution as OrmGrantExecution

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_DEMO_WORKSPACE_ID = "default"


def _orm_to_grant_execution(row: OrmGrantExecution) -> GrantExecution:
    return GrantExecution(
        id=row.id,
        grant_id=row.grant_id,
        grant_request_id=row.grant_request_id,
        operator_id=row.operator_id,
        action=row.action,
        resource=row.resource,
        challenge_id=row.challenge_id,
        challenge_result=row.challenge_result,
        policy_result=row.policy_result or "",
        result=row.result,  # type: ignore[arg-type]
        error_code=row.error_code,
        executed_at=row.executed_at,
        audit_event_id=row.audit_event_id,
        metadata_json=row.metadata_json,
    )


def _row_to_grant_execution(row: dict | None) -> Optional[GrantExecution]:
    if row is None:
        return None
    return GrantExecution(
        id=row["id"],
        grant_id=row["grant_id"],
        grant_request_id=row["grant_request_id"],
        operator_id=row["operator_id"],
        action=row["action"],
        resource=row["resource"],
        challenge_id=row["challenge_id"],
        challenge_result=row["challenge_result"],
        policy_result=row["policy_result"],
        result=row["result"],  # type: ignore[arg-type]
        error_code=row["error_code"],
        executed_at=row["executed_at"],
        audit_event_id=row["audit_event_id"],
        metadata_json=row["metadata_json"],
    )


def create_grant_execution(
    execution: GrantExecution,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> GrantExecution:
    """Insert a new grant execution record."""
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_tenant = tenant_id
    effective_workspace = workspace_id if workspace_id is not None else _DEMO_WORKSPACE_ID

    if session is not None:
        session.execute(
            sa_insert(OrmGrantExecution.__table__).values(
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
                tenant_id=effective_tenant,
                workspace_id=effective_workspace,
            )
        )
    else:
        execute(
            """
            INSERT INTO grant_executions (
                id, grant_id, grant_request_id, operator_id, action, resource,
                challenge_id, challenge_result, policy_result, result, error_code,
                executed_at, audit_event_id, metadata_json, tenant_id, workspace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution.id,
                execution.grant_id,
                execution.grant_request_id,
                execution.operator_id,
                execution.action,
                execution.resource,
                execution.challenge_id,
                execution.challenge_result,
                execution.policy_result,
                execution.result,
                execution.error_code,
                execution.executed_at,
                execution.audit_event_id,
                execution.metadata_json,
                effective_tenant,
                effective_workspace,
            ),
        )
    return execution


def get_grant_execution(
    execution_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> Optional[GrantExecution]:
    """Get a single grant execution by ID, optionally scoped to tenant and workspace."""
    if session is not None:
        stmt = select(OrmGrantExecution).where(OrmGrantExecution.id == execution_id)
        if tenant_id is not None:
            stmt = stmt.where(OrmGrantExecution.tenant_id == tenant_id)
        if workspace_id is not None:
            stmt = stmt.where(OrmGrantExecution.workspace_id == workspace_id)
        orm_row = session.execute(stmt).scalars().first()
        return _orm_to_grant_execution(orm_row) if orm_row else None
    conditions = ["id = ?"]
    params: list = [execution_id]
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    row = query_one(
        "SELECT * FROM grant_executions WHERE " + " AND ".join(conditions),
        tuple(params),
    )
    return _row_to_grant_execution(row)


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
    """List grant executions, optionally filtered by tenant, workspace, and other fields."""
    if session is not None:
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
        return [_orm_to_grant_execution(r) for r in session.execute(stmt).scalars().all()]

    conditions: list[str] = []
    params: list = []
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    if grant_id is not None:
        conditions.append("grant_id = ?")
        params.append(grant_id)
    if grant_request_id is not None:
        conditions.append("grant_request_id = ?")
        params.append(grant_request_id)
    if operator_id is not None:
        conditions.append("operator_id = ?")
        params.append(operator_id)

    base = "SELECT * FROM grant_executions"
    if conditions:
        base += " WHERE " + " AND ".join(conditions)
    base += " ORDER BY executed_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = query_all(base, tuple(params))
    return [e for e in (_row_to_grant_execution(r) for r in rows) if e is not None]


def count_grant_executions(
    grant_id: Optional[str] = None,
    grant_request_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> int:
    if session is not None:
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
    if grant_id is not None:
        conditions.append("grant_id = ?")
        params.append(grant_id)
    if grant_request_id is not None:
        conditions.append("grant_request_id = ?")
        params.append(grant_request_id)
    if operator_id is not None:
        conditions.append("operator_id = ?")
        params.append(operator_id)
    sql = "SELECT COUNT(*) AS count FROM grant_executions"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    row = query_one(sql, tuple(params))
    return int(row["count"]) if row else 0


def list_grant_executions_for_grant(
    grant_id: str,
    limit: int = 200,
    offset: int = 0,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: "Optional[Session]" = None,
) -> List[GrantExecution]:
    """List executions for a specific grant, optionally scoped to tenant and workspace."""
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
    """Link an execution to its audit event after audit insertion."""
    if session is not None:
        session.execute(
            sa_update(OrmGrantExecution.__table__)
            .where(OrmGrantExecution.id == execution_id)
            .values(audit_event_id=audit_event_id)
        )
        return
    execute(
        "UPDATE grant_executions SET audit_event_id = ? WHERE id = ?",
        (audit_event_id, execution_id),
    )
