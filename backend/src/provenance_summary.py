"""GrantLayer MVP — Decision Provenance Summary Builder.

Public builder for a structured decision provenance summary per execution_id.
Read-only. No mutations. No secrets in response.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from .models import GrantExecution, ProvenanceEvent, EvidenceBundle
from . import provenance as prov
from . import grant_executions as execs
from . import evidence_persistence as evp


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _event_to_safe_dict(event: ProvenanceEvent) -> dict[str, Any]:
    """Return a safe, serialisable dict for a provenance event."""
    return {
        "eventType": event.event_type,
        "actorType": event.actor_type,
        "actorId": event.actor_id,
        "action": event.action,
        "occurredAt": event.occurred_at,
        "resourceType": event.resource_type,
        "resourceId": event.resource_id,
        "evidenceHash": event.evidence_hash,
        "verificationStatus": event.verification_status,
    }


def _execution_to_safe_dict(execution: GrantExecution) -> dict[str, Any]:
    """Return a safe dict for a GrantExecution."""
    return {
        "id": execution.id,
        "action": execution.action,
        "resource": execution.resource,
        "operatorId": execution.operator_id,
        "grantId": execution.grant_id,
        "grantRequestId": execution.grant_request_id,
        "challengeId": execution.challenge_id,
        "challengeResult": execution.challenge_result,
        "policyResult": execution.policy_result,
        "result": execution.result,
        "errorCode": execution.error_code,
        "executedAt": execution.executed_at,
        "auditEventId": execution.audit_event_id,
    }


def build_decision_provenance_summary(
    execution_id: str,
    include_timeline: bool = True,
    include_warnings: bool = True,
    include_raw_evidence: bool = False,
) -> Optional[dict[str, Any]]:
    """Build a decision provenance summary for a GrantExecution.

    Retrieves execution, evidence archive, verification status, and
    provenance events, and returns a structured summary dict.

    Args:
        execution_id: The execution to summarise.
        include_timeline: If False, timeline is empty.
        include_warnings: If False, warnings are empty.
        include_raw_evidence: If False, no bundle_json is included.

    Returns:
        A summary dict, or None if the execution does not exist and
        there are no linked provenance events or evidence archives.
    """
    execution = execs.get_grant_execution(execution_id)
    events = prov.list_provenance_events(execution_id=execution_id, limit=1000)
    record = evp.get_bundle_by_execution(execution_id)

    # Not-found guard: if execution is missing AND no events AND no evidence
    if execution is None and not events and record is None:
        return None

    # Derive grant_id from execution, then first event with grant_id, then evidence
    grant_id: Optional[str] = None
    if execution is not None and execution.grant_id is not None:
        grant_id = execution.grant_id
    if grant_id is None:
        for ev in events:
            if ev.grant_id is not None:
                grant_id = ev.grant_id
                break
    if grant_id is None and record is not None:
        grant_id = record.grant_id

    # Provenance events safe list (chronological: oldest first)
    provenance_events = [_event_to_safe_dict(ev) for ev in reversed(events)]

    # Timeline
    timeline = provenance_events if include_timeline else []

    # Evidence section
    evidence: dict[str, Any] = {"present": False}
    if record is not None:
        evidence["present"] = True
        evidence["hash"] = record.evidence_hash
        if include_raw_evidence:
            evidence["bundleJson"] = record.bundle_json
    else:
        evidence["hash"] = None

    # Verification section from evidence archive (read-only, no trigger)
    verification: dict[str, Any] = {"status": None, "verifiedAt": None}
    if record is not None:
        verification["status"] = record.last_verification_status
        verification["verifiedAt"] = record.last_verified_at

    # Warnings
    warnings: list[str] = []
    if include_warnings:
        if execution is not None and record is None:
            warnings.append("missing_evidence")
        if record is not None and record.last_verification_status != "valid":
            warnings.append("unverified_evidence")

    return {
        "executionId": execution_id,
        "grantId": grant_id,
        "execution": _execution_to_safe_dict(execution) if execution else None,
        "evidence": evidence,
        "verification": verification,
        "provenanceEvents": provenance_events,
        "timeline": timeline,
        "warnings": warnings,
        "generatedAt": _iso_now(),
    }
