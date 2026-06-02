# GL-183 External Feedback Triage / Public Issue Hygiene

**Issue ID:** GL-183  
**Title:** External Feedback Triage / Public Issue Hygiene

## Context

GrantLayer is publicly readable on GitHub in a developer-preview / controlled-pilot posture.
GL-182 defined the external developer feedback intake plan.
GL-183 defines the lightweight public triage model for handling that early feedback without overcommitting to production readiness.

This issue is documentation, test, and artifact only.

**No GitHub push was performed by this issue.**  
**No visibility change was performed by this issue.**  
**The internal repo was not pushed directly to GitHub.**  
**No GitHub API label changes were performed by this issue.**

## Scope

This issue defines how early public feedback should be categorized, labeled, routed, and safely handled.

Allowed scope:

- feedback categories for GL-182 review intake
- proposed public GitHub labels, documented only
- severity mapping
- intake workflow
- security handling and public/private routing
- issue template decision
- non-goals and safety confirmations
- one regression test and one JSON example artifact

Not in scope:

- changing backend runtime behavior
- changing OpenAPI, migrations, DB schema, or dependencies
- changing frontend, website, or design assets
- changing GitHub workflows
- creating GitHub labels via API
- pushing anything to public GitHub

## Feedback Categories

Each incoming item should receive exactly one primary category.

| Category | Use When | Typical Handling |
|----------|----------|------------------|
| `blocker` | Something prevents the reviewer from completing any task | Fix now or route to urgent follow-up |
| `confusing-docs` | Documentation is unclear, contradictory, or hard to follow | Clarify docs |
| `broken-quickstart` | Clone/run path or first verifiable output does not work | Fix now |
| `missing-example` | A useful example is absent | Add to backlog or fix now if it blocks comprehension |
| `product-question` | The reviewer is asking what GrantLayer does or how it works | Answer publicly if safe and concise |
| `security-concern` | Potential security issue or sensitive reporting concern | Route to GitHub Security Advisories |
| `production-readiness-concern` | Concern about production suitability, support, or operational maturity | Clarify posture, do not overpromise |
| `feature-request` | Suggestion for new functionality | Backlog |
| `non-scope-later` | Valid feedback that is out of scope for the current developer-preview posture | Defer and label clearly |

## Proposed Public Labels

These labels are proposed for future public hygiene. They are documented here only and are not created by API in this issue.

| Name | Purpose | When to Use | Safety Notes |
|------|---------|-------------|--------------|
| `feedback` | General public feedback bucket | Any external reviewer feedback that is not a bug/security report | Keep wording neutral; do not imply support commitment |
| `good-first-feedback` | Friendly entry point for low-risk reviewer input | Small docs notes, simple quickstart comments, or minor wording suggestions | Do not use for security issues or production commitments |
| `docs` | Documentation-related reports | README, SECURITY, quickstart, examples, or guide clarity | Keep examples synthetic only |
| `quickstart` | Clone/run/first-output issues | Anything affecting the first verifiable output path | Escalate broken paths promptly |
| `bug` | Reproducible non-security defect | Actual broken behavior that is not a security concern | If security-sensitive, do not use this label publicly |
| `security-review-needed` | Security-sensitive report requires private handling | Any report that may involve secrets, exploit details, or exposure concerns | Direct to GitHub Security Advisories; do not ask for exploit steps publicly |
| `production-readiness` | Feedback about production suitability or caveats | Questions or concerns about production status, SLA, onboarding, or operational maturity | Do not let this become a promise of production readiness |
| `question` | General product clarification | Reviewer asks what GrantLayer is or how a documented feature works | Keep responses brief and factual |
| `enhancement` | Feature request or improvement idea | New capability request that is not a bug | Non-blocking ideas belong here |
| `external-review` | Marks public reviewer-originated feedback | Any issue that came from an invited external reviewer | Useful for triage tracking only |
| `needs-triage` | Initial routing state | New feedback that has not yet been categorized and severity-assigned | Move off this label quickly |
| `blocked` | Feedback cannot be actioned yet | Missing reproduction, unclear report, or awaiting safer handling | Do not use to silence valid feedback |
| `non-scope-later` | Explicit deferral bucket | Valid but out-of-scope developer-preview feedback | Explain the deferral reason clearly |

## Severity Mapping

| Severity | Criteria | Examples |
|----------|----------|----------|
| `critical` | Immediate safety or trust failure | Public leak, real secret, harmful overclaim, broken public clone |
| `high` | Serious issue affecting safety or first-use trust | Security reporting broken, quickstart broken, misleading production claim |
| `medium` | Important but not immediately blocking | Confusing docs, unclear caveat, broken important link |
| `low` | Small correctness or clarity issue | Minor wording, formatting, small doc inconsistency |
| `info` | Suggestion or non-blocking observation | Future idea, neutral question, improvement request |

## Intake Workflow

The intake workflow is intentionally simple:

1. Intake received.
2. Classify category.
3. Assign severity.
4. Check safety constraints.
5. Decide public issue vs private security advisory.
6. Record source and date.
7. Decide next action:
   - fix now
   - clarify docs
   - add to backlog
   - defer
   - close as non-scope
   - escalate security

## Security Handling

- Do not post exploit details publicly.
- Do not post secrets publicly.
- Do not post customer data publicly.
- Use GitHub Security Advisories for security-sensitive reports.
- Public issues should use minimal reproduction with synthetic data only.
- If a report includes a secret, treat it as an incident or rotation concern, not normal feedback.
- If a report suggests a repository leak, handle it as a security and hygiene matter before any broader public response.

## Issue Template Decision

**Decision:** `templates_deferred`

Rationale:

- The label and routing model is the higher priority for the first external review window.
- Early feedback should be observed before locking the repository into a more rigid public issue template taxonomy.
- Existing public templates already cover basic bug and security pathways, so GL-183 does not need to add or modify templates to be useful.

Deferred template note:

- A later issue can add a minimal feedback template after the first reviewer window confirms the category and label set.

## Non-Goals

- No production SaaS promise.
- No tenant/workspace isolation claim.
- No customer onboarding.
- No payment or treasury flow.
- No blockchain requirement.
- No SLA or support commitment.
- No collection of real grant or customer data.
- No automated GitHub label creation in this issue.
- No public GitHub push in this issue.
- No visibility change in this issue.
- No internal repo push directly to GitHub in this issue.

## Safety Confirmations

- no GitHub push performed
- no visibility change performed
- internal repo was not pushed directly to GitHub
- no GitHub API label changes performed
- production SaaS not claimed
- tenant isolation not claimed
- real customer data not requested
- secrets not requested
- security-sensitive reports directed to GitHub Security Advisories
- no exploit details requested publicly

## Findings

| ID | Severity | Status | Recommendation | Blocking |
|----|----------|--------|----------------|----------|
| F-183-001 | info | closed | Keep GL-183 documentation-only and defer issue-template expansion until the first external review window is complete. | false |

## Next Recommended Issue

**GL-184 First External Reviewer Invite Pack**

## Explicit Operational Statements

- No GitHub push was performed.
- No visibility change was performed.
- The internal repo was not pushed directly to GitHub.
- No GitHub API label changes were performed.
