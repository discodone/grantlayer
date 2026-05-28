"""Approval Guardrail Agent — dry-run example for GrantLayer.

This module demonstrates a conceptual approval-guardrail workflow using
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
from dataclasses import dataclass
from typing import List


@dataclass
class GrantRequest:
    request_id: str
    subject: str
    action: str
    resource: str
    amount: float
    risk_score: float


def build_demo_grant_request() -> GrantRequest:
    """Return a demo grant request with synthetic identifiers."""
    return GrantRequest(
        request_id="gl155-demo-request-001",
        subject="gl155-demo-subject-001",
        action="disburse_funds",
        resource="gl155-demo-resource-001",
        amount=5000.0,
        risk_score=0.25,
    )


def evaluate_guardrails(req: GrantRequest) -> dict:
    """Evaluate demo guardrails and return a deterministic decision."""
    blocking_reasons: List[str] = []
    required_followups: List[str] = []
    decision = "approve"

    if req.amount > 10000.0:
        blocking_reasons.append("Amount exceeds auto-approval threshold.")
        decision = "block"

    if req.risk_score > 0.7:
        blocking_reasons.append("Risk score exceeds acceptable threshold.")
        decision = "block"

    if req.action == "disburse_funds" and req.amount > 2500.0:
        required_followups.append("Secondary approval required for disbursements over 2500.")
        if decision == "approve":
            decision = "request_followup"

    if not blocking_reasons and not required_followups:
        required_followups.append("None — request meets all guardrails.")

    return {
        "agent_name": "approval_guardrail_agent",
        "mode": "dry_run",
        "developer_preview": True,
        "production_saas_ready": False,
        "tenant_isolation_implemented": False,
        "uses_real_customer_data": False,
        "uses_real_secrets": False,
        "grantlayer_concept": "approval_guardrail",
        "decision": decision,
        "blocking_reasons": blocking_reasons,
        "required_followups": required_followups,
    }


def main() -> None:
    req = build_demo_grant_request()
    result = evaluate_guardrails(req)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
