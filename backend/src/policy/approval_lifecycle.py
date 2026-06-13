"""Approval Request Lifecycle Core.

Pure / read-only.  No DB access.  No secrets exposed.
No persistence, no API endpoints, no migrations.

Provides two functions:
  build_approval_request_lifecycle(...) – construct a lifecycle state from an
      approval-requirement decision.
  transition_approval_request(...)       – move a lifecycle state through a
      transition, validating guards purely from the arguments.
"""

from __future__ import annotations

import json
from typing import Any, Optional

# ── status constants ──
_STATUS_NOT_REQUIRED = "not_required"
_STATUS_PENDING = "pending"
_STATUS_APPROVED = "approved"
_STATUS_REJECTED = "rejected"
_STATUS_EXPIRED = "expired"
_STATUS_CANCELLED = "cancelled"
_STATUS_BLOCKED = "blocked"

_ALL_STATUSES = [
    _STATUS_NOT_REQUIRED,
    _STATUS_PENDING,
    _STATUS_APPROVED,
    _STATUS_REJECTED,
    _STATUS_EXPIRED,
    _STATUS_CANCELLED,
    _STATUS_BLOCKED,
]

_TRANSITIONS = ["create", "approve", "reject", "expire", "cancel", "block", "reopen"]

# Transition matrix:  source_status -> set of allowed transitions
_VALID_TRANSITIONS: dict[str, set[str]] = {
    _STATUS_NOT_REQUIRED: {"create"},
    _STATUS_PENDING: {"create", "approve", "reject", "expire", "cancel", "block"},
    _STATUS_APPROVED: set(),
    _STATUS_REJECTED: {"reopen"},
    _STATUS_EXPIRED: {"reopen"},
    _STATUS_CANCELLED: {"reopen"},
    _STATUS_BLOCKED: {"reopen"},
}

# Sensitive key fragments that must be redacted from context
_SECRET_KEY_FRAGMENTS = frozenset(
    [
        "token",
        "secret",
        "password",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "credential",
        "credentials",
        "private_key",
        "privatekey",
        "netrc",
        "cookie",
        "jwt",
        "ssho",
        "bearer",
        "access_token",
        "refresh_token",
        "id_token",
    ]
)


# ═══════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════

def build_approval_request_lifecycle(
    approval_requirement: Any = None,
    request_id: Optional[str] = None,
    action: Any = None,
    actor_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    requested_by: Optional[str] = None,
    approvers: Optional[list] = None,
    status: Any = None,
    created_at: Any = None,
    expires_at: Any = None,
    context: Any = None,
    include_details: bool = True,
) -> dict:
    """Build an approval-request lifecycle dict from an approval-requirement decision.

    Pure / read-only – uses only the arguments passed in.  No DB access.
    """
    # Normalise approvers early
    normalised_approvers = _normalise_approvers(approvers)

    # ── missing requirement ──
    if approval_requirement is None:
        return _build_response(
            request_id=request_id,
            action=action,
            actor_id=actor_id,
            subject_id=subject_id,
            requested_by=requested_by,
            status=_STATUS_BLOCKED,
            required_approvals=0,
            required_roles=[],
            received_approvals=0,
            approved_by_roles=[],
            approval_history=[],
            approvers=normalised_approvers,
            decision="blocked",
            reason="missing_approval_requirement",
            blockers=["approval_requirement_missing"],
            warnings=[],
            created_at=created_at,
            expires_at=expires_at,
            context=context,
            include_details=include_details,
        )

    # ── malformed requirement ──
    if not isinstance(approval_requirement, dict):
        return _build_response(
            request_id=request_id,
            action=action,
            actor_id=actor_id,
            subject_id=subject_id,
            requested_by=requested_by,
            status=_STATUS_BLOCKED,
            required_approvals=0,
            required_roles=[],
            received_approvals=0,
            approved_by_roles=[],
            approval_history=[],
            approvers=normalised_approvers,
            decision="blocked",
            reason="malformed_approval_requirement",
            blockers=["approval_requirement_malformed"],
            warnings=[],
            created_at=created_at,
            expires_at=expires_at,
            context=context,
            include_details=include_details,
        )

    decision = approval_requirement.get("decision")
    warnings = list(approval_requirement.get("warnings", [])) if isinstance(approval_requirement.get("warnings"), list) else []
    blockers = list(approval_requirement.get("blockers", [])) if isinstance(approval_requirement.get("blockers"), list) else []

    # ── no approval required ──
    if decision == "no_approval_required":
        return _build_response(
            request_id=request_id,
            action=action,
            actor_id=actor_id,
            subject_id=subject_id,
            requested_by=requested_by,
            status=_STATUS_NOT_REQUIRED,
            required_approvals=0,
            required_roles=[],
            received_approvals=0,
            approved_by_roles=[],
            approval_history=[],
            approvers=normalised_approvers,
            decision="no_approval_required",
            reason=approval_requirement.get("reason", "no_approval_required"),
            blockers=blockers,
            warnings=warnings,
            created_at=created_at,
            expires_at=expires_at,
            context=context,
            include_details=include_details,
        )

    # ── blocked ──
    if decision == "blocked":
        return _build_response(
            request_id=request_id,
            action=action,
            actor_id=actor_id,
            subject_id=subject_id,
            requested_by=requested_by,
            status=_STATUS_BLOCKED,
            required_approvals=0,
            required_roles=[],
            received_approvals=0,
            approved_by_roles=[],
            approval_history=[],
            approvers=normalised_approvers,
            decision="blocked",
            reason=approval_requirement.get("reason", "blocked_by_policy"),
            blockers=blockers,
            warnings=warnings,
            created_at=created_at,
            expires_at=expires_at,
            context=context,
            include_details=include_details,
        )

    # ── approval required (single or four-eyes) ──
    if decision in ("approval_required", "four_eyes_required"):
        raw_required = approval_requirement.get("requiredApprovals", 1)
        try:
            required_approvals = max(1, int(raw_required))
        except (ValueError, TypeError):
            required_approvals = 1

        raw_roles = approval_requirement.get("requiredRoles", [])
        if isinstance(raw_roles, list):
            required_roles = [str(r) for r in raw_roles if r is not None]
        else:
            required_roles = []

        return _build_response(
            request_id=request_id,
            action=action,
            actor_id=actor_id,
            subject_id=subject_id,
            requested_by=requested_by,
            status=_STATUS_PENDING,
            required_approvals=required_approvals,
            required_roles=required_roles,
            received_approvals=0,
            approved_by_roles=[],
            approval_history=[],
            approvers=normalised_approvers,
            decision=decision,
            reason=approval_requirement.get("reason", "approval_required"),
            blockers=blockers,
            warnings=warnings,
            created_at=created_at,
            expires_at=expires_at,
            context=context,
            include_details=include_details,
        )

    # ── unknown decision -> blocked ──
    return _build_response(
        request_id=request_id,
        action=action,
        actor_id=actor_id,
        subject_id=subject_id,
        requested_by=requested_by,
        status=_STATUS_BLOCKED,
        required_approvals=0,
        required_roles=[],
        received_approvals=0,
        approved_by_roles=[],
        approval_history=[],
        approvers=normalised_approvers,
        decision="blocked",
        reason="unknown_approval_decision",
        blockers=["unknown_decision"] + blockers,
        warnings=warnings,
        created_at=created_at,
        expires_at=expires_at,
        context=context,
        include_details=include_details,
    )


def transition_approval_request(
    approval_request: Any,
    transition: str,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
    at: Any = None,
    context: Any = None,
    include_details: bool = True,
) -> dict:
    """Transition an approval-request lifecycle to a new state.

    Pure / read-only – validates guards using only the arguments passed in.
    No DB access.  No side effects.
    """
    # ── missing request ──
    if approval_request is None:
        return _build_response(
            request_id=None,
            action=None,
            actor_id=actor_id,
            status=_STATUS_BLOCKED,
            decision="blocked",
            reason="missing_approval_request",
            blockers=["approval_request_missing"],
            created_at=at,
            context=context,
            include_details=include_details,
        )

    # ── malformed request ──
    if not isinstance(approval_request, dict):
        return _build_response(
            request_id=None,
            action=None,
            actor_id=actor_id,
            status=_STATUS_BLOCKED,
            decision="blocked",
            reason="malformed_approval_request",
            blockers=["approval_request_malformed"],
            created_at=at,
            context=context,
            include_details=include_details,
        )

    # ── unknown transition ──
    if transition not in _TRANSITIONS:
        return _copy_request_with_blocker(
            approval_request,
            actor_id=actor_id,
            blocker=f"invalid_transition:{transition}",
            context=context,
            include_details=include_details,
        )

    current_status = approval_request.get("status")

    # ── guard: blocked -> reopen needs explicit flag ──
    if current_status == _STATUS_BLOCKED and transition == "reopen":
        if isinstance(context, dict) and context.get("allowBlockedReopen") is True:
            pass  # allowed
        else:
            return _copy_request_with_blocker(
                approval_request,
                actor_id=actor_id,
                blocker="blocked_cannot_reopen_without_explicit_flag",
                context=context,
                include_details=include_details,
            )

    # ── guard: transition not allowed from current status ──
    allowed = _VALID_TRANSITIONS.get(current_status, set())
    if transition not in allowed:
        return _copy_request_with_blocker(
            approval_request,
            actor_id=actor_id,
            blocker=f"transition_not_allowed:{transition}_from_{current_status}",
            context=context,
            include_details=include_details,
        )

    # ── process valid transition ──
    new_status = current_status
    new_approved_by_roles = list(approval_request.get("approvedByRoles", []))
    new_approval_history = list(approval_request.get("approvalHistory", []))
    new_received_approvals = approval_request.get("receivedApprovals", 0)
    new_reason = reason
    new_decision = approval_request.get("decision")

    if transition == "create":
        new_status = _STATUS_PENDING
        new_reason = reason or "created"

    elif transition == "approve":
        required_approvals = approval_request.get("requiredApprovals", 0)
        required_roles = approval_request.get("requiredRoles", [])
        approvers = approval_request.get("approvers", [])

        valid_approvals, approved_roles = _count_valid_approvals(
            approvers, required_roles
        )

        if valid_approvals >= required_approvals and required_approvals > 0:
            new_status = _STATUS_APPROVED
            new_approved_by_roles = approved_roles
            new_received_approvals = valid_approvals
            new_decision = "approved"
            new_reason = reason or "approved"
            if actor_id:
                new_approval_history.append(f"{at or 'now'}: {actor_id} approved")
        else:
            return _build_response(
                request_id=approval_request.get("requestId"),
                action=approval_request.get("action"),
                actor_id=actor_id,
                subject_id=approval_request.get("subjectId"),
                requested_by=approval_request.get("requestedBy"),
                status=current_status,
                required_approvals=required_approvals,
                required_roles=required_roles,
                received_approvals=valid_approvals,
                approved_by_roles=approved_roles,
                approval_history=approval_request.get("approvalHistory", []),
                approvers=approval_request.get("approvers", []),
                decision=approval_request.get("decision"),
                reason="not_enough_approvals",
                blockers=["not_enough_approvals"],
                warnings=[f"need_{required_approvals - valid_approvals}_more_approval(s)"],
                created_at=approval_request.get("createdAt"),
                expires_at=approval_request.get("expiresAt"),
                context=context,
                include_details=include_details,
            )

    elif transition == "reject":
        new_status = _STATUS_REJECTED
        new_reason = reason or "rejected"
        new_decision = "rejected"

    elif transition == "expire":
        new_status = _STATUS_EXPIRED
        new_reason = reason or "expired"
        new_decision = "expired"

    elif transition == "cancel":
        new_status = _STATUS_CANCELLED
        new_reason = reason or "cancelled"
        new_decision = "cancelled"

    elif transition == "block":
        new_status = _STATUS_BLOCKED
        new_reason = reason or "blocked"
        new_decision = "blocked"

    elif transition == "reopen":
        new_status = _STATUS_PENDING
        new_reason = reason or "reopened"
        # Keep original decision (e.g. "approval_required" or "four_eyes_required")

    return _build_response(
        request_id=approval_request.get("requestId"),
        action=approval_request.get("action"),
        actor_id=actor_id,
        subject_id=approval_request.get("subjectId"),
        requested_by=approval_request.get("requestedBy"),
        status=new_status,
        required_approvals=approval_request.get("requiredApprovals", 0),
        required_roles=approval_request.get("requiredRoles", []),
        received_approvals=new_received_approvals,
        approved_by_roles=new_approved_by_roles,
        approval_history=new_approval_history,
        approvers=approval_request.get("approvers", []),
        decision=new_decision,
        reason=new_reason,
        blockers=[],
        warnings=[],
        created_at=approval_request.get("createdAt"),
        expires_at=approval_request.get("expiresAt"),
        context=context,
        include_details=include_details,
    )


# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════

def _build_response(
    request_id: Any = None,
    action: Any = None,
    actor_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    requested_by: Optional[str] = None,
    status: Optional[str] = None,
    required_approvals: int = 0,
    required_roles: Optional[list] = None,
    received_approvals: int = 0,
    approved_by_roles: Optional[list] = None,
    approval_history: Optional[list] = None,
    approvers: Optional[list] = None,
    decision: Optional[str] = None,
    reason: Optional[str] = None,
    blockers: Optional[list] = None,
    warnings: Optional[list] = None,
    created_at: Any = None,
    expires_at: Any = None,
    context: Any = None,
    include_details: bool = True,
) -> dict:
    """Build the standardised approval-request lifecycle response dict."""
    if required_roles is None:
        required_roles = []
    if approved_by_roles is None:
        approved_by_roles = []
    if approval_history is None:
        approval_history = []
    if approvers is None:
        approvers = []
    if blockers is None:
        blockers = []
    if warnings is None:
        warnings = []

    result: dict[str, Any] = {
        "requestId": request_id,
        "action": action,
        "actorId": actor_id,
        "subjectId": subject_id,
        "requestedBy": requested_by,
        "status": status,
        "requiredApprovals": required_approvals,
        "requiredRoles": list(required_roles),
        "receivedApprovals": received_approvals,
        "approvedByRoles": list(approved_by_roles),
        "approvalHistory": list(approval_history),
        "approvers": _deduplicate_approvers(approvers),
        "decision": decision,
        "reason": reason,
        "blockers": list(blockers),
        "warnings": list(warnings),
        "createdAt": created_at,
        "expiresAt": expires_at,
    }

    if include_details and context is not None:
        safe_context = _sanitize_context(context)
        if safe_context:
            result["context"] = safe_context

    return result


def _copy_request_with_blocker(
    approval_request: dict,
    actor_id: Optional[str] = None,
    blocker: str = "",
    context: Any = None,
    include_details: bool = True,
) -> dict:
    """Return a new response based on *approval_request* with a single blocker added."""
    return _build_response(
        request_id=approval_request.get("requestId"),
        action=approval_request.get("action"),
        actor_id=actor_id,
        subject_id=approval_request.get("subjectId"),
        requested_by=approval_request.get("requestedBy"),
        status=approval_request.get("status"),
        required_approvals=approval_request.get("requiredApprovals", 0),
        required_roles=approval_request.get("requiredRoles", []),
        received_approvals=approval_request.get("receivedApprovals", 0),
        approved_by_roles=approval_request.get("approvedByRoles", []),
        approval_history=approval_request.get("approvalHistory", []),
        approvers=approval_request.get("approvers", []),
        decision=approval_request.get("decision"),
        reason=approval_request.get("reason"),
        blockers=[blocker],
        warnings=[],
        created_at=approval_request.get("createdAt"),
        expires_at=approval_request.get("expiresAt"),
        context=context,
        include_details=include_details,
    )


def _normalise_approvers(approvers: Any) -> list:
    """Normalise approvers to a list, deduplicated and sorted.

    For string approvers, deduplicate and sort strings.
    For dict approvers, deduplicate by JSON string representation and keep dicts.
    """
    if not isinstance(approvers, list):
        return []

    # Separate dict approvers from string/other approvers
    dict_approvers = []
    string_approvers = []

    for a in approvers:
        if isinstance(a, dict):
            dict_approvers.append(a)
        else:
            string_approvers.append(str(a))

    # Deduplicate dict approvers by JSON string representation
    seen_dicts: set[str] = set()
    unique_dicts: list[dict] = []
    dict_keys: list[str] = []
    for d in dict_approvers:
        key = json.dumps(d, sort_keys=True)
        if key not in seen_dicts:
            seen_dicts.add(key)
            unique_dicts.append(d)
            dict_keys.append(key)

    # Sort dict approvers by their JSON representation for determinism
    sorted_dicts = [d for _, d in sorted(zip(dict_keys, unique_dicts))]

    # Deduplicate string approvers
    seen_strings: set[str] = set()
    unique_strings: list[str] = []
    for s in string_approvers:
        if s not in seen_strings:
            seen_strings.add(s)
            unique_strings.append(s)

    # Sort string approvers for determinism
    unique_strings.sort()

    # Return combined list (dicts first, then strings)
    return sorted_dicts + unique_strings


def _deduplicate_approvers(approvers: Any) -> list:
    """Deduplicate and sort approvers deterministically."""
    return _normalise_approvers(approvers)


def _count_valid_approvals(
    approvers: Any, required_roles: Any
) -> tuple[int, list[str]]:
    """Count valid approvals and return (count, list of approved roles).

    An approver is valid when:
      * it is a dict with a "role" key,
      * that role is present in *required_roles*.
    Duplicate roles are de-duplicated.
    """
    if not isinstance(required_roles, list) or not required_roles:
        return 0, []
    if not isinstance(approvers, list):
        return 0, []

    approved_roles: list[str] = []
    for approver in approvers:
        if not isinstance(approver, dict):
            continue
        role = approver.get("role")
        if role and role in required_roles and role not in approved_roles:
            approved_roles.append(str(role))

    return len(approved_roles), approved_roles


def _sanitize_context(context: Any) -> Optional[dict]:
    """Remove secrets and sensitive fields from *context* dict."""
    if not isinstance(context, dict):
        return None
    safe: dict[str, Any] = {}
    for key, value in context.items():
        lower_key = str(key).lower()
        if any(sk in lower_key for sk in _SECRET_KEY_FRAGMENTS):
            safe[key] = "[REDACTED]"
        else:
            safe[key] = value
    return safe
