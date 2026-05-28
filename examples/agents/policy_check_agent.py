"""Policy Check Agent — dry-run example for GrantLayer.

This module demonstrates a conceptual policy-check workflow using
only Python's standard library. It uses fake/demo policy checks only and
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
class PolicyRule:
    rule_id: str
    rule_name: str
    check_fn_name: str


def build_demo_policy_rules() -> List[PolicyRule]:
    """Return a list of demo policy rules."""
    return [
        PolicyRule(
            rule_id="gl155-demo-rule-001",
            rule_name="min_funding_verified",
            check_fn_name="_check_min_funding",
        ),
        PolicyRule(
            rule_id="gl155-demo-rule-002",
            rule_name="identity_attestation_present",
            check_fn_name="_check_identity_attestation",
        ),
        PolicyRule(
            rule_id="gl155-demo-rule-003",
            rule_name="dual_approval_for_high_value",
            check_fn_name="_check_dual_approval",
        ),
        PolicyRule(
            rule_id="gl155-demo-rule-004",
            rule_name="sanctions_screen_clear",
            check_fn_name="_check_sanctions_screen",
        ),
    ]


def _check_min_funding() -> tuple[bool, str]:
    return True, "Synthetic minimum funding requirement satisfied."


def _check_identity_attestation() -> tuple[bool, str]:
    return True, "Synthetic identity attestation present."


def _check_dual_approval() -> tuple[bool, str]:
    return True, "Synthetic dual-approval requirement met."


def _check_sanctions_screen() -> tuple[bool, str]:
    return False, "Synthetic sanctions-screen flag requires manual review."


_CHECK_REGISTRY = {
    "_check_min_funding": _check_min_funding,
    "_check_identity_attestation": _check_identity_attestation,
    "_check_dual_approval": _check_dual_approval,
    "_check_sanctions_screen": _check_sanctions_screen,
}


def run_policy_checks(rules: List[PolicyRule]) -> dict:
    """Run demo policy checks and report pass/fail/warn."""
    passed: List[str] = []
    failed: List[str] = []
    warnings: List[str] = []

    for rule in rules:
        fn = _CHECK_REGISTRY.get(rule.check_fn_name)
        if fn is None:
            warnings.append(f"{rule.rule_id}: check function not found.")
            continue
        ok, msg = fn()
        if ok:
            passed.append(f"{rule.rule_id}: {msg}")
        else:
            failed.append(f"{rule.rule_id}: {msg}")

    if not warnings:
        warnings.append("None — no warnings generated during dry-run policy check.")

    return {
        "agent_name": "policy_check_agent",
        "mode": "dry_run",
        "developer_preview": True,
        "production_saas_ready": False,
        "tenant_isolation_implemented": False,
        "uses_real_customer_data": False,
        "uses_real_secrets": False,
        "grantlayer_concept": "policy_check",
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
    }


def main() -> None:
    rules = build_demo_policy_rules()
    result = run_policy_checks(rules)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
