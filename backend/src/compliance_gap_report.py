"""GrantLayer MVP — GL-038-B1 Compliance Gap Report Builder.

Public builder for a structured compliance gap report per execution_id.
Read-only. No mutations. No secrets in response.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from .auditor_report import build_auditor_report_for_execution
from .evidence_completeness import build_evidence_completeness_for_execution


_REPORT_VERSION = "gl-038-b1"


# Mapping from auditor-report finding prefixes to canonical gap IDs
_FINDING_PREFIX_TO_GAP_ID: dict[str, str] = {
    "missing_evidence": "missing_evidence",
    "unverified_evidence": "unverified_evidence",
    "execution_denied": "execution_denied",
    "execution_failed": "execution_failed",
    "grant_revoked": "grant_revoked",
    "grant_expired": "grant_expired",
    "grant_usage_exhausted": "grant_usage_exhausted",
    "grant_unsigned": "grant_unsigned",
    "grant_request_denied": "grant_request_denied",
    "grant_request_revoked": "grant_request_revoked",
}


_GAP_CATALOGUE: dict[str, dict[str, str]] = {
    "missing_execution_context": {
        "category": "execution",
        "severity": "high",
        "description": (
            "No execution record exists for this grant execution. "
            "Without execution context, compliance auditability is impaired."
        ),
        "remediation": (
            "Ensure the grant execution is properly recorded in the execution ledger."
        ),
    },
    "missing_evidence": {
        "category": "evidence",
        "severity": "critical",
        "description": (
            "No evidence bundle is archived for this execution. "
            "All grant executions must have supporting evidence for audit purposes."
        ),
        "remediation": (
            "Archive an evidence bundle for this execution using the evidence bundle API."
        ),
    },
    "invalid_evidence": {
        "category": "evidence",
        "severity": "critical",
        "description": (
            "The archived evidence bundle failed hash integrity verification. "
            "This indicates potential tampering or corruption."
        ),
        "remediation": (
            "Re-archive the evidence bundle and trigger verification to confirm integrity."
        ),
    },
    "unverified_evidence": {
        "category": "verification",
        "severity": "high",
        "description": (
            "Evidence is present but has not been verified. "
            "Unverified evidence cannot be relied upon for compliance decisions."
        ),
        "remediation": (
            "Run evidence verification for this execution to confirm integrity."
        ),
    },
    "missing_provenance_events": {
        "category": "provenance",
        "severity": "medium",
        "description": (
            "No provenance events are recorded for this execution. "
            "Provenance events are required for full decision traceability."
        ),
        "remediation": (
            "Ensure provenance event recording is enabled and operational during execution."
        ),
    },
    "execution_denied": {
        "category": "execution",
        "severity": "critical",
        "description": (
            "The execution was denied by the policy engine. "
            "Denied executions indicate a failed compliance check."
        ),
        "remediation": (
            "Review the policy engine decision and resolve the underlying compliance issue."
        ),
    },
    "grant_revoked": {
        "category": "grant_state",
        "severity": "critical",
        "description": (
            "The associated grant has been revoked. "
            "Execution under a revoked grant is a critical compliance gap."
        ),
        "remediation": (
            "Re-issue the grant through the appropriate approval workflow if access is still required."
        ),
    },
    "grant_expired": {
        "category": "grant_state",
        "severity": "high",
        "description": (
            "The associated grant has passed its validity window. "
            "Execution under an expired grant violates time-bound policies."
        ),
        "remediation": (
            "Extend or renew the grant if access is still required."
        ),
    },
    "grant_usage_exhausted": {
        "category": "grant_state",
        "severity": "high",
        "description": (
            "The associated grant has reached its usage limit. "
            "Further execution under an exhausted grant is not permitted."
        ),
        "remediation": (
            "Request a new grant or increase the usage limit through the appropriate workflow."
        ),
    },
    "grant_unsigned": {
        "category": "grant_state",
        "severity": "critical",
        "description": (
            "The associated grant lacks a valid signature or payload hash. "
            "Unsigned grants cannot be cryptographically verified."
        ),
        "remediation": (
            "Re-create the grant to ensure it is properly signed."
        ),
    },
    "grant_request_denied": {
        "category": "request_state",
        "severity": "critical",
        "description": (
            "The original grant request was denied. "
            "Execution under a denied request indicates a process violation."
        ),
        "remediation": (
            "Resubmit the grant request with corrected information and obtain approval."
        ),
    },
    "grant_request_revoked": {
        "category": "request_state",
        "severity": "high",
        "description": (
            "The original grant request was revoked. "
            "Execution under a revoked request is a compliance concern."
        ),
        "remediation": (
            "Resubmit the grant request if access is still required."
        ),
    },
    "execution_failed": {
        "category": "execution",
        "severity": "high",
        "description": (
            "The execution failed due to an internal error. "
            "Failed executions may indicate an operational compliance gap."
        ),
        "remediation": (
            "Investigate the execution failure and ensure proper error handling is in place."
        ),
    },
}


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _finding_to_gap_id(finding: str) -> str | None:
    """Map an auditor-report finding string to a canonical gap ID."""
    lower = finding.lower()
    for prefix, gap_id in _FINDING_PREFIX_TO_GAP_ID.items():
        if lower.startswith(prefix):
            return gap_id
    return None


def _collect_all_gaps(
    completeness: dict[str, Any],
    auditor_report: dict[str, Any],
) -> list[str]:
    """Collect all compliance gap IDs from both evidence completeness and auditor report."""
    gap_set: set[str] = set()

    # Gaps directly reported by evidence completeness
    for gap_id in completeness.get("complianceGaps") or []:
        gap_set.add(gap_id)

    # Missing evidence items mapped to canonical gap IDs
    for missing in completeness.get("missingEvidence") or []:
        if missing == "execution_context":
            gap_set.add("missing_execution_context")
        elif missing == "evidence_bundle":
            gap_set.add("missing_evidence")
        elif missing == "provenance_events":
            gap_set.add("missing_provenance_events")

    # Gaps derived from auditor-report findings
    for finding in auditor_report.get("findings") or []:
        gap_id = _finding_to_gap_id(finding)
        if gap_id is not None:
            gap_set.add(gap_id)

    return sorted(gap_set)


def _compute_overall_compliance(gaps: list[dict[str, Any]]) -> str:
    if any(gap["severity"] == "critical" for gap in gaps):
        return "non_compliant"
    if gaps:
        return "partial"
    return "compliant"


def _build_gap_detail(gap_id: str, include_remediation: bool) -> dict[str, Any]:
    meta = _GAP_CATALOGUE.get(gap_id, {
        "category": "unknown",
        "severity": "medium",
        "description": f"Unrecognised compliance gap: {gap_id}",
        "remediation": "Review the gap manually.",
    })
    detail: dict[str, Any] = {
        "gapId": gap_id,
        "category": meta["category"],
        "severity": meta["severity"],
        "description": meta["description"],
    }
    if include_remediation:
        detail["remediation"] = meta["remediation"]
    return detail


def build_compliance_gap_report_for_execution(
    execution_id: str,
    include_remediation: bool = True,
) -> Optional[dict[str, Any]]:
    """Build a compliance gap report for a GrantExecution.

    Uses both the evidence completeness report and the auditor report as
    sources of truth. Does not trigger verification or mutate any state.

    Args:
        execution_id: The execution to report on.
        include_remediation: When True, include remediation recommendations
            for each gap.

    Returns:
        A compliance gap report dict, or None if the execution cannot be
        resolved (no evidence completeness report available).
    """
    completeness = build_evidence_completeness_for_execution(execution_id, include_details=False)
    if completeness is None:
        return None

    auditor_report = build_auditor_report_for_execution(execution_id)
    if auditor_report is None:
        return None

    grant_id = completeness.get("grantId")
    all_gap_ids = _collect_all_gaps(completeness, auditor_report)

    gaps = [_build_gap_detail(gap_id, include_remediation) for gap_id in all_gap_ids]
    overall_compliance = _compute_overall_compliance(gaps)
    critical_count = sum(1 for g in gaps if g["severity"] == "critical")

    report: dict[str, Any] = {
        "reportType": "compliance_gap_report",
        "reportVersion": _REPORT_VERSION,
        "executionId": execution_id,
        "grantId": grant_id,
        "generatedAt": _iso_now(),
        "overallCompliance": overall_compliance,
        "totalGaps": len(gaps),
        "criticalGaps": critical_count,
        "gaps": gaps,
        "evidenceCompletenessScore": completeness.get("completenessScore"),
        "evidenceCompletenessStatus": completeness.get("completenessStatus"),
    }

    return report
