"""GrantLayer MVP — Challenge store and validation."""

import datetime
from typing import Optional, Tuple
from .db import get_conn
from .models import Challenge, ChallengeResult

CHALLENGE_TTL_SECONDS = 300  # 5 minutes


def create_challenge(subject_id: str, action: str, resource: str) -> Challenge:
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + datetime.timedelta(seconds=CHALLENGE_TTL_SECONDS)
    challenge = Challenge(
        subject_id=subject_id,
        action=action,
        resource=resource,
        expires_at=expires.isoformat().replace("+00:00", "Z"),
    )
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO challenges
               (id, subject_id, action, resource, created_at, expires_at, used_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                challenge.id, challenge.subject_id, challenge.action, challenge.resource,
                challenge.created_at, challenge.expires_at, challenge.used_at, challenge.status,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return challenge


def get_challenge(challenge_id: str) -> Optional[Challenge]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM challenges WHERE id = ?", (challenge_id,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_challenge(row) if row else None


def list_challenges() -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM challenges ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_challenge(r) for r in rows]


def mark_used(challenge_id: str) -> None:
    used_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE challenges SET used_at = ?, status = 'used' WHERE id = ?",
            (used_at, challenge_id),
        )
        conn.commit()
    finally:
        conn.close()


def validate_challenge(
    challenge_id: str,
    subject_id: str,
    action: str,
    resource: str,
) -> Tuple[ChallengeResult, Optional[str]]:
    """Validate a challenge and mark it used if valid.

    Returns (result_code, challenge_id_or_None).
    Fail-closed: any problem returns a non-'valid' code.
    """
    challenge = get_challenge(challenge_id)
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


def _row_to_challenge(row) -> Challenge:
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
