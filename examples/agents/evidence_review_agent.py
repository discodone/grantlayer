"""Evidence Review Agent — dry-run example for GrantLayer.

This module demonstrates a conceptual evidence-review workflow using
only Python's standard library. It uses fake/demo data only and
performs no network calls.

Caveats:
- Developer Preview — local evaluation only
- Not a production SaaS
- Tenant isolation is not implemented
- No real secrets
- No real customer data
"""

import json
from dataclasses import dataclass, field
from typing import List


@dataclass
class EvidenceItem:
    item_id: str
    item_type: str
    description: str
    status: str


@dataclass
class EvidenceBundle:
    bundle_id: str
    grant_id: str
    items: List[EvidenceItem] = field(default_factory=list)


def build_demo_evidence_bundle() -> EvidenceBundle:
    """Return a demo evidence bundle with synthetic identifiers."""
    return EvidenceBundle(
        bundle_id="gl155-demo-bundle-001",
        grant_id="gl155-demo-grant-001",
        items=[
            EvidenceItem(
                item_id="gl155-demo-item-001",
                item_type="identity_verification",
                description="Synthetic identity check passed",
                status="complete",
            ),
            EvidenceItem(
                item_id="gl155-demo-item-002",
                item_type="funding_source_confirmation",
                description="Synthetic funding source confirmed",
                status="complete",
            ),
            EvidenceItem(
                item_id="gl155-demo-item-003",
                item_type="compliance_attestation",
                description="Synthetic attestation pending signature",
                status="pending",
            ),
        ],
    )


def review_evidence_bundle(bundle: EvidenceBundle) -> dict:
    """Review a bundle and return deterministic findings as a dict."""
    findings: List[str] = []
    recommended_action = "approve"

    for item in bundle.items:
        if item.status == "pending":
            findings.append(
                f"{item.item_id} ({item.item_type}) is pending and requires follow-up."
            )
            recommended_action = "request_followup"
        elif item.status == "complete":
            findings.append(
                f"{item.item_id} ({item.item_type}) is complete."
            )
        else:
            findings.append(
                f"{item.item_id} ({item.item_type}) has unexpected status '{item.status}'."
            )
            recommended_action = "block"

    return {
        "agent_name": "evidence_review_agent",
        "mode": "dry_run",
        "developer_preview": True,
        "production_saas_ready": False,
        "tenant_isolation_implemented": False,
        "uses_real_customer_data": False,
        "uses_real_secrets": False,
        "grantlayer_concept": "evidence_review",
        "evidence_items_reviewed": len(bundle.items),
        "findings": findings,
        "recommended_action": recommended_action,
    }


def main() -> None:
    bundle = build_demo_evidence_bundle()
    result = review_evidence_bundle(bundle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
