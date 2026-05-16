"""GrantLayer MVP — GL-044-A Compliance Readiness Summary Builder.

Pure / read-only function that builds a compliance readiness summary from
structured GrantLayer signals.

No DB access. No network calls. No secrets exposed.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

# ─── Constants ──────────────────────────────────────────────────────

RECORD_TYPE = "compliance_readiness_summary"
RECORD_VERSION = "gl-compliance-readiness-v1"

_READINESS_STATUSES = {"ready", "needs_review", "blocked", "not_assessed"}


# ─── Helpers ────────────────────────────────────────────────────────

def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _dedupe(lst: list[str]) -> list[str]:
    return list(dict.fromkeys(lst))


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict)


# ─── Recommended actions mapper ─────────────────────────────────────

def _build_recommended_actions(blockers: list[str], warnings: list[str]) -> list[str]:
    """Map blockers and warnings to human-readable recommended actions."""
    actions: list[str] = []
    action_map: dict[str, str] = {
        # Blockers
        "evidence_critical": "Submit missing or incomplete evidence to unblock readiness.",
        "compliance_blocked": "Address compliance gaps identified in the gap report.",
        "permission_denied": "Review agent permission scope and re-evaluate access requirements.",
        "approval_requirement_blocked": "Resolve blocked approval requirement before proceeding.",
        "approval_requirement_denied": "Address denied approval requirement and resubmit.",
        "approval_lifecycle_blocked": "Resolve blocked approval lifecycle state before proceeding.",
        "approval_lifecycle_denied": "Address denied approval lifecycle and resubmit.",
        "auditor_not_ready": "Remediate auditor findings to achieve audit-ready status.",
        "auditor_critical_findings": "Address critical auditor findings immediately.",
        "policy_failed": "Review and fix failed policy checks.",
        # Warnings
        "evidence_incomplete": "Complete outstanding evidence submissions.",
        "compliance_gaps_detected": "Review and remediate detected compliance gaps.",
        "permission_unknown": "Clarify permission status for target scope.",
        "approval_requirement_pending": "Await pending approval requirement decision or follow up.",
        "approval_required": "Submit approval request for required action.",
        "approval_lifecycle_pending": "Await pending approval lifecycle decision or follow up.",
        "provenance_limited": "Expand provenance event coverage for stronger audit trail.",
        "policy_partial": "Review unresolved or partially evaluated policy checks.",
    }
    seen: set[str] = set()
    for signal in blockers + warnings:
        action = action_map.get(signal)
        if action and action not in seen:
            actions.append(action)
            seen.add(action)
    return actions


# ─── Dimension readiness evaluator ──────────────────────────────────

def _evaluate_dimension_readiness(
    evidence_completeness: Optional[dict[str, Any]] = None,
    compliance_gap_report: Optional[dict[str, Any]] = None,
    permission_result: Optional[dict[str, Any]] = None,
    approval_requirement: Optional[dict[str, Any]] = None,
    approval_lifecycle: Optional[dict[str, Any]] = None,
    provenance_summary: Optional[dict[str, Any]] = None,
    auditor_report: Optional[dict[str, Any]] = None,
    policy_results: Optional[list[dict[str, Any]]] = None,
) -> tuple[dict[str, str], list[str], list[str], list[str]]:
    """Evaluate per-dimension readiness and collect blockers/warnings/missing inputs."""
    readiness: dict[str, str] = {}
    blockers: list[str] = []
    warnings: list[str] = []
    missing_inputs: list[str] = []

    # --- Evidence dimension ------------------------------------------
    if evidence_completeness is not None:
        status = evidence_completeness.get("completenessStatus") or evidence_completeness.get("status")
        if status == "complete":
            readiness["evidence"] = "ready"
        elif status == "critical":
            readiness["evidence"] = "blocked"
            blockers.append("evidence_critical")
        else:
            readiness["evidence"] = "needs_review"
            warnings.append("evidence_incomplete")
    else:
        readiness["evidence"] = "not_assessed"
        missing_inputs.append("evidence_completeness")

    # --- Compliance dimension ----------------------------------------
    if compliance_gap_report is not None:
        overall_status = compliance_gap_report.get("overallStatus")
        if overall_status == "clear":
            readiness["compliance"] = "ready"
        elif overall_status == "blocked":
            readiness["compliance"] = "blocked"
            blockers.append("compliance_blocked")
        else:
            readiness["compliance"] = "needs_review"
            warnings.append("compliance_gaps_detected")
    else:
        readiness["compliance"] = "not_assessed"
        missing_inputs.append("compliance_gap_report")

    # --- Permission dimension ----------------------------------------
    if permission_result is not None:
        allowed = permission_result.get("allowed")
        if allowed is True:
            readiness["permission"] = "ready"
        elif allowed is False:
            readiness["permission"] = "blocked"
            blockers.append("permission_denied")
        else:
            readiness["permission"] = "needs_review"
            warnings.append("permission_unknown")
    else:
        readiness["permission"] = "not_assessed"
        missing_inputs.append("permission_result")

    # --- Approval dimension ------------------------------------------
    approval_signals: list[str] = []
    if approval_requirement is not None:
        req_decision = approval_requirement.get("decision")
        if req_decision == "blocked":
            approval_signals.append("blocked")
            blockers.append("approval_requirement_blocked")
        elif req_decision == "denied":
            approval_signals.append("denied")
            blockers.append("approval_requirement_denied")
        elif req_decision == "approved":
            approval_signals.append("approved")
        elif req_decision == "pending":
            approval_signals.append("pending")
            warnings.append("approval_requirement_pending")
        elif approval_requirement.get("required") is True:
            approval_signals.append("required")
            warnings.append("approval_required")
        else:
            approval_signals.append("not_required")
    else:
        approval_signals.append("missing")
        missing_inputs.append("approval_requirement")

    if approval_lifecycle is not None:
        lifecycle_status = approval_lifecycle.get("status")
        if lifecycle_status == "blocked":
            approval_signals.append("blocked")
            blockers.append("approval_lifecycle_blocked")
        elif lifecycle_status == "denied":
            approval_signals.append("denied")
            blockers.append("approval_lifecycle_denied")
        elif lifecycle_status == "pending":
            approval_signals.append("pending")
            warnings.append("approval_lifecycle_pending")
        elif lifecycle_status == "approved":
            approval_signals.append("approved")

    # Approval signal priority: blocked > denied > pending > required > approved > not_required > missing
    for priority in ("blocked", "denied", "pending", "required"):
        if priority in approval_signals:
            readiness["approval"] = "blocked" if priority in ("blocked", "denied") else "needs_review"
            break
    else:
        if "approved" in approval_signals:
            readiness["approval"] = "ready"
        elif "not_required" in approval_signals:
            readiness["approval"] = "ready"
        else:
            readiness["approval"] = "not_assessed"
            if "missing" in approval_signals:
                missing_inputs.append("approval_requirement")

    # --- Provenance dimension ----------------------------------------
    if provenance_summary is not None:
        events = provenance_summary.get("events") or provenance_summary.get("provenanceEvents")
        if events:
            readiness["provenance"] = "ready"
        else:
            readiness["provenance"] = "needs_review"
            warnings.append("provenance_limited")
    else:
        readiness["provenance"] = "not_assessed"
        missing_inputs.append("provenance_summary")

    # --- Auditor dimension -------------------------------------------
    if auditor_report is not None:
        if auditor_report.get("auditReady") is True or auditor_report.get("conclusion") == "clean":
            readiness["auditor"] = "ready"
        else:
            readiness["auditor"] = "blocked"
            blockers.append("auditor_not_ready")
        critical_findings = auditor_report.get("criticalFindings", [])
        if critical_findings:
            blockers.append("auditor_critical_findings")
            readiness["auditor"] = "blocked"
    else:
        readiness["auditor"] = "not_assessed"
        missing_inputs.append("auditor_report")

    # --- Policy dimension --------------------------------------------
    if policy_results is not None:
        all_passed = True
        any_failed = False
        for policy_result in policy_results:
            if not _is_dict(policy_result):
                continue
            if policy_result.get("failed"):
                all_passed = False
                any_failed = True
            elif not policy_result.get("passed"):
                all_passed = False
        if all_passed:
            readiness["policy"] = "ready"
        elif any_failed:
            readiness["policy"] = "blocked"
            blockers.append("policy_failed")
        else:
            readiness["policy"] = "needs_review"
            warnings.append("policy_partial")
    else:
        readiness["policy"] = "not_assessed"
        missing_inputs.append("policy_results")

    return readiness, blockers, warnings, missing_inputs


# ─── Overall readiness computer ───────────────────────────────────

def _compute_overall_readiness(
    readiness: dict[str, str],
    blockers: list[str],
) -> str:
    """Compute overall readiness from dimension readiness and blockers."""
    if blockers:
        return "blocked"
    if any(r == "blocked" for r in readiness.values()):
        return "blocked"
    if any(r == "needs_review" for r in readiness.values()):
        return "needs_review"
    if any(r == "not_assessed" for r in readiness.values()):
        if not any(r == "ready" for r in readiness.values()):
            return "not_assessed"
        return "needs_review"
    return "ready"


# ─── Score computer ───────────────────────────────────────────────

def _compute_readiness_score(readiness: dict[str, str]) -> int:
    """Compute readiness score as percentage of ready dimensions."""
    total = len(readiness)
    ready = sum(1 for r in readiness.values() if r == "ready")
    return int((ready / total) * 100) if total > 0 else 0


# ─── Main builder ─────────────────────────────────────────────────

def build_compliance_readiness_summary(
    execution_id: Optional[str] = None,
    grant_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    evidence_completeness: Optional[dict[str, Any]] = None,
    compliance_gap_report: Optional[dict[str, Any]] = None,
    permission_result: Optional[dict[str, Any]] = None,
    approval_requirement: Optional[dict[str, Any]] = None,
    approval_lifecycle: Optional[dict[str, Any]] = None,
    provenance_summary: Optional[dict[str, Any]] = None,
    auditor_report: Optional[dict[str, Any]] = None,
    policy_results: Optional[list[dict[str, Any]]] = None,
    context: Optional[dict[str, Any]] = None,
    created_at: Optional[str] = None,
    include_details: bool = True,
) -> dict[str, Any]:
    """Build a compliance readiness summary from structured GrantLayer signals.

    Pure / read-only function. No DB access. No network calls.

    Args:
        execution_id: Optional execution identifier.
        grant_id: Optional grant identifier.
        subject_id: Optional subject identifier (preferred over grant_id).
        workflow_id: Optional workflow identifier.
        evidence_completeness: Evidence completeness dict (e.g. from GL-038-A1).
        compliance_gap_report: Compliance gap report dict (e.g. from GL-038-B1).
        permission_result: Permission result dict (e.g. from GL-039-A1).
        approval_requirement: Approval requirement dict (e.g. from GL-040-A1).
        approval_lifecycle: Approval lifecycle dict (e.g. from GL-040-B).
        provenance_summary: Provenance summary dict (e.g. from GL-037-B).
        auditor_report: Auditor report dict (e.g. from GL-037-C1).
        policy_results: List of policy result dicts (e.g. from GL-043-A).
        context: Optional context dict (redacted if secrets are present).
        created_at: Optional ISO timestamp; defaults to now.
        include_details: When True, include detail objects for each dimension.

    Returns:
        A compliance readiness summary dict matching the approved contract:
        recordType, recordVersion, subjectId, workflowId, createdAt,
        readinessStatus, readinessScore,
        evidenceStatus, complianceStatus, permissionStatus, approvalStatus,
        provenanceStatus, auditorExportStatus, policyStatus,
        blockers, warnings, missingInputs, recommendedActions.
    """
    # Evaluate dimension readiness
    readiness, blockers, warnings, missing_inputs = _evaluate_dimension_readiness(
        evidence_completeness=evidence_completeness,
        compliance_gap_report=compliance_gap_report,
        permission_result=permission_result,
        approval_requirement=approval_requirement,
        approval_lifecycle=approval_lifecycle,
        provenance_summary=provenance_summary,
        auditor_report=auditor_report,
        policy_results=policy_results,
    )

    # Compute overall readiness and score
    overall_readiness = _compute_overall_readiness(readiness, blockers)
    readiness_score = _compute_readiness_score(readiness)

    # Build recommended actions from blockers and warnings
    recommended_actions = _build_recommended_actions(blockers, warnings)

    # Deduplicate
    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
    missing_inputs = _dedupe(missing_inputs)

    result: dict[str, Any] = {
        "recordType": RECORD_TYPE,
        "recordVersion": RECORD_VERSION,
        "executionId": execution_id,
        "grantId": grant_id,
        "subjectId": subject_id,
        "workflowId": workflow_id,
        "createdAt": created_at or _iso_now(),
        "readinessStatus": overall_readiness,
        "readinessScore": readiness_score,
        "evidenceStatus": readiness.get("evidence", "not_assessed"),
        "complianceStatus": readiness.get("compliance", "not_assessed"),
        "permissionStatus": readiness.get("permission", "not_assessed"),
        "approvalStatus": readiness.get("approval", "not_assessed"),
        "provenanceStatus": readiness.get("provenance", "not_assessed"),
        "auditorExportStatus": readiness.get("auditor", "not_assessed"),
        "policyStatus": readiness.get("policy", "not_assessed"),
        "blockers": blockers,
        "warnings": warnings,
        "missingInputs": missing_inputs,
        "recommendedActions": recommended_actions,
    }

    # Include detail objects when requested
    if include_details:
        result["evidenceCompleteness"] = evidence_completeness
        result["complianceGapReport"] = compliance_gap_report
        result["permissionResult"] = permission_result
        result["approval"] = {
            "requirement": approval_requirement,
            "lifecycle": approval_lifecycle,
        } if (approval_requirement or approval_lifecycle) else None
        result["provenance"] = provenance_summary
        result["auditorReport"] = auditor_report
        result["policy"] = policy_results
        if context is not None:
            result["context"] = context

    return result
