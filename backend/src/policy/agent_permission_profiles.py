"""Agent Permission Scope Profiles Builder.

Provides reusable named scope profiles for agent integrations.
Read-only. No persistence. No network. No secrets.
"""

from __future__ import annotations

from typing import Optional

from .agent_permissions import (
    _is_known_scope,
    normalize_scope,
)

_PROFILE_VERSION = "gl-scope-profile-v1"


# Built-in scope profiles — deterministic, audited, no wildcards.
_BUILTIN_PROFILES: dict[str, dict[str, object]] = {
    "auditor_readonly": {
        "description": "Read-only access to audit and evidence resources.",
        "scopes": [
            "evidence:read",
            "provenance:read",
            "auditor_report:read",
            "compliance_gap:read",
            "grant_execution:read",
        ],
    },
    "evidence_verifier": {
        "description": "Access to read and verify evidence bundles.",
        "scopes": [
            "evidence:read",
            "evidence:verify",
            "provenance:read",
            "grant_execution:read",
        ],
    },
    "grant_operator_readonly": {
        "description": "Read-only access to grants and related execution data.",
        "scopes": [
            "grant:read",
            "grant_request:read",
            "grant_execution:read",
            "evidence:read",
        ],
    },
    "compliance_reviewer": {
        "description": "Broad read-only access for compliance review workflows.",
        "scopes": [
            "evidence:read",
            "provenance:read",
            "auditor_report:read",
            "compliance_gap:read",
            "grant:read",
            "grant_request:read",
            "grant_execution:read",
        ],
    },
}


def _validate_profile_scopes(scopes: list[str]) -> tuple[list[str], list[str]]:
    """Return (valid_scopes, warnings) for a list of scope strings."""
    valid: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for scope in scopes:
        normalized = normalize_scope(scope)
        if not normalized:
            warnings.append("Empty or invalid scope encountered.")
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        if not _is_known_scope(normalized):
            warnings.append(f"Scope '{scope}' is not a known scope.")
            continue
        valid.append(normalized)
    return valid, warnings


def build_agent_permission_profile_result(
    profile_name: str,
    scopes: list[str],
    description: Optional[str] = None,
) -> dict:
    """Build the standardized profile result dict.

    Validates scopes and attaches warnings for unknown or malformed entries.
    """
    valid_scopes, warnings = _validate_profile_scopes(scopes)
    return {
        "profileName": profile_name,
        "description": description or "",
        "scopes": valid_scopes,
        "scopeCount": len(valid_scopes),
        "warnings": warnings,
    }


def get_agent_permission_profile(profile_name: str) -> Optional[dict]:
    """Return a built-in profile dict by name, or None if unknown.

    The returned dict includes profileName, description, scopes,
    scopeCount, and warnings.
    """
    if not isinstance(profile_name, str):
        return None
    normalized_name = profile_name.strip().lower()
    meta = _BUILTIN_PROFILES.get(normalized_name)
    if meta is None:
        return None
    return build_agent_permission_profile_result(
        profile_name=normalized_name,
        scopes=meta["scopes"],  # type: ignore[arg-type]
        description=meta.get("description"),  # type: ignore[arg-type]
    )


def list_agent_permission_profiles() -> list[dict]:
    """Return all built-in profiles in deterministic alphabetical order.

    Each entry is a full profile dict as returned by
    ``get_agent_permission_profile``.
    """
    return [
        profile
        for name in sorted(_BUILTIN_PROFILES.keys())
        if (profile := get_agent_permission_profile(name)) is not None
    ]


def expand_agent_permission_profiles(profile_names: list[str]) -> dict:
    """Expand a list of profile names into a de-duplicated, sorted scope list.

    Returns a dict with:
        - ``scopes``: deterministic de-duplicated sorted list of scope strings
        - ``scopeCount``: integer count of unique scopes
        - ``warnings``: list of warnings (e.g. unknown profile names)
        - ``resolvedProfiles``: list of profile names that were successfully resolved
    """
    warnings: list[str] = []
    seen_scopes: set[str] = set()
    resolved_profiles: list[str] = []

    for raw_name in profile_names:
        name = normalize_scope(raw_name).replace(":", "_")
        if not name:
            warnings.append("Empty profile name encountered and ignored.")
            continue
        profile = get_agent_permission_profile(name)
        if profile is None:
            warnings.append(f"Unknown profile '{raw_name}' ignored.")
            continue
        resolved_profiles.append(name)
        for scope in profile["scopes"]:
            seen_scopes.add(scope)

    return {
        "scopes": sorted(seen_scopes),
        "scopeCount": len(seen_scopes),
        "warnings": warnings,
        "resolvedProfiles": resolved_profiles,
    }
