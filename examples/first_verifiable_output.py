#!/usr/bin/env python3
"""Generate a deterministic GrantLayer-style first verifiable output example."""

import argparse
import hashlib
import json
from pathlib import Path


FIXED_TIME = "2026-01-15T12:00:00Z"
EXAMPLE_ID = "gl168-first-verifiable-output"
WORKFLOW_ID = "gl168-demo-workflow-001"
SUBJECT_ID = "gl168-demo-subject-001"
REQUEST_ID = "gl168-grant-request-001"
GRANT_ID = "gl168-grant-001"
EVIDENCE_BUNDLE_ID = "gl168-evidence-bundle-001"


def _canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_json(data):
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _evidence_item(item_id, evidence_type, content):
    return {
        "id": item_id,
        "type": evidence_type,
        "content": content,
        "content_sha256": _sha256_json(content),
    }


def _audit_event(event_id, event_type, actor, timestamp, payload, previous_hash=None):
    event = {
        "id": event_id,
        "type": event_type,
        "actor": actor,
        "timestamp": timestamp,
        "payload": payload,
        "previous_event_hash": previous_hash,
    }
    event["event_hash"] = _sha256_json(event)
    return event


def build_record():
    grant_request = {
        "id": REQUEST_ID,
        "workflow_id": WORKFLOW_ID,
        "subject_id": SUBJECT_ID,
        "requested_by": "gl168-demo-agent",
        "requested_role": "evidence_reviewer",
        "action": "review_application",
        "resource": "synthetic-grant-application-gl168",
        "reason": "Synthetic local example showing first verifiable output.",
        "created_at": FIXED_TIME,
    }

    decision = {
        "id": "gl168-decision-001",
        "grant_request_id": REQUEST_ID,
        "decision": "approved",
        "approved_grant_id": GRANT_ID,
        "decided_by": "gl168-demo-operator",
        "decided_at": "2026-01-15T12:01:00Z",
        "rationale": "Synthetic policy and evidence checks passed for local demo.",
    }

    evidence_items = [
        _evidence_item(
            "gl168-evidence-001",
            "policy_check",
            {
                "policy_id": "synthetic-policy-gl168",
                "result": "passed",
                "checked_at": "2026-01-15T12:00:30Z",
                "details": "Requested action is allowed for the synthetic role.",
            },
        ),
        _evidence_item(
            "gl168-evidence-002",
            "approval_record",
            {
                "approval_id": decision["id"],
                "approved": True,
                "approved_by": decision["decided_by"],
                "approved_at": decision["decided_at"],
            },
        ),
        _evidence_item(
            "gl168-evidence-003",
            "compliance_note",
            {
                "status": "ready_for_local_demo",
                "checked_at": "2026-01-15T12:02:00Z",
                "note": "Synthetic data only; no production SaaS readiness claim.",
            },
        ),
    ]

    evidence_bundle_content = {
        "grant_request_id": REQUEST_ID,
        "decision_id": decision["id"],
        "evidence_item_hashes": [
            item["content_sha256"] for item in evidence_items
        ],
        "canonical_version": "gl168.example.v1",
    }
    evidence_bundle = {
        "id": EVIDENCE_BUNDLE_ID,
        "created_at": "2026-01-15T12:02:30Z",
        "content": evidence_bundle_content,
        "bundle_sha256": _sha256_json(evidence_bundle_content),
    }

    audit_trail = []
    for event_id, event_type, actor, timestamp, payload in [
        (
            "gl168-audit-001",
            "grant_request_created",
            grant_request["requested_by"],
            grant_request["created_at"],
            {"grant_request_id": REQUEST_ID},
        ),
        (
            "gl168-audit-002",
            "evidence_collected",
            "gl168-demo-system",
            "2026-01-15T12:00:45Z",
            {"evidence_item_count": len(evidence_items)},
        ),
        (
            "gl168-audit-003",
            "grant_request_approved",
            decision["decided_by"],
            decision["decided_at"],
            {"grant_request_id": REQUEST_ID, "grant_id": GRANT_ID},
        ),
        (
            "gl168-audit-004",
            "evidence_bundle_sealed",
            "gl168-demo-system",
            evidence_bundle["created_at"],
            {
                "evidence_bundle_id": EVIDENCE_BUNDLE_ID,
                "bundle_sha256": evidence_bundle["bundle_sha256"],
            },
        ),
    ]:
        previous_hash = audit_trail[-1]["event_hash"] if audit_trail else None
        audit_trail.append(
            _audit_event(event_id, event_type, actor, timestamp, payload, previous_hash)
        )

    compliance_readiness_summary = {
        "status": "ready_for_local_review",
        "generated_at": "2026-01-15T12:03:00Z",
        "checks": {
            "synthetic_data_only": "passed",
            "evidence_hashes_present": "passed",
            "audit_trail_chained": "passed",
            "production_saas_readiness": "not_claimed",
            "tenant_isolation": "not_implemented",
        },
        "recommended_next_step": "Review the JSON artifact and compare hashes.",
    }

    return {
        "example_id": EXAMPLE_ID,
        "record_type": "grantlayer_first_verifiable_output_example",
        "record_version": "1.0",
        "generated_at": FIXED_TIME,
        "caveats": [
            "Synthetic local example data only.",
            "No network calls, backend service, secrets, or GitHub auth required.",
            "Not production SaaS readiness.",
            "Tenant isolation is not implemented.",
        ],
        "grant_request": grant_request,
        "decision": decision,
        "evidence_items": evidence_items,
        "evidence_bundle": evidence_bundle,
        "audit_trail": audit_trail,
        "compliance_readiness_summary": compliance_readiness_summary,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate the GL-168 first verifiable output JSON example."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path where the generated JSON record should be written.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    if output_path.parent:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(build_record(), f, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
