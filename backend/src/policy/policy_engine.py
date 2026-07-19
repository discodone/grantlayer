"""GrantLayer MVP — Policy Engine.

Fail-closed: any ambiguity results in denial.
"""

import datetime
from typing import List

from ..core.models import AccessRequest, Grant, PolicyResult


def _parse_iso(ts: str) -> datetime.datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
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

    All matching grants (role+action+resource) are evaluated. If the first
    candidate is expired/revoked/exhausted the engine continues to the next
    candidate — a later valid grant can still approve access.  The best
    (most specific) denial reason is returned if no grant approves.
    """
    # Normalize naive 'now' to UTC for comparison with aware parsed datetimes
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    candidates = [g for g in grants if g.subject_id == request.subject_id]

    if not candidates:
        return PolicyResult(
            approved=False,
            reason=f"No grant found for subject '{request.subject_id}'",
            reason_code="no_matching_grant",
        )

    best_denial: PolicyResult | None = None

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
            if best_denial is None:
                best_denial = PolicyResult(
                    approved=False,
                    reason=f"Grant '{grant.id}' is not yet valid (starts {grant.valid_from})",
                    matched_grant_id=grant.id,
                    reason_code="grant_not_yet_valid",
                )
            continue

        if now > valid_until:
            if best_denial is None:
                best_denial = PolicyResult(
                    approved=False,
                    reason=f"Grant '{grant.id}' has expired (expired {grant.valid_until})",
                    matched_grant_id=grant.id,
                    reason_code="grant_expired",
                )
            continue

        if grant.revoked:
            if best_denial is None:
                best_denial = PolicyResult(
                    approved=False,
                    reason=f"Grant '{grant.id}' has been revoked",
                    matched_grant_id=grant.id,
                    reason_code="grant_revoked",
                )
            continue

        if grant.max_uses is not None and grant.use_count >= grant.max_uses:
            if best_denial is None:
                best_denial = PolicyResult(
                    approved=False,
                    reason="grant_usage_exhausted",
                    matched_grant_id=grant.id,
                    reason_code="grant_usage_exhausted",
                )
            continue

        return PolicyResult(
            approved=True,
            reason="Access granted",
            matched_grant_id=grant.id,
            reason_code="access_granted",
        )

    if best_denial is not None:
        return best_denial

    return PolicyResult(
        approved=False,
        reason=(
            f"No matching grant for role='{request.role}', "
            f"action='{request.action}', resource='{request.resource}'"
        ),
        reason_code="no_matching_grant",
    )
