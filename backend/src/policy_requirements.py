"""GrantLayer MVP — Policy Requirement / Grant Rule Pack Evaluator.

Pure / read-only evaluator that checks a machine-readable grant/funding policy
pack against structured GrantLayer signals.

No DB access.  No network calls.  No secrets exposed.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

RECORD_TYPE = "policy_requirement_evaluation"
RECORD_VERSION = "gl-policy-requirements-v1"

_EVALUATION_STATUSES = {"passed", "needs_review", "blocked", "incomplete", "unknown"}
_READINESS_STATUSES = {"ready", "needs_review", "blocked", "insufficient_data"}

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


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict)


def _sanitize_context(context: Any) -> Optional[dict[str, Any]]:
    if not _is_dict(context):
        return None
    safe: dict[str, Any] = {}
    for key, value in context.items():
        lower_key = str(key).lower()
        if any(sk in lower_key for sk in _SECRET_KEY_FRAGMENTS):
            safe[key] = "[REDACTED]"
        else:
            safe[key] = value
    return safe


def _parse_iso(ts: str) -> Optional[datetime.datetime]:
    try:
        ts = ts.rstrip("Z")
        return datetime.datetime.fromisoformat(ts)
    except (ValueError, TypeError, AttributeError):
        return None


# ──────────────────────────────────────────────
# Normalisation
# ──────────────────────────────────────────────

def normalize_policy_pack(policy_pack: Any) -> Optional[dict[str, Any]]:
    """Validate and return a normalised policy pack dict, or None if malformed."""
    if not _is_dict(policy_pack):
        return None
    if not policy_pack.get("policyPackId"):
        return None
    return {
        "policyPackId": str(policy_pack.get("policyPackId", "")),
        "policyPackVersion": str(policy_pack.get("policyPackVersion", "")),
        "name": str(policy_pack.get("name", "")),
        "requiredEvidence": policy_pack.get("requiredEvidence", []),
        "exclusions": policy_pack.get("exclusions", []),
        "deadlines": policy_pack.get("deadlines", []),
        "amountLimits": policy_pack.get("amountLimits", {}),
        "requiredRoles": policy_pack.get("requiredRoles", []),
        "approvalPolicy": policy_pack.get("approvalPolicy", {}),
    }


# ──────────────────────────────────────────────
# Sub-evaluators
# ──────────────────────────────────────────────

def evaluate_required_evidence(
    policy_pack: dict[str, Any],
    subject: Optional[dict[str, Any]],
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Evaluate required evidence against subject evidence types.

    Returns:
        (required_evidence_types, missing_evidence, satisfied_evidence, blockers, warnings)
    """
    required_evidence: list[str] = []
    missing_evidence: list[str] = []
    satisfied_evidence: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    raw_required = policy_pack.get("requiredEvidence", [])
    if not isinstance(raw_required, list):
        return required_evidence, missing_evidence, satisfied_evidence, blockers, warnings

    subject_evidence_types = []
    if _is_dict(subject):
        raw_types = subject.get("evidenceTypes")
        if isinstance(raw_types, list):
            subject_evidence_types = [str(t) for t in raw_types if t is not None]

    for item in raw_required:
        if not _is_dict(item):
            continue
        ev_type = str(item.get("type", "")) if item.get("type") is not None else ""
        if not ev_type:
            continue
        is_required = bool(item.get("required", False))
        if is_required:
            required_evidence.append(ev_type)
            if ev_type not in subject_evidence_types:
                missing_evidence.append(ev_type)
                blockers.append(f"missing_required_evidence:{ev_type}")
            else:
                satisfied_evidence.append(ev_type)
        else:
            if ev_type not in subject_evidence_types:
                warnings.append(f"missing_optional_evidence:{ev_type}")
            else:
                satisfied_evidence.append(ev_type)

    return required_evidence, missing_evidence, satisfied_evidence, blockers, warnings


def evaluate_exclusions(
    policy_pack: dict[str, Any],
    subject: Optional[dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    """Evaluate exclusions against subject exclusion codes.

    Returns:
        (exclusion_violations, blockers, warnings)
    """
    exclusion_violations: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    raw_exclusions = policy_pack.get("exclusions", [])
    if not isinstance(raw_exclusions, list):
        return exclusion_violations, blockers, warnings

    subject_codes = []
    if _is_dict(subject):
        raw_codes = subject.get("exclusionCodes")
        if isinstance(raw_codes, list):
            subject_codes = [str(c) for c in raw_codes if c is not None]

    for item in raw_exclusions:
        if not _is_dict(item):
            continue
        code = str(item.get("code", "")) if item.get("code") is not None else ""
        if not code:
            continue
        severity = str(item.get("severity", "")).lower()
        if code in subject_codes:
            exclusion_violations.append(code)
            if severity == "blocking":
                blockers.append(f"exclusion:{code}")
            else:
                warnings.append(f"exclusion:{code}")

    return exclusion_violations, blockers, warnings


def evaluate_deadlines(
    policy_pack: dict[str, Any],
    subject: Optional[dict[str, Any]],
    now: Optional[datetime.datetime] = None,
) -> tuple[str, list[str], list[str]]:
    """Evaluate deadlines.

    Returns:
        (deadline_status, blockers, warnings)
    """
    blockers: list[str] = []
    warnings: list[str] = []

    raw_deadlines = policy_pack.get("deadlines", [])
    if not isinstance(raw_deadlines, list):
        return "missing", blockers, warnings

    if not raw_deadlines:
        return "none", blockers, warnings

    current_time = now or datetime.datetime.utcnow()
    any_expired_required = False
    any_expired = False
    any_present = False

    for item in raw_deadlines:
        if not _is_dict(item):
            continue
        due_at = item.get("dueAt")
        is_required = bool(item.get("required", False))
        if not due_at:
            continue
        any_present = True
        due_dt = _parse_iso(due_at)
        if due_dt is None:
            if is_required:
                any_expired_required = True
                blockers.append("deadline_malformed")
            else:
                warnings.append("deadline_malformed")
            continue
        if current_time > due_dt:
            any_expired = True
            if is_required:
                any_expired_required = True
                blockers.append(f"deadline_expired:{item.get('name', 'unknown')}")
            else:
                warnings.append(f"deadline_expired:{item.get('name', 'unknown')}")

    if not any_present:
        return "none", blockers, warnings

    if any_expired_required:
        return "expired", blockers, warnings
    if any_expired:
        return "expired_optional", blockers, warnings
    return "on_time", blockers, warnings


def evaluate_amount_limits(
    policy_pack: dict[str, Any],
    subject: Optional[dict[str, Any]],
) -> tuple[str, list[str], list[str]]:
    """Evaluate amount limits.

    Returns:
        (amount_status, blockers, warnings)
    """
    blockers: list[str] = []
    warnings: list[str] = []

    amount_limits = policy_pack.get("amountLimits", {})
    if not _is_dict(amount_limits):
        return "missing", blockers, warnings

    max_amount = amount_limits.get("maxAmount")
    policy_currency = str(amount_limits.get("currency", "")) if amount_limits.get("currency") is not None else ""

    if max_amount is None and not policy_currency:
        return "none", blockers, warnings

    if not _is_dict(subject):
        return "missing_subject", blockers, warnings

    subject_amount = subject.get("amount")
    subject_currency = str(subject.get("currency", "")) if subject.get("currency") is not None else ""

    if subject_amount is None:
        return "missing_subject_amount", blockers, warnings

    # Currency mismatch
    if policy_currency and subject_currency and policy_currency != subject_currency:
        warnings.append("currency_mismatch")
        return "currency_mismatch", blockers, warnings

    try:
        amount_val = float(subject_amount)
        max_val = float(max_amount) if max_amount is not None else None
    except (ValueError, TypeError):
        warnings.append("amount_malformed")
        return "malformed", blockers, warnings

    if max_val is not None and amount_val > max_val:
        blockers.append("amount_above_max")
        return "above_limit", blockers, warnings

    return "within_limit", blockers, warnings


def evaluate_required_roles(
    policy_pack: dict[str, Any],
    subject: Optional[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Evaluate required roles.

    Returns:
        (required_roles, blockers)
    """
    required_roles: list[str] = []
    blockers: list[str] = []

    raw_roles = policy_pack.get("requiredRoles", [])
    if isinstance(raw_roles, list):
        required_roles = [str(r) for r in raw_roles if r is not None]

    if required_roles and _is_dict(subject):
        # Subject does not carry roles in the expected shape, so we only record
        # the required roles but do not block unless the caller explicitly
        # passes a role mismatch signal.
        pass

    return required_roles, blockers


def evaluate_required_approvals(
    policy_pack: dict[str, Any],
    subject: Optional[dict[str, Any]],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Evaluate approval policy.

    Returns:
        (approval_policy, blockers, warnings)
    """
    blockers: list[str] = []
    warnings: list[str] = []

    raw_policy = policy_pack.get("approvalPolicy", {})
    if not _is_dict(raw_policy):
        return {}, blockers, warnings

    approval_policy = {
        "minimumApprovals": raw_policy.get("minimumApprovals"),
        "fourEyesAboveAmount": raw_policy.get("fourEyesAboveAmount"),
    }

    return approval_policy, blockers, warnings


def _check_upstream_signals(
    evidence_completeness: Any,
    compliance_gap_report: Any,
    permission_result: Any,
    approval_requirement: Any,
    approval_lifecycle: Any,
    decision_provenance: Any,
    auditor_export: Any,
) -> tuple[list[str], list[str], list[str]]:
    """Check upstream GrantLayer signals for blockers and missing inputs.

    Returns:
        (blockers, warnings, missing_inputs)
    """
    blockers: list[str] = []
    warnings: list[str] = []
    missing_inputs: list[str] = []

    # Evidence completeness
    if evidence_completeness is None:
        missing_inputs.append("evidence_completeness")
    else:
        if _is_dict(evidence_completeness) and evidence_completeness.get("complete") is not True:
            warnings.append("evidence_incomplete")

    # Compliance gap report
    if compliance_gap_report is None:
        missing_inputs.append("compliance_gap_report")
    elif _is_dict(compliance_gap_report):
        overall_status = compliance_gap_report.get("overallStatus")
        severity = compliance_gap_report.get("severity")
        blocking_gaps = compliance_gap_report.get("blockingGaps", [])
        if overall_status == "blocked":
            blockers.append("compliance_blocked")
        if severity in ("critical", "high"):
            blockers.append("compliance_gap_critical_or_high")
        if isinstance(blocking_gaps, list) and len(blocking_gaps) > 0:
            blockers.append("compliance_blocking_gaps")

    # Permission result
    if permission_result is None:
        missing_inputs.append("permission_result")
    elif _is_dict(permission_result):
        if permission_result.get("allowed") is False:
            blockers.append("permission_denied")

    # Approval requirement
    if approval_requirement is None:
        missing_inputs.append("approval_requirement")
    elif _is_dict(approval_requirement):
        if approval_requirement.get("decision") == "blocked":
            blockers.append("approval_requirement_blocked")

    # Approval lifecycle
    if approval_lifecycle is None:
        missing_inputs.append("approval_lifecycle")
    elif _is_dict(approval_lifecycle):
        if approval_lifecycle.get("status") == "blocked":
            blockers.append("approval_lifecycle_blocked")

    # Decision provenance
    if decision_provenance is None:
        missing_inputs.append("decision_provenance")
    elif _is_dict(decision_provenance):
        if decision_provenance.get("decisionStatus") == "blocked":
            blockers.append("decision_provenance_blocked")

    # Auditor export
    if auditor_export is None:
        missing_inputs.append("auditor_export")
    elif _is_dict(auditor_export):
        if auditor_export.get("exportStatus") == "blocked":
            blockers.append("auditor_export_blocked")

    return blockers, warnings, missing_inputs


# ──────────────────────────────────────────────
# Result builder
# ──────────────────────────────────────────────

def build_policy_requirement_result(
    policy_pack_id: str,
    policy_pack_version: str,
    subject_id: Optional[str],
    evaluation_status: str,
    readiness: str,
    required_evidence: list[str],
    missing_evidence: list[str],
    satisfied_evidence: list[str],
    exclusion_violations: list[str],
    deadline_status: str,
    amount_status: str,
    required_roles: list[str],
    approval_policy: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
    missing_inputs: list[str],
    created_at: Optional[str],
    policy_pack: Optional[dict[str, Any]] = None,
    subject: Optional[dict[str, Any]] = None,
    evidence_completeness: Any = None,
    compliance_gap_report: Any = None,
    permission_result: Any = None,
    approval_requirement: Any = None,
    approval_lifecycle: Any = None,
    decision_provenance: Any = None,
    auditor_export: Any = None,
    context: Any = None,
    include_details: bool = True,
) -> dict[str, Any]:
    """Build the standardised policy-requirement evaluation response dict."""
    result: dict[str, Any] = {
        "recordType": RECORD_TYPE,
        "recordVersion": RECORD_VERSION,
        "policyPackId": policy_pack_id,
        "policyPackVersion": policy_pack_version,
        "subjectId": subject_id,
        "evaluationStatus": evaluation_status,
        "readiness": readiness,
        "requiredEvidence": required_evidence,
        "missingEvidence": missing_evidence,
        "satisfiedEvidence": satisfied_evidence,
        "exclusionViolations": exclusion_violations,
        "deadlineStatus": deadline_status,
        "amountStatus": amount_status,
        "requiredRoles": required_roles,
        "approvalPolicy": approval_policy,
        "blockers": blockers,
        "warnings": warnings,
        "missingInputs": missing_inputs,
        "createdAt": created_at or _iso_now(),
    }

    if include_details:
        if policy_pack is not None:
            result["policyPack"] = policy_pack
        if subject is not None:
            result["subject"] = subject
        if evidence_completeness is not None:
            result["evidenceCompleteness"] = evidence_completeness
        if compliance_gap_report is not None:
            result["complianceGapReport"] = compliance_gap_report
        if permission_result is not None:
            result["permissionResult"] = permission_result
        if approval_requirement is not None:
            result["approvalRequirement"] = approval_requirement
        if approval_lifecycle is not None:
            result["approvalLifecycle"] = approval_lifecycle
        if decision_provenance is not None:
            result["decisionProvenance"] = decision_provenance
        if auditor_export is not None:
            result["auditorExport"] = auditor_export
        if context is not None:
            safe = _sanitize_context(context)
            if safe is not None:
                result["context"] = safe

    return result


# ──────────────────────────────────────────────
# Main evaluator
# ──────────────────────────────────────────────

def evaluate_policy_requirements(
    policy_pack: Any,
    subject: Any = None,
    evidence_completeness: Any = None,
    compliance_gap_report: Any = None,
    permission_result: Any = None,
    approval_requirement: Any = None,
    approval_lifecycle: Any = None,
    decision_provenance: Any = None,
    auditor_export: Any = None,
    context: Any = None,
    created_at: Any = None,
    include_details: bool = True,
) -> dict[str, Any]:
    """Evaluate a machine-readable grant/funding policy pack.

    Fail-closed: missing or malformed policy pack results in a blocked status.
    Pure / read-only — uses only the arguments passed in.  No DB access.
    """
    # ── Normalise policy pack ──
    normalized = normalize_policy_pack(policy_pack)

    # ── missing / malformed policy pack ──
    if policy_pack is None:
        return build_policy_requirement_result(
            policy_pack_id="",
            policy_pack_version="",
            subject_id=subject.get("subjectId") if _is_dict(subject) else None,
            evaluation_status="blocked",
            readiness="blocked",
            required_evidence=[],
            missing_evidence=[],
            satisfied_evidence=[],
            exclusion_violations=[],
            deadline_status="missing",
            amount_status="missing",
            required_roles=[],
            approval_policy={},
            blockers=["policy_pack_missing"],
            warnings=[],
            missing_inputs=["policy_pack"],
            created_at=created_at,
            include_details=include_details,
        )

    if not _is_dict(policy_pack) or normalized is None:
        return build_policy_requirement_result(
            policy_pack_id=str(policy_pack.get("policyPackId", "")) if _is_dict(policy_pack) else "",
            policy_pack_version=str(policy_pack.get("policyPackVersion", "")) if _is_dict(policy_pack) else "",
            subject_id=subject.get("subjectId") if _is_dict(subject) else None,
            evaluation_status="blocked",
            readiness="blocked",
            required_evidence=[],
            missing_evidence=[],
            satisfied_evidence=[],
            exclusion_violations=[],
            deadline_status="missing",
            amount_status="missing",
            required_roles=[],
            approval_policy={},
            blockers=["policy_pack_malformed"],
            warnings=[],
            missing_inputs=[],
            created_at=created_at,
            include_details=include_details,
        )

    # ── Initialise collections ──
    all_blockers: list[str] = []
    all_warnings: list[str] = []
    missing_inputs: list[str] = []

    # ── Subject check ──
    subject_id: Optional[str] = None
    if _is_dict(subject):
        subject_id = str(subject.get("subjectId", "")) if subject.get("subjectId") is not None else None
    else:
        missing_inputs.append("subject")

    # ── Evaluate policy pack rules ──
    required_evidence, missing_evidence, satisfied_evidence, ev_blockers, ev_warnings = evaluate_required_evidence(
        normalized, subject
    )
    all_blockers.extend(ev_blockers)
    all_warnings.extend(ev_warnings)

    exclusion_violations, ex_blockers, ex_warnings = evaluate_exclusions(
        normalized, subject
    )
    all_blockers.extend(ex_blockers)
    all_warnings.extend(ex_warnings)

    deadline_status, dl_blockers, dl_warnings = evaluate_deadlines(
        normalized, subject
    )
    all_blockers.extend(dl_blockers)
    all_warnings.extend(dl_warnings)

    amount_status, amt_blockers, amt_warnings = evaluate_amount_limits(
        normalized, subject
    )
    all_blockers.extend(amt_blockers)
    all_warnings.extend(amt_warnings)

    required_roles, role_blockers = evaluate_required_roles(normalized, subject)
    all_blockers.extend(role_blockers)

    approval_policy, appr_blockers, appr_warnings = evaluate_required_approvals(
        normalized, subject
    )
    all_blockers.extend(appr_blockers)
    all_warnings.extend(appr_warnings)

    # ── Evaluate upstream signals ──
    upstream_blockers, upstream_warnings, upstream_missing = _check_upstream_signals(
        evidence_completeness=evidence_completeness,
        compliance_gap_report=compliance_gap_report,
        permission_result=permission_result,
        approval_requirement=approval_requirement,
        approval_lifecycle=approval_lifecycle,
        decision_provenance=decision_provenance,
        auditor_export=auditor_export,
    )
    all_blockers.extend(upstream_blockers)
    all_warnings.extend(upstream_warnings)
    missing_inputs.extend(upstream_missing)

    # ── Deduplicate ──
    all_blockers = _dedupe(all_blockers)
    all_warnings = _dedupe(all_warnings)
    missing_inputs = _dedupe(missing_inputs)
    required_evidence = _dedupe(required_evidence)
    missing_evidence = _dedupe(missing_evidence)
    satisfied_evidence = _dedupe(satisfied_evidence)
    exclusion_violations = _dedupe(exclusion_violations)

    # ── Determine final status ──
    if all_blockers:
        evaluation_status = "blocked"
        readiness = "blocked"
    elif all_warnings:
        evaluation_status = "needs_review"
        readiness = "needs_review"
    else:
        evaluation_status = "passed"
        readiness = "ready"

    # ── Build response ──
    return build_policy_requirement_result(
        policy_pack_id=normalized["policyPackId"],
        policy_pack_version=normalized["policyPackVersion"],
        subject_id=subject_id,
        evaluation_status=evaluation_status,
        readiness=readiness,
        required_evidence=required_evidence,
        missing_evidence=missing_evidence,
        satisfied_evidence=satisfied_evidence,
        exclusion_violations=exclusion_violations,
        deadline_status=deadline_status,
        amount_status=amount_status,
        required_roles=required_roles,
        approval_policy=approval_policy,
        blockers=all_blockers,
        warnings=all_warnings,
        missing_inputs=missing_inputs,
        created_at=created_at,
        policy_pack=normalized if include_details else None,
        subject=subject if include_details else None,
        evidence_completeness=evidence_completeness if include_details else None,
        compliance_gap_report=compliance_gap_report if include_details else None,
        permission_result=permission_result if include_details else None,
        approval_requirement=approval_requirement if include_details else None,
        approval_lifecycle=approval_lifecycle if include_details else None,
        decision_provenance=decision_provenance if include_details else None,
        auditor_export=auditor_export if include_details else None,
        context=context if include_details else None,
        include_details=include_details,
    )
