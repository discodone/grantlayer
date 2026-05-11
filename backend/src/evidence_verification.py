"""GrantLayer MVP — GL-036-R2 Evidence Verification Core."""

from typing import Any
import datetime

from . import evidence_persistence
from .evidence_bundle import check_evidence_completeness, check_denial_code_consistency


VerificationStatus = {"valid", "invalid", "missing_data", "unsupported_version"}


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def verify_execution(execution_id: str) -> dict[str, Any]:
    """Verify persisted evidence for a GrantExecution.

    Loads the persisted bundle from evidence_archives, recomputes the
    SHA-256 evidenceHash, validates structural completeness and denial-code
    consistency, then records the result in last_verified_at and
    last_verification_status.

    Returns a structured result dict:
      {
        "status": "valid" | "invalid" | "missing_data" | "unsupported_version",
        "executionId": str,
        "verifiedAt": str,
        "reason": str,
      }
    """
    record = evidence_persistence.get_bundle_by_execution(execution_id)
    if record is None:
        return {
            "status": "missing_data",
            "executionId": execution_id,
            "verifiedAt": _iso_now(),
            "reason": "No persisted evidence bundle found for execution.",
        }

    import json
    bundle_dict = json.loads(record.bundle_json)

    canonical_version = bundle_dict.get("canonicalVersion")
    hash_algorithm = bundle_dict.get("hashAlgorithm")
    evidence_hash = bundle_dict.get("evidenceHash")

    # Check supported format
    if canonical_version != "gl-evidence-v1" or hash_algorithm != "sha256":
        status = "unsupported_version"
        reason = (
            f"Unsupported evidence format: canonicalVersion={canonical_version}, "
            f"hashAlgorithm={hash_algorithm}."
        )
        now = _iso_now()
        evidence_persistence.update_verification_status(record.id, status)
        return {
            "status": status,
            "executionId": execution_id,
            "verifiedAt": now,
            "reason": reason,
        }

    # Check hash presence and format
    if not evidence_hash or not isinstance(evidence_hash, str) or len(evidence_hash) != 64:
        status = "invalid"
        reason = "evidenceHash missing or not a 64-character lowercase hex string."
        now = _iso_now()
        evidence_persistence.update_verification_status(record.id, status)
        return {
            "status": status,
            "executionId": execution_id,
            "verifiedAt": now,
            "reason": reason,
        }

    # Recompute and compare hash
    from .evidence_bundle import compute_evidence_hash
    recomputed = compute_evidence_hash(bundle_dict)
    if recomputed != evidence_hash:
        status = "invalid"
        reason = "Computed hash does not match stored evidenceHash."
        now = _iso_now()
        evidence_persistence.update_verification_status(record.id, status)
        return {
            "status": status,
            "executionId": execution_id,
            "verifiedAt": now,
            "reason": reason,
        }

    # Structural and consistency checks
    completeness = check_evidence_completeness(bundle_dict)
    consistency = check_denial_code_consistency(bundle_dict)

    if not completeness["complete"] or not consistency["consistent"]:
        status = "invalid"
        parts = []
        if not completeness["complete"]:
            parts.append("Structural completeness check failed.")
        if not consistency["consistent"]:
            parts.append("Denial-code consistency check failed.")
        reason = " ".join(parts)
        now = _iso_now()
        evidence_persistence.update_verification_status(record.id, status)
        return {
            "status": status,
            "executionId": execution_id,
            "verifiedAt": now,
            "reason": reason,
        }

    # All checks passed
    status = "valid"
    reason = "Evidence bundle is valid, hash matches, and structure is consistent."
    now = _iso_now()
    evidence_persistence.update_verification_status(record.id, status)
    return {
        "status": status,
        "executionId": execution_id,
        "verifiedAt": now,
        "reason": reason,
    }
