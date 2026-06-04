# GL-198 Controlled Preview Boundary Pack

## Issue ID

GL-198

## Title

Controlled Preview Boundary Pack

## Context

GrantLayer is publicly available on GitHub at
`https://github.com/Discodone/grantlayer.git` in a Developer Preview /
controlled-pilot posture.

The sequence GL-187 through GL-197 delivered: stale public docs cleanup, a
first-output verify helper, a grant lifecycle evidence bundle, a demo endpoint
safety guard (GL-190), a developer experience polish pack (GL-191), a public
feedback infrastructure (GL-192), a public agent/API walkthrough refresh
(GL-193), a public preview review & feedback triage pack (GL-194), a public
safety/scanner/claim consistency gate (GL-195), a public smoke matrix pack
(GL-196), and an API/SDK/Agent value decision pack (GL-197).

GL-197 concluded `api_first_agent_examples_now_sdk_later` and noted that the
controlled preview boundary had not been formally documented. This issue
creates that boundary pack as a review/docs/test artifact only. It does not
implement production features, change the backend, push to GitHub, or modify
any runtime behavior.

---

## Scope

This issue is **review / docs / test / artifact only.**

Allowed files created:
- `docs/controlled_preview_boundary_pack.md` (this file)
- `docs/examples/gl198/controlled_preview_boundary_pack.json`
- `backend/tests/test_gl198_controlled_preview_boundary_pack.py`

This issue does **not**:
- implement backend features or modify `backend/src/*`
- change `docs/openapi.yaml`, migrations, DB/schema, or dependency manifests
- publish packages to PyPI or any registry
- implement or change SDK code
- push to GitHub
- change GitHub visibility, labels, or issues via API
- send reviewer outreach
- modify frontend, website, or design
- change snapshot publish script behavior
- change examples runtime implementation
- change GitHub workflow files

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|---------|
| README.md | yes |
| SECURITY.md | yes |
| CONTRIBUTING.md | yes (if present) |
| AGENTS.md | yes |
| llms.txt | yes |
| llms-full.txt | yes |
| docs/api_sdk_agent_value_decision_pack.md | yes |
| docs/public_preview_review_feedback_triage_pack.md | yes |
| docs/public_feedback_infrastructure_pack.md | yes |
| docs/public_safety_scanner_claim_consistency_gate.md | yes |
| docs/public_smoke_matrix_pack.md | yes |
| docs/public_agent_api_walkthrough_refresh.md | yes |
| docs/demo_endpoint_safety_guard.md (GL-190) | yes |
| docs/first_output_verify_helper.md | yes |
| docs/grant_lifecycle_evidence_bundle.md | yes |
| docs/agent_quickstart.md | yes |
| docs/ten_minute_quickstart.md | yes |
| examples/first_verifiable_output.py | yes |
| examples/first_verifiable_output.json | yes |
| examples/grant_lifecycle_evidence_bundle.py | yes |
| examples/grant_lifecycle_evidence_bundle.json | yes |
| scripts/verify-first-output.sh | yes |
| docs/examples/gl190/demo_endpoint_safety_guard.json | yes |
| docs/examples/gl191/public_developer_experience_polish_pack.json | yes |
| docs/examples/gl192/public_feedback_infrastructure_pack.json | yes |
| docs/examples/gl193/public_agent_api_walkthrough_refresh.json | yes |
| docs/examples/gl194/public_preview_review_feedback_triage_pack.json | yes |
| docs/examples/gl195/public_safety_scanner_claim_consistency_gate.json | yes |
| docs/examples/gl196/public_smoke_matrix_pack.json | yes |
| docs/examples/gl197/api_sdk_agent_value_decision_pack.json | yes |

---

## Controlled Preview Purpose

GrantLayer's controlled preview is a **narrow, bounded technical preview** for
qualified external participants who want to:

1. Evaluate the core value proposition — verifiable grant workflow evidence,
   auditability, and agent-facing trust checks — using publicly available
   examples and documentation.
2. Provide technical feedback on the API design, developer experience, and
   agent integration story.
3. Run the two deterministic no-install examples and the verify-first-output
   helper to gain confidence in the public snapshot's correctness.
4. Inspect the backend and API surface in a local, synthetic-data-only
   environment.

The controlled preview is **not**:
- a production SaaS trial
- a multi-tenant pilot with real customer data
- a validator of tenant/workspace isolation (not implemented)
- an official SDK or package distribution
- a commitment to production-level service-level agreements

This posture is intentional. The preview allows public inspection and feedback
while explicitly ruling out data-sensitive or production-commitment use patterns
that are not yet safe to support.

---

## Controlled Preview Audience

The controlled preview is intended for **technically qualified external
participants** who understand that they are interacting with a Developer
Preview, not a production-ready SaaS product.

All participants must:
- understand the synthetic-data-only constraint,
- agree not to submit real customer data, private grants, secrets, or
  institutional records,
- route security-sensitive reports through GitHub Security Advisories,
- not treat the local examples as a production SDK or stable API client.

---

## Allowed Participant Profiles

| Profile | Description |
|---------|-------------|
| External developer reviewer | A developer who evaluates the public examples, API docs, and DX feedback path. Uses synthetic data. No production deployments. |
| AI/coding-agent reviewer | A coding agent that reads AGENTS.md, llms.txt, llms-full.txt and runs the deterministic no-install examples. Uses synthetic identifiers only. |
| Grant/compliance domain reviewer (synthetic scenarios only) | A reviewer with grant or compliance domain knowledge who evaluates whether the grant workflow model, evidence structure, and audit chain design make sense — using synthetic scenarios only, no real grants or institutional data. |
| Security-minded reviewer (high-level public-safe reporting only) | A security reviewer who inspects the public surface for design-level concerns, reporting high-level findings via GitHub Security Advisories without publishing exploit details in public issues. |
| Product/UX reviewer for docs and examples | A reviewer who assesses the developer experience, documentation clarity, and example quality with synthetic data only. |

---

## Disallowed Participant Profiles

| Profile | Reason |
|---------|--------|
| Real customer pilot with private data | Tenant/workspace isolation is not implemented; real data would commingle in a single namespace. |
| Production grant workflow operator | Production SaaS readiness is not claimed; no production-level hardening, TLS, IAM, or SLA exists. |
| Institutional deployment | Not appropriate until production hardening gates (auth, encryption at rest, backup, incident response) are complete. |
| Tenant-isolation validation with real tenants | Tenant isolation is not implemented; validating it with real tenants would be misleading. |
| Security exploit publication in public issue | Exploit details must not appear in public GitHub issues; use GitHub Security Advisories. |
| Integration requiring secrets or private credentials | The preview must use placeholder tokens and synthetic identifiers only. No real secrets should enter the review environment. |

---

## Allowed Data

| Data Type | Notes |
|-----------|-------|
| Synthetic/demo grant data | The repository examples use synthetic subject, role, action, and resource identifiers. |
| Repository sample JSON | The committed reference artifacts in `examples/*.json` are synthetic reference outputs. |
| Generated local example outputs | Outputs produced by running the local examples with synthetic identifiers. |
| Public docs feedback | Textual feedback on documentation, DX, examples, and API design. |
| Public GitHub issue feedback without secrets | Feedback submitted via GitHub Issues — must not contain real credentials, real data, or exploit details. |
| High-level security concern without exploit details | Security design observations submitted via GitHub Security Advisories only. |

---

## Forbidden Data

| Data Type | Notes |
|-----------|-------|
| Real customer data | Any data relating to real individuals, organizations, or grant transactions. |
| Private grants | Real grant records from real institutional processes. |
| Institutional records | Compliance records, regulatory data, or other institutionally sensitive information. |
| PII (Personally Identifiable Information) | Names, email addresses, phone numbers, IDs, or any data that can identify a real individual. |
| Secrets | API keys, tokens, passwords, private keys, or any credential material. |
| Tokens/API keys/passwords/private keys | See above. |
| Internal hostnames/remotes | Internal network addresses, private repository URLs, or internal service endpoints. |
| Exploit details in public issues | Attack reproduction steps, proof-of-concept code, or bypass details must not appear in public GitHub issues. |
| Private compliance records | Regulatory, legal, or compliance-sensitive institutional records. |
| Production credentials | Any credential used in a real production system. |

---

## Allowed Activities

| Activity | Notes |
|----------|-------|
| Clone the public repository | `git clone https://github.com/Discodone/grantlayer.git` |
| Read README, AGENTS.md, llms.txt, llms-full.txt | Public entry point documents are open for inspection. |
| Run `scripts/verify-first-output.sh` | No backend, no network, no secrets required. Returns MATCH or DIFF CLEAN. |
| Run `python3 examples/grant_lifecycle_evidence_bundle.py` | No backend, no network, no secrets required. Uses synthetic identifiers. |
| Run `python3 examples/first_verifiable_output.py` | No backend, no network, no secrets required. |
| Inspect API docs and server path documentation | README API table, `docs/openapi.yaml` (local), `docs/ten_minute_quickstart.md`. |
| Provide documentation and DX feedback | Via GitHub Issues (no secrets, no exploit details) or the feedback template. |
| Ask product questions with public/synthetic context | General product, API design, and DX questions. |
| Start the local backend with synthetic data | `pip install -r requirements.txt && python3 -m backend` — local machine only, placeholder tokens. |
| Report security-sensitive issues via GitHub Security Advisories | `https://github.com/Discodone/grantlayer/security/advisories` — no exploit details in public issues. |
| Inspect `sdk/python/README.md` and `sdk/python/grantlayer_client.py` as a local reference | The minimal local client wrapper is a reference example, not a published package. |

---

## Forbidden Activities

| Activity | Reason |
|----------|--------|
| Production deployment | No production hardening, TLS, IAM, or SLA. Production SaaS not claimed. |
| Processing real grant or customer data | Data safety boundary — no tenant isolation, no encryption at rest guarantee. |
| Testing tenant isolation with real tenants | Tenant isolation is not implemented. |
| Uploading secrets, private grant data, or PII | Violates data safety boundary. |
| Treating examples as a production SDK | Examples are local-only demos; no published package exists. |
| Claiming official SDK/package readiness | No pip package is published; no PyPI release exists. |
| Publishing exploit details in public issues | Must route through GitHub Security Advisories. |
| Changing GitHub visibility or repository settings | Forbidden. |
| Using internal/private repo paths or remotes | Forbidden. |
| Submitting feedback that contains real credentials | Any credential or secret must not appear in issues, discussions, or feedback forms. |
| Running demo endpoints with real data or non-local binding without explicit acknowledgement | See demo endpoint safety boundary (GL-190). |

---

## Allowed Environments

| Environment | Notes |
|-------------|-------|
| Local developer machine with synthetic/demo data | The primary allowed environment. pip install + python3 -m backend, synthetic identifiers only. |
| Ephemeral clone (read-only or no-commit) | Clone the public repo for inspection without modifying anything. |
| Docs-only review | Reading and reviewing the documentation without running any code. |
| Offline/no-network example validation (where supported) | `scripts/verify-first-output.sh` and the two no-install examples run offline. |
| Local CI/test pipeline (synthetic data) | Running the test suite against a local backend with synthetic identifiers. |

---

## Forbidden Environments

| Environment | Reason |
|-------------|--------|
| Production SaaS usage | Not claimed; no production deployment exists. |
| Customer environment usage | Real customer data must not enter the review environment. |
| Regulated/private institutional workflow | Compliance requirements not yet met; no encryption at rest, no audit trail at production level. |
| Multi-tenant production trial | Tenant isolation is not implemented. |
| Secret-bearing integration | Any integration that requires real credentials or tokens is forbidden in the controlled preview. |
| Public-facing server with demo endpoints enabled (without explicit acknowledgement) | See GL-190 demo endpoint safety guard. |

---

## Demo Endpoint Safety Boundary

**Reference:** GL-190 Demo Endpoint Safety Guard (`docs/demo_endpoint_safety_guard.md`)

Key constraints for the controlled preview:

1. Demo endpoints (`/demo-action`, related demo routes) are disabled by default
   (`GRANTLAYER_ENABLE_DEMO_ENDPOINTS=false`).
2. When demo endpoints are enabled, they must be bound to a local host
   (`localhost`, `127.0.0.1`, `::1`) or an empty bind address.
3. Binding demo endpoints to a non-local interface (e.g., `0.0.0.0`) is blocked
   at startup unless `GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS=true` is explicitly
   set.
4. Controlled preview participants must not expose demo endpoints publicly
   without understanding and acknowledging this guard.
5. Demo endpoints must not be used with real grant data, real customer records,
   or real credentials.

The startup error name is `demo_endpoints_public_exposure_blocked`. This error
contains no secrets, tokens, endpoint paths, or exploit details.

**In the controlled preview:** demo endpoints are for local synthetic-data-only
evaluation. Do not expose them to the public internet without the explicit
acknowledgement mechanism.

---

## API/SDK/Agent Boundary

**Reference:** GL-197 API/SDK/Agent Value Decision Pack (`docs/api_sdk_agent_value_decision_pack.md`)

Decision: **api_first_agent_examples_now_sdk_later**

Key constraints for the controlled preview:

1. **API-first:** The public API surface (README table, `docs/openapi.yaml`,
   `docs/ten_minute_quickstart.md`) is sufficient for Developer Preview
   evaluation. No hosted interactive playground exists.
2. **Examples now:** The two deterministic no-install examples
   (`examples/first_verifiable_output.py`,
   `examples/grant_lifecycle_evidence_bundle.py`) are the highest-value
   public assets for controlled preview use.
3. **SDK later:** No official SDK or pip package is claimed. The minimal local
   Python client wrapper at `sdk/python/grantlayer_client.py` is a local
   reference only — not a published package, not a stable API client.
4. **Agent workflows are examples/guidance:** `AGENTS.md`, `llms.txt`,
   `llms-full.txt`, and the LangGraph/LangChain-style example show how coding
   agents can use GrantLayer. These are guidance documents and examples, not
   production automation.
5. **No SDK implementation added in GL-198.** The decision to defer SDK
   packaging remains from GL-197.

Participants must not treat `sdk/python/grantlayer_client.py` as a published
SDK, claim pip install availability, or depend on it as a stable API contract.

---

## Security-Sensitive Reporting Boundary

All security-sensitive findings must be reported via:

> **GitHub Security Advisories**
> `https://github.com/Discodone/grantlayer/security/advisories`

This includes:
- Authentication or authorization design concerns
- Data exposure risks
- Demo endpoint exposure scenarios
- Potential injection or API abuse patterns
- Cryptographic or audit chain weaknesses

**Do not** file exploit details, proof-of-concept code, or reproduction steps
in public GitHub issues. Public issues are appropriate for general design
questions and documentation feedback only.

High-level security observations (e.g., "the auth configuration friction could
lead to misconfiguration") may be noted in public issues as long as they
contain no exploit details, no bypass instructions, and no credential material.

---

## Public Claim Boundary

The following claims are **explicitly forbidden** in the controlled preview
period and in any public-facing communication:

| Forbidden Claim | Reason |
|-----------------|--------|
| "GrantLayer is a production SaaS" | Not true; no production deployment exists. |
| "GrantLayer provides tenant/workspace isolation" | Tenant isolation is not implemented. All data lives in a single namespace. |
| "The Python SDK is available on PyPI" | No pip package is published. The local wrapper is not a published package. |
| "GrantLayer is production-ready for institutional use" | Multiple hardening gates remain (auth, encryption at rest, IAM, SLA). |
| "GrantLayer guarantees audit trail immutability in production" | Audit hash chain exists; production-level guarantees require additional hardening. |
| "Reviewer data is tenant-isolated from other reviewer data" | Not true; tenant isolation is not implemented. |

The following claims are **allowed** in the controlled preview:

| Allowed Claim | Basis |
|---------------|-------|
| "GrantLayer is an API-first Developer Preview" | GL-197 decision. |
| "The examples run deterministically with no install and no network" | Verified by smoke matrix (GL-196) and verify-first-output helper (GL-188). |
| "The public snapshot is free of internal paths and real secrets" | Verified by GL-195 scanner gate and GL-196 smoke matrix. |
| "Security-sensitive reports go to GitHub Security Advisories" | Routing established in SECURITY.md and GL-192. |
| "Tenant isolation is not implemented" | Honest Developer Preview posture. |
| "No pip package is published; the local wrapper is a reference example" | GL-197 packaging boundaries. |

---

## Preview Entry Criteria

The following conditions must be true before the controlled preview is
considered open:

| Criterion | Status |
|-----------|--------|
| GL-191 through GL-197 public docs published | confirmed |
| First output helper works (MATCH result) | confirmed (GL-188, GL-197 smoke) |
| Grant lifecycle example works (DIFF CLEAN result) | confirmed (GL-189, GL-197 smoke) |
| Public feedback infrastructure exists (GitHub Issues + Security Advisories) | confirmed (GL-192) |
| Security advisory routing exists (SECURITY.md + docs/public_feedback_infrastructure_pack.md) | confirmed |
| Public smoke matrix exists (GL-196) | confirmed |
| Public safety/claim gate passed with cautions (GL-195) | confirmed |
| No current blocker from GL-195, GL-196, or GL-197 | confirmed — all findings non-blocking |
| Demo endpoint safety guard in place (GL-190) | confirmed |
| API/SDK/agent boundary decision documented (GL-197) | confirmed |
| This GL-198 boundary pack published | pending |

---

## Preview Exit Criteria

The controlled preview can be closed or transitioned when:

| Criterion | Notes |
|-----------|-------|
| Clear reviewer feedback captured and triaged | All submitted feedback normalized, categorized, and converted to roadmap issues. |
| No private data or security leak identified | No real customer data, private grants, secrets, or exploit details in public channels. |
| No misleading production or tenant isolation claims | All participant communications remain within the allowed claim boundary. |
| Public examples remain deterministic | Verify-first-output MATCH and grant lifecycle DIFF CLEAN maintained. |
| Known follow-ups converted into roadmap | All non-blocking findings from the controlled preview documented as issues. |
| Production-readiness gaps explicitly deferred to GL-199 | The gap report v2 documents all remaining hardening gates and defers them explicitly. |
| Decision made on whether to widen the preview, proceed to pilot, or continue boundary | Product decision documented in a follow-up. |

---

## Escalation Criteria

The following conditions require immediate escalation and should be treated as
blocking:

| Condition | Action |
|-----------|--------|
| Real customer data, PII, or private grants found in the public snapshot | Remove immediately; notify via GitHub Security Advisory; assess scope of exposure. |
| Real secret, token, or private key found in the public snapshot | Rotate immediately; remove from history; notify via GitHub Security Advisory. |
| Security-sensitive finding posted publicly with exploit details | Request GitHub issue removal; acknowledge via Security Advisory; assess scope. |
| Demo endpoint exposed to the public internet with real data | Shut down immediately; assess scope; notify via Security Advisory. |
| Evidence of unauthorized production deployment claiming GrantLayer identity | Legal and security escalation path; assess scope. |
| Internal hostname, private remote, or internal path found in public snapshot | Remove from public snapshot; assess scope of exposure. |

---

## Follow-up Roadmap

| Issue | Title | Priority | Notes |
|-------|-------|----------|-------|
| GL-199 | Production Readiness Gap Report v2 | high | Consolidate all hardening gaps with owner, priority, and estimated scope. Covers auth, encryption at rest, IAM, SLA, tenant isolation path, and remaining gates. |
| GL-198P | GL-198 Combined Merge-and-Publish | high | Merge GL-198 to main and push public snapshot update. |

### Optional future follow-ups (only if useful)

| Topic | Notes |
|-------|-------|
| Controlled reviewer feedback round | Capture and triage feedback from the first controlled preview participants. |
| API walkthrough implementation refresh | Add cURL collection, expand auth docs — addresses GL-197-F001, F006. |
| Minimal SDK prototype follow-up | Only after API contract stability commitment and external demand. |
| Agent-to-API standalone example | Complete the agent workflow integration story — GL-197-F004. |
| Pilot data safety checklist | Before any pilot involving synthetic-but-realistic data from real organizations. |

---

## Decision

**controlled_preview_allowed_with_strict_boundaries**

---

## Decision Rationale

The input review from GL-187 through GL-197 confirms:

1. The public snapshot is clean — no internal paths, no real secrets, no
   private data found in any scan.
2. The public examples are deterministic and verified — MATCH and DIFF CLEAN
   results confirmed in GL-197 smoke.
3. The public safety/claim gate (GL-195) passed with cautions — no blockers.
4. The public smoke matrix (GL-196) passed — all 22 check IDs confirmed.
5. The API/SDK/agent value decision (GL-197) is clear — api_first_agent_examples_now_sdk_later.
6. Security-sensitive reporting routing is established — GitHub Security
   Advisories documented in SECURITY.md and GL-192.
7. The demo endpoint safety guard (GL-190) is in place — non-local exposure
   blocked by default.
8. No finding from GL-195, GL-196, or GL-197 is blocking.

A narrow controlled preview is acceptable for public docs/examples/API-understanding
feedback under strict data and participant boundaries. The preview must use
only synthetic/demo data. It must not involve production deployments, real
customer data, private grants, secrets, tenant-isolation claims, or official
SDK/package claims. Security-sensitive reports must go through GitHub Security
Advisories.

Remaining caveats (GL-198-F001 through GL-198-F007 below) are non-blocking
and do not prevent the controlled preview from proceeding.

---

## Findings

### GL-198-F001

| Field | Value |
|-------|-------|
| id | GL-198-F001 |
| severity | medium |
| category | preview-boundary |
| summary | The controlled preview boundary has not been formally documented until this issue. Reviewers joining the preview before GL-198 are operating without an explicit data safety boundary document. |
| evidence | GL-197 risk: "The controlled preview boundary (GL-198) has not been formally documented; until it is, the reviewer pool should remain limited." |
| blocking | no — resolved by this issue |
| recommended_action | Publish GL-198 boundary pack. Ensure all future reviewer invitations reference this document. |
| recommended_issue | GL-198 (this issue); GL-198P for public publish |

### GL-198-F002

| Field | Value |
|-------|-------|
| id | GL-198-F002 |
| severity | medium |
| category | claim-safety |
| summary | The README Developer entry path table labels Step 5 as "Python SDK" without a qualifier, which may set incorrect expectations about published package availability. |
| evidence | GL-197-F002: README.md Developer entry path table, Step 5: "Python SDK" — `sdk/python/README.md`. The SDK README correctly states "No pip package is published," but the table label alone is ambiguous. |
| blocking | no |
| recommended_action | Add a qualifier to the README table: change "Python SDK" to "Minimal Python client (local only, not published)" or equivalent. Can be done in GL-198P or a subsequent small fix. |
| recommended_issue | GL-198P or a dedicated README fix issue |

### GL-198-F003

| Field | Value |
|-------|-------|
| id | GL-198-F003 |
| severity | low |
| category | preview-boundary |
| summary | `llms.txt` Next Steps section still references "GL-193" as an upcoming issue, but GL-193 is complete. First identified in GL-195-F003, carried through GL-197-F003. |
| evidence | llms.txt line approximately 78: references GL-193 as upcoming. GL-193 was merged and published. |
| blocking | no |
| recommended_action | Update llms.txt Next Steps to reference GL-198–GL-199 roadmap. Minimal one-line fix appropriate for GL-198P or a subsequent issue. |
| recommended_issue | GL-198P or a small docs refresh |

### GL-198-F004

| Field | Value |
|-------|-------|
| id | GL-198-F004 |
| severity | low |
| category | tenant-isolation |
| summary | No consolidated reminder of the tenant-isolation-not-implemented constraint appears in the new reviewer entry path (ten-minute quickstart, agent quickstart). Reviewers who skip SECURITY.md or README caveats may not encounter this disclaimer. |
| evidence | `docs/ten_minute_quickstart.md` and `docs/agent_quickstart.md` focus on the happy path without a prominent tenant isolation caveat. The constraint is documented in README.md and SECURITY.md but not surfaced at the quickstart entry point. |
| blocking | no |
| recommended_action | Add a one-line Developer Preview caveat to the top of `docs/ten_minute_quickstart.md` and `docs/agent_quickstart.md` referencing the boundary doc or SECURITY.md. Non-blocking; appropriate for GL-198P or GL-199. |
| recommended_issue | GL-198P or GL-199 |

### GL-198-F005

| Field | Value |
|-------|-------|
| id | GL-198-F005 |
| severity | low |
| category | api-sdk-agent-boundary |
| summary | No agent-to-API integration example exists showing a coding agent calling the live local backend (health → create grant → demo action → check audit) with placeholder tokens. GL-197-F004 identified this gap. |
| evidence | `examples/langgraph_langchain/grantlayer_agent_example.py` exists but is not a standalone, fully documented agent-to-API smoke path. |
| blocking | no |
| recommended_action | Add a future standalone agent-to-API example that uses placeholder tokens and produces a structured JSON report. Defer to GL-199 or a dedicated follow-up issue. |
| recommended_issue | GL-199 or a future agent example issue |

### GL-198-F006

| Field | Value |
|-------|-------|
| id | GL-198-F006 |
| severity | low |
| category | production-caveat |
| summary | No consolidated production readiness gap report v2 exists. Individual caveats are spread across README.md, SECURITY.md, and docs/security_boundaries.md. |
| evidence | GL-194-F002, GL-195-F004, GL-197-F007 all identify this gap. No single document maps all remaining hardening gates with owner, priority, and estimated scope. |
| blocking | no |
| recommended_action | GL-199 Production Readiness Gap Report v2 should consolidate all remaining hardening gates. |
| recommended_issue | GL-199 |

### GL-198-F007

| Field | Value |
|-------|-------|
| id | GL-198-F007 |
| severity | info |
| category | data-safety |
| summary | No formal reviewer data safety checklist exists for participants who wish to run the backend with synthetic-but-realistic data from real organizations. All current examples use fully synthetic identifiers. |
| evidence | The boundary doc (this issue) defines the data boundary. No formal per-reviewer checklist exists for edge cases such as a grant reviewer who works at a real organization but wants to test with their own anonymized scenarios. |
| blocking | no |
| recommended_action | Consider a pilot data safety checklist follow-up if any reviewer proposes using organization-specific but anonymized scenarios. Defer until a concrete request arises. |
| recommended_issue | Optional future pilot data safety checklist issue |

---

## Risks and Caveats

- The controlled preview boundary is documented here for the first time (GL-198). Until this is published, reviewers lack an explicit data safety boundary reference. Publishing GL-198 closes this gap.
- Tenant isolation is not implemented. All reviewer data in a shared local instance is in a single namespace. This is an acceptable risk for synthetic-data-only local review, but not for any real-data or multi-party pilot.
- The API contract has no stability commitment. Reviewers who write integrations against the current API should expect changes.
- The `sdk/python/` directory name implies more maturity than exists. The README qualifier ("No pip package is published") must remain prominent.
- The minimal local Python client wrapper at `sdk/python/grantlayer_client.py` must not be described as a published SDK or a stable API client.
- Security-sensitive findings submitted via public issues before GitHub Security Advisories routing was established (pre-GL-192) may require retroactive handling if exploit details were included. No such incidents are known.
- The escalation criteria in this document must be followed immediately if any condition is triggered.

---

## Non-Goals

This issue does **not**:
- implement a real SDK or publish a pip package
- change backend runtime behavior or add new API surface
- change `backend/src/*`, OpenAPI, migrations, DB/schema, or dependency manifests
- push to GitHub or change GitHub visibility
- create or modify GitHub labels/issues via API
- send reviewer outreach or contact reviewers
- change frontend, website, or design
- change snapshot publish script behavior
- claim production SaaS readiness
- claim tenant isolation is implemented
- request real customer data, private grants, or secrets
- include exploit details
- process real grant data
- make production deployment decisions

---

## Exact Safety Phrases

The following lowercase phrases are intentionally included for agent and test
compatibility:

- tenant isolation is not implemented
- no real secrets
- no real customer data
- developer preview / technical preview only
- not production saas

---

## Current Public Preview State

| Posture | Value |
|---------|-------|
| Release label | **GL-0.1 / Developer Preview** |
| Maturity | Developer Preview / technical preview only |
| Production SaaS readiness | **Not claimed** |
| Tenant/workspace isolation | **Not implemented** |
| Public GitHub repository | **Available** — `https://github.com/Discodone/grantlayer.git` (GL-176) |
| Public snapshot | Clean developer-facing snapshot — no internal paths, no real secrets |
| Real customer data in examples | **No** — all examples use synthetic identifiers |
| Real secrets in examples | **No** — all tokens and keys are placeholders |
| Official SDK/package | **Not claimed** — no pip package published |

---

## Safety Confirmations

| Confirmation | Status |
|-------------|--------|
| no_github_push_performed | confirmed |
| no_visibility_change_performed | confirmed |
| internal_repo_not_pushed_directly_to_github | confirmed |
| no_github_api_label_changes_performed | confirmed |
| no_github_issue_changes_performed | confirmed |
| no_reviewer_outreach_sent | confirmed |
| no_backend_src_changes | confirmed |
| no_openapi_changes | confirmed |
| no_migration_db_dependency_changes | confirmed |
| no_dependency_manifest_changes | confirmed |
| no_sdk_implementation_changes | confirmed |
| no_package_publishing_changes | confirmed |
| no_examples_runtime_changes | confirmed |
| no_frontend_website_design_changes | confirmed |
| no_github_workflow_changes | confirmed |
| no_snapshot_publish_script_behavior_changes | confirmed |
| no_production_saas_claim | confirmed |
| tenant_isolation_not_claimed | confirmed |
| official_sdk_package_not_claimed_unless_verified | confirmed |
| no_real_customer_data_requested | confirmed |
| no_private_grant_data_requested | confirmed |
| no_secrets_requested | confirmed |
| no_exploit_details_included | confirmed |
| security_sensitive_reports_routed_to_github_security_advisories | confirmed |

Security-sensitive reports should be submitted via GitHub Security Advisories
at `https://github.com/Discodone/grantlayer/security/advisories`. Do not file
exploit details in public issues.

---

> This document was created in **GL-198 Controlled Preview Boundary Pack**. It
> is a review/docs/test artifact only. It does not change git remotes, rewrite
> history, modify production code, change API behavior, add migrations, change
> the database schema, add dependencies, implement SDK changes, publish packages,
> launch a website or frontend, claim production SaaS readiness, or claim tenant
> isolation implementation. All examples use synthetic identifiers and
> placeholder tokens only.
