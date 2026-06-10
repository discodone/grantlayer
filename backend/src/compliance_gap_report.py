"""GrantLayer MVP — Compliance Gap Report Builder.

Public builder for a structured compliance gap report per execution_id.
Read-only. No mutations. No secrets in response.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from .evidence_completeness import build_evidence_completeness_for_execution


_REPORT_VERSION = "gl-compliance-gap-v1"


_GAP_CATALOGUE: dict[str, dict[str, str]] = {
    "missing_execution_context": {
        "category": "execution",
        "severity": "high",
        "description": (
            "No execution record exists for this grant execution. "
            "Without execution context, compliance auditability is impaired."
        ),
    },
    "missing_evidence": {
        "category": "evidence",
        "severity": "high",
        "description": (
            "No evidence bundle is archived for this execution. "
            "All grant executions must have supporting evidence for audit purposes."
        ),
    },
    "invalid_evidence": {
        "category": "evidence",
        "severity": "critical",
        "description": (
            "The archived evidence bundle failed hash integrity verification. "
            "This indicates potential tampering or corruption."
        ),
    },
    "unverified_evidence": {
        "category": "verification",
        "severity": "medium",
        "description": (
            "Evidence is present but has not been verified. "
            "Unverified evidence cannot be relied upon for compliance decisions."
        ),
    },
    "missing_provenance_events": {
        "category": "provenance",
        "severity": "low",
        "description": (
            "No provenance events are recorded for this execution. "
            "Provenance events are required for full decision traceability."
        ),
    },
    "execution_denied": {
        "category": "execution",
        "severity": "critical",
        "description": (
            "The execution was denied by the policy engine. "
            "Denied executions indicate a failed compliance check."
        ),
    },
    "execution_failed": {
        "category": "execution",
        "severity": "high",
        "description": (
            "The execution failed due to an internal error. "
            "Failed executions may indicate an operational compliance gap."
        ),
    },
    "grant_revoked": {
        "category": "grant_state",
        "severity": "critical",
        "description": (
            "The associated grant has been revoked. "
            "Execution under a revoked grant is a critical compliance gap."
        ),
    },
    "grant_expired": {
        "category": "grant_state",
        "severity": "high",
        "description": (
            "The associated grant has passed its validity window. "
            "Execution under an expired grant violates time-bound policies."
        ),
    },
    "grant_usage_exhausted": {
        "category": "grant_state",
        "severity": "high",
        "description": (
            "The associated grant has reached its usage limit. "
            "Further execution under an exhausted grant is not permitted."
        ),
    },
    "grant_unsigned": {
        "category": "grant_state",
        "severity": "critical",
        "description": (
            "The associated grant lacks a valid signature or payload hash. "
            "Unsigned grants cannot be cryptographically verified."
        ),
    },
    "grant_request_denied": {
        "category": "request",
        "severity": "critical",
        "description": (
            "The original grant request was denied. "
            "Execution under a denied request indicates a process violation."
        ),
    },
    "grant_request_revoked": {
        "category": "request",
        "severity": "high",
        "description": (
            "The original grant request was revoked. "
            "Execution under a revoked request is a compliance concern."
        ),
    },
}


_RECOMMENDED_ACTION_MAP: dict[str, str] = {
    "missing_evidence": "collect_missing_evidence",
    "invalid_evidence": "resolve_invalid_evidence",
    "unverified_evidence": "verify_evidence",
    "missing_provenance_events": "add_provenance_events",
    "missing_execution_context": "review_auditor_report",
    "execution_denied": "review_auditor_report",
    "execution_failed": "review_auditor_report",
    "grant_revoked": "review_auditor_report",
    "grant_expired": "review_auditor_report",
    "grant_usage_exhausted": "review_auditor_report",
    "grant_unsigned": "review_auditor_report",
    "grant_request_denied": "review_auditor_report",
    "grant_request_revoked": "review_auditor_report",
}


_BLOCKING_SEVERITIES = {"critical", "high"}


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _severity_rank(severity: str) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(severity, 0)


def _build_gap_detail(gap_id: str) -> dict[str, Any]:
    meta = _GAP_CATALOGUE.get(gap_id, {
        "category": "unknown",
        "severity": "medium",
        "description": f"Unrecognised compliance gap: {gap_id}",
    })
    return {
        "gapId": gap_id,
        "category": meta["category"],
        "severity": meta["severity"],
        "description": meta["description"],
    }


def _compute_overall_status_and_severity(
    gaps: list[dict[str, Any]],
    completeness_status: str,
) -> tuple[str, str]:
    if not gaps and completeness_status == "complete":
        return "clear", "none"
    if completeness_status == "critical" or any(g["severity"] == "critical" for g in gaps):
        return "blocked", "critical"
    if gaps:
        max_rank = max(_severity_rank(g["severity"]) for g in gaps)
        severity = {0: "none", 1: "low", 2: "medium", 3: "high", 4: "critical"}[max_rank]
        return "gaps_detected", severity
    return "gaps_detected", "low"


def _build_recommended_actions(gaps: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for gap in gaps:
        action = _RECOMMENDED_ACTION_MAP.get(gap["gapId"])
        if action and action not in seen:
            actions.append(action)
            seen.add(action)
    if not actions:
        actions.append("no_action_required")
    return actions


def _build_blocking_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [g for g in gaps if g["severity"] in _BLOCKING_SEVERITIES]


def build_compliance_gap_report_for_execution(
    execution_id: str,
    include_details: bool = True,
) -> Optional[dict[str, Any]]:
    """Build a compliance gap report for a GrantExecution.

    Uses the evidence completeness report as the single source of truth.
    Does not trigger verification or mutate any state.

    Args:
        execution_id: The execution to report on.
        include_details: When True, include detailed provenance events
            and completeness check objects.

    Returns:
        A compliance gap report dict, or None if the execution cannot be
        resolved (no evidence completeness report available).
    """
    completeness = build_evidence_completeness_for_execution(execution_id, include_details=include_details)
    if completeness is None:
        return None

    gap_ids = completeness.get("complianceGaps") or []
    gaps = [_build_gap_detail(gid) for gid in gap_ids]

    overall_status, severity = _compute_overall_status_and_severity(
        gaps, completeness.get("completenessStatus", "")
    )

    blocking_gaps = _build_blocking_gaps(gaps)
    recommended_actions = _build_recommended_actions(gaps)

    report: dict[str, Any] = {
        "reportType": "compliance_gap_report",
        "reportVersion": _REPORT_VERSION,
        "executionId": execution_id,
        "grantId": completeness.get("grantId"),
        "generatedAt": _iso_now(),
        "overallStatus": overall_status,
        "severity": severity,
        "complianceGaps": gaps,
        "blockingGaps": blocking_gaps,
        "recommendedActions": recommended_actions,
        "completeness": {
            "score": completeness.get("completenessScore"),
            "status": completeness.get("completenessStatus"),
        },
        "evidence": completeness.get("evidence"),
        "verification": completeness.get("verification"),
        "provenance": completeness.get("provenance"),
        "warnings": completeness.get("warnings") or [],
        "auditReadiness": completeness.get("auditReadiness"),
    }

    return report
