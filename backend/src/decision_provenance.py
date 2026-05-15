"""GrantLayer MVP — GL-041-A Decision Provenance v2 Builder.

Pure/read-only function that determines decision provenance from structured inputs.
No DB access, no network calls, no API endpoint, no persistence.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional, TypedDict

# ─── Constants ──────────────────────────────────────────────────────

RECORD_TYPE = "decision_provenance"
RECORD_VERSION = "gl-decision-provenance-v2"


# ─── Input types ────────────────────────────────────────────────────

class EvidenceCompleteness(TypedDict, total=False):
    """Evidence completeness assessment."""
    complete: bool
    missing: list[str]
    present: list[str]
    warning: str


class ComplianceGapReport(TypedDict, total=False):
    """Compliance gap report."""
    overallStatus: str  # "complete", "incomplete", "blocked"
    criticalGaps: list[dict[str, Any]]
    highGaps: list[dict[str, Any]]
    mediumGaps: list[dict[str, Any]]
    lowGaps: list[dict[str, Any]]


class PermissionResult(TypedDict, total=False):
    """Permission evaluation result."""
    allowed: bool
    reason: Optional[str]
    requiredPermissions: Optional[list[str]]
    grantedPermissions: Optional[list[str]]
    missingPermissions: Optional[list[str]]


class ApprovalRequirement(TypedDict, total=False):
    """Approval requirement evaluation."""
    required: bool
    approvers: Optional[list[str]]
    threshold: Optional[int]
    approved: Optional[bool]
    pending: Optional[bool]
    decision: Optional[str]  # "approved", "denied", "pending", "blocked"


class ApprovalLifecycle(TypedDict, total=False):
    """Approval lifecycle state."""
    status: Optional[str]  # "started", "pending", "approved", "denied", "blocked"
    currentStep: Optional[int]
    totalSteps: Optional[int]
    expiresAt: Optional[str]
    approvedBy: Optional[list[str]]
    deniedBy: Optional[list[str]]


class ProvenanceSummary(TypedDict, total=False):
    """Provenance summary."""
    decisionId: Optional[str]
    events: Optional[list[dict[str, Any]]]
    warnings: Optional[list[str]]


class AuditorReport(TypedDict, total=False):
    """Auditor report."""
    auditReady: Optional[bool]
    criticalFindings: Optional[list[dict[str, Any]]]
    warnings: Optional[list[dict[str, Any]]]
    recommendations: Optional[list[dict[str, Any]]]


# ─── Output types ───────────────────────────────────────────────────

class DecisionProvenanceV2(TypedDict, total=False):
    """Decision provenance v2 output structure."""
    recordType: str
    recordVersion: str
    decisionId: Optional[str]
    decisionType: Optional[str]
    subjectId: Optional[str]
    actorId: Optional[str]
    action: Optional[str]
    decision: Optional[str]
    decisionStatus: Optional[str]
    reason: Optional[str]
    readiness: dict[str, Any]
    signals: dict[str, str]
    blockers: list[str]
    warnings: list[str]
    missingInputs: list[str]
    auditReadiness: dict[str, Any]
    createdAt: str
    # Optional detail objects (when include_details=True)
    evidence: Optional[Any]
    compliance: Optional[Any]
    permission: Optional[Any]
    approval: Optional[Any]
    provenance: Optional[Any]
    auditor: Optional[Any]
    policy: Optional[Any]
    inputs: Optional[Any]


# ─── Helpers ───────────────────────────────────────────────────────

def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _dedupe(lst: list[str]) -> list[str]:
    return list(dict.fromkeys(lst))


def _redact_sensitive(data: Any) -> Any:
    """Redact secrets/tokens/auth hashes from dicts/lists/strings."""
    if data is None:
        return None
    if isinstance(data, str):
        lowered = data.lower()
        if any(
            keyword in lowered
            for keyword in [
                "token", "secret", "password", "credential", "api_key",
                "apikey", "auth", "hash", "private_key", "privatekey",
                "signature", "salt", "bearer",
            ]
        ):
            return "[REDACTED]"
        return data
    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if any(
                keyword in k.lower()
                for keyword in [
                    "token", "secret", "password", "credential", "api_key",
                    "apikey", "auth", "hash", "private_key", "privatekey",
                    "signature", "salt", "bearer",
                ]
            ) else _redact_sensitive(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_redact_sensitive(v) for v in data]
    return data


# ─── Builder ───────────────────────────────────────────────────────

def build_decision_provenance_v2(
    decision_id: Optional[str] = None,
    decision_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    decision: Optional[str] = None,
    reason: Optional[str] = None,
    evidence_completeness: Optional[EvidenceCompleteness] = None,
    compliance_gap_report: Optional[ComplianceGapReport] = None,
    permission_result: Optional[PermissionResult] = None,
    approval_requirement: Optional[ApprovalRequirement] = None,
    approval_lifecycle: Optional[ApprovalLifecycle] = None,
    provenance_summary: Optional[ProvenanceSummary] = None,
    auditor_report: Optional[AuditorReport] = None,
    policy_results: Optional[list[dict[str, Any]]] = None,
    inputs: Optional[dict[str, Any]] = None,
    context: Optional[dict[str, Any]] = None,
    created_at: Optional[str] = None,
    include_details: bool = True,
) -> DecisionProvenanceV2:
    """Build decision provenance v2 from structured inputs.

    Pure/read-only function. No DB access, no network calls.
    """
    result: DecisionProvenanceV2 = {
        "recordType": RECORD_TYPE,
        "recordVersion": RECORD_VERSION,
        "decisionId": decision_id,
        "decisionType": decision_type,
        "subjectId": subject_id,
        "actorId": actor_id,
        "action": action,
        "decision": decision,
        "decisionStatus": None,
        "reason": reason,
        "readiness": {},
        "signals": {},
        "blockers": [],
        "warnings": [],
        "missingInputs": [],
        "auditReadiness": {},
        "createdAt": created_at or _iso_now(),
    }

    # ── Determine decision status ───────────────────────────────────
    if decision is None:
        result["decisionStatus"] = "incomplete"
        result["missingInputs"].append("decision")
    else:
        result["decisionStatus"] = decision

    # ── Signals and readiness ──────────────────────────────────────
    readiness = {}
    signals = {}
    blockers: list[str] = []
    warnings: list[str] = []
    missing_inputs: list[str] = result["missingInputs"].copy()
    audit_readiness = {}

    # --- Evidence signal and readiness ----------------------------
    if evidence_completeness is not None:
        if evidence_completeness.get("complete") is True:
            signals["evidence"] = "complete"
            readiness["evidence"] = "ready"
        elif evidence_completeness.get("missing"):
            signals["evidence"] = "incomplete"
            readiness["evidence"] = "needs_attention"
            warnings.append("evidence_incomplete")
        elif evidence_completeness.get("warning"):
            signals["evidence"] = "warning"
            readiness["evidence"] = "needs_attention"
            warnings.append("evidence_warning")
        else:
            signals["evidence"] = "incomplete"
            readiness["evidence"] = "needs_attention"
            warnings.append("evidence_incomplete")
    else:
        signals["evidence"] = "missing"
        readiness["evidence"] = "not_assessed"
        missing_inputs.append("evidence_completeness")

    # --- Compliance signal and readiness --------------------------
    if compliance_gap_report is not None:
        status = compliance_gap_report.get("overallStatus")
        if status == "complete":
            signals["compliance"] = "complete"
            readiness["compliance"] = "ready"
        elif status == "incomplete":
            signals["compliance"] = "incomplete"
            readiness["compliance"] = "needs_attention"
            warnings.append("compliance_incomplete")
        elif status == "blocked":
            signals["compliance"] = "blocked"
            readiness["compliance"] = "blocked"
            blockers.append("compliance_blocked")
        else:
            signals["compliance"] = "unknown"
            readiness["compliance"] = "needs_attention"
            warnings.append("compliance_unknown_status")

        critical_gaps = compliance_gap_report.get("criticalGaps", [])
        high_gaps = compliance_gap_report.get("highGaps", [])
        if critical_gaps:
            blockers.append("critical_compliance_gaps")
            signals["compliance"] = "blocked"
            readiness["compliance"] = "blocked"
        elif high_gaps:
            blockers.append("high_compliance_gaps")
            signals["compliance"] = "blocked"
            readiness["compliance"] = "blocked"
    else:
        signals["compliance"] = "missing"
        readiness["compliance"] = "not_assessed"
        missing_inputs.append("compliance_gap_report")

    # --- Permission signal and readiness -------------------------
    if permission_result is not None:
        allowed = permission_result.get("allowed")
        if allowed is True:
            signals["permission"] = "allowed"
            readiness["permission"] = "ready"
        elif allowed is False:
            signals["permission"] = "denied"
            readiness["permission"] = "blocked"
            blockers.append("permission_denied")
        else:
            signals["permission"] = "unknown"
            readiness["permission"] = "needs_attention"
            warnings.append("permission_unknown")

        missing_perms = permission_result.get("missingPermissions")
        if missing_perms:
            warnings.append("partial_permission")
            if signals["permission"] != "denied":
                signals["permission"] = "partial"
                readiness["permission"] = "needs_attention"
    else:
        signals["permission"] = "missing"
        readiness["permission"] = "not_assessed"
        missing_inputs.append("permission_result")

    # --- Approval signal and readiness ---------------------------
    approval_signals = []
    approval_readiness = None
    if approval_requirement is not None:
        req_decision = approval_requirement.get("decision")
        if req_decision == "blocked":
            approval_signals.append("blocked")
            approval_readiness = "blocked"
            blockers.append("approval_requirement_blocked")
        elif req_decision == "denied":
            approval_signals.append("denied")
            approval_readiness = "blocked"
            blockers.append("approval_requirement_denied")
        elif req_decision == "approved":
            approval_signals.append("approved")
            approval_readiness = "ready"
        elif req_decision == "pending":
            approval_signals.append("pending")
            approval_readiness = "needs_attention"
            blockers.append("approval_requirement_pending")
        elif approval_requirement.get("required") is True:
            approval_signals.append("required")
            approval_readiness = "needs_attention"
            blockers.append("approval_required")
        else:
            approval_signals.append("not_required")
            approval_readiness = "ready"
    else:
        approval_signals.append("missing")
        approval_readiness = "not_assessed"
        missing_inputs.append("approval_requirement")

    # Approval lifecycle overrides
    if approval_lifecycle is not None:
        lifecycle_status = approval_lifecycle.get("status")
        if lifecycle_status == "blocked":
            blockers.append("approval_lifecycle_blocked")
            approval_signals.append("blocked")
            approval_readiness = "blocked"
        elif lifecycle_status == "denied":
            blockers.append("approval_lifecycle_denied")
            approval_signals.append("denied")
            approval_readiness = "blocked"
        elif lifecycle_status == "pending":
            approval_signals.append("pending")
            approval_readiness = "needs_attention"
            blockers.append("approval_lifecycle_pending")
        elif lifecycle_status == "approved":
            approval_signals.append("approved")
            approval_readiness = "ready"

    # Approval signal priority: blocked > denied > pending > required > approved > not_required > missing
    for priority in ["blocked", "denied", "pending", "required"]:
        if priority in approval_signals:
            signals["approval"] = priority
            readiness["approval"] = "blocked" if priority in ["blocked", "denied"] else "needs_attention"
            break
    else:
        if "approved" in approval_signals:
            signals["approval"] = "approved"
            readiness["approval"] = "ready"
        elif "not_required" in approval_signals:
            signals["approval"] = "not_required"
            readiness["approval"] = "ready"
        else:
            signals["approval"] = "missing"
            readiness["approval"] = "not_assessed"

    # --- Provenance signal and readiness -------------------------
    if provenance_summary is not None:
        events = provenance_summary.get("events")
        prov_warnings = provenance_summary.get("warnings", [])
        if events:
            signals["provenance"] = "present"
            readiness["provenance"] = "ready"
        elif prov_warnings:
            signals["provenance"] = "warning"
            readiness["provenance"] = "needs_attention"
            warnings.extend(prov_warnings)
        else:
            signals["provenance"] = "limited"
            readiness["provenance"] = "needs_attention"
            warnings.append("provenance_limited")

        if decision_id and provenance_summary.get("decisionId") is not None and provenance_summary.get("decisionId") != decision_id:
            warnings.append("provenance_decision_id_mismatch")
    else:
        signals["provenance"] = "missing"
        readiness["provenance"] = "not_assessed"
        missing_inputs.append("provenance_summary")

    # --- Auditor signal and readiness ---------------------------
    if auditor_report is not None:
        if auditor_report.get("auditReady") is True:
            audit_readiness["status"] = "ready"
            audit_readiness["auditReady"] = True
            signals["auditor"] = "ready"
        else:
            audit_readiness["status"] = "blocked"
            audit_readiness["auditReady"] = False
            signals["auditor"] = "blocked"
            blockers.append("audit_not_ready")

        critical_findings = auditor_report.get("criticalFindings", [])
        if critical_findings:
            blockers.append("auditor_critical_findings")
            audit_readiness["status"] = "blocked"
            signals["auditor"] = "blocked"

        auditor_warnings = auditor_report.get("warnings", [])
        if auditor_warnings:
            warnings.append("auditor_warnings")
            if signals["auditor"] != "blocked":
                signals["auditor"] = "warning"
                audit_readiness["status"] = "warning"
    else:
        signals["auditor"] = "missing"
        audit_readiness["status"] = "not_assessed"
        audit_readiness["auditReady"] = False
        missing_inputs.append("auditor_report")

    # --- Policy signal and readiness ----------------------------
    if policy_results is not None:
        all_passed = True
        any_failed = False
        for policy_result in policy_results:
            if not isinstance(policy_result, dict):
                continue
            if policy_result.get("failed"):
                all_passed = False
                any_failed = True
            elif not policy_result.get("passed"):
                all_passed = False
        if all_passed:
            signals["policy"] = "passed"
            readiness["policy"] = "ready"
        elif any_failed:
            signals["policy"] = "failed"
            readiness["policy"] = "blocked"
            blockers.append("policy_failed")
        else:
            signals["policy"] = "partial"
            readiness["policy"] = "needs_attention"
            warnings.append("policy_partial")
    else:
        signals["policy"] = "missing"
        readiness["policy"] = "not_assessed"
        missing_inputs.append("policy_results")

    # --- Deduplicate --------------------------------------------
    result["signals"] = signals
    result["readiness"] = readiness
    result["auditReadiness"] = audit_readiness
    result["blockers"] = _dedupe(blockers)
    result["warnings"] = _dedupe(warnings)
    result["missingInputs"] = _dedupe(missing_inputs)

    # --- Override decisionStatus if blocked ----------------------
    if result["blockers"] and result["decisionStatus"] not in ["denied", "blocked", None]:
        result["decisionStatus"] = "blocked"
        result["reason"] = f"Blocked by: {', '.join(result['blockers'][:3])}"

    # --- Detail objects (only when include_details=True) --------
    if include_details:
        result["evidence"] = evidence_completeness
        result["compliance"] = compliance_gap_report
        result["permission"] = permission_result
        result["approval"] = {
            "requirement": approval_requirement,
            "lifecycle": approval_lifecycle,
        } if (approval_requirement or approval_lifecycle) else None
        result["provenance"] = provenance_summary
        result["auditor"] = auditor_report
        result["policy"] = policy_results
        if inputs is not None or context is not None:
            merged_inputs = {}
            if inputs:
                merged_inputs.update(inputs)
            if context:
                merged_inputs.update(context)
            result["inputs"] = _redact_sensitive(merged_inputs)
        else:
            result["inputs"] = None

    return result