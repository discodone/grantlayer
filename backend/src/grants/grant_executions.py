"""GrantLayer MVP — Grant Execution ledger.

One row per protected action attempt.
"""

from typing import List, Optional
import json
from ..core.db import execute, query_one, query_all
from ..core.models import GrantExecution


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
) -> GrantExecution:
    """Insert a new grant execution record."""
    effective_tenant = tenant_id or "demo"
    execute(
        """
        INSERT INTO grant_executions (
            id, grant_id, grant_request_id, operator_id, action, resource,
            challenge_id, challenge_result, policy_result, result, error_code,
            executed_at, audit_event_id, metadata_json, tenant_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        ),
    )
    return execution


def get_grant_execution(
    execution_id: str,
    tenant_id: Optional[str] = None,
) -> Optional[GrantExecution]:
    """Get a single grant execution by ID, optionally scoped to tenant."""
    if tenant_id is not None:
        row = query_one(
            "SELECT * FROM grant_executions WHERE id = ? AND tenant_id = ?",
            (execution_id, tenant_id),
        )
    else:
        row = query_one("SELECT * FROM grant_executions WHERE id = ?", (execution_id,))
    return _row_to_grant_execution(row)


def list_grant_executions(
    grant_id: Optional[str] = None,
    grant_request_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    limit: int = 200,
    tenant_id: Optional[str] = None,
) -> List[GrantExecution]:
    """List grant executions, optionally filtered by tenant and other fields."""
    conditions: list[str] = []
    params: list = []
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
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
    base += " ORDER BY executed_at DESC LIMIT ?"
    params.append(limit)

    rows = query_all(base, tuple(params))
    return [_row_to_grant_execution(r) for r in rows]


def list_grant_executions_for_grant(
    grant_id: str,
    limit: int = 200,
    tenant_id: Optional[str] = None,
) -> List[GrantExecution]:
    """List executions for a specific grant, optionally scoped to tenant."""
    return list_grant_executions(grant_id=grant_id, limit=limit, tenant_id=tenant_id)


def update_grant_execution_audit_event_id(
    execution_id: str, audit_event_id: str
) -> None:
    """Link an execution to its audit event after audit insertion."""
    execute(
        "UPDATE grant_executions SET audit_event_id = ? WHERE id = ?",
        (audit_event_id, execution_id),
    )
