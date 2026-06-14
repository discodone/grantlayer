# GL-196 Public Smoke Matrix Pack

This public smoke matrix defines the repeatable checks for the current
Developer Preview. GrantLayer is not production SaaS. Tenant/workspace isolation
not implemented remains a required public caveat. The examples use synthetic
data only: no real customer data, no real secrets, and no private grants.
Security-sensitive reports route to GitHub Security Advisories.

## Public Smoke Matrix

Required checks include repository reachability, README presence, README entry
path clarity, first output helper presence, first output helper match, grant
lifecycle example presence, grant lifecycle example match, public agent/API
walkthrough presence, public feedback infrastructure presence, public safety
gate presence, security advisory route visibility, Developer Preview caveats,
not production SaaS caveats, tenant/workspace isolation not implemented caveats,
no real customer data caveats, no secrets caveats, stale public-state phrase
absence, private data scan cleanliness, secret scan cleanliness, internal
infrastructure scan cleanliness, no force publication requirement, and internal
repository publication safety.

## Commands

- scripts/verify-first-output.sh
- python3 examples/grant_lifecycle_evidence_bundle.py --output /tmp/grantlayer_gl196_grant_lifecycle_check.json
- diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_gl196_grant_lifecycle_check.json
- rg -n "publication pending|public GitHub release has not happened|visibility decision pending|formal visibility decision pending|approved internal source|if and when public publication is approved" README.md CONTRIBUTING.md AGENTS.md llms-full.txt llms.txt docs/ten_minute_quickstart.md docs/agent_quickstart.md || true
- rg -n "GitHub Security Advisories|security/advisories" SECURITY.md docs/public_feedback_infrastructure_pack.md README.md
- rg -n "Developer Preview|technical preview|not production SaaS|tenant.*not implemented|no real secrets|customer data|private grants" README.md AGENTS.md llms.txt llms-full.txt docs/public_agent_api_walkthrough_refresh.md docs/public_safety_scanner_claim_consistency_gate.md

The stale public-state scanner explicitly checks publication pending and public
GitHub release has not happened, plus related visibility-decision phrases.

## Expected Results

The first output helper reports MATCH. The grant lifecycle reference comparison
is an empty diff. Public caveats are visible. Security-sensitive reports route to
GitHub Security Advisories. No private data, secret material, internal
infrastructure references, or stale public-state claims are present in public
entry points.

## Blocking Criteria

Blocking failures include missing public caveats, missing security advisory
routing, deterministic example mismatch, real customer data, real secrets,
private grants, stale public-state claims, or public claims that GrantLayer is
production SaaS or has implemented tenant/workspace isolation.

## Safety Confirmations

- no_github_push_performed: true
- no_visibility_change_performed: true
- internal_repo_not_pushed_directly_to_github: true
- no backend/src, OpenAPI, migration, dependency, SDK, runtime example,
  frontend, workflow, or snapshot publish script behavior changes.
- no_production_saas_claim: true
- tenant_isolation_not_claimed: true

## Next Recommended Issue

GL-196 combined merge-and-publish for public smoke matrix pack.
