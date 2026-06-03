#!/usr/bin/env python3
"""Generate a deterministic grant lifecycle evidence bundle example."""

import argparse
import hashlib
import json
from pathlib import Path


FIXED_GENERATED_AT = "2026-02-03T09:35:00Z"
FIXED_SUBMITTED_AT = "2026-02-03T09:30:00Z"
FIXED_EVIDENCE_ATTACHED_AT = "2026-02-03T09:31:00Z"
FIXED_ELIGIBILITY_CHECKED_AT = "2026-02-03T09:32:00Z"
FIXED_APPROVAL_RECOMMENDED_AT = "2026-02-03T09:33:00Z"
FIXED_BUNDLE_GENERATED_AT = "2026-02-03T09:34:00Z"

EXAMPLE_ID = "gl189-grant-lifecycle-evidence-bundle"
GRANT_ID = "gl189-synthetic-grant-001"
BUNDLE_ID = "gl189-evidence-bundle-001"
DEFAULT_OUTPUT_PATH = Path("/tmp/grantlayer_grant_lifecycle_evidence_bundle.json")
REFERENCE_ARTIFACT = "examples/grant_lifecycle_evidence_bundle.json"


def _canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_json(data):
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _evidence_item(evidence_id, evidence_type, content):
    return {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "content": content,
        "content_sha256": _sha256_json(content),
    }


def _audit_chain_entry(event_index, event_type, event_at, payload, previous_event_hash):
    source = {
        "event_at": event_at,
        "event_index": event_index,
        "event_type": event_type,
        "payload": payload,
        "previous_event_hash": previous_event_hash,
    }
    return {
        "event_index": event_index,
        "event_type": event_type,
        "event_hash": _sha256_json(source),
        "previous_event_hash": previous_event_hash,
    }


def build_record():
    grant_request = {
        "grant_id": GRANT_ID,
        "applicant_type": "synthetic-demo",
        "program": "synthetic-community-capacity-grant",
        "requested_amount": 12500,
        "currency": "USD",
        "purpose": "Demonstrate a deterministic grant lifecycle evidence bundle.",
        "submitted_at": FIXED_SUBMITTED_AT,
    }

    lifecycle_events = [
        {
            "event_index": 0,
            "event_type": "submitted",
            "event_at": FIXED_SUBMITTED_AT,
            "summary": "Synthetic grant request submitted for local preview.",
            "evidence_ids": [],
        },
        {
            "event_index": 1,
            "event_type": "evidence_attached",
            "event_at": FIXED_EVIDENCE_ATTACHED_AT,
            "summary": "Synthetic budget and eligibility evidence attached.",
            "evidence_ids": [
                "gl189-evidence-001",
                "gl189-evidence-002",
            ],
        },
        {
            "event_index": 2,
            "event_type": "eligibility_checked",
            "event_at": FIXED_ELIGIBILITY_CHECKED_AT,
            "summary": "Deterministic eligibility rule set passed.",
            "evidence_ids": ["gl189-evidence-002"],
        },
        {
            "event_index": 3,
            "event_type": "approval_recommended",
            "event_at": FIXED_APPROVAL_RECOMMENDED_AT,
            "summary": "Synthetic reviewer note recommends approval.",
            "evidence_ids": ["gl189-evidence-003"],
        },
        {
            "event_index": 4,
            "event_type": "bundle_generated",
            "event_at": FIXED_BUNDLE_GENERATED_AT,
            "summary": "Evidence bundle sealed for deterministic verification.",
            "evidence_ids": [
                "gl189-evidence-001",
                "gl189-evidence-002",
                "gl189-evidence-003",
            ],
        },
    ]

    evidence_items = [
        _evidence_item(
            "gl189-evidence-001",
            "synthetic_budget_summary",
            {
                "grant_id": GRANT_ID,
                "line_items": [
                    {"category": "program_delivery", "amount": 8500},
                    {"category": "materials", "amount": 2500},
                    {"category": "community_outreach", "amount": 1500},
                ],
                "currency": "USD",
                "total_requested": 12500,
            },
        ),
        _evidence_item(
            "gl189-evidence-002",
            "synthetic_eligibility_statement",
            {
                "grant_id": GRANT_ID,
                "eligibility_rules": [
                    "synthetic-demo-entity-only",
                    "local-preview-only",
                    "no-network-required",
                ],
                "result": "eligible",
                "reviewed_at": FIXED_ELIGIBILITY_CHECKED_AT,
            },
        ),
        _evidence_item(
            "gl189-evidence-003",
            "synthetic_review_note",
            {
                "grant_id": GRANT_ID,
                "note": "Synthetic reviewer recommends approval after deterministic checks.",
                "recommended_action": "approve",
                "reviewed_at": FIXED_APPROVAL_RECOMMENDED_AT,
            },
        ),
    ]

    audit_chain = []
    previous_event_hash = None
    for event in lifecycle_events:
        payload = {
            "event_at": event["event_at"],
            "grant_id": GRANT_ID,
            "summary": event["summary"],
            "evidence_ids": event["evidence_ids"],
        }
        chain_entry = _audit_chain_entry(
            event["event_index"],
            event["event_type"],
            event["event_at"],
            payload,
            previous_event_hash,
        )
        audit_chain.append(chain_entry)
        previous_event_hash = chain_entry["event_hash"]

    evidence_bundle = {
        "bundle_id": BUNDLE_ID,
        "grant_id": GRANT_ID,
        "event_count": len(lifecycle_events),
        "evidence_count": len(evidence_items),
        "final_event_hash": audit_chain[-1]["event_hash"],
        "bundle_hash_algorithm": "sha256",
    }

    bundle_sha256 = _sha256_json(evidence_bundle)

    return {
        "record_type": "grantlayer_grant_lifecycle_evidence_bundle_example",
        "record_version": "1.0",
        "generated_at": FIXED_GENERATED_AT,
        "example_id": EXAMPLE_ID,
        "preview_mode": True,
        "safety_notice": (
            "Synthetic demo data only. No network, backend, secrets, customer data, "
            "or production SaaS assumptions are required."
        ),
        "grant_request": grant_request,
        "lifecycle_events": lifecycle_events,
        "evidence_items": evidence_items,
        "audit_chain": audit_chain,
        "evidence_bundle": evidence_bundle,
        "bundle_sha256": bundle_sha256,
        "verification_summary": {
            "deterministic_output": True,
            "no_network_required": True,
            "no_backend_required": True,
            "no_secrets_required": True,
            "no_customer_data_required": True,
            "reference_artifact": REFERENCE_ARTIFACT,
            "exact_match_expected": True,
        },
        "non_goals": [
            "No backend server startup is demonstrated.",
            "No real grant, customer data, or private institutional record is used.",
            "No production SaaS readiness claim is made.",
            "Tenant/workspace isolation is not claimed as implemented.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate the GL-189 grant lifecycle evidence bundle example."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
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
