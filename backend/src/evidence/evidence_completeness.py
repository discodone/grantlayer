"""GrantLayer MVP — Evidence Completeness Scoring Builder.

Public builder for a structured evidence completeness score per execution_id.
Read-only. No mutations. No secrets in response.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from ..audit.auditor_report import build_auditor_report_for_execution


# Mapping of auditor-report findings considered "critical compliance gaps"
_CRITICAL_FINDING_PREFIXES = (
    "execution_denied",
    "grant_revoked",
    "grant_expired",
    "grant_usage_exhausted",
    "grant_unsigned",
    "grant_request_denied",
    "grant_request_revoked",
)


_REPORT_VERSION = "gl-038-a1"


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _has_critical_finding(findings: list[str]) -> bool:
    for finding in findings:
        lower = finding.lower()
        for prefix in _CRITICAL_FINDING_PREFIXES:
            if lower.startswith(prefix):
                return True
    return False


def _extract_critical_gaps(findings: list[str]) -> list[str]:
    gaps: list[str] = []
    for finding in findings:
        lower = finding.lower()
        for prefix in _CRITICAL_FINDING_PREFIXES:
            if lower.startswith(prefix):
                # Normalise to snake_case gap id
                gap_id = prefix.replace("grant_request_", "request_").replace("grant_", "")
                # Ensure we keep the full semantic name for clarity
                if prefix == "execution_denied":
                    gaps.append("execution_denied")
                elif prefix == "grant_revoked":
                    gaps.append("grant_revoked")
                elif prefix == "grant_expired":
                    gaps.append("grant_expired")
                elif prefix == "grant_usage_exhausted":
                    gaps.append("grant_usage_exhausted")
                elif prefix == "grant_unsigned":
                    gaps.append("grant_unsigned")
                elif prefix == "grant_request_denied":
                    gaps.append("grant_request_denied")
                elif prefix == "grant_request_revoked":
                    gaps.append("grant_request_revoked")
                break
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            unique.append(g)
    return unique


def build_evidence_completeness_for_execution(
    execution_id: str,
    include_details: bool = True,
) -> Optional[dict[str, Any]]:
    """Build an evidence completeness score/report for a GrantExecution.

    Uses the existing auditor report as the single source of truth.
    Does not trigger verification or mutate any state.

    Args:
        execution_id: The execution to score.
        include_details: When True, include detailed ``checks``, ``provenance.events``,
            and other diagnostic fields.

    Returns:
        A completeness result dict, or None if the execution cannot be resolved
        (no auditor report available).
    """
    report = build_auditor_report_for_execution(execution_id)
    if report is None:
        return None

    summary = report.get("provenanceSummary") or {}
    grant_id = summary.get("grantId")

    execution = summary.get("execution")
    evidence = summary.get("evidence") or {}
    verification = summary.get("verification") or {}
    provenance_events = summary.get("provenanceEvents") or []
    findings = report.get("findings") or []
    warnings = summary.get("warnings") or []

    # ── Score derivation ───────────────────────────────────────
    score = 100

    missing_evidence_list: list[str] = []
    compliance_gaps: list[str] = []

    # Missing execution context
    execution_present = execution is not None
    if not execution_present:
        score -= 10
        missing_evidence_list.append("execution_context")
        compliance_gaps.append("missing_execution_context")

    # Evidence presence
    evidence_present = evidence.get("present", False)
    if not evidence_present:
        score -= 20
        missing_evidence_list.append("evidence_bundle")
        compliance_gaps.append("missing_evidence")

    # Verification status
    verification_status = verification.get("status")
    evidence_verified = evidence_present and verification_status == "valid"
    evidence_unverified = evidence_present and verification_status in ("invalid", None, "missing_data", "unsupported_version")

    if evidence_present:
        if verification_status == "invalid":
            score -= 25
            compliance_gaps.append("invalid_evidence")
        elif verification_status in (None, "missing_data", "unsupported_version"):
            score -= 15
            compliance_gaps.append("unverified_evidence")

    # Provenance events
    provenance_events_present = bool(provenance_events)
    if not provenance_events_present:
        score -= 10
        missing_evidence_list.append("provenance_events")
        compliance_gaps.append("missing_provenance_events")

    # Critical compliance flags from auditor report findings
    critical_gaps_present = _has_critical_finding(findings)
    if critical_gaps_present:
        score -= 15 * len(_extract_critical_gaps(findings))

    # Also map auditor warnings into compliance gaps when they overlap
    for warning in warnings:
        if warning == "missing_evidence" and "missing_evidence" not in compliance_gaps:
            compliance_gaps.append("missing_evidence")
        if warning == "unverified_evidence" and "unverified_evidence" not in compliance_gaps:
            compliance_gaps.append("unverified_evidence")

    score = max(0, min(100, score))

    # ── Status determination ───────────────────────────────────
    if score < 50 or (evidence_present and verification_status == "invalid") or critical_gaps_present:
        status = "critical"
    elif score >= 90 and not critical_gaps_present and not compliance_gaps:
        status = "complete"
    else:
        status = "incomplete"

    # ── Audit readiness ──────────────────────────────────────────
    if status == "complete":
        audit_readiness = "ready"
    elif status == "critical":
        audit_readiness = "blocked"
    else:
        audit_readiness = "not_ready"

    # ── Build response ───────────────────────────────────────────
    result: dict[str, Any] = {
        "reportType": "evidence_completeness",
        "reportVersion": _REPORT_VERSION,
        "executionId": execution_id,
        "grantId": grant_id,
        "generatedAt": _iso_now(),
        "completenessScore": score,
        "completenessStatus": status,
        "missingEvidence": missing_evidence_list,
        "complianceGaps": compliance_gaps,
        "warnings": warnings,
        "auditReadiness": audit_readiness,
        "evidence": {
            "present": evidence_present,
            "hash": evidence.get("hash") if evidence_present else None,
        },
        "verification": {
            "status": verification_status,
            "verifiedAt": verification.get("verifiedAt") if evidence_present else None,
        },
        "provenance": {
            "eventCount": len(provenance_events),
        },
    }

    if include_details:
        result["checks"] = {
            "auditorReportAvailable": True,
            "executionPresent": execution_present,
            "evidencePresent": evidence_present,
            "evidenceVerified": evidence_verified,
            "evidenceValid": verification_status == "valid",
            "provenanceEventsPresent": provenance_events_present,
            "criticalGapsPresent": critical_gaps_present,
        }
        # Safe provenance events (no metadata_json, no secrets)
        result["provenance"]["events"] = provenance_events
    else:
        result["checks"] = None
        result["provenance"]["events"] = None

    return result
