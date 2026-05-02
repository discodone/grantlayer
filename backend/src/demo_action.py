"""GrantLayer MVP — Protected demo action handler."""

import datetime
from .models import AccessRequest, AuditEvent, PolicyResult
from .policy_engine import evaluate_access
from .grants import list_grants
from .audit_log import append_event


def handle_demo_action(subject_id: str, role: str, action: str, resource: str) -> dict:
    """Evaluate and execute (or block) a demo action.

    No real system changes are made — this is a pure demonstration.
    """
    request = AccessRequest(
        subject_id=subject_id,
        role=role,
        action=action,
        resource=resource,
    )

    grants = list_grants()
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    result: PolicyResult = evaluate_access(request, grants, now)

    event = AuditEvent(
        subject_id=subject_id,
        role=role,
        action=action,
        resource=resource,
        approved=result.approved,
        reason=result.reason,
        matched_grant_id=result.matched_grant_id,
    )
    append_event(event)

    if result.approved:
        return {
            "approved": True,
            "message": f"[DEMO] Action '{action}' on '{resource}' approved for '{subject_id}'.",
            "matchedGrantId": result.matched_grant_id,
            "auditEventId": event.id,
        }
    else:
        return {
            "approved": False,
            "reason": result.reason,
            "auditEventId": event.id,
        }
