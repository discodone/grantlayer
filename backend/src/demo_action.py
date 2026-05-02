"""GrantLayer MVP — Protected demo action handler."""

import datetime
from typing import Optional
from .models import AccessRequest, AuditEvent, PolicyResult
from .policy_engine import evaluate_access
from .grants import list_grants
from .audit_log import append_event
from .challenges import validate_challenge


def handle_demo_action(
    subject_id: str,
    role: str,
    action: str,
    resource: str,
    challenge_id: Optional[str] = None,
) -> dict:
    request = AccessRequest(
        subject_id=subject_id,
        role=role,
        action=action,
        resource=resource,
    )

    grants = list_grants()
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    result: PolicyResult = evaluate_access(request, grants, now)

    challenge_present = challenge_id is not None
    challenge_result = "legacy_mode"
    resolved_challenge_id: Optional[str] = None

    if challenge_present:
        c_result, c_id = validate_challenge(challenge_id, subject_id, action, resource)
        challenge_result = c_result
        resolved_challenge_id = c_id
        # Fail-closed: invalid challenge blocks even a valid grant
        if c_result != "valid":
            result = PolicyResult(
                approved=False,
                reason=f"Challenge invalid: {c_result}",
                matched_grant_id=result.matched_grant_id,
            )

    event = AuditEvent(
        subject_id=subject_id,
        role=role,
        action=action,
        resource=resource,
        approved=result.approved,
        reason=result.reason,
        matched_grant_id=result.matched_grant_id,
        challenge_id=resolved_challenge_id,
        challenge_present=challenge_present,
        challenge_result=challenge_result,
    )
    append_event(event)

    if result.approved:
        return {
            "approved": True,
            "message": f"[DEMO] Action '{action}' on '{resource}' approved for '{subject_id}'.",
            "matchedGrantId": result.matched_grant_id,
            "challengeId": resolved_challenge_id,
            "auditEventId": event.id,
        }
    else:
        return {
            "approved": False,
            "reason": result.reason,
            "challengeResult": challenge_result,
            "auditEventId": event.id,
        }
