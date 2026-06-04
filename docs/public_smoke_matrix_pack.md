# GL-196 Public Smoke Matrix Pack

## Issue ID

GL-196

## Title

Public Smoke Matrix Pack

## Context

GrantLayer is publicly available on GitHub at
`https://github.com/Discodone/grantlayer.git` in a Developer Preview /
controlled-pilot posture. GL-196 defines the minimal repeatable smoke matrix
for the public repository so reviewers can verify the public entry path,
public examples, safety caveats, and security-routing claims without changing
runtime behavior.

This is a docs/test/artifact issue only.

## Scope

- Public clone/readability verification
- README entry path verification
- First verifiable output helper verification
- Grant lifecycle evidence bundle verification
- Public agent/API walkthrough verification
- Public feedback infrastructure verification
- Public safety / claim consistency verification
- Security reporting route verification
- Stale phrase absence verification
- Public caveat presence verification
- Private data / secret / internal infrastructure absence checks
- No force-push / no direct internal repo push expectation checks

## Smoke Matrix Overview

The matrix below defines the smallest repeatable set of checks that keeps the
public snapshot honest:

- Can the public repository be reached and cloned?
- Does the README still point to the correct entry path?
- Do the two deterministic no-install examples still match their references?
- Are the public walkthrough, feedback, and safety docs still present and
  consistent?
- Are the public caveats still visible everywhere they need to be?
- Are stale public-state phrases absent from the public entry docs?
- Do the public-facing files stay free of private data, secrets, and internal
  infrastructure hints?
- Are there no expectations of force-pushes or direct internal repo pushes to
  GitHub?

## Smoke Check Categories

| Category | What It Covers |
|---|---|
| `public-reachability` | Public clone/readability, optional network confirmation |
| `entry-paths` | README entry path and public walkthrough links |
| `deterministic-examples` | First output helper and grant lifecycle evidence bundle |
| `public-safety-and-feedback` | Safety gate, feedback infrastructure, security reporting route |
| `claim-consistency` | Developer Preview, not production SaaS, tenant isolation caveat |
| `snapshot-hygiene` | Stale phrases, private data, secrets, and internal infrastructure absence |
| `publish-expectations` | No force-push and no direct internal repo push expectations |

## Commands To Run Locally

Use these from the repository root. `rg` is preferred; if it is unavailable in
your environment, substitute `grep -n` with the same patterns.

```bash
# Optional external reachability check; skip if offline.
git ls-remote --heads https://github.com/Discodone/grantlayer.git HEAD

# README entry path and entry-point links.
rg -n "What to try first|What to try next|Developer entry path|first_output_verify_helper|grant_lifecycle_evidence_bundle" README.md

# First verifiable output helper.
scripts/verify-first-output.sh

# Grant lifecycle evidence bundle.
python3 examples/grant_lifecycle_evidence_bundle.py --output /tmp/grantlayer_gl196_grant_lifecycle_check.json
diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_gl196_grant_lifecycle_check.json

# Public agent/API walkthrough.
rg -n "public_agent_api_walkthrough_refresh|What to try first|What to try next|security/advisories" docs/public_agent_api_walkthrough_refresh.md README.md

# Public feedback infrastructure.
rg -n "GitHub Security Advisories|security/advisories|severity:critical|security-sensitive-report" SECURITY.md docs/public_feedback_infrastructure_pack.md README.md

# Public safety / claim consistency docs.
rg -n "Developer Preview|technical preview|not production SaaS|tenant.*not implemented|no real secrets|customer data|private grants" README.md AGENTS.md llms.txt llms-full.txt docs/public_agent_api_walkthrough_refresh.md docs/public_safety_scanner_claim_consistency_gate.md

# Stale phrase absence.
rg -n "publication pending|public GitHub release has not happened|visibility decision pending|formal visibility decision pending|approved internal source|if and when public publication is approved" README.md CONTRIBUTING.md AGENTS.md llms-full.txt llms.txt docs/ten_minute_quickstart.md docs/agent_quickstart.md || true

# Private data / secrets / internal infrastructure scans.
rg -n "customer data|private grants|real customer|real grant|real institutional|PII|email|phone number" README.md AGENTS.md llms.txt llms-full.txt SECURITY.md CONTRIBUTING.md docs/public_agent_api_walkthrough_refresh.md docs/public_feedback_infrastructure_pack.md docs/public_safety_scanner_claim_consistency_gate.md || true
rg -n "ghp_|sk-|Bearer |API key|password|private key" README.md AGENTS.md llms.txt llms-full.txt SECURITY.md CONTRIBUTING.md docs/public_agent_api_walkthrough_refresh.md docs/public_feedback_infrastructure_pack.md docs/public_safety_scanner_claim_consistency_gate.md || true
rg -n "Forgejo|/home/adminuser/|internal hostname|internal remote|private absolute path" README.md AGENTS.md llms.txt llms-full.txt SECURITY.md CONTRIBUTING.md docs/public_agent_api_walkthrough_refresh.md docs/public_feedback_infrastructure_pack.md docs/public_safety_scanner_claim_consistency_gate.md || true

# No force-push / no direct internal repo push expectations.
rg -n "git push --force|force push|internal repo directly to GitHub|git push github|push internal repo" README.md AGENTS.md llms.txt llms-full.txt SECURITY.md docs/public_feedback_infrastructure_pack.md docs/public_safety_scanner_claim_consistency_gate.md || true
```

## Expected Results

- The public repository is reachable when network access is available.
- `README.md` still points first-time readers at the deterministic examples and
  the agent entry path.
- `scripts/verify-first-output.sh` exits `0` and reports `MATCH`.
- `examples/grant_lifecycle_evidence_bundle.py` produces an empty diff against
  `examples/grant_lifecycle_evidence_bundle.json`.
- The public agent/API walkthrough, feedback infrastructure, and safety docs
  are present and consistent.
- The public entry docs continue to state Developer Preview / technical preview
  posture, not production SaaS, and tenant/workspace isolation not implemented.
- Stale public-state phrases stay absent from the public entry docs.
- Public-facing files do not expose private data, secrets, or internal
  infrastructure details.
- The public docs do not imply that a force-push is required or that the
  internal repo is pushed directly to GitHub.

## Pass / Fail Criteria

- **Pass** when all non-optional local checks succeed and the optional network
  check either succeeds or is clearly noted as skipped because the environment
  is offline.
- **Fail** when any required check finds a missing doc, a mismatch, a stale
  phrase, private data, secrets, internal infrastructure, or an incorrect
  public claim.
- **Fail** when any public safety or security-routing doc stops pointing to
  GitHub Security Advisories for security-sensitive reports.

## Troubleshooting

- If `scripts/verify-first-output.sh` fails, rerun the generator directly and
  compare the output path it reports.
- If the grant lifecycle diff is non-empty, check for local edits to the
  example script or reference artifact.
- If `rg` is unavailable, rerun the same searches with `grep -n`.
- If the optional public clone check fails, note whether the environment is
  offline before treating it as a public availability regression.

## Safety Checks

- No real secrets.
- No real customer data.
- No private grants.
- No private internal infrastructure.
- No exploit details.
- No production SaaS claim.
- Tenant/workspace isolation is not implemented.
- Security-sensitive reports route to GitHub Security Advisories.

## Non-Goals

- No backend runtime behavior changes.
- No OpenAPI changes.
- No migrations, schema, dependency, SDK implementation, or frontend/design
  changes.
- No GitHub workflow changes.
- No publication or visibility changes.
- No GitHub API label or issue automation.
- No reviewer outreach.
- No change to the snapshot publish script.

## Next Recommended Issue

GL-196 Combined Merge-and-Publish for Public Smoke Matrix Pack
