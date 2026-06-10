"""GrantLayer MVP — Institutional Auditor Export Builder.

Pure/read-only function that builds an institutional auditor export from
structured inputs.  No DB access, no network calls, no API endpoint, no
persistence.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

# ─── Constants ──────────────────────────────────────────────────────

RECORD_TYPE = "auditor_export"
RECORD_VERSION = "gl-auditor-export-v1"

EXPORT_STATUSES = {"ready", "needs_review", "blocked", "incomplete", "unknown"}
AUDIT_READINESS_STATUSES = {"audit_ready", "needs_review", "blocked", "insufficient_evidence"}

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


# ─── Helpers ────────────────────────────────────────────────────────

def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _dedupe(lst: list[str]) -> list[str]:
    return list(dict.fromkeys(lst))


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict)


def _sanitize_context(context: Any) -> Any:
    """Remove secrets and sensitive fields from *context* dict."""
    if not _is_dict(context):
        return context
    safe: dict[str, Any] = {}
    for key, value in context.items():
        lower_key = str(key).lower()
        if any(sk in lower_key for sk in _SECRET_KEY_FRAGMENTS):
            safe[key] = "[REDACTED]"
        else:
            safe[key] = value
    return safe


def _sections_from_inputs(
    decision_provenance: Optional[dict[str, Any]] = None,
    auditor_report: Optional[dict[str, Any]] = None,
    evidence_completeness: Optional[dict[str, Any]] = None,
    compliance_gap_report: Optional[dict[str, Any]] = None,
    permission_result: Optional[dict[str, Any]] = None,
    approval_requirement: Optional[dict[str, Any]] = None,
    approval_lifecycle: Optional[dict[str, Any]] = None,
    policy_results: Optional[list[dict[str, Any]]] = None,
) -> list[str]:
    """Return list of section names present in the export."""
    sections: list[str] = []
    if decision_provenance is not None:
        sections.append("decisionProvenance")
    if auditor_report is not None:
        sections.append("auditorReport")
    if evidence_completeness is not None:
        sections.append("evidence")
    if compliance_gap_report is not None:
        sections.append("compliance")
    if permission_result is not None:
        sections.append("permission")
    if approval_requirement is not None or approval_lifecycle is not None:
        sections.append("approval")
    if policy_results is not None:
        sections.append("policy")
    return sections


# ─── Builder ───────────────────────────────────────────────────────

def build_institutional_auditor_export(
    export_id: Optional[str] = None,
    export_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    decision_id: Optional[str] = None,
    generated_by: Optional[str] = None,
    auditor_id: Optional[str] = None,
    decision_provenance: Optional[dict[str, Any]] = None,
    auditor_report: Optional[dict[str, Any]] = None,
    evidence_completeness: Optional[dict[str, Any]] = None,
    compliance_gap_report: Optional[dict[str, Any]] = None,
    permission_result: Optional[dict[str, Any]] = None,
    approval_requirement: Optional[dict[str, Any]] = None,
    approval_lifecycle: Optional[dict[str, Any]] = None,
    policy_results: Optional[list[dict[str, Any]]] = None,
    metadata: Optional[dict[str, Any]] = None,
    context: Optional[dict[str, Any]] = None,
    created_at: Optional[str] = None,
    include_details: bool = True,
) -> dict[str, Any]:
    """Build an institutional auditor export from structured inputs.

    Pure/read-only function.  No DB access, no network calls.
    """
    result: dict[str, Any] = {
        "recordType": RECORD_TYPE,
        "recordVersion": RECORD_VERSION,
        "exportId": export_id,
        "exportType": export_type,
        "subjectId": subject_id,
        "decisionId": decision_id,
        "generatedBy": generated_by,
        "auditorId": auditor_id,
        "exportStatus": "unknown",
        "auditReadiness": "unknown",
        "sections": [],
        "blockers": [],
        "warnings": [],
        "missingSections": [],
        "createdAt": created_at or _iso_now(),
    }

    # ── Determine sections and missing sections ────────────────────
    sections = _sections_from_inputs(
        decision_provenance=decision_provenance,
        auditor_report=auditor_report,
        evidence_completeness=evidence_completeness,
        compliance_gap_report=compliance_gap_report,
        permission_result=permission_result,
        approval_requirement=approval_requirement,
        approval_lifecycle=approval_lifecycle,
        policy_results=policy_results,
    )
    result["sections"] = sections

    all_possible_sections = [
        "decisionProvenance",
        "auditorReport",
        "evidence",
        "compliance",
        "permission",
        "approval",
        "policy",
    ]
    missing_sections = [s for s in all_possible_sections if s not in sections]
    result["missingSections"] = missing_sections

    # ── Collect blockers and warnings ──────────────────────────────
    blockers: list[str] = []
    warnings: list[str] = []

    # --- Decision provenance checks --------------------------------
    if decision_provenance is not None:
        dp_decision_status = decision_provenance.get("decisionStatus")
        if dp_decision_status == "blocked":
            blockers.append("decision_provenance_blocked")

        dp_readiness = decision_provenance.get("readiness", {})
        if isinstance(dp_readiness, dict):
            for key, value in dp_readiness.items():
                if value == "blocked":
                    blockers.append(f"decision_provenance_{key}_blocked")

        dp_audit_readiness = decision_provenance.get("auditReadiness", {})
        if isinstance(dp_audit_readiness, dict):
            if dp_audit_readiness.get("status") == "blocked":
                blockers.append("decision_provenance_audit_readiness_blocked")
        elif dp_audit_readiness == "blocked":
            blockers.append("decision_provenance_audit_readiness_blocked")
    else:
        warnings.append("missing_decision_provenance")
        result["missingSections"].append("decisionProvenance")

    # --- Auditor report checks ------------------------------------
    if auditor_report is not None:
        critical_findings = auditor_report.get("criticalFindings", [])
        if critical_findings:
            blockers.append("auditor_report_critical_findings")
    else:
        warnings.append("missing_auditor_report")
        result["missingSections"].append("auditorReport")

    # --- Compliance gap report checks -----------------------------
    if compliance_gap_report is not None:
        critical_gaps = compliance_gap_report.get("criticalGaps", [])
        high_gaps = compliance_gap_report.get("highGaps", [])
        if critical_gaps:
            blockers.append("compliance_critical_gaps")
        if high_gaps:
            blockers.append("compliance_high_gaps")
    else:
        warnings.append("missing_compliance_gap_report")
        result["missingSections"].append("compliance")

    # --- Evidence completeness checks -----------------------------
    if evidence_completeness is not None:
        if evidence_completeness.get("complete") is not True:
            warnings.append("evidence_incomplete")
            result["missingSections"].append("evidence")
        missing_items = evidence_completeness.get("missing", [])
        if missing_items:
            warnings.append("evidence_missing_items")
    else:
        warnings.append("missing_evidence_completeness")
        result["missingSections"].append("evidence")

    # --- Permission result checks ---------------------------------
    if permission_result is not None:
        if permission_result.get("allowed") is False:
            blockers.append("permission_denied")
    else:
        warnings.append("missing_permission_result")
        result["missingSections"].append("permission")

    # --- Approval checks ------------------------------------------
    approval_present = False
    if approval_requirement is not None:
        approval_present = True
        req_decision = approval_requirement.get("decision")
        if req_decision in ("blocked", "denied"):
            blockers.append(f"approval_requirement_{req_decision}")
        elif req_decision == "pending":
            warnings.append("approval_requirement_pending")
    if approval_lifecycle is not None:
        approval_present = True
        lifecycle_status = approval_lifecycle.get("status")
        if lifecycle_status in ("blocked", "denied"):
            blockers.append(f"approval_lifecycle_{lifecycle_status}")
        elif lifecycle_status == "pending":
            warnings.append("approval_lifecycle_pending")
    if not approval_present:
        warnings.append("missing_approval")
        result["missingSections"].append("approval")

    # --- Policy checks --------------------------------------------
    if policy_results is not None:
        for policy_result in policy_results:
            if not isinstance(policy_result, dict):
                continue
            if policy_result.get("failed"):
                blockers.append("policy_failed")
                break
            if policy_result.get("blocked"):
                blockers.append("policy_blocked")
                break
    else:
        warnings.append("missing_policy_results")
        result["missingSections"].append("policy")

    # ── Determine export status ────────────────────────────────────
    if blockers:
        result["exportStatus"] = "blocked"
    elif missing_sections and not sections:
        result["exportStatus"] = "incomplete"
    elif missing_sections:
        result["exportStatus"] = "needs_review"
    elif warnings:
        result["exportStatus"] = "needs_review"
    elif sections and not blockers and not missing_sections and not warnings:
        result["exportStatus"] = "ready"
    else:
        result["exportStatus"] = "unknown"

    # ── Determine audit readiness ─────────────────────────────────
    if blockers:
        result["auditReadiness"] = "blocked"
    elif missing_sections and not sections:
        result["auditReadiness"] = "insufficient_evidence"
    elif missing_sections or warnings:
        result["auditReadiness"] = "needs_review"
    elif sections and not blockers and not missing_sections and not warnings:
        result["auditReadiness"] = "audit_ready"
    else:
        result["auditReadiness"] = "unknown"

    # ── Deduplicate ───────────────────────────────────────────────
    result["blockers"] = _dedupe(blockers)
    result["warnings"] = _dedupe(warnings)
    result["missingSections"] = _dedupe(result["missingSections"])

    # ── Detail objects (only when include_details=True) ───────────
    if include_details:
        result["decisionProvenance"] = decision_provenance
        result["auditorReport"] = auditor_report
        result["evidence"] = evidence_completeness
        result["compliance"] = compliance_gap_report
        result["permission"] = permission_result
        result["approval"] = {
            "requirement": approval_requirement,
            "lifecycle": approval_lifecycle,
        } if (approval_requirement or approval_lifecycle) else None
        result["policy"] = policy_results
        result["metadata"] = metadata
        if context is not None:
            result["context"] = _sanitize_context(context)

    return result
