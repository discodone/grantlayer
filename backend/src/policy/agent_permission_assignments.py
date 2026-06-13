"""Agent Permission Assignments.

Fail-closed resolver that determines whether an agent's permission assignment
(a combination of directly assigned scopes and profile-based scopes) authorizes
a requested scope.  No DB access, no secrets, no network calls.

Usage:
  from src.agent_permission_assignments import resolve_agent_permission_assignment

  result = resolve_agent_permission_assignment(
      agent_id="agent-123",
      requested_scope="evidence:read",
      assigned_scopes=["evidence:verify"],
      assigned_profiles=["auditor_readonly"],
      resource_type="evidence",
      resource_id="ev-456"
  )

  result["allowed"]         # True/False
  result["matchedScope"]    # Scope that granted access (or None)
  result["resolvedScopes"]  # Effective scopes after profile expansion
  # ... and other fields

Design:
  - Combines directly assigned scopes and profile-derived scopes
  - Uses existing agent_permission_profiles.expand_agent_permission_profiles()
  - Uses existing agent_permissions.evaluate_agent_permission()
  - Fail-closed: invalid inputs, missing agent_id → denies
  - Clear warnings for malformed scopes, unknown profiles
  - Deterministic ordering (sorted, deduplicated)
  - No admin:* escalation from assignments
"""

from __future__ import annotations

from typing import Any, Optional

from .agent_permission_profiles import expand_agent_permission_profiles
from .agent_permissions import evaluate_agent_permission

# ──────────────────────────────────────────────
# Main resolver
# ──────────────────────────────────────────────

def _combine_effective_scopes(
    assigned_scopes: Optional[list[str]],
    assigned_profiles: Optional[list[str]],
) -> dict[str, Any]:
    """Combine direct scopes and profile-derived scopes into effective scopes.

    Returns:
        Dict with keys:
          - resolvedScopes: list of effective scopes
          - warnings: list of warnings
          - profileResolution: dict with resolvedProfiles, unresolvedProfiles
    """
    warnings = []
    effective_scopes = []

    # Start with directly assigned scopes
    direct_scopes = assigned_scopes or []
    for scope in direct_scopes:
        if not scope or not isinstance(scope, str):
            warnings.append(f"Skipping malformed scope: {repr(scope)}")
            continue
        effective_scopes.append(scope)

    # Expand profiles (if any)
    profile_scopes = []
    profile_resolution = {"resolvedProfiles": [], "unresolvedProfiles": [], "warnings": []}

    if assigned_profiles:
        for profile in assigned_profiles:
            if not profile or not isinstance(profile, str):
                warnings.append(f"Skipping malformed profile name: {repr(profile)}")
                continue

        # Use existing profile expander
        profile_expansion = expand_agent_permission_profiles(assigned_profiles or [])
        profile_scopes = profile_expansion.get("scopes", [])
        profile_resolution = {
            "resolvedProfiles": profile_expansion.get("resolvedProfiles", []),
            "unresolvedProfiles": profile_expansion.get("unresolvedProfiles", []),
            "warnings": profile_expansion.get("warnings", []),
        }
        warnings.extend(profile_resolution["warnings"])

    # Combine and deduplicate
    all_scopes = list(set(direct_scopes + profile_scopes))
    # Sort for deterministic order
    all_scopes.sort()

    return {
        "resolvedScopes": all_scopes,
        "warnings": warnings,
        "profileResolution": profile_resolution,
    }


def _build_permission_evaluation(
    agent_id: str,
    requested_scope: str,
    effective_scopes: list[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
) -> dict[str, Any]:
    """Evaluate permission using existing evaluator."""
    return evaluate_agent_permission(
        agent_id=agent_id,
        requested_scope=requested_scope,
        assigned_scopes=effective_scopes,
        resource_type=resource_type,
        resource_id=resource_id,
    )


def resolve_agent_permission_assignment(
    agent_id: str,
    requested_scope: str,
    assigned_scopes: Optional[list[str]] = None,
    assigned_profiles: Optional[list[str]] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
    include_details: bool = True,
) -> dict[str, Any]:
    """Resolve whether an agent's permission assignment authorizes a requested scope.

    Combines directly assigned scopes and profile-based scopes to produce
    effective scopes, then evaluates the requested scope against them.

    Args:
        agent_id: Unique identifier of the agent.
        requested_scope: The permission scope being requested (e.g., "evidence:read").
        assigned_scopes: Scopes directly assigned to the agent.
        assigned_profiles: Permission profile names assigned to the agent.
        resource_type: Optional resource type for contextual evaluation.
        resource_id: Optional resource identifier for contextual evaluation.
        context: Optional additional context (currently unused, reserved for future).
        include_details: Whether to include profileResolution and evaluation details.

    Returns:
        Dict with keys:
          - allowed: bool - Whether the requested scope is authorized
          - agentId: str - Echo of the agent_id argument
          - requestedScope: str - Echo of the requested_scope argument
          - assignedScopes: list[str] - Echo of assigned_scopes (or empty list)
          - assignedProfiles: list[str] - Echo of assigned_profiles (or empty list)
          - resolvedScopes: list[str] - Effective scopes after combining direct+profile
          - matchedScope: Optional[str] - Scope that granted access (if allowed)
          - resourceType: Optional[str] - Echo of resource_type
          - resourceId: Optional[str] - Echo of resource_id
          - reason: str - Human-readable reason for allow/deny
          - warnings: list[str] - Array of warnings about inputs
          - profileResolution: dict - Only if include_details=True
                - resolvedProfiles: list[str]
                - unresolvedProfiles: list[str]
                - warnings: list[str]
          - evaluation: dict - Only if include_details=True - full evaluation result

    Fail‑closed behavior:
      - Missing or empty agent_id → denies with reason "agent_id_missing"
      - Malformed assigned_scopes → warns but includes what's parseable
      - Unknown assigned_profiles → warns but proceeds with known profiles
      - No effective scopes → denies with reason "scope_not_matched"
    """
    warnings = []

    # ── Agent ID validation (fail‑closed) ──────────────────────
    if not agent_id or not isinstance(agent_id, str) or agent_id.strip() == "":
        warnings.append("agent_id is missing or empty")
        return {
            "allowed": False,
            "agentId": agent_id or "",
            "requestedScope": requested_scope,
            "assignedScopes": assigned_scopes or [],
            "assignedProfiles": assigned_profiles or [],
            "resolvedScopes": [],
            "matchedScope": None,
            "resourceType": resource_type,
            "resourceId": resource_id,
            "reason": "agent_id_missing",
            "warnings": warnings,
        }

    # ── Combine scopes and profiles ────────────────────────────
    combination = _combine_effective_scopes(assigned_scopes, assigned_profiles)
    effective_scopes = combination["resolvedScopes"]
    warnings.extend(combination["warnings"])

    # ── Evaluate permission ────────────────────────────────────
    evaluation = _build_permission_evaluation(
        agent_id=agent_id,
        requested_scope=requested_scope,
        effective_scopes=effective_scopes,
        resource_type=resource_type,
        resource_id=resource_id,
    )

    # ── Build final result ─────────────────────────────────────
    result = {
        "allowed": evaluation["allowed"],
        "agentId": agent_id,
        "requestedScope": requested_scope,
        "assignedScopes": assigned_scopes or [],
        "assignedProfiles": assigned_profiles or [],
        "resolvedScopes": effective_scopes,
        "matchedScope": evaluation.get("matchedScope"),
        "resourceType": resource_type,
        "resourceId": resource_id,
        "reason": evaluation.get("reason", "unknown"),
        "warnings": warnings,
    }

    if include_details:
        result["profileResolution"] = combination["profileResolution"]
        result["evaluation"] = evaluation

    return result
