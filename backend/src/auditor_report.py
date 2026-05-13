"""GrantLayer MVP — GL-037-C1 Minimal Auditor Report Builder.

Public builder for a structured auditor report per execution_id.
Read-only. No mutations. No secrets in response.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from .models import Grant, GrantRequest
from .provenance_summary import build_decision_provenance_summary
from .grants import get_grant
from .grant_requests import get_grant_request, get_grant_request_id_by_grant_id


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _grant_to_safe_dict(grant: Grant) -> dict[str, Any]:
    """Return a safe, serialisable dict for a Grant."""
    return {
        "id": grant.id,
        "subjectId": grant.subject_id,
        "role": grant.role,
        "action": grant.action,
        "resource": grant.resource,
        "validFrom": grant.valid_from,
        "validUntil": grant.valid_until,
        "createdBy": grant.created_by,
        "reason": grant.reason,
        "createdAt": grant.created_at,
        "revoked": grant.revoked,
        "revokedBy": grant.revoked_by,
        "revokedAt": grant.revoked_at,
        "revokedReason": grant.revoked_reason,
        "signingKeyId": grant.signing_key_id,
        "payloadHash": grant.payload_hash,
        "maxUses": grant.max_uses,
        "useCount": grant.use_count,
        "signaturePresent": grant.signature is not None,
    }


def _grant_request_to_safe_dict(request: GrantRequest) -> dict[str, Any]:
    """Return a safe, serialisable dict for a GrantRequest."""
    return {
        "id": request.id,
        "subjectId": request.subject_id,
        "role": request.role,
        "action": request.action,
        "resource": request.resource,
        "validFrom": request.valid_from,
        "validUntil": request.valid_until,
        "requestedBy": request.requested_by,
        "reason": request.reason,
        "status": request.status,
        "approvedBy": request.approved_by,
        "approvedAt": request.approved_at,
        "deniedBy": request.denied_by,
        "deniedAt": request.denied_at,
        "denialReason": request.denial_reason,
        "revokedBy": request.revoked_by,
        "revokedAt": request.revoked_at,
        "revokedReason": request.revoked_reason,
        "grantId": request.grant_id,
        "createdAt": request.created_at,
        "updatedAt": request.updated_at,
    }


def _compute_findings(
    summary: dict[str, Any],
    grant: Optional[Grant],
    request: Optional[GrantRequest],
) -> list[str]:
    """Derive auditor findings from the provenance summary and grant context."""
    findings: list[str] = []

    # Warnings from the provenance summary
    for warning in summary.get("warnings", []):
        if warning == "missing_evidence":
            findings.append("missing_evidence: no evidence bundle archived for this execution")
        elif warning == "unverified_evidence":
            findings.append("unverified_evidence: archived evidence has not been verified as valid")
        else:
            findings.append(f"warning: {warning}")

    execution = summary.get("execution")
    if execution is not None:
        result = execution.get("result")
        error_code = execution.get("errorCode")
        if result == "denied" and error_code:
            findings.append(f"execution_denied: {error_code}")
        elif result == "denied":
            findings.append("execution_denied: no error code provided")
        elif result == "failed":
            findings.append("execution_failed: internal error during action execution")

    if grant is not None:
        if grant.revoked:
            findings.append("grant_revoked: the associated grant has been revoked")
        # Check expiry using ISO string comparison (sufficient for this MVP)
        now = _iso_now()
        if grant.valid_until and grant.valid_until < now:
            findings.append("grant_expired: the associated grant has passed its validity window")
        if grant.max_uses is not None and grant.use_count >= grant.max_uses:
            findings.append("grant_usage_exhausted: the associated grant has reached its usage limit")
        if not grant.signature or not grant.payload_hash:
            findings.append("grant_unsigned: the associated grant lacks a signature or payload hash")

    if request is not None:
        if request.status == "denied":
            findings.append("grant_request_denied: the original grant request was denied")
        elif request.status == "revoked":
            findings.append("grant_request_revoked: the original grant request was revoked")

    return findings


def build_auditor_report(execution_id: str) -> Optional[dict[str, Any]]:
    """Build a minimal auditor report for a GrantExecution.

    Wraps the decision provenance summary with a formal report envelope,
    includes linked grant and grant-request context, and derives automated
    findings for auditor review.

    Args:
        execution_id: The execution to report on.

    Returns:
        A report dict, or None if the execution does not exist and has no
        linked provenance records or evidence archives.
    """
    summary = build_decision_provenance_summary(execution_id)
    if summary is None:
        return None

    grant_id = summary.get("grantId")
    grant: Optional[Grant] = None
    request: Optional[GrantRequest] = None

    if grant_id is not None:
        grant = get_grant(grant_id)
        request_id = get_grant_request_id_by_grant_id(grant_id)
        if request_id is not None:
            request = get_grant_request(request_id)

    findings = _compute_findings(summary, grant, request)
    conclusion = "clean" if not findings else "attention_required"

    report: dict[str, Any] = {
        "reportId": str(uuid.uuid4()),
        "reportType": "auditor_report",
        "scope": {
            "executionId": execution_id,
            "grantId": grant_id,
        },
        "generatedAt": _iso_now(),
        "findings": findings,
        "conclusion": conclusion,
        "provenanceSummary": summary,
    }

    if grant is not None:
        report["grant"] = _grant_to_safe_dict(grant)
    else:
        report["grant"] = None

    if request is not None:
        report["grantRequest"] = _grant_request_to_safe_dict(request)
    else:
        report["grantRequest"] = None

    return report
