"""Agent Permission Scope Evaluator.

Fail-closed evaluator that determines whether an agent's assigned scopes
authorize a requested scope.  No DB access, no secrets, no network calls.
"""

from __future__ import annotations

import re
from typing import Any, Optional

# ──────────────────────────────────────────────
# Known scope vocabulary
# ──────────────────────────────────────────────

# Actions the system explicitly recognizes.
KNOWN_ACTIONS = {
    "read",
    "verify",
    "write",
    "admin",
    "create",
    "delete",
    "*",
}

# Suggested concrete scopes (for documentation / validation).
KNOWN_SCOPES = {
    "evidence:read",
    "evidence:verify",
    "provenance:read",
    "auditor_report:read",
    "compliance_gap:read",
    "grant_execution:read",
    "grant_request:read",
    "grant:read",
}

# Regex for a well-formed scope: two non-empty parts separated by a single colon,
# each part containing only a-z, 0-9, _, -, or *.
_SCOPE_RE = re.compile(r"^[a-z0-9_*-]+:[a-z0-9_*-]+$")


# ──────────────────────────────────────────────
# Scope helpers
# ──────────────────────────────────────────────

def normalize_scope(scope: str) -> str:
    """Return a cleaned, lowercased scope string."""
    if not isinstance(scope, str):
        return ""
    return scope.strip().lower()


def _is_valid_format(scope: str) -> bool:
    """Return True if *scope* matches the `resource:action` format."""
    if not scope or scope.count(":") != 1:
        return False
    domain, action = scope.split(":", 1)
    if not domain or not action:
        return False
    return bool(_SCOPE_RE.match(scope))


def _is_known_action(action: str) -> bool:
    """Return True if *action* is in the system's known action vocabulary."""
    return action in KNOWN_ACTIONS


def _is_known_scope(scope: str) -> bool:
    """Return True if *scope* is well-formed and uses a known action."""
    if not _is_valid_format(scope):
        return False
    _domain, action = scope.split(":", 1)
    return _is_known_action(action)


def scope_matches(assigned_scope: str, requested_scope: str) -> bool:
    """Return True if *assigned_scope* authorizes *requested_scope*.

    Rules (all against normalized, lowercased values):
    1. Exact match → True.
    2. assigned == ``admin:*`` and requested is a known scope → True.
    3. assigned == ``*:read`` and requested action == ``read`` and requested is
       well-formed → True.
    4. Anything else → False.
    """
    assigned = normalize_scope(assigned_scope)
    requested = normalize_scope(requested_scope)

    if not _is_valid_format(assigned) or not _is_valid_format(requested):
        return False

    # Exact match.
    if assigned == requested:
        return True

    # Wildcard: admin:* allows any known scope.
    if assigned == "admin:*" and _is_known_scope(requested):
        return True

    # Wildcard: *:read allows any well-formed scope whose action is ``read``.
    if assigned == "*:read":
        _domain, req_action = requested.split(":", 1)
        return req_action == "read"

    return False


# ──────────────────────────────────────────────
# Result builder
# ──────────────────────────────────────────────

def build_agent_permission_result(
    allowed: bool,
    agent_id: str,
    requested_scope: str,
    matched_scope: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    reason: str,
    warnings: list[str],
) -> dict:
    """Build the standardized permission evaluation response dict."""
    return {
        "allowed": allowed,
        "agentId": agent_id,
        "requestedScope": requested_scope,
        "matchedScope": matched_scope,
        "resourceType": resource_type,
        "resourceId": resource_id,
        "reason": reason,
        "warnings": warnings,
    }


# ──────────────────────────────────────────────
# Main evaluator
# ──────────────────────────────────────────────

def evaluate_agent_permission(
    agent_id: str,
    requested_scope: str,
    assigned_scopes: list[str],
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    context: Optional[Any] = None,
) -> dict:
    """Evaluate whether an agent's assigned scopes permit a requested scope.

    * deny-by-default
    * no database access
    * no secrets exposed
    * *context* is accepted but never required for the decision
    """
    warnings: list[str] = []
    normalized_requested = normalize_scope(requested_scope)

    # Missing / empty requested scope.
    if not normalized_requested:
        return build_agent_permission_result(
            allowed=False,
            agent_id=agent_id,
            requested_scope=requested_scope,
            matched_scope=None,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="requested_scope_missing",
            warnings=["Requested scope is missing or empty."],
        )

    # Malformed requested scope.
    if not _is_valid_format(normalized_requested):
        return build_agent_permission_result(
            allowed=False,
            agent_id=agent_id,
            requested_scope=requested_scope,
            matched_scope=None,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="requested_scope_malformed",
            warnings=[f"Requested scope '{requested_scope}' is malformed."],
        )

    # Unknown requested scope (well-formed but action not recognized).
    if not _is_known_scope(normalized_requested):
        return build_agent_permission_result(
            allowed=False,
            agent_id=agent_id,
            requested_scope=requested_scope,
            matched_scope=None,
            resource_type=resource_type,
            resource_id=resource_id,
            reason="requested_scope_unknown",
            warnings=[f"Requested scope '{requested_scope}' is not a known scope."],
        )

    # Scan assigned scopes.
    for raw_assigned in assigned_scopes:
        normalized_assigned = normalize_scope(raw_assigned)
        if not normalized_assigned:
            continue
        if not _is_valid_format(normalized_assigned):
            warnings.append(
                f"Assigned scope '{raw_assigned}' is malformed and was ignored."
            )
            continue

        if scope_matches(normalized_assigned, normalized_requested):
            return build_agent_permission_result(
                allowed=True,
                agent_id=agent_id,
                requested_scope=requested_scope,
                matched_scope=raw_assigned,
                resource_type=resource_type,
                resource_id=resource_id,
                reason="scope_matched",
                warnings=warnings,
            )

    # No match.
    return build_agent_permission_result(
        allowed=False,
        agent_id=agent_id,
        requested_scope=requested_scope,
        matched_scope=None,
        resource_type=resource_type,
        resource_id=resource_id,
        reason="scope_not_matched",
        warnings=warnings,
    )
