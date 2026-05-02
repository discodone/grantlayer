"""GrantLayer MVP — Policy Engine.

Fail-closed: any ambiguity results in denial.
"""

import datetime
from typing import List
from .models import AccessRequest, Grant, PolicyResult


def _parse_iso(ts: str) -> datetime.datetime:
    ts = ts.rstrip("Z")
    return datetime.datetime.fromisoformat(ts)


def evaluate_access(request: AccessRequest, grants: List[Grant], now: datetime.datetime) -> PolicyResult:
    """Evaluate whether the request is permitted by any active grant.

    Checks in order:
    1. Grant exists for subject_id
    2. Role matches
    3. Action matches
    4. Resource matches
    5. Now is within [valid_from, valid_until]
    6. Grant is not revoked
    """
    candidates = [g for g in grants if g.subject_id == request.subject_id]

    if not candidates:
        return PolicyResult(
            approved=False,
            reason=f"No grant found for subject '{request.subject_id}'",
        )

    for grant in candidates:
        if grant.role != request.role:
            continue

        if grant.action != request.action and grant.action != "*":
            continue

        if grant.resource != request.resource and grant.resource != "*":
            continue

        try:
            valid_from = _parse_iso(grant.valid_from)
            valid_until = _parse_iso(grant.valid_until)
        except ValueError:
            continue

        if now < valid_from:
            return PolicyResult(
                approved=False,
                reason=f"Grant '{grant.id}' is not yet valid (starts {grant.valid_from})",
                matched_grant_id=grant.id,
            )

        if now > valid_until:
            return PolicyResult(
                approved=False,
                reason=f"Grant '{grant.id}' has expired (expired {grant.valid_until})",
                matched_grant_id=grant.id,
            )

        if grant.revoked:
            return PolicyResult(
                approved=False,
                reason=f"Grant '{grant.id}' has been revoked",
                matched_grant_id=grant.id,
            )

        return PolicyResult(
            approved=True,
            reason="Access granted",
            matched_grant_id=grant.id,
        )

    return PolicyResult(
        approved=False,
        reason=(
            f"No matching grant for role='{request.role}', "
            f"action='{request.action}', resource='{request.resource}'"
        ),
    )
