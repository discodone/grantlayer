"""Approval Rule Evaluator Builder (GL-040-A1).

Fail-closed evaluator that determines whether a proposed grant-related action
requires approval, how many approvals, and which roles, based on risk,
compliance, evidence, permission, and amount signals.

Pure / read-only.  No DB access.  No secrets exposed.
"""

from __future__ import annotations

from typing import Any, Optional


# ──────────────────────────────────────────────
# Role catalogues
# ──────────────────────────────────────────────

_ONE_APPROVAL_ROLES = ["grant_admin"]
_FOUR_EYES_ROLES = ["grant_admin", "owner"]


# ──────────────────────────────────────────────
# Normalization helpers
# ──────────────────────────────────────────────

def normalize_risk_level(risk_level: Any) -> Optional[str]:
    """Return a lower-case risk level string, or None if empty."""
    if risk_level is None:
        return None
    if not isinstance(risk_level, str):
        return "unknown"
    normalized = risk_level.strip().lower()
    if normalized in ("low", "medium", "high"):
        return normalized
    if normalized == "":
        return None
    return "unknown"


def normalize_amount(amount: Any) -> Optional[float]:
    """Return a float amount, or None if missing / malformed."""
    if amount is None:
        return None
    if isinstance(amount, (int, float)):
        return float(amount)
    try:
        return float(amount)
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────────
# Signal extractors
# ──────────────────────────────────────────────

def _extract_compliance_signals(compliance_report: Optional[dict]) -> dict:
    """Extract overallStatus and severity from a compliance report dict."""
    if not isinstance(compliance_report, dict):
        return {"overall_status": None, "severity": None}
    return {
        "overall_status": compliance_report.get("overallStatus")
        if isinstance(compliance_report.get("overallStatus"), str)
        else None,
        "severity": compliance_report.get("severity")
        if isinstance(compliance_report.get("severity"), str)
        else None,
    }


def _extract_evidence_signals(evidence_completeness: Optional[dict]) -> dict:
    """Extract evidence status signals."""
    if not isinstance(evidence_completeness, dict):
        return {"status": "missing", "complete": None, "invalid": None}

    # Determine if evidence is explicitly marked invalid
    invalid = evidence_completeness.get("invalid")
    if isinstance(invalid, bool) and invalid:
        return {"status": "invalid", "complete": False, "invalid": True}

    # Fallback: look for errors/warnings that imply invalidity
    errors = evidence_completeness.get("errors", [])
    if isinstance(errors, list) and len(errors) > 0:
        return {"status": "invalid", "complete": False, "invalid": True}

    # Determine completeness
    complete = evidence_completeness.get("complete")
    if isinstance(complete, bool):
        if complete:
            return {"status": "complete", "complete": True, "invalid": False}
        return {"status": "incomplete", "complete": False, "invalid": False}

    return {"status": "missing", "complete": None, "invalid": None}


def _extract_permission_signals(permission_result: Optional[dict]) -> dict:
    """Extract permission signals."""
    if not isinstance(permission_result, dict):
        return {"present": False, "allowed": None}
    allowed = permission_result.get("allowed")
    if isinstance(allowed, bool):
        return {"present": True, "allowed": allowed}
    return {"present": False, "allowed": None}


def _extract_policy_signals(policy_flags: Optional[list]) -> dict:
    """Extract known / unknown policy flags."""
    requires_approval = False
    requires_four_eyes = False
    unknown_flags: list[str] = []

    if not isinstance(policy_flags, list):
        if policy_flags is not None:
            unknown_flags.append(str(policy_flags))
        return {
            "requires_approval": False,
            "requires_four_eyes": False,
            "unknown_flags": unknown_flags,
        }

    for flag in policy_flags:
        flag_str = str(flag).strip().lower() if flag is not None else ""
        if flag_str == "requires_approval":
            requires_approval = True
        elif flag_str == "requires_four_eyes":
            requires_four_eyes = True
        elif flag_str:
            unknown_flags.append(str(flag))

    return {
        "requires_approval": requires_approval,
        "requires_four_eyes": requires_four_eyes,
        "unknown_flags": unknown_flags,
    }


# ──────────────────────────────────────────────
# Result builder
# ──────────────────────────────────────────────

def build_approval_requirement_result(
    action: Any,
    actor_id: Optional[str],
    approval_required: bool,
    required_approvals: int,
    required_roles: list[str],
    decision: str,
    reason: str,
    blockers: list[str],
    warnings: list[str],
    risk_level: Optional[str],
    amount: Optional[float],
    currency: Optional[str],
    checks: Optional[dict] = None,
    inputs: Optional[dict] = None,
) -> dict:
    """Build the standardized approval-requirement response dict."""
    result: dict[str, Any] = {
        "action": action if action is not None else None,
        "actorId": actor_id,
        "approvalRequired": approval_required,
        "requiredApprovals": required_approvals,
        "requiredRoles": required_roles,
        "decision": decision,
        "reason": reason,
        "blockers": blockers,
        "warnings": warnings,
        "riskLevel": risk_level,
        "amount": amount,
        "currency": currency,
    }
    if checks is not None:
        result["checks"] = checks
    if inputs is not None:
        result["inputs"] = inputs
    return result


# ──────────────────────────────────────────────
# Main evaluator
# ──────────────────────────────────────────────

def evaluate_approval_requirements(
    action: Any,
    actor_id: Optional[str] = None,
    amount: Optional[Any] = None,
    currency: Optional[str] = None,
    risk_level: Optional[Any] = None,
    compliance_report: Optional[dict] = None,
    evidence_completeness: Optional[dict] = None,
    permission_result: Optional[dict] = None,
    policy_flags: Optional[list] = None,
    context: Optional[Any] = None,
    include_details: bool = True,
) -> dict:
    """Evaluate whether a proposed action requires approval.

    * deny-by-default / fail-closed
    * no database access
    * no secrets exposed
    * *context* is accepted but never required for the decision
    """
    warnings: list[str] = []
    blockers: list[str] = []

    # ── Normalise inputs ──
    normalized_risk = normalize_risk_level(risk_level)
    normalized_amount = normalize_amount(amount)

    compliance = _extract_compliance_signals(compliance_report)
    evidence = _extract_evidence_signals(evidence_completeness)
    permission = _extract_permission_signals(permission_result)
    policy = _extract_policy_signals(policy_flags)

    # Track decision tiers.
    blocked = False
    four_eyes = False
    one_approval = False

    # ── 1. Missing / empty action ──
    if action is None or (isinstance(action, str) and action.strip() == ""):
        blocked = True
        blockers.append("action_missing_or_empty")

    # ── 2. Permission denied ──
    if permission["present"] and permission["allowed"] is False:
        blocked = True
        blockers.append("permission_denied")

    # ── 3. Compliance blocked ──
    if compliance["overall_status"] is not None:
        if compliance["overall_status"].lower() == "blocked":
            blocked = True
            blockers.append("compliance_blocked")

    # ── 4. Invalid evidence ──
    if evidence["status"] == "invalid":
        blocked = True
        blockers.append("evidence_invalid")

    # ── 5. Malformed amount ──
    if amount is not None and normalized_amount is None:
        warnings.append("amount_malformed")
        one_approval = True

    # ── 6. Unknown risk level ──
    if normalized_risk == "unknown":
        warnings.append("unknown_risk_level")
        one_approval = True

    # ── 7. Unknown policy flags ──
    for unknown_flag in policy["unknown_flags"]:
        warnings.append(f"unknown_policy_flag:{unknown_flag}")

    # ── 8. Risk-based requirements ──
    if normalized_risk == "high":
        four_eyes = True
    elif normalized_risk == "medium":
        one_approval = True
    elif normalized_risk == "low":
        pass  # baseline: no approval required unless other signals trigger it

    # ── 9. Amount-based requirements ──
    if normalized_amount is not None:
        if normalized_amount >= 100_000:
            four_eyes = True
        elif normalized_amount >= 10_000:
            one_approval = True

    # ── 10. Compliance severity critical ──
    if not blocked and compliance["severity"] is not None:
        if compliance["severity"].lower() == "critical":
            four_eyes = True

    # ── 11. Policy flags ──
    if policy["requires_four_eyes"]:
        four_eyes = True
    if policy["requires_approval"]:
        one_approval = True

    # ── 12. Missing evidence ──
    if evidence["status"] == "missing" or evidence["status"] == "incomplete":
        one_approval = True

    # ── 13. Missing permission result ──
    if not permission["present"]:
        if not blocked:
            one_approval = True
            warnings.append("missing_permission_result")

    # ── Compute final decision ──
    if blocked:
        decision = "blocked"
        approval_required = False
        required_approvals = 0
        required_roles: list[str] = []
        reason = "blocked_by_policy"
    elif four_eyes:
        decision = "four_eyes_required"
        approval_required = True
        required_approvals = 2
        required_roles = _FOUR_EYES_ROLES.copy()
        reason = "four_eyes_approval_required"
    elif one_approval:
        decision = "approval_required"
        approval_required = True
        required_approvals = 1
        required_roles = _ONE_APPROVAL_ROLES.copy()
        reason = "approval_required"
    else:
        decision = "no_approval_required"
        approval_required = False
        required_approvals = 0
        required_roles = []
        reason = "no_approval_required"

    # ── Build checks / inputs if requested ──
    checks: Optional[dict] = None
    inputs: Optional[dict] = None
    if include_details:
        checks = {
            "actionChecked": True,
            "riskLevelChecked": normalized_risk is not None,
            "riskLevelValue": normalized_risk,
            "amountChecked": amount is not None,
            "amountValue": normalized_amount,
            "complianceChecked": compliance_report is not None,
            "complianceOverallStatus": compliance["overall_status"],
            "complianceSeverity": compliance["severity"],
            "evidenceChecked": evidence_completeness is not None,
            "evidenceStatus": evidence["status"],
            "permissionChecked": permission_result is not None,
            "permissionAllowed": permission["allowed"],
            "policyFlagsChecked": policy_flags is not None,
        }
        inputs = {
            "action": action if action is not None else None,
            "actorId": actor_id,
            "riskLevel": normalized_risk,
            "amount": normalized_amount,
            "currency": currency,
            "complianceOverallStatus": compliance["overall_status"],
            "complianceSeverity": compliance["severity"],
            "evidenceStatus": evidence["status"],
            "permissionAllowed": permission["allowed"],
            "policyFlags": policy_flags if policy_flags is not None else None,
        }

    return build_approval_requirement_result(
        action=action,
        actor_id=actor_id,
        approval_required=approval_required,
        required_approvals=required_approvals,
        required_roles=required_roles,
        decision=decision,
        reason=reason,
        blockers=blockers,
        warnings=warnings,
        risk_level=normalized_risk,
        amount=normalized_amount,
        currency=currency,
        checks=checks,
        inputs=inputs,
    )
