"""GrantLayer MVP — Challenge store and validation."""

import datetime
from typing import Optional, Tuple

from ..core.db import execute, query_all, query_one
from ..core.models import Challenge, ChallengeResult
from ..core.validation import MAX_NAME_LENGTH, MAX_SHORT_ID_LENGTH, validate_string_length

CHALLENGE_TTL_SECONDS = 300  # 5 minutes


def create_challenge(
    subject_id: str,
    action: str,
    resource: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Challenge:
    validate_string_length(subject_id, "subject_id", MAX_SHORT_ID_LENGTH)
    validate_string_length(action, "action", MAX_NAME_LENGTH)
    validate_string_length(resource, "resource", MAX_NAME_LENGTH)
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + datetime.timedelta(seconds=CHALLENGE_TTL_SECONDS)
    challenge = Challenge(
        subject_id=subject_id,
        action=action,
        resource=resource,
        expires_at=expires.isoformat().replace("+00:00", "Z"),
    )
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    effective_tenant = tenant_id
    effective_workspace = workspace_id if workspace_id is not None else "default"
    execute(
        """INSERT INTO challenges
           (id, subject_id, action, resource, created_at, expires_at, used_at, status, tenant_id, workspace_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            challenge.id, challenge.subject_id, challenge.action, challenge.resource,
            challenge.created_at, challenge.expires_at, challenge.used_at, challenge.status,
            effective_tenant, effective_workspace,
        ),
    )
    return challenge


def get_challenge(challenge_id: str, tenant_id: Optional[str] = None) -> Optional[Challenge]:
    if tenant_id is not None:
        row = query_one(
            "SELECT * FROM challenges WHERE id = ? AND tenant_id = ?",
            (challenge_id, tenant_id),
        )
    else:
        row = query_one("SELECT * FROM challenges WHERE id = ?", (challenge_id,))
    return _row_to_challenge(row) if row else None


def list_challenges(
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> list:
    conditions: list[str] = []
    params: list = []
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    sql = "SELECT * FROM challenges"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    rows = query_all(sql, tuple(params))
    return [_row_to_challenge(r) for r in rows]


def count_challenges(
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> int:
    conditions: list[str] = []
    params: list = []
    if tenant_id is not None:
        conditions.append("tenant_id = ?")
        params.append(tenant_id)
    if workspace_id is not None:
        conditions.append("workspace_id = ?")
        params.append(workspace_id)
    sql = "SELECT COUNT(*) AS count FROM challenges"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    row = query_one(sql, tuple(params))
    return int(row["count"]) if row else 0


def mark_used(challenge_id: str) -> None:
    used_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    execute(
        "UPDATE challenges SET used_at = ?, status = 'used' WHERE id = ?",
        (used_at, challenge_id),
    )


def validate_challenge(
    challenge_id: str,
    subject_id: str,
    action: str,
    resource: str,
    tenant_id: Optional[str] = None,
) -> Tuple[ChallengeResult, Optional[str]]:
    """Validate a challenge and mark it used if valid.

    Returns (result_code, challenge_id_or_None).
    Fail-closed: any problem returns a non-'valid' code.
    tenant_id is required to prevent cross-tenant challenge reuse.
    """
    challenge = get_challenge(challenge_id, tenant_id=tenant_id)
    if challenge is None:
        return "not_found", None

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    if challenge.expires_at < now_str:
        return "expired", challenge_id

    if challenge.status == "used":
        return "already_used", challenge_id

    if (challenge.subject_id != subject_id
            or challenge.action != action
            or challenge.resource != resource):
        return "mismatch", challenge_id

    mark_used(challenge_id)
    return "valid", challenge_id


def _row_to_challenge(row: dict) -> Challenge:
    return Challenge(
        id=row["id"],
        subject_id=row["subject_id"],
        action=row["action"],
        resource=row["resource"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        used_at=row["used_at"],
        status=row["status"],
    )
