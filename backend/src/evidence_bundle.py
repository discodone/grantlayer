"""GrantLayer MVP — Evidence bundle builder.

Read-only aggregation of the full grant lifecycle for a single
GrantExecution.  Produces a safe, flat JSON evidence bundle
with a deterministic integrity hash.
No mutation, no new tables, no migrations.
"""

from typing import Optional, Any
import datetime
import hashlib
import json

from . import audit_log
from . import grant_executions as execs
from . import grant_requests as greps
from . import grants
from .models import GrantExecution, Grant, GrantRequest, AuditEvent


SAFE_AUDIT_FIELDS = [
    "id",
    "timestamp",
    "subject_id",
    "role",
    "action",
    "resource",
    "approved",
    "reason",
    "matched_grant_id",
    "challenge_id",
    "challenge_present",
    "challenge_result",
    "grant_signature_result",
]


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _audit_to_safe_dict(event: AuditEvent) -> dict[str, Any]:
    """Return a safe, serialisable dict for an audit event."""
    d: dict[str, Any] = {}
    for key in SAFE_AUDIT_FIELDS:
        value = getattr(event, key, None)
        if isinstance(value, bool):
            d[key] = value
        else:
            d[key] = value
    # NEVER include token hashes, env values, or internal secrets.
    return d


def _sort_keys_deep(obj: Any) -> Any:
    """Recursively sort dict keys for deterministic JSON."""
    if isinstance(obj, dict):
        return {k: _sort_keys_deep(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_keys_deep(v) for v in obj]
    return obj


def canonical_evidence_bundle(bundle: dict[str, Any]) -> str:
    """Return a deterministic, canonical JSON string for the bundle.

    Excludes mutable/generated fields (generatedAt, evidenceHash,
    canonicalVersion, hashAlgorithm) so the hash is stable across rebuilds.
    """
    scrubbed = dict(bundle)
    scrubbed.pop("generatedAt", None)
    scrubbed.pop("evidenceHash", None)
    scrubbed.pop("canonicalVersion", None)
    scrubbed.pop("hashAlgorithm", None)
    canonical = _sort_keys_deep(scrubbed)
    return json.dumps(canonical, separators=(",", ":"), ensure_ascii=False, default=str)


def compute_evidence_hash(bundle: dict[str, Any]) -> str:
    """Compute the SHA-256 evidence hash for a bundle dict.

    Returns a 64-character lowercase hex string.
    """
    canonical = canonical_evidence_bundle(bundle)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def export_bundle_json(bundle: dict[str, Any]) -> str:
    """Return a deterministic, pretty-printed JSON string for export.

    Uses sorted keys and 2-space indentation so the artifact is human-readable
    and diff-friendly.  The pretty-print whitespace does *not* affect the
    evidenceHash because that hash is computed from the compact
    canonical form (see canonical_evidence_bundle).
    """
    return json.dumps(
        bundle,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        default=str,
    )


# ── Offline verification helper ──────────────────────────────

VERIFY_ERROR_CODES = {"hash_mismatch", "invalid_artifact", "unsupported_format", "parse_error"}


def verify_evidence_export_artifact(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate an exported evidence bundle dict offline.

    Recomputes the evidenceHash from canonical bundle content and
    compares it to the embedded hash.  Returns a structured result dict.

    Validation order:
      1. canonicalVersion exists and == "gl-evidence-v1"
      2. hashAlgorithm exists and == "sha256"
      3. evidenceHash exists, is exactly 64-char lowercase hex
      4. Rebuild canonical input (same rules as )
      5. Recompute SHA-256
      6. Compare to evidenceHash
    """
    evidence_id = bundle.get("evidenceId")

    # 1. canonicalVersion
    canonical_version = bundle.get("canonicalVersion")
    if canonical_version is None:
        return {
            "ok": False,
            "error": "invalid_artifact",
            "reason": "missing canonicalVersion",
            "evidenceId": evidence_id,
        }
    if canonical_version != "gl-evidence-v1":
        return {
            "ok": False,
            "error": "unsupported_format",
            "reason": f"unsupported canonicalVersion: {canonical_version}",
            "evidenceId": evidence_id,
        }

    # 2. hashAlgorithm
    hash_algorithm = bundle.get("hashAlgorithm")
    if hash_algorithm is None:
        return {
            "ok": False,
            "error": "invalid_artifact",
            "reason": "missing hashAlgorithm",
            "evidenceId": evidence_id,
        }
    if hash_algorithm != "sha256":
        return {
            "ok": False,
            "error": "unsupported_format",
            "reason": f"unsupported hashAlgorithm: {hash_algorithm}",
            "evidenceId": evidence_id,
        }

    # 3. evidenceHash
    evidence_hash = bundle.get("evidenceHash")
    if evidence_hash is None:
        return {
            "ok": False,
            "error": "invalid_artifact",
            "reason": "missing evidenceHash",
            "evidenceId": evidence_id,
        }
    if (
        not isinstance(evidence_hash, str)
        or len(evidence_hash) != 64
        or not all(c in "0123456789abcdef" for c in evidence_hash)
    ):
        return {
            "ok": False,
            "error": "invalid_artifact",
            "reason": "evidenceHash must be 64-character lowercase hex",
            "evidenceId": evidence_id,
        }

    # 4–6. Rebuild canonical input, recompute, compare
    recomputed = compute_evidence_hash(bundle)
    if recomputed != evidence_hash:
        return {
            "ok": False,
            "error": "hash_mismatch",
            "reason": "computed hash does not match evidenceHash",
            "evidenceId": evidence_id,
        }

    return {
        "ok": True,
        "evidenceId": evidence_id,
        "evidenceHash": evidence_hash,
        "canonicalVersion": canonical_version,
        "hashAlgorithm": hash_algorithm,
        "verifiedAt": _iso_now(),
    }


# ── Evidence completeness check ─────────────────────────────

def check_evidence_completeness(bundle: dict[str, Any]) -> dict[str, Any]:
    """Check structural completeness of an evidence bundle."""
    checks: dict[str, Any] = {}
    warnings: list[str] = []
    errors: list[str] = []

    execution = bundle.get("execution")
    checks["executionPresent"] = execution is not None
    if not checks["executionPresent"]:
        errors.append("missing execution section")

    grant_id = bundle.get("grantId")
    grant = bundle.get("grant")
    checks["grantLinkage"] = (grant_id is None) or (grant is not None)
    if grant_id is not None and grant is None:
        errors.append("grantId set but grant section missing")

    grant_request_id = bundle.get("grantRequestId")
    request = bundle.get("request")
    approval = bundle.get("approval")
    if grant_request_id is not None:
        if request is not None and approval is not None:
            checks["grantRequestLinkage"] = "present"
        else:
            checks["grantRequestLinkage"] = "missing_required"
            errors.append("grantRequestId set but request or approval section missing")
    else:
        if request is not None or approval is not None:
            warnings.append("request or approval present without grantRequestId")
        checks["grantRequestLinkage"] = "missing_optional"

    audit_event_id = execution.get("auditEventId") if execution else None
    audit_trail = bundle.get("auditTrail")
    checks["auditEventLinkage"] = audit_event_id is not None or (
        isinstance(audit_trail, list) and len(audit_trail) > 0
    )
    checks["auditTrailPresent"] = isinstance(audit_trail, list) and len(audit_trail) > 0
    if not checks["auditTrailPresent"]:
        warnings.append("auditTrail is empty")

    if isinstance(audit_trail, list) and len(audit_trail) > 0:
        keys = [(ev.get("timestamp") or "", ev.get("id") or "") for ev in audit_trail]
        if keys != sorted(keys):
            warnings.append("auditTrail is not chronologically sorted")
        if len(keys) != len({k for k in keys}):
            errors.append("auditTrail contains duplicate events")

    usage_limits = bundle.get("usageLimits")
    checks["usageLimitsConsistent"] = True
    if isinstance(usage_limits, dict):
        error_code = execution.get("errorCode") if execution else None
        if error_code == "grant_usage_exhausted":
            if not usage_limits.get("affectedOutcome"):
                checks["usageLimitsConsistent"] = False
                errors.append(
                    "errorCode is grant_usage_exhausted but usageLimits.affectedOutcome is false"
                )
        else:
            if usage_limits.get("affectedOutcome") and error_code != "grant_usage_exhausted":
                checks["usageLimitsConsistent"] = False
                errors.append(
                    "usageLimits.affectedOutcome is true but errorCode is not grant_usage_exhausted"
                )
    else:
        if execution and execution.get("errorCode") == "grant_usage_exhausted":
            checks["usageLimitsConsistent"] = False
            errors.append("errorCode is grant_usage_exhausted but usageLimits section missing")

    checks["outcomeConsistent"] = True
    if execution:
        result = execution.get("result")
        error_code = execution.get("errorCode")
        if result == "succeeded" and error_code is not None:
            checks["outcomeConsistent"] = False
            errors.append("result is succeeded but errorCode is not null")
        if result == "denied" and error_code is None:
            checks["outcomeConsistent"] = False
            errors.append("result is denied but errorCode is null")

    complete = len(errors) == 0 and checks.get("executionPresent", False)

    return {
        "complete": complete,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }


# ── Denial / error-code consistency check ───────────────────

KNOWN_DENIAL_CODES = {
    "no_grant",
    "grant_expired",
    "grant_revoked",
    "grant_usage_exhausted",
    "invalid_challenge",
    "challenge_required_missing",
    "grant_signature_missing",
    "grant_signature_invalid",
    "grant_payload_hash_mismatch",
    "grant_request_denied",
    "policy_mismatch",
    "role_mismatch",
    "internal_error",
}


def check_denial_code_consistency(bundle: dict[str, Any]) -> dict[str, Any]:
    """Check that result and errorCode in the execution block are mutually consistent."""
    execution = bundle.get("execution") or {}
    result = execution.get("result")
    error_code = execution.get("errorCode")

    checks: dict[str, Any] = {}
    warnings: list[str] = []
    errors: list[str] = []

    # errorCode catalog membership
    if error_code is not None:
        checks["errorCodeCatalogMembership"] = error_code in KNOWN_DENIAL_CODES
        if not checks["errorCodeCatalogMembership"]:
            warnings.append(f"unknown error code: {error_code}")
    else:
        checks["errorCodeCatalogMembership"] = True

    # result matches errorCode
    if result == "succeeded":
        checks["resultMatchesErrorCode"] = error_code is None
        if not checks["resultMatchesErrorCode"]:
            errors.append("result is succeeded but errorCode is present")
    elif result == "denied":
        checks["resultMatchesErrorCode"] = error_code is not None
        if not checks["resultMatchesErrorCode"]:
            errors.append("result is denied but errorCode is missing")
    elif result == "failed":
        checks["resultMatchesErrorCode"] = True
        warnings.append("result is failed — manual review recommended")
    else:
        checks["resultMatchesErrorCode"] = False
        errors.append(f"unexpected result value: {result}")

    # outcome matches bundle data
    checks["outcomeMatchesBundleData"] = True
    if result == "succeeded" and bundle.get("grantId") and not bundle.get("grant"):
        checks["outcomeMatchesBundleData"] = False
        errors.append("result succeeded but grant missing despite grantId")
    if result == "denied":
        if error_code == "grant_request_denied" and bundle.get("grant") is not None:
            checks["outcomeMatchesBundleData"] = False
            errors.append("result denied with grant_request_denied but grant section present")
        if error_code == "no_grant" and bundle.get("grant") is not None:
            checks["outcomeMatchesBundleData"] = False
            errors.append("result denied with no_grant but grant section present")
    if error_code == "grant_usage_exhausted":
        ul = bundle.get("usageLimits")
        if not isinstance(ul, dict) or not ul.get("affectedOutcome"):
            checks["outcomeMatchesBundleData"] = False
            errors.append("errorCode grant_usage_exhausted but usageLimits.affectedOutcome is false")

    denial_reason = ""
    if result == "denied" and error_code:
        _denial_reasons = {
            "no_grant": "no matching grant found",
            "grant_expired": "grant has expired",
            "grant_revoked": "grant has been revoked",
            "grant_usage_exhausted": "grant usage limit reached",
            "invalid_challenge": "challenge invalid or expired",
            "challenge_required_missing": "required challenge missing",
            "grant_signature_missing": "grant signature missing",
            "grant_signature_invalid": "grant signature invalid",
            "grant_payload_hash_mismatch": "grant payload hash mismatch",
            "grant_request_denied": "grant request was denied",
            "policy_mismatch": "policy mismatch",
            "role_mismatch": "role mismatch",
            "internal_error": "internal handler error",
        }
        denial_reason = _denial_reasons.get(error_code, f"denied: {error_code}")

    consistent = len(errors) == 0 and checks.get("resultMatchesErrorCode", False)

    return {
        "consistent": consistent,
        "result": result,
        "errorCode": error_code,
        "denialReason": denial_reason,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }


def build_evidence_bundle(execution_id: str) -> Optional[dict[str, Any]]:
    """Build a safe evidence bundle for a GrantExecution.

    Returns None if the execution does not exist.
    """
    execution = execs.get_grant_execution(execution_id)
    if execution is None:
        return None

    # ── Linked entities ───────────────────────────────
    grant: Optional[Grant] = None
    if execution.grant_id:
        grant = grants.get_grant(execution.grant_id)

    grant_request: Optional[GrantRequest] = None
    if execution.grant_request_id:
        grant_request = greps.get_grant_request(execution.grant_request_id)
    # Fallback: resolve via grant linkage if execution didn't capture it.
    if grant_request is None and grant is not None:
        req_id = greps.get_grant_request_id_by_grant_id(grant.id)
        if req_id:
            grant_request = greps.get_grant_request(req_id)

    audit_event: Optional[AuditEvent] = None
    if execution.audit_event_id:
        audit_event = audit_log.get_event(execution.audit_event_id)

    # Related audit events by grant (safe, bounded)
    related_events: list[dict[str, Any]] = []
    if execution.grant_id:
        for ev in audit_log.list_events_by_grant(execution.grant_id, limit=20):
            related_events.append(_audit_to_safe_dict(ev))

    # ── Build safe response ───────────────────────────
    now = _iso_now()

    bundle: dict[str, Any] = {
        "evidenceId": execution.id,
        "generatedAt": now,
        "executionId": execution.id,
        "grantId": execution.grant_id,
        "grantRequestId": execution.grant_request_id,
    }

    # Request section (from GrantRequest if available)
    request_section: Optional[dict[str, Any]] = None
    approval_section: Optional[dict[str, Any]] = None
    if grant_request is not None:
        request_section = {
            "id": grant_request.id,
            "requestedBy": grant_request.requested_by,
            "requestedAt": grant_request.created_at,
            "reason": grant_request.reason,
        }
        if grant_request.status == "approved" and grant_request.approved_by:
            approval_section = {
                "approvedBy": grant_request.approved_by,
                "approvedAt": grant_request.approved_at,
            }
        elif grant_request.status == "denied" and grant_request.denied_by:
            approval_section = {
                "deniedBy": grant_request.denied_by,
                "deniedAt": grant_request.denied_at,
                "denialReason": grant_request.denial_reason,
            }

    bundle["request"] = request_section
    bundle["approval"] = approval_section

    # Grant section
    grant_section: Optional[dict[str, Any]] = None
    if grant is not None:
        grant_section = {
            "id": grant.id,
            "subjectId": grant.subject_id,
            "role": grant.role,
            "action": grant.action,
            "resource": grant.resource,
            "validFrom": grant.valid_from,
            "validUntil": grant.valid_until,
            "createdBy": grant.created_by,
            "createdAt": grant.created_at,
            "signingKeyId": grant.signing_key_id,
            "payloadHash": grant.payload_hash,
            "maxUses": grant.max_uses,
            "useCount": grant.use_count,
        }
        # Include signature result only if we have execution/audit data
        if execution.challenge_result is not None:
            # The execution already captured whatever sig result it had.
            # Prefer the audit event's grant_signature_result.
            sig_result = (
                audit_event.grant_signature_result
                if audit_event is not None
                else "not_checked"
            )
            grant_section["grantSignatureResult"] = sig_result

    bundle["grant"] = grant_section

    # Execution section
    bundle["execution"] = {
        "action": execution.action,
        "resource": execution.resource,
        "operatorId": execution.operator_id,
        "challengeId": execution.challenge_id,
        "challengeResult": execution.challenge_result,
        "policyResult": execution.policy_result,
        "result": execution.result,
        "errorCode": execution.error_code,
        "executedAt": execution.executed_at,
        "auditEventId": execution.audit_event_id,
    }

    # Usage limits slice
    usage_limits: dict[str, Any] = {"affectedOutcome": False}
    if grant is not None and grant.max_uses is not None:
        usage_limits["maxUses"] = grant.max_uses
        usage_limits["useCount"] = grant.use_count
        if execution.error_code == "grant_usage_exhausted":
            usage_limits["affectedOutcome"] = True
            usage_limits["reason"] = "grant_usage_exhausted"
    bundle["usageLimits"] = usage_limits

    # Audit trail (always include at least the primary event)
    audit_trail: list[dict[str, Any]] = []
    if audit_event is not None:
        audit_trail.append(_audit_to_safe_dict(audit_event))
    # Append related events that are not the primary event
    primary_event_id = audit_event.id if audit_event else None
    for ev_dict in related_events:
        if ev_dict.get("id") != primary_event_id:
            audit_trail.append(ev_dict)

    # sort audit trail deterministically by timestamp then id
    audit_trail.sort(key=lambda ev: (ev.get("timestamp") or "", ev.get("id") or ""))
    bundle["auditTrail"] = audit_trail

    # compute deterministic evidence hash (before exposing hash metadata)
    bundle["evidenceHash"] = compute_evidence_hash(bundle)
    bundle["canonicalVersion"] = "gl-evidence-v1"
    bundle["hashAlgorithm"] = "sha256"

    return bundle
