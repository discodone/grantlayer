"""GrantLayer MVP — GL-025 / GL-026 Evidence bundle builder.

Read-only aggregation of the full grant lifecycle for a single
GrantExecution.  Produces a safe, flat JSON evidence bundle
with a deterministic integrity hash (GL-026).
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
    GL-026 evidenceHash because that hash is computed from the compact
    canonical form (see canonical_evidence_bundle).
    """
    return json.dumps(
        bundle,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        default=str,
    )


# ── GL-028: Offline verification helper ──────────────────────────────

VERIFY_ERROR_CODES = {"hash_mismatch", "invalid_artifact", "unsupported_format"}


def verify_evidence_export_artifact(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate an exported evidence bundle dict offline.

    Recomputes the GL-026 evidenceHash from canonical bundle content and
    compares it to the embedded hash.  Returns a structured result dict.

    Validation order:
      1. canonicalVersion exists and == "gl-evidence-v1"
      2. hashAlgorithm exists and == "sha256"
      3. evidenceHash exists, is exactly 64-char lowercase hex
      4. Rebuild canonical input (same rules as GL-026)
      5. Recompute SHA-256
      6. Compare to evidenceHash
    """
    # 1. canonicalVersion
    canonical_version = bundle.get("canonicalVersion")
    if canonical_version is None:
        return {
            "ok": False,
            "error": "invalid_artifact",
            "reason": "missing canonicalVersion",
        }
    if canonical_version != "gl-evidence-v1":
        return {
            "ok": False,
            "error": "unsupported_format",
            "reason": f"unsupported canonicalVersion: {canonical_version}",
        }

    # 2. hashAlgorithm
    hash_algorithm = bundle.get("hashAlgorithm")
    if hash_algorithm is None:
        return {
            "ok": False,
            "error": "invalid_artifact",
            "reason": "missing hashAlgorithm",
        }
    if hash_algorithm != "sha256":
        return {
            "ok": False,
            "error": "unsupported_format",
            "reason": f"unsupported hashAlgorithm: {hash_algorithm}",
        }

    # 3. evidenceHash
    evidence_hash = bundle.get("evidenceHash")
    if evidence_hash is None:
        return {
            "ok": False,
            "error": "invalid_artifact",
            "reason": "missing evidenceHash",
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
        }

    # 4–6. Rebuild canonical input, recompute, compare
    recomputed = compute_evidence_hash(bundle)
    if recomputed != evidence_hash:
        return {
            "ok": False,
            "error": "hash_mismatch",
            "reason": "computed hash does not match evidenceHash",
        }

    return {
        "ok": True,
        "evidenceId": bundle.get("evidenceId"),
        "canonicalVersion": canonical_version,
        "hashAlgorithm": hash_algorithm,
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

    # GL-026: sort audit trail deterministically by timestamp then id
    audit_trail.sort(key=lambda ev: (ev.get("timestamp") or "", ev.get("id") or ""))
    bundle["auditTrail"] = audit_trail

    # GL-026: compute deterministic evidence hash (before exposing hash metadata)
    bundle["evidenceHash"] = compute_evidence_hash(bundle)
    bundle["canonicalVersion"] = "gl-evidence-v1"
    bundle["hashAlgorithm"] = "sha256"

    return bundle
