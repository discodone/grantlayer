# GL-197 API/SDK/Agent Value Decision Pack

## Issue ID

GL-197

## Title

API/SDK/Agent Value Decision Pack

## Context

GrantLayer is publicly available on GitHub at
`https://github.com/Discodone/grantlayer.git` in a Developer Preview /
controlled-pilot posture.

The sequence GL-187 through GL-196 delivered: stale public docs cleanup, a
first-output verify helper, a grant lifecycle evidence bundle, a demo endpoint
safety guard, a developer experience polish pack, a public feedback
infrastructure, a public agent/API walkthrough refresh, a public preview review
& feedback triage pack (GL-194), a public safety/scanner/claim consistency gate
(GL-195), and a public smoke matrix pack (GL-196).

GL-195 recommended GL-197 to document SDK maturity, packaging decision, and
agent integration value. This issue creates that decision pack as a
review/docs/test artifact only. It does not implement a real SDK, modify the
backend, or push to GitHub.

---

## Scope

This issue is **review / docs / test / artifact only.**

Allowed files created:
- `docs/api_sdk_agent_value_decision_pack.md` (this file)
- `docs/examples/gl197/api_sdk_agent_value_decision_pack.json`
- `backend/tests/test_gl197_api_sdk_agent_value_decision_pack.py`

This issue does **not**:
- implement a real SDK or backend feature
- change `backend/src/*`, `docs/openapi.yaml`, migrations, DB/schema, or dependency manifests
- publish packages to PyPI or any registry
- push to GitHub
- change GitHub visibility, labels, or issues via API
- send reviewer outreach
- modify frontend, website, or design
- change snapshot publish script behavior
- claim production SaaS readiness
- claim tenant isolation is implemented
- request real secrets, customer data, or private grants

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|---------|
| README.md | yes |
| AGENTS.md | yes |
| llms.txt | yes |
| llms-full.txt | yes (header and map) |
| sdk/python/README.md | yes |
| sdk/python/grantlayer_client.py | yes (stat only) |
| docs/public_agent_api_walkthrough_refresh.md | yes |
| docs/public_developer_experience_polish_pack.md | yes |
| docs/public_feedback_infrastructure_pack.md | yes |
| docs/public_preview_review_feedback_triage_pack.md | yes |
| docs/public_safety_scanner_claim_consistency_gate.md | yes |
| docs/public_smoke_matrix_pack.md | yes |
| docs/first_output_verify_helper.md | yes |
| docs/grant_lifecycle_evidence_bundle.md | yes |
| docs/agent_quickstart.md | yes |
| docs/ten_minute_quickstart.md | yes |
| examples/first_verifiable_output.py | smoke-tested |
| examples/first_verifiable_output.json | smoke-tested |
| examples/grant_lifecycle_evidence_bundle.py | smoke-tested |
| examples/grant_lifecycle_evidence_bundle.json | smoke-tested |
| scripts/verify-first-output.sh | smoke-tested |
| docs/examples/gl191/public_developer_experience_polish_pack.json | referenced |
| docs/examples/gl192/public_feedback_infrastructure_pack.json | referenced |
| docs/examples/gl193/public_agent_api_walkthrough_refresh.json | referenced |
| docs/examples/gl194/public_preview_review_feedback_triage_pack.json | referenced |
| docs/examples/gl195/public_safety_scanner_claim_consistency_gate.json | referenced |
| docs/examples/gl196/public_smoke_matrix_pack.json | referenced |

---

## Current Public Value Surface

GrantLayer presents the following public value surface today:

| Asset | Status | Path |
|-------|--------|------|
| First verifiable output example | ready | `examples/first_verifiable_output.py` |
| Verify-first-output helper script | ready | `scripts/verify-first-output.sh` |
| Grant lifecycle evidence bundle | ready | `examples/grant_lifecycle_evidence_bundle.py` |
| Committed reference artifacts | ready | `examples/*.json` |
| Backend quickstart (local, pip install) | ready_with_cautions | `docs/ten_minute_quickstart.md` |
| API quick reference | ready_with_cautions | `README.md` (API table) |
| Minimal Python SDK README | ready_with_cautions | `sdk/python/README.md` |
| Minimal Python SDK client module | ready_with_cautions | `sdk/python/grantlayer_client.py` (not published) |
| LangGraph/LangChain-style example | ready_with_cautions | `examples/langgraph_langchain/` |
| Agent entry points | ready | `AGENTS.md`, `llms.txt`, `llms-full.txt` |
| Public feedback routing | ready | `docs/public_feedback_infrastructure_pack.md` |
| Public safety / claim consistency gate | ready | `docs/public_safety_scanner_claim_consistency_gate.md` |
| Public smoke matrix | ready | `docs/public_smoke_matrix_pack.md` |
| OpenAPI contract | draft | `docs/openapi.yaml` (local, not served externally) |

No value surface above implies production SaaS readiness. Tenant isolation is
not implemented. No real customer data or secrets appear anywhere.

---

## API Value Assessment

### Status

`ready_with_cautions`

### What exists

GrantLayer has a local HTTP backend server (`python3 -m backend`, port 8765 by
default) that exposes a documented REST API. The API quick reference in
`README.md` lists the full set of endpoints (health, grants, grant-requests,
challenges, demo-action, audit-events, grant-executions, evidence). A formal
OpenAPI contract exists at `docs/openapi.yaml`. The ten-minute quickstart
(`docs/ten_minute_quickstart.md`) guides a developer from clone through `pip
install` to a first curl smoke check.

### What an integrator can understand today

A developer who reads README.md and `docs/ten_minute_quickstart.md` can:
- start the local backend server,
- create a grant via `POST /grants`,
- run a demo action via `POST /demo-action` to see approved/denied workflow,
- list audit events via `GET /audit-events`,
- verify evidence via `GET /evidence/executions/:id`.

The API surface is sufficient for local integration evaluation and controlled
pilot discussion.

### Where the API walkthrough still needs improvement

- No interactive API playground or hosted demo endpoint exists.
- The OpenAPI contract at `docs/openapi.yaml` is not served externally; an
  integrator must open it locally in a Swagger/Redoc viewer.
- The backend requires a local `pip install` and a running process — the
  no-install path (examples 1 and 2) does not reach the API layer.
- Auth configuration (admin token, challenge flow) adds setup friction for
  first-time API users.
- No cURL collection, Postman collection, or HAR export exists for quick
  API exploration.

### Whether OpenAPI/docs are sufficient for Developer Preview

**Yes, with caveats.** The OpenAPI contract and README API table are sufficient
for Developer Preview evaluation. They are not sufficient for a production
integration or an external service-level agreement claim.

### Recommended follow-up

GL-198 or a future API walkthrough implementation refresh should:
- add a cURL collection or request collection for the most common API paths,
- clarify the auth configuration in the backend quickstart,
- document the relationship between the no-install examples and the API layer
  more explicitly.

---

## SDK Value Assessment

### Status

`ready_with_cautions`

### Whether a real SDK exists

A minimal Python client module exists at `sdk/python/grantlayer_client.py` and
is documented at `sdk/python/README.md`. It wraps the HTTP API with typed
request/response helpers and is imported directly from the local repository
(no pip install, no PyPI release). It is a **local developer convenience
wrapper**, not a published SDK package.

**No official SDK or package is claimed.** The examples are examples, not a
published SDK. `sdk/python/grantlayer_client.py` should be described as a
"minimal Python client" or "local SDK wrapper" — not as a published package
or a stable API client.

### Whether SDK/package should be claimed publicly

**No.** Until the following conditions are met, no official SDK or package
claim should be made:

1. The HTTP API surface is stable (v1 contract with a stability commitment).
2. The package is published to PyPI or an equivalent registry.
3. A versioning and changelog policy exists for the SDK.
4. The SDK test coverage is sufficient for external consumer confidence.

None of these conditions are currently met. Claiming SDK availability would
be misleading to external integrators.

### Whether local example scripts can be described as examples, not SDK

**Yes.** `examples/first_verifiable_output.py` and
`examples/grant_lifecycle_evidence_bundle.py` are standalone local examples
that use Python stdlib only. They do not import `grantlayer_client`. They
should be described as **deterministic local examples**, not as SDK usage
patterns.

`sdk/python/grantlayer_client.py` may be described as a **minimal local
client wrapper** that shows how the HTTP API can be called. It must not be
described as a published SDK.

### What a future minimal SDK should include

When the time is right, a future minimal SDK should include:
- A stable HTTP client wrapping the v1 API contract.
- Typed request/response models for all core endpoints.
- Basic auth configuration (admin token, no-auth public paths).
- A pip-installable package with a version constraint.
- Integration tests that run against a live local backend.
- A changelog and version compatibility matrix.

### Package naming risks

- Publishing a package named `grantlayer` to PyPI before the API is stable
  risks locking in an unstable API contract.
- Publishing prematurely invites external consumer dependencies that become
  hard to break without a deprecation cycle.
- Package names should be reserved only when there is a commitment to maintain
  them.

### Install/publish risks

- Publishing to PyPI requires ongoing maintenance (security patches, dependency
  updates, PyPI API key management).
- A published package implies a stability commitment that is not appropriate
  for Developer Preview.
- No publish metadata (`pyproject.toml`, `setup.py`) exists; this is the
  correct posture for now.

### Decision on SDK

**Defer official SDK packaging.** Continue describing the local client wrapper
as a minimal convenience module. Focus documentation effort on the API
walkthrough and local examples first. Revisit SDK packaging when the API
contract is stable and there is external demand for a pip-installable client.

SDK work must not request secrets or real customer data at any stage.

---

## Agent Workflow Value Assessment

### Status

`ready_with_cautions`

### How an AI/coding agent can use the repo today

An AI coding agent that reads `AGENTS.md`, `llms.txt`, and
`docs/public_agent_api_walkthrough_refresh.md` can:
- understand the repository structure and safe/forbidden areas,
- run the two deterministic no-install examples without any backend,
- verify the first output with `scripts/verify-first-output.sh`,
- start the backend and run a local API smoke path,
- create docs/test/artifact issues following the established pattern,
- follow the agent task contract for branch/commit/report workflow.

The LangGraph/LangChain-style example at
`examples/langgraph_langchain/grantlayer_agent_example.py` shows how GrantLayer
fits into a coding agent's workflow as a verification layer — without requiring
LangGraph or LangChain to be installed.

### First output helper value

**High.** `scripts/verify-first-output.sh` is the smallest public confidence
check: it runs in under 5 seconds, requires no backend, no network, and no
secrets. It confirms the public snapshot is consistent with committed reference
artifacts. It is the recommended first step for any new developer or agent
evaluating the repository.

Current state: **MATCH** (confirmed in GL-197 smoke check).

### Grant lifecycle evidence bundle value

**High.** `examples/grant_lifecycle_evidence_bundle.py` extends the first
output with a full grant lifecycle sequence: subject, role, action, resource,
time window, evidence hashes, audit chain links. It demonstrates the core
value proposition — verifiable, deterministic, locally reproducible grant
workflow records — without starting the backend.

Current state: **DIFF CLEAN** (confirmed in GL-197 smoke check).

### AGENTS.md / llms.txt / llms-full.txt usefulness

**High for coding agents.** The three agent entry files provide:
- `AGENTS.md` — explicit safe/forbidden boundaries, task workflow, and safety phrases.
- `llms.txt` — concise machine-readable project summary.
- `llms-full.txt` — expanded repository map, safe/forbidden areas, and next steps.

One known issue: `llms.txt` still references `GL-193` as an upcoming issue,
but GL-193 is complete (GL-195-F003). This should be updated in a small
follow-up to GL-197 or as part of GL-198.

### Safety boundaries for coding agents

Coding agents must:
- use synthetic/demo data only,
- not request or paste secrets, real customer data, or private grants,
- not modify `backend/src/*`, OpenAPI, migrations, DB/schema, or dependency manifests,
- not push to GitHub or change GitHub repository settings,
- not claim production SaaS readiness or tenant isolation implementation,
- route security-sensitive reports to GitHub Security Advisories.

These boundaries are correctly documented in `AGENTS.md` and enforced by the
security boundary regression test.

### What future agent example would add value

A future agent example that shows:
1. An agent calling the live local API (health → create grant → demo action → check audit),
2. using only placeholder tokens,
3. without modifying any committed file,
4. with a final structured JSON report,

would complete the agent-to-API integration story. This is a candidate for a
future GL-198 or GL-200 follow-up.

---

## Packaging Boundaries

| Asset | Current Status | Recommended Boundary |
|-------|---------------|----------------------|
| `examples/first_verifiable_output.py` | public, stdlib-only | Remain as a public example; do not package |
| `examples/grant_lifecycle_evidence_bundle.py` | public, stdlib-only | Remain as a public example; do not package |
| `sdk/python/grantlayer_client.py` | public, local only | Remain as a local wrapper; do not publish to PyPI yet |
| `sdk/python/README.md` | public | Remain as documentation; no stability claim |
| `examples/langgraph_langchain/` | public, stdlib-only | Remain as integration examples; do not package |
| `backend/` | internal source | Not packaged for public use in Developer Preview |
| `docs/openapi.yaml` | local draft | Keep as local draft; no external contract commitment |
| Package name `grantlayer` on PyPI | not reserved/published | Reserve only when API contract is stable |

### What should remain examples/docs

All current public examples should be positioned as examples and documentation
only. They demonstrate the product value without creating package availability
obligations.

### What could become SDK later

`sdk/python/grantlayer_client.py` is the natural starting point for a future
pip-installable SDK. Preconditions before packaging:
1. API v1 stability commitment.
2. `pyproject.toml` or `setup.py` with correct metadata.
3. CI publishing workflow.
4. Version and changelog policy.

### What should remain internal/not public

- `backend/src/` — production runtime code; should not be packaged separately.
- Internal Forgejo configuration, migration state, and deployment scripts.
- Any file that contains internal paths, private hostnames, or secrets.

### What requires production-readiness before public claim

- Production SaaS hosting.
- Tenant/workspace isolation implementation.
- TLS/mTLS backend configuration.
- Real IAM / OAuth / JWT authentication.
- Hardened database configuration (connection pooling, backup, encryption at rest).
- Published SDK with stable API contract.

---

## Recommended Product Narrative

> GrantLayer is an API-first Developer Preview for verifiable grant workflow
> evidence, auditability, and agent-facing trust checks.
>
> Today, developers can run deterministic local examples and inspect the API
> and server path. The examples are standalone Python stdlib scripts — they are
> not a production SaaS, not a published SDK, and not a tenant-isolated service.
>
> A minimal local Python client wrapper exists in `sdk/python/` for developers
> who want to make typed HTTP calls against the local backend. No pip package
> has been published; the wrapper is local only.
>
> AI coding agents can use the repository today via the documented entry points
> (AGENTS.md, llms.txt, llms-full.txt) and the two deterministic no-install
> examples.
>
> Future SDK and API packaging should follow after the API contract is stable
> and there is demonstrated external demand from the controlled preview
> reviewer pool.

---

## What Is Ready Now

| Capability | Status |
|-----------|--------|
| First verifiable output (no install, no backend, no network) | ready |
| Verify-first-output helper (offline confidence check) | ready |
| Grant lifecycle evidence bundle (no install, no backend, no network) | ready |
| Backend quickstart (local, pip install required) | ready |
| Local API smoke path (curl or SDK wrapper) | ready_with_cautions |
| Public feedback routing (GitHub Issues + Security Advisories) | ready |
| Agent entry points (AGENTS.md, llms.txt, llms-full.txt) | ready |
| Public smoke matrix (GL-196) | ready |
| Public safety / claim consistency gate (GL-195) | ready |
| LangGraph/LangChain-style agent integration example | ready_with_cautions |
| Minimal local Python SDK wrapper | ready_with_cautions |

---

## What Is Not Ready

| Capability | Status | Notes |
|-----------|--------|-------|
| Production SaaS | not_ready | Not claimed; hardening gates incomplete |
| Tenant/workspace isolation | not_ready | Not implemented; all data in a single namespace |
| Published SDK package on PyPI | not_ready | No pyproject.toml; no PyPI release |
| Stable API v1 contract | not_ready | No stability commitment made |
| Real customer data support | not_ready | Examples use synthetic identifiers only |
| TLS / real IAM / OAuth | not_ready | Local demo mode only |
| Hosted interactive API playground | not_ready | No external endpoint exists |
| Production deployment | not_ready | No production deployment exists |

---

## Decision

**api_first_agent_examples_now_sdk_later**

---

## Decision Rationale

GrantLayer's current public value is concentrated in:
1. Two deterministic no-install examples that can be run by any developer or
   coding agent in under 60 seconds without secrets, without a backend, and
   without a network connection.
2. A local backend that demonstrates the API value surface through a
   well-documented quickstart.
3. Agent-friendly entry points (AGENTS.md, llms.txt) that give coding agents
   clear task boundaries and safety rules.

The API layer has sufficient clarity for Developer Preview evaluation. The
existing minimal Python client wrapper in `sdk/python/` shows the API call
pattern without requiring package publishing.

Reasons to defer official SDK packaging:
- No external demand has been confirmed from the controlled preview reviewer pool.
- The API contract has no stability commitment; premature packaging locks in
  an unstable surface.
- No PyPI release infrastructure, version policy, or SDK changelog exists.
- Packaging adds maintenance obligations inconsistent with Developer Preview posture.

Reasons to focus on API-first + agent examples now:
- The two no-install examples are already the highest-value public assets.
- An agent-to-API integration example (calling the live local backend) would
  close the remaining gap between the no-install path and the API path.
- Improving the API walkthrough (cURL collection, auth config clarity) adds
  integrator confidence without packaging risk.

This decision does not prevent a future SDK prototype. It sets the correct
sequencing: API walkthrough clarity → controlled preview feedback → SDK when
demand is demonstrated.

---

## Findings

### GL-197-F001

| Field | Value |
|-------|-------|
| id | GL-197-F001 |
| severity | medium |
| category | api-docs |
| summary | The backend API walkthrough lacks a cURL collection or request collection for the most common API paths, increasing friction for first-time integrators. |
| evidence | `README.md` has a partial curl example for grant creation and demo action, but no downloadable request collection or structured API smoke path exists beyond the ten-minute quickstart prose. |
| blocking | no |
| recommended_action | Add a minimal cURL collection or Postman/Bruno collection for the core API paths (health, create grant, demo action, revoke, audit events) as a future API walkthrough refresh. |
| recommended_issue | GL-198 or a dedicated API walkthrough refresh issue |

### GL-197-F002

| Field | Value |
|-------|-------|
| id | GL-197-F002 |
| severity | medium |
| category | sdk-packaging |
| summary | The README Developer entry path (Step 5) reads "Python SDK" and links to `sdk/python/README.md`, which may lead readers to expect a published, pip-installable package. |
| evidence | README.md Developer entry path table, Step 5: "Python SDK" — `sdk/python/README.md`. The SDK README correctly states "No pip package is published," but the README table label "Python SDK" may set incorrect expectations without a qualification caveat in the table. |
| blocking | no |
| recommended_action | Add a qualifier to the README Developer entry path table: change "Python SDK" to "Minimal Python client (local only, not published)" or equivalent to prevent overclaiming. |
| recommended_issue | GL-198 or a cross-link fix in a subsequent issue |

### GL-197-F003

| Field | Value |
|-------|-------|
| id | GL-197-F003 |
| severity | low |
| category | agent-value |
| summary | `llms.txt` Next Steps section still references "GL-193 (public agent/API walkthrough refresh)" as an upcoming issue, but GL-193 is complete. |
| evidence | `llms.txt` line 78: "Upcoming issues: GL-193 (public agent/API walkthrough refresh)." GL-193 was merged and published. First identified in GL-195-F003. |
| blocking | no |
| recommended_action | Update `llms.txt` Next Steps to reference the current upcoming issues (GL-197–GL-199 roadmap) in this or a subsequent issue. |
| recommended_issue | This issue (GL-197) or GL-198 |

### GL-197-F004

| Field | Value |
|-------|-------|
| id | GL-197-F004 |
| severity | low |
| category | agent-value |
| summary | No agent-to-API integration example exists that shows an AI coding agent calling the live local backend (health → create grant → demo action → check audit) with placeholder tokens. |
| evidence | `examples/langgraph_langchain/grantlayer_agent_example.py` shows the agent pattern, but the full agent-to-API smoke path (calling each major API endpoint in sequence) is not yet a standalone, self-explanatory example. |
| blocking | no |
| recommended_action | Add a future standalone agent-to-API example that is fully documented, uses placeholder tokens, and produces a structured JSON report. |
| recommended_issue | GL-198 or a future agent workflow example issue |

### GL-197-F005

| Field | Value |
|-------|-------|
| id | GL-197-F005 |
| severity | info |
| category | public-positioning |
| summary | The OpenAPI contract at `docs/openapi.yaml` is not served externally; an integrator cannot browse the API interactively without a local Swagger/Redoc viewer. |
| evidence | `docs/openapi.yaml` exists and is referenced in README, but no hosted or embedded playground is available. |
| blocking | no |
| recommended_action | Consider linking to a static Redoc/Swagger viewer or adding a `docs/api_reference.md` rendered table in a future issue. Non-blocking for Developer Preview. |
| recommended_issue | GL-199 or future API reference issue |

### GL-197-F006

| Field | Value |
|-------|-------|
| id | GL-197-F006 |
| severity | info |
| category | developer-preview |
| summary | Auth configuration (admin token, challenge flow) adds setup friction for first-time API users who come from the no-install examples without reading the quickstart docs carefully. |
| evidence | Backend requires `GRANTLAYER_REQUIRE_ADMIN_TOKEN` and `GRANTLAYER_REQUIRE_CHALLENGE` to be understood before the protected endpoints make sense. Demo-mode vs product-mode distinction is in README but may not be obvious to new developers. |
| blocking | no |
| recommended_action | Add a "quickstart auth guide" or expand the auth section of `docs/ten_minute_quickstart.md` to cover demo-mode vs product-mode in one clear step. |
| recommended_issue | GL-198 or future quickstart improvement |

### GL-197-F007

| Field | Value |
|-------|-------|
| id | GL-197-F007 |
| severity | info |
| category | production-caveat |
| summary | No consolidated production readiness gap report v2 exists (also identified in GL-194-F002 and GL-195-F004). Non-blocking. |
| evidence | Individual caveats are scattered across README.md, SECURITY.md, and docs/security_boundaries.md. No single document maps all remaining hardening gates with owner, priority, and estimated scope. |
| blocking | no |
| recommended_action | GL-199 Production Readiness Gap Report v2 should consolidate all hardening gaps. |
| recommended_issue | GL-199 |

---

## Recommended Next Issues

| Issue | Title | Priority | Rationale |
|-------|-------|----------|-----------|
| GL-197 combined | GL-197 Combined Merge-and-Publish | high | Merge GL-197 to main and publish public snapshot update. |
| GL-198 | Controlled Preview Boundary Pack | medium | Draft reviewer invite criteria, data policy summary, onboarding/offboarding, and first agent-to-API example. |
| GL-199 | Production Readiness Gap Report v2 | medium | Consolidated production-vs-preview gap analysis, tenant isolation path, and remaining hardening gates. |

### Optional follow-ups (propose only if useful)

| Topic | Rationale |
|-------|-----------|
| API walkthrough implementation refresh | Add cURL collection, expand auth docs — addresses GL-197-F001, F006 |
| llms.txt Next Steps update | One-line fix for GL-197-F003; can be done in GL-198 |
| README SDK label qualifier | Two-word fix for GL-197-F002; can be done in GL-198 |
| Future minimal SDK prototype | Only after API contract stability commitment and external demand |
| Future agent-to-API standalone example | Complete the agent workflow integration story — GL-197-F004 |
| Hosted OpenAPI viewer or rendered API reference | Addresses GL-197-F005; non-blocking for Developer Preview |

---

## Risks and Caveats

- Overclaiming SDK availability would mislead external integrators and create
  maintenance obligations inconsistent with Developer Preview posture.
- Premature API contract stability claims could lock in an unstable surface.
- The `sdk/python/` directory name may signal more maturity than intended; the
  README qualifier ("No pip package is published") must remain prominent.
- All examples use synthetic identifiers and placeholder tokens. Any future
  agent-to-API example must preserve this constraint.
- The controlled preview boundary (GL-198) has not been formally documented;
  until it is, the reviewer pool should remain limited.

---

## Non-Goals

This issue does **not**:
- implement a real SDK or publish a pip package
- change backend runtime behavior or add new API surface
- change `backend/src/*`, OpenAPI, migrations, DB/schema, or dependency manifests
- push to GitHub or change GitHub visibility
- create or modify GitHub labels/issues via API
- send reviewer outreach
- change frontend, website, or design
- change snapshot publish script behavior
- claim production SaaS readiness
- claim tenant isolation is implemented
- request real customer data, private grants, or secrets
- include exploit details

---

## Exact Safety Phrases

The following lowercase phrases are intentionally included for agent and test
compatibility:

- tenant isolation is not implemented
- no real secrets
- no real customer data

---

## Current Public Preview State

| Posture | Value |
|---------|-------|
| Release label | **GL-0.1 / Developer Preview** |
| Maturity | Local evaluation and controlled pilot only |
| Production SaaS readiness | **Not claimed** |
| Tenant/workspace isolation | **Not implemented** |
| Public GitHub repository | **Available** — `https://github.com/Discodone/grantlayer.git` (GL-176) |
| Public snapshot | Clean developer-facing snapshot — no internal paths, no real secrets |
| Real customer data in examples | **No** — all examples use synthetic identifiers |
| Real secrets in examples | **No** — all tokens and keys are placeholders |

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

> This document was created in **GL-197 API/SDK/Agent Value Decision Pack**. It
> is a review/docs/test artifact only. It does not change git remotes, rewrite
> history, modify production code, change API behavior, add migrations, change
> the database schema, add dependencies, implement SDK changes, publish packages,
> launch a website or frontend, claim production SaaS readiness, or claim tenant
> isolation implementation. All examples use synthetic identifiers and
> placeholder tokens only.
